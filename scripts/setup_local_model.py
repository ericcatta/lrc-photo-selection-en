"""Explicit download step; application inference never downloads models."""
import argparse
import json
import os
from pathlib import Path
import sys

# Permit direct execution from a source checkout without installing the backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from lrc_selection.local_models import DEFAULT_MODEL, MODELS, activate_model, model_ready

REPO = MODELS[DEFAULT_MODEL]['repo']
REVISION = MODELS[DEFAULT_MODEL]['revision']


def main(argv=None):
    parser = argparse.ArgumentParser(description='Download a local vision model; no photographs are sent')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / 'Library/Application Support/LrC Photo Selection EN')
    parser.add_argument('--model', choices=tuple(MODELS), default=DEFAULT_MODEL)
    parser.add_argument('--activate', action='store_true', help='Explicitly select the model after verifying its files')
    args = parser.parse_args(argv)
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from huggingface_hub import snapshot_download
    spec = MODELS[args.model]
    target = args.data_dir / 'models' / args.model
    snapshot_download(spec['repo'], revision=spec['revision'], local_dir=target,
                      allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja', '*.model', 'README.md', 'LICENSE*'])
    if not model_ready(target):
        raise ValueError('Local model configuration or weights are missing or incomplete')
    (target / 'provenance.json').write_text(json.dumps({**spec, 'license': 'Apache-2.0'}))
    if args.activate:
        activate_model(args.data_dir, args.model)
    print('Local model available. No analysis was started.')


if __name__ == '__main__':
    main()
