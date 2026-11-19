"""Explicit, offline feature extraction on already imported previews only.

Does not download weights, access original file paths, identify people, or reduce
candidates. Uncalibrated similarity is presented as review evidence, not truth.
"""
import argparse
import hashlib
import json
import platform
import sqlite3
import subprocess
from pathlib import Path

from .store import Store

class SiglipEncoder:
    def __init__(self, model_dir: Path):
        if not model_dir.is_dir():
            raise ValueError('Specify a local directory containing downloaded and verified weights')
        # Imports are lazy so the complete manual/local baseline needs no ML stack.
        import torch
        from transformers import AutoModel, AutoProcessor, __version__ as transformers_version
        self.torch = torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.processor = AutoProcessor.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False).to(self.device).eval()
        config = self.model.config
        if getattr(config, 'model_type', '') not in {'siglip', 'siglip2'}:
            raise ValueError('This adapter supports only SigLIP 2 checkpoints')
        hashes = {}
        for path in sorted(model_dir.rglob('*')):
            if path.is_file() and path.suffix in ('.json', '.safetensors', '.model', '.txt'):
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                hashes[str(path.relative_to(model_dir))] = digest.hexdigest()
        self.identity = {'adapter': 'siglip2-v1', 'files': hashes, 'device': self.device,
                         'torch': torch.__version__, 'transformers': transformers_version}

    def encode(self, path):
        from PIL import Image
        with Image.open(path) as source:
            image = source.convert('RGB')
        inputs = self.processor(images=image, return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            vector = self.model.get_image_features(**inputs)
            vector = getattr(vector, 'pooler_output', vector)
            vector = vector / vector.norm(dim=-1, keepdim=True).clamp(min=1e-12)
        return vector[0].float().cpu().tolist()

    def encode_text(self, text):
        inputs = self.processor(text=[text], padding='max_length', truncation=True,
                                return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            vector = self.model.get_text_features(**inputs)
            vector = getattr(vector, 'pooler_output', vector)
            vector = vector / vector.norm(dim=-1, keepdim=True).clamp(min=1e-12)
        return vector[0].float().cpu().tolist()

def face_rectangles(tool, path):
    completed = subprocess.run([str(tool), str(path)], check=True, capture_output=True, timeout=120)
    result = json.loads(completed.stdout)[0]
    return {'engine': 'Apple Vision VNDetectFaceRectanglesRequest', 'os': platform.mac_ver(),
            'observations': result['faces'], 'error': result.get('error'),
            'warning': 'No detected face does not mean no person is present. Identities were not compared.'}

class FeatureCache:
    """Successful component results survive interrupted runs; no source paths stored."""
    def __init__(self, root):
        self.path = root / 'feature-cache.sqlite3'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS features (key TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.path.chmod(0o600)

    def get_or_compute(self, preview_hash, component, identity, compute):
        key = hashlib.sha256(json.dumps([preview_hash, component, identity], sort_keys=True).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT body FROM features WHERE key=?', (key,)).fetchone()
        if row:
            return json.loads(row[0])
        value = compute()
        # A failed detection is not evidence and must be retryable.
        if isinstance(value, dict) and value.get('error'):
            return value
        encoded = json.dumps(value, allow_nan=False)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO features VALUES (?, ?)', (key, encoded))
        return value


def comparison_suggestions(records):
    """Nearest visual neighbors for manual comparison, never equivalence groups.

    Blocked numpy multiplication bounds temporary memory; no model download.
    At most one neighbor per image, with symmetric pairs deduplicated.
    """
    vectors = [(pid, record.get('embedding')) for pid, record in records.items() if record.get('embedding')]
    if len(vectors) < 2:
        return []
    import numpy as np
    matrix = np.asarray([v for _, v in vectors], dtype=np.float32)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError('Invalid embeddings')
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if (norms == 0).any():
        raise ValueError('Zero embedding')
    matrix = matrix / norms
    pairs = {}
    for start in range(0, len(vectors), 128):
        scores = matrix[start:start + 128] @ matrix.T
        for offset, row in enumerate(scores):
            i = start + offset
            row[i] = -np.inf
            j = int(np.argmax(row))
            a, b = sorted((vectors[i][0], vectors[j][0]))
            pairs[(a, b)] = {'photo_id': a, 'other_photo_id': b,
                            'cosine_similarity': float(np.clip(row[j], -1, 1)),
                            'reason': 'Nearby in visual space: comparison suggested, equivalence not established.'}
    return sorted(pairs.values(), key=lambda pair: (-pair['cosine_similarity'], pair['photo_id'], pair['other_photo_id']))


def extract(store, sid, encoder=None, vision_tool=None, *, job_revision=None):
    service = store.get(sid)
    expected_status = 'analyzing' if job_revision is not None else 'ready'
    if job_revision is not None:
        store.check_revision(service, job_revision)
    if service['status'] != expected_status or service.get('archived'):
        raise ValueError('Service not ready')
    revision = service['revision']
    records = {}
    cache = FeatureCache(store.root)
    vision_identity = None
    if vision_tool:
        vision_identity = {'binary_sha256': hashlib.sha256(Path(vision_tool).read_bytes()).hexdigest(),
                           'os': platform.mac_ver(), 'adapter': 'apple-vision-rectangles-v1'}
    for photo in service['photos']:
        if not photo['preview_ready']:
            records[photo['id']] = {'error': 'Missing preview'}
            continue
        path = store.preview_path(sid, photo['id'])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != photo['preview_sha256']:
            raise ValueError('Preview changed: import again before analysis')
        record = {'preview_sha256': digest}
        if encoder:
            record['embedding'] = cache.get_or_compute(digest, 'embedding', encoder.identity, lambda: encoder.encode(path))
        if vision_tool:
            record['faces'] = cache.get_or_compute(digest, 'faces', vision_identity, lambda: face_rectangles(vision_tool, path))
        records[photo['id']] = record
    evidence = {'schema_version': 1, 'model': encoder.identity if encoder else None, 'records': records, 'comparisons': comparison_suggestions(records),
                'warning': 'Uncalibrated evidence: no photos automatically excluded based on these signals.'}
    with store.transaction() as db:
        latest = store.get(sid, db)
        store.check_revision(latest, revision)
        if latest['status'] != expected_status:
            raise ValueError('Service busy: extraction not applied')
        latest['interpretations'] = evidence
        latest.pop('confirmed_batch_id', None)
        if job_revision is not None:
            latest['status'] = 'ready'
            latest['job'] = {'kind': 'features', 'status': 'completed', 'completed': len(records), 'total': len(records), 'error': None}
        latest['revision'] += 1
        store.put(db, latest)
    return evidence

def main():
    parser = argparse.ArgumentParser(description='Extracts local signals only from previously imported previews; no downloads')
    parser.add_argument('--data-dir', required=True, type=Path)
    parser.add_argument('--service-id', required=True)
    parser.add_argument('--siglip-dir', type=Path)
    parser.add_argument('--vision-tool', type=Path)
    args = parser.parse_args()
    if not args.siglip_dir and not args.vision_tool:
        parser.error('Specify at least one local component')
    encoder = SiglipEncoder(args.siglip_dir) if args.siglip_dir else None
    result = extract(Store(args.data_dir), args.service_id, encoder, args.vision_tool)
    print(f"Evidence saved for {len(result['records'])} photos; selection unchanged.")

if __name__ == '__main__':
    main()
