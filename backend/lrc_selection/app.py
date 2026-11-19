from copy import deepcopy
import hashlib
import fcntl
import io
import json
import os
import secrets
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import analyze, effective_selected
from .models import (Archive, BatchInput, CompleteImport, Decision, ImportManifest, ImportPhotos,
                     PresetInput, Receipt, Replace, Revision, SettingsUpdate)
from .store import Store
from .local_models import resolve_model

MAX_PREVIEW_BYTES = 24 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 50_000_000

def criteria_for(settings):
    criteria = settings.get('service_criteria')
    if criteria is None:
        criteria = (settings.get('preset_snapshot') or {}).get('criteria', [])
    result = [{'text': criterion, 'status': 'pending',
               'reason': 'Will be assessed by the vision model during analysis.'}
              for criterion in criteria]
    if settings.get('subject_query', '').strip():
        result.append({'text': settings['subject_query'], 'status': 'pending',
                       'reason': 'Requested subject for local visual comparison; review the new analysis result.'})
    if settings.get('instructions', '').strip():
        result.append({'text': settings['instructions'], 'status': 'pending',
                       'reason': 'The original text is sent verbatim to the vision model.'})
    return result

def load_connection_token(root: Path):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_file = root / 'connection-token'
    if not token_file.exists():
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secrets.token_urlsafe(32))
    return token_file.read_text().strip()

def create_app(data_dir: Path | None = None, token: str | None = None, web_dir: Path | None = None):
    root = data_dir or Path(os.environ.get('LRC_SELECTION_EN_DATA', Path.home() / 'Library/Application Support/LrC Photo Selection EN'))
    store = Store(root)
    if token is None:
        token = load_connection_token(root)
    if not token:
        raise ValueError('Connection token must not be empty')
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='selection')

    @asynccontextmanager
    async def lifespan(app):
        lock_file = (root / 'server.lock').open('a')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.close()
            raise RuntimeError('A backend is already using this data directory')
        try:
            store.recover_jobs()
            app.state.openai_analysis.recover()
            yield
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

    app = FastAPI(title='LrC Photo Selection EN', version='0.1.0', lifespan=lifespan)
    app.state.store = store
    from .openai_config import register_openai_config
    register_openai_config(app, root)
    from .model_registry import register_model_catalog
    register_model_catalog(app, root)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def protect(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return Response('Origin not allowed', status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return Response('Cross-site request not allowed', status_code=403)
        if request.url.path.startswith('/api/') and request.url.path != '/api/session':
            supplied = request.headers.get('authorization', '').removeprefix('Bearer ') or request.cookies.get('lrc_session_en', '')
            if not secrets.compare_digest(supplied, token):
                return Response('Unauthenticated connection', status_code=401)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
        return response

    class SessionInput(BaseModel):
        token: str

    @app.post('/api/session')
    def session(body: SessionInput, response: Response):
        if not secrets.compare_digest(body.token, token):
            raise HTTPException(401, 'Invalid token')
        response.set_cookie('lrc_session_en', token, httponly=True, samesite='strict', path='/')
        return {'ok': True}

    @app.get('/health')
    def health():
        return {'status': 'ok', 'version': '0.1.0'}

    @app.get('/api/presets')
    def presets():
        with store.connect() as db:
            return [json.loads(r['body']) for r in db.execute('SELECT body FROM presets')]

    @app.post('/api/presets')
    def create_preset(body: PresetInput):
        preset = {'id': str(uuid.uuid4()), 'name': body.name, 'criteria': body.criteria, 'subject_query': body.subject_query, 'instructions': body.instructions, 'version': 1}
        with store.transaction() as db:
            db.execute('INSERT INTO presets VALUES(?,?)', (preset['id'], json.dumps(preset)))
        return preset

    @app.put('/api/presets/{pid}')
    def update_preset(pid: str, body: PresetInput):
        with store.transaction() as db:
            row = db.execute('SELECT body FROM presets WHERE id=?', (pid,)).fetchone()
            if not row:
                raise HTTPException(404, 'Preset not found')
            old = json.loads(row['body'])
            if old['version'] != body.version:
                raise HTTPException(409, 'Preset changed: reload')
            updated = {'id': pid, 'name': body.name, 'criteria': body.criteria, 'subject_query': body.subject_query, 'instructions': body.instructions, 'version': old['version'] + 1}
            db.execute('UPDATE presets SET body=? WHERE id=?', (json.dumps(updated), pid))
        return updated

    @app.post('/api/imports')
    def import_service(body: ImportManifest):
        digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with store.transaction() as db:
            existing = db.execute('SELECT body FROM services WHERE id=?', (body.id,)).fetchone()
            if existing:
                service = json.loads(existing['body'])
                if service['manifest_sha256'] != digest:
                    raise HTTPException(409, 'Service ID already used by a different manifest')
                return service
            settings = {'target': min(500, len(body.photos)), 'preset_id': '', 'preset_version': 0,
                        'preset_snapshot': None, 'service_criteria': [], 'subject_query': '',
                        'mode': 'local', 'instructions': '', 'camera_offsets': {}}
            service = {'id': body.id, 'title': body.title, 'catalog_id': body.catalog_id, 'catalog_label': body.catalog_label,
                       'schema_version': 1, 'manifest_sha256': digest, 'revision': 1, 'status': 'importing',
                       'settings': settings, 'photos': [dict(p.model_dump(), preview_ready=False) for p in body.photos],
                       'decisions': {}, 'proposal': None, 'job': None, 'receipts': [], 'criteria': criteria_for(settings)}
            store.put(db, service)
        return service

    @app.post('/api/services/{sid}/append')
    def append_import(sid: str, body: ImportPhotos):
        digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with store.transaction() as db:
            service = store.get(sid, db)
            if service['catalog_id'] != body.catalog_id:
                raise HTTPException(409, 'Service belongs to another catalog')
            operations = service.setdefault('append_operations', {})
            if body.id in operations:
                operation = operations[body.id]
                if operation['sha256'] != digest:
                    raise HTTPException(409, 'Import ID already used with different data')
                return {k: operation[k] for k in ('photo_ids', 'completed')}
            if service['status'] != 'ready' or service.get('archived'):
                raise HTTPException(409, 'Service is not ready for additional photos')
            by_id = {p['id']: p for p in service['photos']}
            by_local_id = {p['local_id']: p for p in service['photos']}
            added = []
            for photo in body.photos:
                existing = by_id.get(photo.id) or by_local_id.get(photo.local_id)
                if existing:
                    if (existing['id'], existing['uuid'], existing['local_id']) != (photo.id, photo.uuid, photo.local_id):
                        raise HTTPException(409, 'Photo identity conflicts with this service')
                    continue
                added.append(dict(photo.model_dump(), preview_ready=False))
            operation = {'sha256': digest, 'photo_ids': [p['id'] for p in added], 'completed': not added}
            operations[body.id] = operation
            if added:
                service['photos'].extend(added)
                service['status'] = 'importing'
                service['active_import_id'] = body.id
                service['revision'] += 1
                service['requires_analysis'] = True
                service.pop('confirmed_batch_id', None)
                if service.get('proposal'):
                    service['proposal']['stale'] = True
                    service['proposal'].setdefault('added_candidates', []).extend(operation['photo_ids'])
            store.put(db, service)
        return {k: operation[k] for k in ('photo_ids', 'completed')}

    @app.get('/api/services')
    def services():
        with store.connect() as db:
            items = [json.loads(r['body']) for r in db.execute('SELECT body FROM services ORDER BY rowid DESC')]
        return [{k: s[k] for k in ['id', 'title', 'catalog_id', 'revision', 'status']} | {'photo_count': len(s['photos']), 'archived': s.get('archived', False)} for s in items]

    def present(service):
        result = dict(service)
        job = service.get('job') or {}
        diagnostics = service.get('analysis_diagnostics') or {}
        if (job.get('status') == 'failed' and diagnostics.get('attempted') == 0
                and diagnostics.get('not_assessed') == len(service['photos'])
                and (job.get('error') or '').startswith('Local analysis incomplete: 0 invalid responses')):
            result['job'] = job | {'error': 'The previous analysis stopped before assessing photos. Start a new analysis after updating; saved candidates and decisions are unchanged.'}
        result.pop('decision_history', None)
        result.pop('append_operations', None)
        result['criteria'] = criteria_for(service['settings'])
        interpreted = (service.get('proposal') or {}).get('instruction_interpretation')
        if interpreted and not service['proposal'].get('stale'):
            blocked = interpreted.get('ambiguities', []) + interpreted.get('unsupported', [])
            for criterion in result['criteria']:
                criterion['status'] = 'ambiguous' if blocked else 'supported'
                criterion['reason'] = ('; '.join(blocked) if blocked else
                    'Request assessed by the vision model using previews; the result still requires review.')
        from .workflow import workflow_summary
        receipt_revision = service.get('last_rating_revision')
        if receipt_revision is None and service.get('receipts'):
            with store.connect() as db:
                row = db.execute('SELECT body FROM batches WHERE id=? AND service_id=?',
                                 (service['receipts'][-1]['batch_id'], service['id'])).fetchone()
            if row:
                receipt_revision = json.loads(row['body'])['revision'] + 1
        result['workflow'] = workflow_summary(service, receipt_revision)
        if result['workflow']['blocked'] and job.get('status') == 'completed':
            result['job'] = job | {'status': 'blocked', 'error': 'Request needs clarification: ' + '; '.join(result['workflow']['blocked_reasons'])}
        result['selected_ids'] = effective_selected(service)
        result['can_undo'] = service.get('decision_cursor', 0) > 0
        result['can_redo'] = service.get('decision_cursor', 0) < len(service.get('decision_history', []))
        if service.get('proposal'):
            proposal = deepcopy(service['proposal'])
            if 'shortlist' in proposal:
                from .engine import effective_shortlist
                proposal['effective_shortlist'] = effective_shortlist(service)
            selected = set(result['selected_ids'])
            uncovered = 0
            for group in proposal['groups']:
                available = selected.intersection(group['members'])
                preferred = next((pid for pid in group['members'] if pid in available and service['decisions'].get(pid, {}).get('state') == 'preferred'), None)
                if preferred:
                    group['representative'] = preferred
                if group['representative'] not in available:
                    group['representative'] = next((pid for pid in group['members'] if pid in available), None)
                uncovered += not available
            stale_warning = 'A group has no candidates because of manual decisions.'
            proposal['warnings'] = [warning for warning in proposal['warnings'] if warning != stale_warning]
            if uncovered:
                proposal['warnings'].append(f'Groups without candidates after review: {uncovered}.')
            quantity_warnings = {
                'Target cannot be reached without changing manual decisions: review required.',
                'Target exceeded: insufficient evidence to safely reduce further images.',
            }
            proposal['warnings'] = [w for w in proposal['warnings'] if w not in quantity_warnings]
            if 'shortlist' not in proposal and len(selected) < service['settings']['target']:
                proposal['warnings'].append('Target cannot be reached without changing manual decisions: review required.')
            elif 'shortlist' not in proposal and len(selected) > service['settings']['target']:
                proposal['warnings'].append('Target exceeded: insufficient evidence to safely reduce further images.')
            for pid, decision in service['decisions'].items():
                proposal['reasons'][pid] = 'Manual decision: ' + {'candidate': 'candidate', 'preferred': 'preferred', 'review': 'requires review', 'excluded': 'excluded', 'alternative': 'alternative'}[decision['state']] + '.'
            result['proposal'] = proposal
        return result

    @app.get('/api/services/{sid}')
    def detail(sid: str):
        service = store.get(sid)
        return present(service)

    @app.put('/api/services/{sid}/photos/{pid}/preview')
    async def upload_preview(sid: str, pid: str, request: Request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_PREVIEW_BYTES:
                raise HTTPException(413, 'Preview too large')
        try:
            with Image.open(io.BytesIO(data)) as im:
                if im.format != 'JPEG':
                    raise ValueError('Format is not JPEG')
                im.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(422, 'Invalid JPEG preview')
        digest = hashlib.sha256(data).hexdigest()
        with store.transaction() as db:
            service = store.get(sid, db)
            photo = next((p for p in service['photos'] if p['id'] == pid), None)
            if photo is None:
                raise HTTPException(404, 'Photo not found')
            if photo.get('preview_sha256') == digest:
                return {'ok': True}
            active = service.get('active_import_id')
            if service['status'] != 'importing' or (active and pid not in service['append_operations'][active]['photo_ids']):
                raise HTTPException(409, 'Photo does not belong to the active import')
            path = store.preview_path(sid, pid)
            if shutil.disk_usage(store.root).free < len(data) + 512 * 1024 * 1024:
                raise HTTPException(507, 'Insufficient storage: import paused, received data preserved')
            path.parent.mkdir(exist_ok=True, mode=0o700)
            temporary = path.with_suffix('.tmp')
            temporary.write_bytes(data)
            temporary.chmod(0o600)
            temporary.replace(path)
            photo.update(preview_ready=True, preview_sha256=digest)
            service['revision'] += 1
            store.put(db, service)
        return {'ok': True}

    @app.get('/api/services/{sid}/photos/{pid}/preview')
    def preview(sid: str, pid: str):
        s = store.get(sid)
        if not any(p['id'] == pid and p['preview_ready'] for p in s['photos']):
            raise HTTPException(404, 'Preview unavailable')
        return FileResponse(store.preview_path(sid, pid), media_type='image/jpeg')

    @app.post('/api/services/{sid}/complete')
    def complete(sid: str, body: CompleteImport | None = None):
        with store.transaction() as db:
            s = store.get(sid, db)
            active = s.get('active_import_id')
            if body:
                operation = s.get('append_operations', {}).get(body.import_id)
                if operation and operation['completed']:
                    return present(s)
                if not active or active != body.import_id:
                    raise HTTPException(409, 'Import is not active')
                operation['completed'] = True
                s.pop('active_import_id')
            elif active:
                raise HTTPException(409, 'Specify the import to complete')
            if s['status'] == 'importing':
                s['status'] = 'ready'
                s['revision'] += 1
                store.put(db, s)
        return present(s)

    def require_editable(service):
        if service['status'] != 'ready' or service.get('archived'):
            raise HTTPException(409, 'Service is busy or archived')

    @app.put('/api/services/{sid}/archive')
    def archive_service(sid: str, body: Archive):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            if s['status'] != 'ready':
                raise HTTPException(409, 'Complete the current operation before archiving')
            if s.get('archived', False) != body.archived:
                s['archived'] = body.archived
                s.pop('confirmed_batch_id', None)
                s['revision'] += 1
                store.put(db, s)
        return present(s)

    @app.put('/api/services/{sid}/settings')
    def settings(sid: str, body: SettingsUpdate):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            if body.settings.target > len(s['photos']):
                raise HTTPException(422, 'Quantity exceeds the number of imported photos')
            new = body.settings.model_dump()
            if not new['preset_id']:
                new['preset_version'] = 0
                new['preset_snapshot'] = None
            elif (new['preset_id'], new['preset_version']) == (s['settings']['preset_id'], s['settings']['preset_version']):
                new['preset_snapshot'] = s['settings']['preset_snapshot']
            else:
                row = db.execute('SELECT body FROM presets WHERE id=?', (new['preset_id'],)).fetchone()
                if not row or json.loads(row['body'])['version'] != new['preset_version']:
                    raise HTTPException(409, 'Preset version unavailable: reload')
                new['preset_snapshot'] = json.loads(row['body'])
            if new['service_criteria'] is None:
                new['service_criteria'] = (new.get('preset_snapshot') or {}).get('criteria', [])
            s.pop('confirmed_batch_id', None)
            s['settings'] = new
            s['criteria'] = criteria_for(new)
            s['revision'] += 1
            if s.get('proposal'):
                s['proposal']['stale'] = True
                warning = 'Settings changed: start a new analysis to update the proposal.'
                if warning not in s['proposal']['warnings']:
                    s['proposal']['warnings'].append(warning)
            store.put(db, s)
        return present(s)

    def apply_decisions(service, changes):
        for pid, value in changes.items():
            if value is None:
                service['decisions'].pop(pid, None)
            else:
                service['decisions'][pid] = value

    def record_decisions(service, changes):
        before = {pid: service['decisions'].get(pid) for pid in changes}
        if before == changes:
            return
        history = service.get('decision_history', [])[:service.get('decision_cursor', 0)]
        history.append({'before': before, 'after': changes})
        service['decision_history'] = history
        service['decision_cursor'] = len(history)
        apply_decisions(service, changes)
        service.pop('confirmed_batch_id', None)
        service['revision'] += 1

    @app.patch('/api/services/{sid}/decisions/{pid}')
    def decide(sid: str, pid: str, body: Decision):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            if not any(p['id'] == pid for p in s['photos']):
                raise HTTPException(404, 'Photo not found')
            previously_selected = set(effective_selected(s))
            if pid in previously_selected and body.state in ('excluded', 'alternative') and not body.confirm_last:
                group = next((g['members'] for g in (s.get('proposal') or {}).get('groups', []) if pid in g['members']), [pid])
                if previously_selected.intersection(group) == {pid}:
                    raise HTTPException(409, {'code': 'last_candidate', 'message': 'Exclude the last candidate in this group. Confirm?'})
            record_decisions(s, {pid: {'state': body.state, 'locked': body.locked}})
            store.put(db, s)
        return present(s)

    class AcceptShortlist(Revision):
        confirm_last: bool = False

    @app.post('/api/services/{sid}/accept-shortlist')
    def accept_shortlist(sid: str, body: AcceptShortlist):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            proposal = s.get('proposal') or {}
            if 'shortlist' not in proposal or proposal.get('stale') or not body.confirm_last:
                raise HTTPException(409, 'Review and confirm an up-to-date proposal before applying it')
            from .engine import effective_shortlist
            selected = set(effective_shortlist(s))
            review = set(proposal.get('review_ids', []))
            if not selected:
                raise HTTPException(409, 'No proposed matches: no decisions changed')
            changes = {p['id']: {'state': ('review' if p['id'] in review else 'candidate') if p['id'] in selected else 'excluded', 'locked': False}
                       for p in s['photos'] if p['id'] not in s['decisions']}
            from .workflow import workflow_summary
            accepted_after_block = workflow_summary(s)['blocked']
            record_decisions(s, changes)
            s['proposal']['shortlist_accepted'] = True
            if accepted_after_block:
                s['proposal']['accepted_after_block'] = True
            store.put(db, s)
        return present(s)

    @app.post('/api/services/{sid}/replace')
    def replace_candidate(sid: str, body: Replace):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            source, target = body.from_photo_id, body.to_photo_id
            selected = set(effective_selected(s))
            group = next((g for g in (s.get('proposal') or {}).get('groups', []) if source in g['members']), None)
            if not group or source not in selected or target in selected or target not in group['members']:
                raise HTTPException(422, 'Choose a candidate and an alternative from the same group')
            if any(s['decisions'].get(pid, {}).get('locked') for pid in (source, target)):
                raise HTTPException(409, 'Unlock photos before replacing')
            record_decisions(s, {source: {'state': 'alternative', 'locked': False},
                                 target: {'state': 'preferred', 'locked': False}})
            store.put(db, s)
        return present(s)

    def move_history(sid, body, direction):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            cursor = s.get('decision_cursor', 0)
            history = s.get('decision_history', [])
            index = cursor - 1 if direction == -1 else cursor
            if not 0 <= index < len(history):
                raise HTTPException(409, 'No decision to undo or redo')
            apply_decisions(s, history[index]['before' if direction == -1 else 'after'])
            s['decision_cursor'] = cursor + direction
            if s.get('proposal'):
                s['proposal']['shortlist_accepted'] = False
            s.pop('confirmed_batch_id', None)
            s['revision'] += 1
            store.put(db, s)
        return present(s)

    @app.post('/api/services/{sid}/undo')
    def undo(sid: str, body: Revision):
        return move_history(sid, body, -1)

    @app.post('/api/services/{sid}/redo')
    def redo(sid: str, body: Revision):
        return move_history(sid, body, 1)

    semantic_encoder = None
    instruction_model = None

    def run_analysis(sid: str, start_revision: int):
        nonlocal semantic_encoder, instruction_model
        try:
            snapshot = store.get(sid)
            proposal = analyze(snapshot)
            semantic = None
            model_path, _ = local_components()
            vlm_path = instruction_component()
            def progress(completed, total):
                with store.transaction() as progress_db:
                    current = store.get(sid, progress_db)
                    store.check_revision(current, start_revision)
                    current['job'].update(completed=completed, total=total)
                    store.put(progress_db, current)
            if vlm_path:
                from .vlm import LocalVLM, build_instruction_proposal
                if instruction_model is None:
                    instruction_model = LocalVLM(vlm_path)
                semantic = build_instruction_proposal(store, snapshot, instruction_model, progress)
                diagnostics = semantic.get('diagnostics', {})
                if semantic.get('blocked') or semantic.get('incomplete'):
                    interpreted = semantic.get('instruction_interpretation', {})
                    blockers = interpreted.get('ambiguities', []) + interpreted.get('unsupported', [])
                    if semantic.get('blocked'):
                        failure = 'Analysis not started: instructions require clarification. ' + '; '.join(blockers)
                        diagnostics = diagnostics | {'stage': 'instructions', 'blocking_reasons': blockers}
                    elif diagnostics.get('invalid', 0):
                        failure = f"Local analysis incomplete: {diagnostics['invalid']} invalid responses out of {len(snapshot['photos'])}."
                    elif diagnostics.get('missing_preview', 0):
                        failure = f"Local analysis incomplete: {diagnostics['missing_preview']} missing previews."
                    else:
                        failure = f"Local analysis incomplete: {diagnostics.get('not_assessed', 0)} photos not assessed."
                    failure += ' No new selection applied; saved candidates and decisions remain unchanged.'
                    with store.transaction() as failed_db:
                        current = store.get(sid, failed_db)
                        store.check_revision(current, start_revision)
                        current['analysis_diagnostics'] = diagnostics
                        current['analysis_instruction_interpretation'] = interpreted
                        current['analysis_partial_interpretations'] = semantic['interpretations']
                        if current.get('proposal'):
                            current['proposal']['stale'] = True
                        current['requires_analysis'] = True
                        current['status'] = 'ready'
                        current['job'] = {'status': 'failed', 'completed': diagnostics.get('valid', 0),
                                          'total': len(snapshot['photos']),
                                          'error': failure}
                        current['revision'] += 1
                        store.put(failed_db, current)
                    return
                if model_path and semantic['shortlist'] and not semantic.get('blocked'):
                    from .features import SiglipEncoder
                    from .semantic import rerank_instruction_shortlist
                    if semantic_encoder is None:
                        semantic_encoder = SiglipEncoder(model_path)
                    semantic = rerank_instruction_shortlist(semantic, snapshot, store, semantic_encoder)

            elif snapshot['settings'].get('instructions', '').strip() or snapshot['settings'].get('service_criteria'):
                raise ValueError('Free-form instruction model not configured')
            elif model_path:
                from .features import SiglipEncoder
                from .semantic import build_semantic_proposal
                if semantic_encoder is None:
                    semantic_encoder = SiglipEncoder(model_path)
                semantic = build_semantic_proposal(store, snapshot, semantic_encoder, progress)
            elif snapshot['settings'].get('subject_query', '').strip():
                raise ValueError('Local semantic model not configured')
            if semantic is not None:
                proposal.update({k: semantic[k] for k in ('shortlist', 'shortlist_reasons', 'query_scores')})
                proposal['review_ids'] = semantic.get('review_ids', [])
                for key in ('selection_policy', 'selection_groups', 'coverage'):
                    if key in semantic:
                        proposal[key] = semantic[key]
                proposal['semantic'] = {k: semantic[k] for k in ('model', 'query', 'method')}
                proposal['warnings'] = semantic['warnings']
                if 'instruction_interpretation' in semantic:
                    proposal['instruction_interpretation'] = semantic['instruction_interpretation']
            with store.transaction() as db:
                s = store.get(sid, db)
                if s['revision'] != start_revision:
                    s['job'] = {'status': 'interrupted', 'completed': 0, 'total': len(s['photos']), 'error': 'Decisions or settings changed during analysis; start again.'}
                else:
                    s['proposal'] = proposal
                    s['analysis_diagnostics'] = (semantic or {}).get('diagnostics', {})
                    s.pop('analysis_instruction_interpretation', None)
                    s.pop('analysis_partial_interpretations', None)
                    if semantic:
                        s['interpretations'] = semantic['interpretations']
                    s.pop('requires_analysis', None)
                    s['job'] = {'status': 'completed_with_warnings' if semantic and semantic.get('review_ids') else 'completed',
                                'completed': len(s['photos']), 'total': len(s['photos']), 'error': None}
                s['status'] = 'ready'
                s['revision'] += 1
                store.put(db, s)
        except Exception:
            with store.transaction() as db:
                s = store.get(sid, db)
                s['job'] = {'status': 'failed', 'completed': 0, 'total': len(s['photos']), 'error': 'Analysis failed. Data and decisions preserved.'}
                s['requires_analysis'] = True
                if s.get('proposal'):
                    s['proposal']['stale'] = True
                s['status'] = 'ready'
                s['revision'] += 1
                store.put(db, s)

    @app.post('/api/services/{sid}/analyze')
    def start_analysis(sid: str, body: Revision):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            # This endpoint is always local, including the first pass of hybrid mode.
            # Cloud requests require a separate immutable estimate and confirmation.
            s.pop('confirmed_batch_id', None)
            s['status'] = 'analyzing'
            s['job'] = {'status': 'running', 'completed': 0, 'total': len(s['photos']), 'error': None}
            s['revision'] += 1
            store.put(db, s)
        executor.submit(run_analysis, sid, s['revision'])
        return present(s)

    def local_components():
        vision_path = Path(os.environ.get('LRC_VISION_TOOL', Path(__file__).resolve().parents[2] / '.build/lrc-face-detection'))
        siglip_path = os.environ.get('LRC_SIGLIP_DIR', str(root / 'models' / 'siglip2-base-patch16-224'))
        return (Path(siglip_path) if siglip_path and (Path(siglip_path) / 'model.safetensors').is_file() else None,
                vision_path if vision_path.is_file() and os.access(vision_path, os.X_OK) else None)

    def instruction_component():
        try:
            return resolve_model(root)
        except ValueError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get('/api/capabilities')
    def capabilities():
        siglip_path, vision_path = local_components()
        return {'features': bool(siglip_path or vision_path), 'siglip': bool(siglip_path), 'semantic': bool(siglip_path or instruction_component()), 'instructions': bool(instruction_component()), 'faces': bool(vision_path)}

    def run_features(sid, revision, siglip_path, vision_path):
        try:
            from .features import SiglipEncoder, extract
            encoder = SiglipEncoder(siglip_path) if siglip_path else None
            extract(store, sid, encoder, vision_path, job_revision=revision)
        except Exception:
            with store.transaction() as db:
                service = store.get(sid, db)
                if service['revision'] == revision and service['status'] == 'analyzing':
                    service['job']['status'] = 'failed'
                    service['job']['error'] = 'Local extraction failed. Cached results will be reused.'
                    service['status'] = 'ready'
                    service['revision'] += 1
                    store.put(db, service)

    @app.post('/api/services/{sid}/features')
    def start_features(sid: str, body: Revision):
        siglip_path, vision_path = local_components()
        if not (siglip_path or vision_path):
            raise HTTPException(409, 'No local vision component configured')
        with store.transaction() as db:
            service = store.get(sid, db)
            store.check_revision(service, body.revision)
            require_editable(service)
            service.pop('confirmed_batch_id', None)
            service['status'] = 'analyzing'
            service['job'] = {'kind': 'features', 'status': 'running', 'completed': 0, 'total': len(service['photos']), 'error': None}
            service['revision'] += 1
            store.put(db, service)
        executor.submit(run_features, sid, service['revision'], siglip_path, vision_path)
        return present(service)

    @app.post('/api/services/{sid}/rating-plan')
    def rating_plan(sid: str, body: Revision):
        with store.transaction() as db:
            s = store.get(sid, db)
            store.check_revision(s, body.revision)
            require_editable(s)
            if s.get('requires_analysis') or (s.get('proposal') and s['proposal'].get('stale')):
                raise HTTPException(409, 'Proposal stale: run selection again before applying stars')
            # Applied, conflicting and uncertain attempts are protected. Never-started skips may retry.
            attempted = {r['photo_id'] for receipt in s['receipts'] for r in receipt['results'] if r['status'] != 'skipped'}
            selected = set(effective_selected(s))
            items, warnings = [], []
            for p in s['photos']:
                if p['id'] not in selected or p['baseline_rating'] != 0 or p['id'] in attempted:
                    continue
                if p['baseline_edit_time'] is None:
                    warnings.append(f"{p['filename']}: initial state unverifiable, no star can be applied")
                    continue
                items.append({'photo_id': p['id'], 'uuid': p['uuid'], 'local_id': p['local_id'], 'expected_rating': 0,
                              'expected_edit_time': p['baseline_edit_time'], 'target_rating': 1, 'filename': p['filename']})
            plan = {'batch_id': str(uuid.uuid4()), 'service_id': sid, 'catalog_id': s['catalog_id'], 'revision': s['revision'],
                    'items': items, 'warnings': warnings, 'created_at': time.time(), 'schema_version': 1}
            db.execute('INSERT INTO batches VALUES(?,?,?)', (plan['batch_id'], sid, json.dumps(plan)))
        return plan

    def get_plan(db, sid, batch_id):
        row = db.execute('SELECT body FROM batches WHERE id=? AND service_id=?', (batch_id, sid)).fetchone()
        if not row:
            raise HTTPException(404, 'Plan not found')
        return json.loads(row['body'])

    @app.post('/api/services/{sid}/rating-plan/confirm')
    def confirm_plan(sid: str, body: BatchInput):
        with store.transaction() as db:
            s = store.get(sid, db)
            plan = get_plan(db, sid, body.batch_id)
            store.check_revision(s, plan['revision'])
            if s['status'] != 'ready' or s.get('archived'):
                raise HTTPException(409, 'Service unavailable')
            s['confirmed_batch_id'] = body.batch_id
            store.put(db, s)
        return plan

    @app.get('/api/services/{sid}/rating-plan/latest')
    def latest_plan(sid: str):
        with store.connect() as db:
            s = store.get(sid, db)
            batch_id = s.get('active_batch_id') or s.get('confirmed_batch_id')
            if not batch_id:
                raise HTTPException(404, 'Confirm a plan in the web app')
            plan = get_plan(db, sid, batch_id)
            store.check_revision(s, plan['revision'])
            return plan

    @app.post('/api/services/{sid}/rating-plan/claim')
    def claim_plan(sid: str, body: BatchInput):
        with store.transaction() as db:
            s = store.get(sid, db)
            plan = get_plan(db, sid, body.batch_id)
            store.check_revision(s, plan['revision'])
            if s['status'] == 'applying' and s.get('active_batch_id') == body.batch_id:
                return {'ok': True, 'resumed': True}
            if s['status'] != 'ready' or s.get('archived') or s.get('confirmed_batch_id') != body.batch_id:
                raise HTTPException(409, 'Plan unconfirmed or service busy')
            s['status'] = 'applying'
            s['active_batch_id'] = body.batch_id
            store.put(db, s)
        return {'ok': True, 'resumed': False}

    @app.post('/api/services/{sid}/rating-receipts')
    def receipt(sid: str, body: Receipt):
        with store.transaction() as db:
            s = store.get(sid, db)
            row = db.execute('SELECT body FROM batches WHERE id=? AND service_id=?', (body.batch_id, sid)).fetchone()
            if not row:
                raise HTTPException(404, 'Application not found')
            plan = json.loads(row['body'])
            allowed = {i['photo_id'] for i in plan['items']}
            if len({r.photo_id for r in body.results}) != len(body.results) or any(r.photo_id not in allowed for r in body.results):
                raise HTTPException(422, 'Receipt does not match the plan')
            incoming = body.model_dump()
            old = next((r for r in s['receipts'] if r['batch_id'] == body.batch_id), None)
            if old:
                if old != incoming:
                    raise HTTPException(409, 'Receipt already recorded with different outcomes')
                return {'ok': True}
            if s.get('active_batch_id') != body.batch_id:
                raise HTTPException(409, 'The plugin must claim the plan before submitting a receipt')
            if {r.photo_id for r in body.results} != allowed:
                raise HTTPException(422, 'The receipt must contain an outcome for every photo in the plan')
            if any(r.status == 'applied' and (r.before != 0 or r.after != 1) for r in body.results):
                raise HTTPException(422, 'Invalid applied outcome: only ratings from 0 to 1 are allowed')
            s['receipts'].append(incoming)
            s['last_rating_revision'] = s['revision'] + 1
            s['status'] = 'ready'
            s.pop('active_batch_id', None)
            s.pop('confirmed_batch_id', None)
            s['revision'] += 1
            store.put(db, s)
        return {'ok': True}

    from .openai_analysis import register_openai_analysis
    register_openai_analysis(app, store, executor, present, require_editable)

    assets = web_dir or Path(__file__).resolve().parents[2] / 'web/dist'
    if assets.is_dir():
        app.mount('/', StaticFiles(directory=assets, html=True), name='web')
    else:
        @app.get('/')
        def no_build():
            return {'message': 'Frontend not built. Run npm ci and npm run build in the web directory.'}
    return app
