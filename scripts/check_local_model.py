"""Offline adapter smoke check on generated shapes, never user photographs.

This checks compatibility/format/basic vision only, not photographic merit.
"""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

from PIL import Image, ImageDraw
from lrc_selection.vlm import LocalVLM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    model = LocalVLM(args.model_dir)
    loaded = time.monotonic()
    results, contexts = [], {}
    for name, text, count, mode in [
        ('plain', 'birds, portraits, landscapes', 3, 'any'),
        ('or', 'circles, squares', 2, 'any'),
        ('cooccur', 'A red circle and a blue square together in the same image', 2, 'all'),
    ]:
        begin = time.monotonic()
        value = model.interpret(text, [])
        passed = (len(value['requested_categories']) == count and value['category_mode'] == mode
                  and not (value['ambiguities'] or value['unsupported']))
        results.append({'kind': 'interpretation', 'name': name, 'instructions': text,
                        'seconds': time.monotonic() - begin, 'result': value, 'passed': passed})
        contexts[name] = value | {'original_instructions': text, 'original_criteria': [],
                                  'original_subject_query': ''}
        print(json.dumps({'check': name, 'passed': passed}), flush=True)
    with tempfile.TemporaryDirectory(prefix='lrc-synthetic-model-') as directory:
        for mode in ['or', 'cooccur']:
            for shape in ['red_circle', 'blue_square', 'both', 'blank']:
                preview = Image.new('RGB', (448, 448), 'white')
                draw = ImageDraw.Draw(preview)
                if shape == 'red_circle':
                    draw.ellipse((100, 100, 348, 348), fill='red')
                elif shape == 'blue_square':
                    draw.rectangle((100, 100, 348, 348), fill='blue')
                elif shape == 'both':
                    draw.ellipse((30, 130, 190, 290), fill='red')
                    draw.rectangle((260, 130, 420, 290), fill='blue')
                path = Path(directory) / (shape + '.png')
                preview.save(path)
                begin = time.monotonic()
                try:
                    value, error = model.assess(path, contexts[mode]), None
                except Exception as exc:
                    value, error = None, type(exc).__name__ + ': ' + str(exc)
                expected = 'yes' if (shape != 'blank' if mode == 'or' else shape == 'both') else 'no'
                passed = value is not None and value['match'] == expected
                results.append({'kind': 'synthetic_image', 'mode': mode, 'fixture': shape,
                                'seconds': time.monotonic() - begin, 'result': value,
                                'error': error, 'expected': expected, 'passed': passed})
                print(json.dumps({'check': mode + '/' + shape, 'passed': passed}), flush=True)
    import mlx.core as mx
    report = {'synthetic_only': True, 'photo_quality_validated': False,
              'model_directory': args.model_dir.name, 'prompt_revision': model.identity['adapter'],
              'runtime': model.identity['mlx_vlm'], 'load_seconds': loaded - started,
              'peak_memory_bytes': mx.get_peak_memory(),
              'seconds': time.monotonic() - started, 'checks': results,
              'passed': all(row['passed'] for row in results)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
