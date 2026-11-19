"""Reviewed vision models/pricing; account discovery never sends photographs."""
import json
import os
import re
import ssl
import certifi
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException

MODEL_SPECS = {
    'gpt-5.4-mini-2026-03-17': {
        'id': 'gpt-5.4-mini-2026-03-17', 'label': 'GPT-5.4 mini',
        'input_per_million': .75, 'output_per_million': 4.5,
        'source': 'https://developers.openai.com/api/docs/models/gpt-5.4-mini', 'verified_at': '2026-11-18',
    },
    'gpt-5.4-2026-03-05': {
        'id': 'gpt-5.4-2026-03-05', 'label': 'GPT-5.4',
        'input_per_million': 2.5, 'output_per_million': 15.,
        'source': 'https://developers.openai.com/api/docs/models/gpt-5.4', 'verified_at': '2026-11-18',
    },
}
MODEL_SPECS.update({
    'gpt-5.3-codex': {'id': 'gpt-5.3-codex', 'label': 'GPT-5.3 Codex', 'input_per_million': 1.75, 'output_per_million': 14., 'source': 'https://developers.openai.com/api/docs/models/gpt-5.3-codex', 'verified_at': '2026-11-19'},
    'gpt-6.2-sol': {'id': 'gpt-6.2-sol', 'label': 'GPT-6.2 Sol', 'input_per_million': 2., 'output_per_million': 10., 'source': 'https://developers.openai.com/api/docs/models/gpt-6.2-sol', 'verified_at': '2026-11-19'},
    'gpt-6.2-astra': {'id': 'gpt-6.2-astra', 'label': 'GPT-6.2 Astra', 'input_per_million': 8., 'output_per_million': 40., 'source': 'https://developers.openai.com/api/docs/models/gpt-6.2-astra', 'verified_at': '2026-11-19'},
})
ALIASES = {'gpt-5.4-mini': 'gpt-5.4-mini-2026-03-17', 'gpt-5.4': 'gpt-5.4-2026-03-05'}


def compatible_family(model):
    """Candidate image/Responses families; discovery is not a capability proof."""
    if any(part in model for part in ('audio', 'realtime', 'transcribe', 'tts', 'embedding', 'image', 'search', 'instruct', 'moderation', 'chat-latest')):
        return False
    if model.startswith(('gpt-5.4-pro', 'o1-mini', 'o1-preview', 'gpt-4o-2024-05-13')):
        return False
    return bool(re.fullmatch(r'(?:gpt-(?:4o|4\.1|[56](?:\.\d+)?)(?:-[a-z0-9]+)*|o[134](?:-[a-z0-9]+)*)', model))


def lookup_model(model):
    canonical = ALIASES.get(model, model)
    if canonical in MODEL_SPECS:
        return dict(MODEL_SPECS[canonical], pricing_known=True, compatibility='verified', **({'long_context_threshold': 272000, 'long_context_input_multiplier': 2., 'long_context_output_multiplier': 1.5} if canonical.startswith('gpt-6.2') else {}))
    if not compatible_family(canonical):
        raise ValueError('Model incompatible with photo analysis. Select a model from the list.')
    return {'id': canonical, 'label': canonical, 'input_per_million': None, 'output_per_million': None,
            'source': None, 'verified_at': None, 'pricing_known': False, 'compatibility': 'family'}


def request_parameters(model):
    if model.startswith('gpt-6') or model.startswith('gpt-5.3-codex'):
        return {'reasoning': {'effort': 'low'}}
    if model.startswith('gpt-5.4'):
        return {'reasoning': {'effort': 'none'}}
    return {}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('API redirect rejected')


def fetch_account_models(key):
    request = urllib.request.Request('https://api.openai.com/v1/models', headers={'Authorization': 'Bearer '+key})
    with urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where()))).open(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Invalid model list')
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        raise ValueError('Invalid model list')
    return {item['id'] for item in data['data'] if isinstance(item, dict) and isinstance(item.get('id'), str) and len(item['id']) <= 200}


class ModelCatalog:
    def __init__(self, root, config):
        self.path = Path(root) / 'openai-available-models.json'
        self.config = config
        self.transport = fetch_account_models

    def read(self):
        cached = json.loads(self.path.read_text()) if self.path.exists() else None
        available = set(cached['ids']) if cached else None
        ids = set(MODEL_SPECS) | (available or set())
        models = []
        for model in sorted(ids.difference(ALIASES)):
            try:
                spec = lookup_model(model)
                models.append(dict(spec, supported=True, available=(model in available if available is not None else None),
                                   compatibility_note=('Compatibility verified; access depends on the account.' if spec['compatibility'] == 'verified' else 'Candidate family: actual compatibility is checked only during the first confirmed submission. Pricing unavailable.')))
            except ValueError:
                models.append({'id': model, 'label': model, 'available': True, 'supported': False,
                               'input_per_million': None, 'output_per_million': None, 'pricing_known': False,
                               'compatibility': 'unsupported', 'compatibility_note': 'Model unsuitable for images or the required format.'})
        checked_at = cached['checked_at'] if cached else None
        stale = not checked_at or (datetime.now(timezone.utc) - datetime.fromisoformat(checked_at)).total_seconds() > 86400
        return {'models': models, 'checked_at': checked_at, 'stale': stale,
                'note': 'Model list can be refreshed from the OpenAI account. Compatible photo model families can be used without pricing after explicitly confirming the unestimable cost. The selected model is never substituted automatically.'}

    def refresh(self):
        try:
            key = self.config.secrets().get()
            if not key:
                raise HTTPException(409, 'Save the API key in settings first.')
            available = self.transport(key)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, 'Model check failed. Check the key, permissions and connection; no photos sent.') from None
        record = {'ids': sorted(set(available)),
                  'checked_at': datetime.now(timezone.utc).isoformat()}
        temporary = self.path.with_suffix('.pending')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream)
        temporary.replace(self.path)
        return self.read()


def register_model_catalog(app, root):
    catalog = ModelCatalog(root, app.state.openai_config)
    app.state.openai_models = catalog
    @app.get('/api/openai/models')
    def models():
        return catalog.read()
    @app.post('/api/openai/models/refresh')
    def refresh_models():
        return catalog.refresh()
