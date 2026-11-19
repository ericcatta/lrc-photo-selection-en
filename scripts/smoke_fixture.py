"""Isolated synthetic UI fixture. Never points to a Lightroom catalog."""
import argparse
import io
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from lrc_selection.app import create_app

TOKEN = 'synthetic-ui-test-only'

class SyntheticKeychain:
    def get(self):
        return None
    def set(self, value):
        raise RuntimeError('Fixture: real keys are not allowed')

def isolate_config(app):
    if hasattr(app.state, 'openai_config'):
        app.state.openai_config.keychain = SyntheticKeychain()
    return app

def make_app(root):
    # Test-only override keeps staged builds separate from the installed UI.
    web_dir = Path(os.environ['LRC_SMOKE_WEB_DIR']) if os.environ.get('LRC_SMOKE_WEB_DIR') else None
    app = isolate_config(create_app(root, token=TOKEN, web_dir=web_dir))
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + TOKEN
        photos = [{'id': f'synthetic-{i}', 'uuid': f'synthetic-uuid-{i}', 'local_id': i,
                   'filename': f'SINTETICO_{i:03d}.jpg', 'camera': 'Fotocamera simulata',
                   'captured_at': 1700000000 + i, 'baseline_rating': 3 if i == 5 else 0,
                   'baseline_edit_time': 100, 'is_virtual_copy': False} for i in range(6)]
        response = c.post('/api/imports', json={'schema_version': 1, 'id': 'synthetic-ui',
            'title': 'TEST SINTETICO — nessuna fotografia reale', 'catalog_id': 'synthetic-not-a-real-catalog', 'photos': photos})
        response.raise_for_status()
        for i in range(6):
            image = Image.new('RGB', (600, 400), ['#536f80', '#536f80', '#8a684b', '#6f7966', '#816879', '#5c627e'][i])
            draw = ImageDraw.Draw(image)
            draw.rectangle((40, 45, 560, 355), outline='white', width=3)
            draw.text((70, 90), 'DATI SINTETICI - TEST INTERFACCIA', fill='white')
            draw.text((70, 160), f'Variante {max(0, i-1)}', fill='white')
            output = io.BytesIO()
            image.save(output, 'JPEG')
            c.put(f'/api/services/synthetic-ui/photos/synthetic-{i}/preview', content=output.getvalue()).raise_for_status()
        c.post('/api/services/synthetic-ui/complete').raise_for_status()
    # TestClient lifespan shut down executor; create a fresh runtime for the server.
    return isolate_config(create_app(root, token=TOKEN, web_dir=web_dir))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='lrc-synthetic-ui-'))
    app = make_app(root)
    print(f'Synthetic fixture only: {root}', flush=True)
    print(f'http://127.0.0.1:{args.port}/#token={TOKEN}', flush=True)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)
