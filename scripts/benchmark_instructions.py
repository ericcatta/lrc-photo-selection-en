"""Run only on an explicitly authorized imported service; never change decisions."""
import argparse
import collections
import json
import time
from copy import deepcopy
from pathlib import Path

from lrc_selection.store import Store
from lrc_selection.vlm import LocalVLM, build_instruction_proposal


def main():
    parser = argparse.ArgumentParser(description='Local benchmark using only imported previews')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / 'Library/Application Support/LrC Photo Selection EN')
    parser.add_argument('--service-id', required=True)
    parser.add_argument('--instructions-file', type=Path, help='Separate test: exact file text, without modifying the service')
    parser.add_argument('--without-preset', action='store_true')
    parser.add_argument('--target', type=int)
    parser.add_argument('--diversity', action='store_true')
    args = parser.parse_args()
    store = Store(args.data_dir)
    snapshot = deepcopy(store.get(args.service_id))
    if args.instructions_file:
        snapshot['settings']['instructions'] = args.instructions_file.read_text()
    if args.without_preset:
        snapshot['settings'].update(service_criteria=[], subject_query='')
    if args.target is not None:
        if not 1 <= args.target <= len(snapshot['photos']):
            parser.error('Invalid quantity')
        snapshot['settings']['target'] = args.target
    start = time.monotonic()
    vlm = LocalVLM(args.data_dir / 'models/Qwen3-VL-4B-Instruct-4bit')
    def progress(done, total):
        if done % 10 == 0 or done == total:
            print(f'{done}/{total} — {time.monotonic()-start:.1f}s', flush=True)
    result = build_instruction_proposal(store, snapshot, vlm, progress)
    if args.diversity:
        from lrc_selection.features import SiglipEncoder
        from lrc_selection.semantic import rerank_instruction_shortlist
        encoder = SiglipEncoder(args.data_dir / 'models/siglip2-base-patch16-224')
        result = rerank_instruction_shortlist(result, snapshot, store, encoder)
    report = {'service_id': args.service_id, 'settings': snapshot['settings'],
              'seconds': time.monotonic()-start, 'result': result}
    output = args.data_dir / 'benchmarks' / f'{int(time.time())}.json'
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False))
    output.chmod(0o600)
    print(json.dumps({'assessments': dict(collections.Counter(a['match'] for a in result['assessments'].values())),
                      'shortlist': len(result['shortlist']), 'seconds': report['seconds'], 'report': str(output)}))


if __name__ == '__main__':
    main()
