import io
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from lrc_selection.app import create_app

TOKEN = 'test-only-local-token'

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path, token=TOKEN)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        yield c

def manifest(sid='test-service', count=4, catalog='test-catalog'):
    return {'schema_version': 1, 'id': sid, 'title': 'DATI SINTETICI — test', 'catalog_id': catalog,
            'photos': [{'id': f'u{i}:1', 'uuid': f'u{i}', 'local_id': i, 'filename': 'duplicate-name.jpg',
                        'camera': 'camera-a', 'captured_at': i, 'baseline_rating': 0,
                        'baseline_edit_time': 10.0, 'is_virtual_copy': i == 1} for i in range(count)]}

def imported(c, m=None):
    m = m or manifest()
    response = c.post('/api/imports', json=m)
    assert response.status_code == 200, response.text
    s = c.post(f"/api/services/{m['id']}/complete").json()
    return s

def detail(c, sid='test-service'):
    return c.get('/api/services/' + sid).json()

def configure(c, s, **changes):
    response = c.put(f"/api/services/{s['id']}/settings", json={'revision': s['revision'], 'settings': s['settings'] | changes})
    assert response.status_code == 200, response.text
    return response.json()

def jpeg(color):
    data = io.BytesIO()
    Image.new('RGB', (24, 16), color).save(data, 'JPEG')
    return data.getvalue()

def run(c, s):
    response = c.post(f"/api/services/{s['id']}/analyze", json={'revision': s['revision']})
    assert response.status_code == 200, response.text
    for _ in range(100):
        current = detail(c, s['id'])
        if current['job']['status'] not in ('running', 'queued'):
            return current
        time.sleep(.01)
    pytest.fail('Analysis did not complete')

def test_auth_host_origin_and_cookie(client):
    assert client.get('/api/services', headers={'Authorization': ''}).status_code == 401
    assert client.get('/api/services', headers={'Host': 'evil.test'}).status_code == 400
    assert client.post('/api/session', json={'token': TOKEN}, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert client.post('/api/session', json={'token': TOKEN}).status_code == 200
    assert client.get('/api/services', headers={'Authorization': ''}).status_code == 200
    assert client.cookies.get('lrc_session_en') == TOKEN

def test_identity_idempotency_and_manifest_conflict(client):
    m = manifest()
    s = imported(client, m)
    assert len(s['photos']) == 4
    assert client.post('/api/imports', json=m).json()['revision'] == s['revision']
    changed = dict(m, title='changed')
    assert client.post('/api/imports', json=changed).status_code == 409
    other = imported(client, manifest('other', catalog='other-catalog'))
    assert other['catalog_id'] != s['catalog_id']
    m['photos'][1]['id'] = m['photos'][0]['id']
    assert client.post('/api/imports', json=m).status_code == 422

def test_safe_preview_paths_and_validation(client, tmp_path):
    m = manifest()
    m['photos'][0]['filename'] = '../../../../original.jpg'
    client.post('/api/imports', json=m)
    endpoint = '/api/services/test-service/photos/u0:1/preview'
    assert client.put(endpoint, content=b'bad').status_code == 422
    assert client.put(endpoint, content=jpeg('red')).status_code == 200
    assert client.get(endpoint).content == jpeg('red')
    assert client.put('/api/services/test-service/photos/not-present/preview', content=jpeg('red')).status_code == 404
    client.post('/api/services/test-service/complete')
    assert client.put(endpoint, content=jpeg('red')).status_code == 200
    assert client.put(endpoint, content=jpeg('blue')).status_code == 409
    assert not (tmp_path / 'original.jpg').exists()

def test_target_and_conservative_groups(client):
    m = manifest()
    client.post('/api/imports', json=m)
    for i, color in enumerate(['red', 'red', 'red', 'blue']):
        assert client.put(f'/api/services/test-service/photos/u{i}:1/preview', content=jpeg(color)).status_code == 200
    s = client.post('/api/services/test-service/complete').json()
    s = configure(client, s, target=3)
    s = run(client, s)
    assert len(s['selected_ids']) == 3
    assert 'u3:1' in s['selected_ids'] # unique image retained even when target low
    groups = s['proposal']['groups']
    assert len(groups) == 2
    assert all(set(g['members']) & set(s['selected_ids']) for g in groups)
    s = configure(client, s, target=1)
    s = run(client, s)
    assert len(s['selected_ids']) == 2 # coverage exceeds requested quantity

def test_missing_previews_never_equivalent(client):
    s = configure(client, imported(client), target=1)
    s = run(client, s)
    assert len(s['selected_ids']) == 4
    assert len(s['proposal']['groups']) == 4

def test_manual_decisions_lock_and_coverage_confirmation(client):
    s = imported(client)
    body = {'revision': s['revision'], 'state': 'excluded', 'locked': True}
    endpoint = '/api/services/test-service/decisions/u0:1'
    response = client.patch(endpoint, json=body)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'last_candidate'
    s = client.patch(endpoint, json=body | {'confirm_last': True}).json()
    assert client.patch(endpoint, json=body | {'confirm_last': True}).status_code == 409
    s = run(client, s)
    assert s['decisions']['u0:1'] == {'state': 'excluded', 'locked': True}
    assert 'u0:1' not in s['selected_ids']
    assert len(s['selected_ids']) == 3
    assert any('cannot be reached' in w for w in s['proposal']['warnings'])

def test_preset_snapshot_and_unsupported_instructions(client):
    s = imported(client)
    old = s['settings']['preset_snapshot']
    r = client.put('/api/presets/wedding', json={'name': 'Changed', 'criteria': ['different'], 'version': 1})
    assert r.status_code == 200
    s = configure(client, s, instructions='Scegli solo foto con lo zio')
    assert s['settings']['preset_snapshot'] == old
    assert s['criteria'][-1]['status'] == 'pending'
    assert client.put('/api/presets/wedding', json={'name': 'stale', 'criteria': [], 'version': 1}).status_code == 409
    s = configure(client, s, preset_id='wedding', preset_version=2)
    assert s['settings']['preset_snapshot']['name'] == 'Changed'

def test_rating_plan_preserves_existing_and_missing_edit_time(client):
    m = manifest()
    m['photos'][1]['baseline_rating'] = 5
    m['photos'][2]['baseline_rating'] = 1
    m['photos'][3]['baseline_edit_time'] = None
    s = imported(client, m)
    p = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    assert [i['photo_id'] for i in p['items']] == ['u0:1']
    assert p['items'][0]['target_rating'] == 1
    assert p['warnings']
    client.post('/api/services/test-service/rating-plan/confirm', json={'batch_id': p['batch_id']}).raise_for_status()
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).status_code == 200
    receipt = {'batch_id': p['batch_id'], 'results': [{'photo_id': 'u0:1', 'status': 'applied', 'before': 0, 'after': 1, 'reason': ''}]}
    assert client.post('/api/services/test-service/rating-receipts', json=receipt).status_code == 200
    assert client.post('/api/services/test-service/rating-receipts', json=receipt).status_code == 200
    assert client.get('/api/services/test-service/rating-plan/latest').status_code == 404
    s = detail(client)
    assert client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()['items'] == []

def test_stale_plan_and_receipt_validation(client):
    s = imported(client)
    p = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    s = configure(client, s, target=2)
    assert client.get('/api/services/test-service/rating-plan/latest').status_code == 404
    invalid = {'batch_id': p['batch_id'], 'results': [{'photo_id': 'foreign-photo', 'status': 'applied', 'after': 1}]}
    assert client.post('/api/services/test-service/rating-receipts', json=invalid).status_code == 422
    # A stale plan cannot be claimed after edits.
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).status_code == 409
    p = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    client.post('/api/services/test-service/rating-plan/confirm', json={'batch_id': p['batch_id']}).raise_for_status()
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).status_code == 200
    assert client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': p['batch_id']}).json()['resumed']
    assert client.put('/api/services/test-service/settings', json={'revision': s['revision'], 'settings': s['settings']}).status_code == 409
    assert client.patch('/api/services/test-service/decisions/u0:1', json={'revision': s['revision'], 'state': 'preferred'}).status_code == 409
    valid = {'batch_id': p['batch_id'], 'results': [{'photo_id': i['photo_id'], 'status': 'uncertain'} for i in p['items']]}
    assert client.post('/api/services/test-service/rating-receipts', json=valid).status_code == 200
    assert detail(client)['status'] == 'ready'


def test_quantity_validation_and_no_implicit_cloud(client):
    s = imported(client)
    for target in [0, 5]:
        assert client.put('/api/services/test-service/settings', json={'revision': s['revision'], 'settings': s['settings'] | {'target': target}}).status_code == 422
    s = configure(client, s, mode='hybrid')
    class NoKeyAccess:
        def get(self):
            raise AssertionError('Local analysis must not access an API credential')
    client.app.state.openai_config.keychain = NoKeyAccess()
    result = run(client, s)
    assert result['job']['status'] == 'completed'
    assert client.get('/api/services/test-service/api-status').json()['job'] is None

def test_restart_recovers_job_and_decisions(tmp_path):
    app = create_app(tmp_path, token=TOKEN)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        s = imported(c)
        store = app.state.store
        with store.transaction() as db:
            s['status'] = 'analyzing'
            s['job'] = {'status': 'running'}
            s['decisions']['u0:1'] = {'state': 'preferred', 'locked': True}
            store.put(db, s)
    with TestClient(create_app(tmp_path, token=TOKEN)) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        s = detail(c)
        assert s['job']['status'] == 'interrupted'
        assert s['decisions']['u0:1']['locked']


def test_analysis_settings_change_invalidates_rating_proposal(client):
    s = run(client, imported(client))
    s = configure(client, s, target=2)
    assert client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).status_code == 409
    s = run(client, s)
    assert client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).status_code == 200


def test_duplicated_local_id_is_rejected(client):
    m = manifest()
    m['photos'][1]['local_id'] = m['photos'][0]['local_id']
    assert client.post('/api/imports', json=m).status_code == 422


def test_concurrent_edits_cannot_both_commit_same_revision(client):
    s = imported(client)
    def change(pid):
        return client.patch('/api/services/test-service/decisions/' + pid,
                            json={'revision': s['revision'], 'state': 'preferred', 'locked': True}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(change, ['u0:1', 'u1:1']))
    assert statuses == [200, 409]
    assert len(detail(client)['decisions']) == 1


def test_low_disk_preserves_import_and_does_not_write_preview(client, monkeypatch):
    from collections import namedtuple
    import lrc_selection.app as module
    client.post('/api/imports', json=manifest())
    usage = namedtuple('usage', 'total used free')
    monkeypatch.setattr(module.shutil, 'disk_usage', lambda _: usage(100, 99, 1))
    response = client.put('/api/services/test-service/photos/u0:1/preview', content=jpeg('red'))
    assert response.status_code == 507
    assert detail(client)['status'] == 'importing'
    assert not detail(client)['photos'][0]['preview_ready']


def test_connection_token_does_not_reset_active_job(client):
    from lrc_selection.app import load_connection_token
    store = client.app.state.store
    s = imported(client)
    with store.transaction() as db:
        s['job'] = {'status': 'running'}
        s['status'] = 'analyzing'
        store.put(db, s)
    assert len(load_connection_token(store.root)) > 20
    assert store.get(s['id'])['job']['status'] == 'running'


def test_second_server_cannot_reset_first_servers_jobs(client):
    store = client.app.state.store
    imported(client)
    with pytest.raises(RuntimeError, match='backend is already using'):
        with TestClient(create_app(store.root, token=TOKEN)):
            pass
    assert detail(client)['status'] == 'ready'


def test_cancelled_before_attempt_can_be_retried(client):
    s = imported(client, manifest(count=1))
    plan = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    client.post('/api/services/test-service/rating-plan/confirm', json={'batch_id': plan['batch_id']}).raise_for_status()
    client.post('/api/services/test-service/rating-plan/claim', json={'batch_id': plan['batch_id']}).raise_for_status()
    client.post('/api/services/test-service/rating-receipts', json={'batch_id': plan['batch_id'], 'results': [{'photo_id': 'u0:1', 'status': 'skipped'}]}).raise_for_status()
    s = detail(client)
    new = client.post('/api/services/test-service/rating-plan', json={'revision': s['revision']}).json()
    assert len(new['items']) == 1


def test_rating_confirmation_pins_plan_and_active_batch_survives_restart(tmp_path):
    base = '/api/services/test-service/rating-plan'
    headers = {'Authorization': 'Bearer ' + TOKEN}
    with TestClient(create_app(tmp_path, token=TOKEN), headers=headers) as client:
        service = imported(client)
        first = client.post(base, json={'revision': service['revision']}).json()
        second = client.post(base, json={'revision': service['revision']}).json()
        assert client.post(base + '/claim', json={'batch_id': first['batch_id']}).status_code == 409
        client.post(base + '/confirm', json={'batch_id': first['batch_id']}).raise_for_status()
        assert client.get(base + '/latest').json() == first
        assert client.post(base + '/claim', json={'batch_id': second['batch_id']}).status_code == 409
        client.post(base + '/claim', json={'batch_id': first['batch_id']}).raise_for_status()
        assert client.post(base + '/confirm', json={'batch_id': second['batch_id']}).status_code == 409
    with TestClient(create_app(tmp_path, token=TOKEN), headers=headers) as client:
        assert client.get(base + '/latest').json() == first
        assert client.post(base + '/claim', json={'batch_id': first['batch_id']}).json()['resumed'] is True


def test_append_resumes_preserves_previous_decisions_and_invalidates_plan(client):
    base = '/api/services/test-service'
    service = imported(client, manifest(count=1))
    service = client.patch(base + '/decisions/u0:1', json={'revision': service['revision'], 'state': 'preferred', 'locked': True}).json()
    plan = client.post(base + '/rating-plan', json={'revision': service['revision']}).json()
    client.post(base + '/rating-plan/confirm', json={'batch_id': plan['batch_id']}).raise_for_status()
    photos = manifest(count=2)['photos']
    photos[0]['baseline_rating'] = 5
    request = {'id': 'append-1', 'catalog_id': service['catalog_id'], 'photos': photos}
    assert client.post(base + '/append', json=request | {'catalog_id': 'different'}).status_code == 409
    expected = {'photo_ids': ['u1:1'], 'completed': False}
    assert client.post(base + '/append', json=request).json() == expected
    assert client.post(base + '/append', json=request).json() == expected
    assert client.post(base + '/complete').status_code == 409
    assert client.put(base + '/photos/u0:1/preview', content=jpeg('red')).status_code == 409
    client.put(base + '/photos/u1:1/preview', content=jpeg('red')).raise_for_status()
    client.post(base + '/complete', json={'import_id': 'append-1'}).raise_for_status()
    assert client.post(base + '/append', json=request).json() == (expected | {'completed': True})
    current = detail(client)
    assert current['photos'][0]['baseline_rating'] == 0
    assert current['settings']['target'] == service['settings']['target']
    assert current['decisions'] == service['decisions']
    assert current['selected_ids'] == ['u0:1', 'u1:1']
    assert client.post(base + '/rating-plan/claim', json={'batch_id': plan['batch_id']}).status_code == 409
    assert client.post(base + '/rating-plan', json={'revision': current['revision']}).status_code == 409
    current = run(client, current)
    archived = client.put(base + '/archive', json={'revision': current['revision'], 'archived': True}).json()
    assert archived['archived'] is True
    assert client.post(base + '/rating-plan', json={'revision': archived['revision']}).status_code == 409
    reopened = client.put(base + '/archive', json={'revision': archived['revision'], 'archived': False}).json()
    assert reopened['decisions'] == service['decisions']


def test_replace_changes_representative_and_history_is_atomic(client):
    base = '/api/services/test-service'
    client.post('/api/imports', json=manifest(count=2)).raise_for_status()
    for pid in ('u0:1', 'u1:1'):
        client.put(f'{base}/photos/{pid}/preview', content=jpeg('red')).raise_for_status()
    service = client.post(base + '/complete').json()
    service = run(client, configure(client, service, target=1))
    assert service['proposal']['groups'][0]['representative'] == 'u0:1'
    replaced = client.post(base + '/replace', json={'revision': service['revision'], 'from_photo_id': 'u0:1', 'to_photo_id': 'u1:1'}).json()
    assert replaced['selected_ids'] == ['u1:1']
    assert replaced['proposal']['groups'][0]['representative'] == 'u1:1'
    assert replaced['can_undo']
    undone = client.post(base + '/undo', json={'revision': replaced['revision']}).json()
    assert undone['decisions'] == {}
    assert undone['selected_ids'] == ['u0:1']
    assert undone['can_redo']
    redone = client.post(base + '/redo', json={'revision': undone['revision']}).json()
    assert redone['decisions'] == replaced['decisions']


def test_custom_criteria_never_claim_text_understanding(client):
    from lrc_selection.app import criteria_for
    assert criteria_for({'preset_snapshot': {'criteria': ['Solo foto dello sposo']}})[0]['status'] == 'pending'


def test_history_survives_restart_and_new_branch_drops_redo(tmp_path):
    headers = {'Authorization': 'Bearer ' + TOKEN}
    base = '/api/services/test-service'
    with TestClient(create_app(tmp_path, token=TOKEN), headers=headers) as c:
        s = imported(c)
        c.patch(base + '/decisions/u0:1', json={'revision': s['revision'], 'state': 'preferred', 'locked': True}).raise_for_status()
    with TestClient(create_app(tmp_path, token=TOKEN), headers=headers) as c:
        s = c.get(base).json()
        assert s['can_undo']
        s = c.post(base + '/undo', json={'revision': s['revision']}).json()
        assert not s['decisions']
        s = c.patch(base + '/decisions/u1:1', json={'revision': s['revision'], 'state': 'review'}).json()
        assert not s['can_redo']
        assert c.post(base + '/redo', json={'revision': s['revision']}).status_code == 409


def test_settings_clear_confirmed_plan_and_legacy_manifest_digest(client):
    import hashlib
    import json
    m = manifest()
    service = imported(client, m)
    # Original Pydantic field order, including default catalog label.
    original = {k: (m.get(k, '') if k == 'catalog_label' else m[k]) for k in
                ('schema_version', 'id', 'title', 'catalog_id', 'catalog_label', 'photos')}
    original['photos'] = [dict(photo, captured_at=float(photo['captured_at'])) for photo in original['photos']]
    assert client.app.state.store.get(service['id'])['manifest_sha256'] == hashlib.sha256(
        json.dumps(original, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    plan = client.post('/api/services/test-service/rating-plan', json={'revision': service['revision']}).json()
    client.post('/api/services/test-service/rating-plan/confirm', json={'batch_id': plan['batch_id']}).raise_for_status()
    service = configure(client, service, target=1)
    assert 'confirmed_batch_id' not in service
    assert client.get('/api/services/test-service/rating-plan/latest').status_code == 404
    with client.app.state.store.connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1


def test_optional_preset_copy_can_be_edited_removed_and_reloaded(client):
    s = imported(client)
    assert s['settings']['preset_id'] == ''
    assert s['settings']['preset_snapshot'] is None
    p = client.post('/api/presets', json={'name': 'Natura', 'criteria': ['Conservare varianti'], 'subject_query': 'uccelli'}).json()
    s = configure(client, s, preset_id=p['id'], preset_version=1, service_criteria=p['criteria'], subject_query=p['subject_query'])
    other = imported(client, manifest('other-preset-test'))
    s = configure(client, s, service_criteria=['Varianti del volo'], subject_query='uccelli in volo')
    assert detail(client)['settings']['service_criteria'] == ['Varianti del volo']
    assert detail(client)['settings']['subject_query'] == 'uccelli in volo'
    assert next(x for x in client.get('/api/presets').json() if x['id'] == p['id'])['criteria'] == ['Conservare varianti']
    assert detail(client, other['id'])['settings']['service_criteria'] == []
    client.put('/api/presets/'+p['id'], json={'name': 'Natura', 'criteria': ['Nuove'], 'subject_query': 'animali', 'version': 1})
    assert detail(client)['settings']['preset_snapshot']['version'] == 1
    s = configure(client, s, preset_id='', service_criteria=[], subject_query='')
    assert s['settings']['preset_snapshot'] is None
    assert s['settings']['preset_version'] == 0


def test_review_shortlist_does_not_warn_about_unaccepted_candidate_count(client):
    service = imported(client)
    store = client.app.state.store
    with store.transaction() as db:
        s = store.get(service['id'], db)
        from lrc_selection.engine import analyze
        s['settings']['target'] = 1
        s['proposal'] = analyze(s)
        s['proposal']['shortlist'] = [s['photos'][0]['id']]
        s['proposal']['warnings'] = ['Copertura categoria ritratti da verificare.']
        store.put(db, s)
    result = detail(client)
    assert len(result['selected_ids']) == 4  # Review proposal has not applied exclusions.
    assert result['proposal']['warnings'] == ['Copertura categoria ritratti da verificare.']


def test_invalid_local_responses_are_retained_for_review_without_failing_batch(client, monkeypatch, tmp_path):
    from lrc_selection import vlm
    model_dir = tmp_path / 'fake-vlm'
    model_dir.mkdir()
    (model_dir / 'config.json').write_text('{"model_type":"synthetic"}')
    (model_dir / 'fake.safetensors').write_text('synthetic only')
    monkeypatch.setenv('LRC_VLM_DIR', str(model_dir))
    class FakeVLM:
        identity = {'test': 'partial-synthetic'}
        calls = 0
        def assess(self, path, interpretation):
            self.calls += 1
            if self.calls > 1:
                raise ValueError('Synthetic malformed response')
            return {'match': 'yes', 'reason': 'Synthetic positive', 'scene': 'synthetic',
                    'quality_issues': [], 'preference_score': .8,
                    'category_matches': {c['id']: 'yes' for c in interpretation['requested_categories']}}
    monkeypatch.setattr(vlm, 'LocalVLM', lambda _: FakeVLM())
    service = client.post('/api/imports', json=manifest()).json()
    for photo, color in zip(service['photos'], ['red', 'green', 'blue', 'white']):
        assert client.put(f"/api/services/{service['id']}/photos/{photo['id']}/preview", content=jpeg(color),
                          headers={'Content-Type': 'image/jpeg'}).status_code == 200
    assert client.post(f"/api/services/{service['id']}/complete").status_code == 200
    service = configure(client, detail(client), instructions='uccelli, ritratti, landscape', service_criteria=[], target=3)
    result = run(client, service)
    assert result['job']['status'] == 'completed_with_warnings'
    assert result['job']['error'] is None
    assert not result.get('requires_analysis')
    assert len(result['selected_ids']) == 4
    assert result['analysis_diagnostics']['invalid'] == 3
    assert len(result['proposal']['shortlist']) == 4
    assert len(result['proposal']['review_ids']) == 3
    assert result['decisions'] == {}
    accepted = client.post(f"/api/services/{service['id']}/accept-shortlist", json={
        'revision': result['revision'], 'confirm_last': True}).json()
    assert len(accepted['selected_ids']) == 4
    for pid in result['proposal']['review_ids']:
        assert accepted['decisions'][pid]['state'] == 'review'
    assert accepted['receipts'] == []


def test_blocked_instructions_report_reason_without_claiming_invalid_photos(client, monkeypatch, tmp_path):
    from lrc_selection import vlm
    model_dir = tmp_path / 'fake-vlm'
    model_dir.mkdir()
    (model_dir / 'config.json').write_text('{"model_type":"synthetic"}')
    (model_dir / 'fake.safetensors').write_text('synthetic only')
    monkeypatch.setenv('LRC_VLM_DIR', str(model_dir))
    monkeypatch.setattr(vlm, 'LocalVLM', lambda _: object())
    interpretation = {'ambiguities': ['Richieste contraddittorie sul medesimo soggetto.'], 'unsupported': []}
    monkeypatch.setattr(vlm, 'build_instruction_proposal', lambda *args: {
        'diagnostics': {'invalid': 0, 'valid': 0, 'attempted': 0, 'total': 4, 'not_assessed': 4},
        'interpretations': {'records': {}, 'comparisons': []},
        'instruction_interpretation': interpretation, 'blocked': True, 'incomplete': True,
        'shortlist': [],
    })
    service = configure(client, imported(client), instructions='Includi ed escludi lo stesso soggetto', service_criteria=[])
    store = client.app.state.store
    previous = {'records': {'u0:1': {'synthetic_previous_analysis': True}}}
    with store.transaction() as db:
        current = store.get(service['id'], db)
        current['interpretations'] = previous
        store.put(db, current)
    result = run(client, service)
    assert result['job']['status'] == 'failed'
    assert 'Analysis not started' in result['job']['error']
    assert interpretation['ambiguities'][0] in result['job']['error']
    assert 'risposte non valide' not in result['job']['error']
    assert result['analysis_diagnostics']['stage'] == 'instructions'
    assert result['analysis_instruction_interpretation'] == interpretation
    assert result['interpretations'] == previous
    assert result['analysis_partial_interpretations']['records'] == {}
    assert len(result['selected_ids']) == 4
    assert not result['decisions']


def test_old_zero_response_failure_is_presented_as_not_assessed(client):
    s = imported(client)
    store = client.app.state.store
    with store.transaction() as db:
        current = store.get(s['id'], db)
        current['job'] = {'status': 'failed', 'completed': 0, 'total': 4,
                          'error': 'Local analysis incomplete: 0 invalid responses su 4.'}
        current['analysis_diagnostics'] = {'attempted': 0, 'invalid': 0, 'not_assessed': 4}
        store.put(db, current)
    result = detail(client)
    assert 'before assessing photos' in result['job']['error']
    assert len(result['selected_ids']) == 4
    assert store.get(s['id'])['job']['error'].startswith('Local analysis incomplete: 0')
