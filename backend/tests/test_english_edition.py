"""English-edition isolation and verbatim input contracts; synthetic data only."""
from pathlib import Path

from fastapi.testclient import TestClient

from lrc_selection.app import create_app
from lrc_selection.openai_config import MacKeychain
from lrc_selection.openai_analysis import _interpret_request
from test_workflow import client, TOKEN


def test_english_cookie_never_authenticates_from_italian_cookie(client):
    client.cookies.set('lrc_session', TOKEN)
    assert client.get('/api/services', headers={'Authorization':''}).status_code == 401
    response = client.post('/api/session', json={'token':TOKEN})
    assert response.status_code == 200
    assert 'lrc_session_en=' in response.headers['set-cookie']
    assert client.get('/api/services', headers={'Authorization':''}).status_code == 200
    assert client.cookies.get('lrc_session') == TOKEN  # Other edition is not overwritten.


def test_default_storage_and_secrets_are_isolated_from_italian_edition(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.delenv('LRC_SELECTION_EN_DATA', raising=False)
    italian = tmp_path/'italian-data'
    italian.mkdir()
    sentinel = italian/'do-not-touch'
    sentinel.write_text('Italian edition remains unchanged')
    monkeypatch.setenv('LRC_SELECTION_DATA', str(italian))
    app = create_app(token=TOKEN)
    with TestClient(app) as request:
        assert request.get('/api/services', headers={'Authorization':'Bearer '+TOKEN}).json() == []
    assert app.state.store.root == tmp_path/'Library/Application Support/LrC Photo Selection EN'
    assert sentinel.read_text() == 'Italian edition remains unchanged'
    assert not (italian/'selection.sqlite3').exists()
    assert MacKeychain.service == b'lrc-photo-selection-en-openai'


def test_english_model_context_keeps_multilingual_original_verbatim():
    original = '  Scegli gli uccelli.\nPreserve the embrace! È importante.\n'
    payload = _interpret_request({'model':'gpt-6.2-sol','instructions':original,'criteria':[],'subject_query':''})
    assert payload['input'][1]['content'][0]['text'] == original
    assert 'Respond in English.' in payload['input'][0]['content'][0]['text']
