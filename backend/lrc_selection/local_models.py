"""Reviewed local model locations; importing this module performs no I/O."""
import json
import os
from pathlib import Path
import tempfile

DEFAULT_MODEL = 'Qwen3-VL-4B-Instruct-4bit'
MODELS = {
    DEFAULT_MODEL: {'repo': 'mlx-community/Qwen3-VL-4B-Instruct-4bit',
                    'revision': '2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b'},
    'Qwen3.5-9B-MLX-4bit': {'repo': 'mlx-community/Qwen3.5-9B-MLX-4bit',
                           'revision': '938d8919941c6e7efd3c7150eff7fe9d12afa631'},
}
SELECTION_FILE = 'local-model-selection.json'


def model_ready(path: Path) -> bool:
    """Check local configuration and all declared shards without loading weights."""
    try:
        config = json.loads((path / 'config.json').read_text())
        if not isinstance(config, dict) or not config:
            return False
        index = path / 'model.safetensors.index.json'
        if index.exists():
            weights = json.loads(index.read_text()).get('weight_map', {})
            if not isinstance(weights, dict) or not weights:
                return False
            names = set(weights.values())
            if any(not isinstance(name, str) or Path(name).name != name or not name.endswith('.safetensors') for name in names):
                return False
            files = [path / name for name in names]
        else:
            files = list(path.glob('*.safetensors'))
        return bool(files) and all(file.is_file() and file.stat().st_size > 0 for file in files)
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def resolve_model(data_dir: Path) -> Path | None:
    override = os.environ.get('LRC_VLM_DIR')
    if override is not None:
        path = Path(override)
    else:
        selection = data_dir / SELECTION_FILE
        model = DEFAULT_MODEL
        if selection.exists():
            try:
                value = json.loads(selection.read_text())
                if value.get('schema_version') != 1 or value.get('model') not in MODELS:
                    raise ValueError('Unsupported local model selection')
                model = value['model']
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                raise ValueError('Invalid local model configuration') from exc
        path = data_dir / 'models' / model
    return path if model_ready(path) else None


def activate_model(data_dir: Path, model: str) -> None:
    if model not in MODELS:
        raise ValueError('Unsupported local model')
    if not model_ready(data_dir / 'models' / model):
        raise ValueError('Local model configuration or weights missing or incomplete')
    data_dir.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=data_dir, prefix='.local-model-', delete=False) as file:
            temporary = Path(file.name)
            json.dump({'schema_version': 1, 'model': model}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, data_dir / SELECTION_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
