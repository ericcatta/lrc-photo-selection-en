import importlib.util
from pathlib import Path
from lrc_selection.features import extract
from test_workflow import imported

# Reuse API fixture; no model installation or real photograph involved.
from test_workflow import client

class FakeEncoder:
    identity = {'adapter': 'synthetic-test-only'}
    def encode(self, path):
        assert path.suffix == '.jpg'
        return [1.0, 0.0]

def test_optional_features_do_not_remove_candidates(client):
    s = imported(client)
    before = client.get('/api/services/' + s['id']).json()
    evidence = extract(client.app.state.store, s['id'], FakeEncoder())
    after = client.get('/api/services/' + s['id']).json()
    assert before['selected_ids'] == after['selected_ids']
    assert after['decisions'] == before['decisions']
    assert all(r['error'] == 'Missing preview' for r in evidence['records'].values())
    assert after['interpretations']['model']['adapter'] == 'synthetic-test-only'

def test_benchmark_detects_loss_and_merge(client):
    spec = importlib.util.spec_from_file_location('benchmark', Path(__file__).resolve().parents[2] / 'scripts/benchmark.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    s = imported(client)
    s['proposal'] = {'selected': ['u0:1'], 'groups': [{'members': ['u0:1', 'u1:1']}], 'engine': 'synthetic'}
    result = module.evaluate(s, {'service_id': s['id'], 'significant_groups': [['u2:1']],
                                 'unique_images': ['u3:1'], 'must_separate_pairs': [['u0:1', 'u1:1']]})
    assert result['significant_groups_lost'] == 1
    assert result['unique_images_excluded'] == 1
    assert result['person_compositions_merged'] == 1


def test_apple_vision_processes_synthetic_preview(tmp_path):
    import sys
    import pytest
    from PIL import Image
    from lrc_selection.features import face_rectangles
    tool = Path(__file__).resolve().parents[2] / '.build/lrc-face-detection'
    if sys.platform != 'darwin' or not tool.exists():
        pytest.skip('Apple Vision requires a compiled macOS helper')
    preview = tmp_path / 'synthetic.jpg'
    Image.new('RGB', (100, 100), 'gray').save(preview)
    result = face_rectangles(tool, preview)
    assert result['observations'] == []
    assert result['error'] is None


def test_feature_cache_survives_interruption_and_model_changes(client, monkeypatch):
    from lrc_selection import features
    from test_workflow import manifest, jpeg
    m = manifest(count=2)
    client.post('/api/imports', json=m)
    for i, color in enumerate(['red', 'blue']):
        client.put(f'/api/services/test-service/photos/u{i}:1/preview', content=jpeg(color))
    s = client.post('/api/services/test-service/complete').json()
    monkeypatch.setattr(features, 'comparison_suggestions', lambda records: [])
    class Interruptible:
        identity = {'adapter': 'synthetic-cache-v1'}
        calls = 0
        fail = True
        def encode(self, path):
            self.calls += 1
            if self.fail and self.calls == 2:
                raise RuntimeError('synthetic interruption')
            return [1.0, 0.0]
    import pytest
    encoder = Interruptible()
    with pytest.raises(RuntimeError, match='synthetic interruption'):
        extract(client.app.state.store, s['id'], encoder)
    assert 'interpretations' not in client.app.state.store.get(s['id'])
    encoder.fail = False
    extract(client.app.state.store, s['id'], encoder)
    assert encoder.calls == 3  # successful first image reused
    extract(client.app.state.store, s['id'], encoder)
    assert encoder.calls == 3
    encoder.identity = {'adapter': 'synthetic-cache-v2'}
    extract(client.app.state.store, s['id'], encoder)
    assert encoder.calls == 5
    assert client.app.state.store.get(s['id'])['decisions'] == s['decisions']


def test_failed_face_detection_not_cached(tmp_path):
    from lrc_selection.features import FeatureCache
    cache = FeatureCache(tmp_path)
    calls = []
    def failed():
        calls.append(True)
        return {'error': 'synthetic error', 'observations': []}
    for _ in range(2):
        cache.get_or_compute('hash', 'faces', {'version': 1}, failed)
    assert len(calls) == 2


def test_comparison_suggestions_are_evidence_only():
    import pytest
    pytest.importorskip('numpy')
    from lrc_selection.features import comparison_suggestions
    records = {'a': {'embedding': [1, 0]}, 'b': {'embedding': [0.99, 0.01]}, 'c': {'embedding': [0, 1]}}
    pairs = comparison_suggestions(records)
    assert pairs[0]['photo_id'] == 'a' and pairs[0]['other_photo_id'] == 'b'
    assert all('selected' not in p and 'representative' not in p for p in pairs)
    assert len({tuple(sorted((p['photo_id'], p['other_photo_id']))) for p in pairs}) == len(pairs)
    with pytest.raises(ValueError):
        comparison_suggestions({'a': {'embedding': [0, 0]}, 'b': {'embedding': [1, 0]}})


def test_feature_job_is_explicit_and_keeps_decisions(client, monkeypatch, tmp_path):
    import time
    from lrc_selection import features
    from test_workflow import manifest, jpeg
    tool = tmp_path / 'synthetic-vision-helper'
    tool.write_text('synthetic-test-only')
    tool.chmod(0o700)
    monkeypatch.setenv('LRC_VISION_TOOL', str(tool))
    monkeypatch.delenv('LRC_SIGLIP_DIR', raising=False)
    calls = []
    def detect(tool, path):
        calls.append(path)
        return {'observations': [], 'error': None}
    monkeypatch.setattr(features, 'face_rectangles', detect)
    client.post('/api/imports', json=manifest(count=1)).raise_for_status()
    client.put('/api/services/test-service/photos/u0:1/preview', content=jpeg('red')).raise_for_status()
    s = client.post('/api/services/test-service/complete').json()
    assert calls == []
    base = '/api/services/test-service'
    s = client.patch(base + '/decisions/u0:1', json={'revision': s['revision'], 'state': 'preferred', 'locked': True}).json()
    assert client.get('/api/capabilities').json()['faces']
    for _ in range(2):
        client.post(base + '/features', json={'revision': s['revision']}).raise_for_status()
        for _ in range(100):
            s = client.get(base).json()
            if s['job']['status'] != 'running':
                break
            time.sleep(.01)
        assert s['job']['status'] == 'completed'
        assert s['decisions']['u0:1'] == {'state': 'preferred', 'locked': True}
        assert s['selected_ids'] == ['u0:1']
    assert len(calls) == 1
    assert s['interpretations']['records']['u0:1']['faces']['observations'] == []


def test_missing_feature_components_are_reported(client, monkeypatch, tmp_path):
    monkeypatch.setenv('LRC_VISION_TOOL', str(tmp_path / 'absent'))
    monkeypatch.delenv('LRC_SIGLIP_DIR', raising=False)
    s = imported(client)
    assert client.get('/api/capabilities').json()['features'] is False
    assert client.post('/api/services/test-service/features', json={'revision': s['revision']}).status_code == 409
