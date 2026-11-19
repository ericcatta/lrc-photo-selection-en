"""Isolated 5,000-photo browser fixture made entirely from generated shapes.

No catalog, user photograph, credential store, model or cloud is accessed.
"""
import argparse
import io
import json
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from smoke_fixture import isolate_config
from lrc_selection.app import create_app

SERVICE = 'synthetic-scale-ui'
TOKEN = 'synthetic-scale-ui-only'


def make_app(root, count=5000):
    web_dir = Path(os.environ['LRC_SMOKE_WEB_DIR']) if os.environ.get('LRC_SMOKE_WEB_DIR') else None
    app = isolate_config(create_app(root, token=TOKEN, web_dir=web_dir))
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer ' + TOKEN
        photos = [{'id': f'scale-{i}', 'uuid': f'scale-uuid-{i}', 'local_id': i,
                   'filename': f'SYNTHETIC_{i:05d}.jpg', 'camera': 'Synthetic camera',
                   'captured_at': 1700000000 + i, 'baseline_rating': 0,
                   'baseline_edit_time': 100, 'is_virtual_copy': False}
                  for i in range(count)]
        client.post('/api/imports', json={'schema_version': 1, 'id': SERVICE,
                    'title': 'SYNTHETIC SCALE — no real photographs',
                    'catalog_id': 'synthetic-scale-no-catalog', 'photos': photos}).raise_for_status()
        image = Image.new('RGB', (600, 400), '#536f80')
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 45, 560, 355), outline='white', width=3)
        draw.ellipse((180, 80, 420, 320), fill='#c99f55')
        draw.text((70, 60), 'SYNTHETIC SCALE FIXTURE', fill='white')
        output = io.BytesIO()
        image.save(output, 'JPEG')
        client.put(f'/api/services/{SERVICE}/photos/scale-0/preview', content=output.getvalue()).raise_for_status()
        # Every photo refers to the same generated image; hard links avoid 5,000
        # uploads and duplicated image data while preserving the real HTTP path.
        store = app.state.store
        source = store.preview_path(SERVICE, 'scale-0')
        with store.transaction() as db:
            service = store.get(SERVICE, db)
            for photo in service['photos']:
                if photo['id'] != 'scale-0':
                    os.link(source, store.preview_path(SERVICE, photo['id']))
                photo['preview_ready'] = True
            store.put(db, service)
        client.post(f'/api/services/{SERVICE}/complete').raise_for_status()
    app = isolate_config(create_app(root, token=TOKEN, web_dir=web_dir))
    class SyntheticSecrets:
        def get(self):
            return 'synthetic-scale-key-no-network'
    app.state.openai_config.keychain = SyntheticSecrets()
    from lrc_selection.openai_analysis import MODEL
    app.state.openai_config.path.write_text(json.dumps({'model': MODEL}))
    calls = []
    def reject_transport(*args, **kwargs):
        calls.append('unexpected')
        raise AssertionError('Scale browser test must never confirm a cloud request')
    app.state.openai_analysis.transport = reject_transport
    @app.get('/api/synthetic-scale-transport')
    def transport_status():
        return {'mock_calls': len(calls), 'real_network_calls': 0}
    app.router.routes.insert(0, app.router.routes.pop())
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18767)
    parser.add_argument('--count', type=int, default=5000)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000:
        parser.error('Synthetic count must be between 1 and 10000')
    root = Path(tempfile.mkdtemp(prefix='lrc-synthetic-scale-ui-'))
    app = make_app(root, args.count)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)
