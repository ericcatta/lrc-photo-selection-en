"""Shared selection policy: requested content, representatives, balanced extras.

Groups describe review evidence, not certified identities or semantic equivalence.
The input ranking supplies photographic merit inside each group.
"""
import hashlib
import io
from collections import Counter, deque
import heapq
from PIL import Image, ImageOps, UnidentifiedImageError

SELECTION_POLICY = 'distinct-groups-balanced-rounds-v1'
GROUPING_POLICY = 'conservative-preview-similarity-v1'


def visual_signature(data):
    """Small deterministic descriptor of an already authorized derived preview."""
    import numpy as np
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert('RGB')
            ratio = image.width / image.height
            pixels = np.asarray(image.resize((16, 16), Image.Resampling.BILINEAR), dtype=np.uint8)
            grey = np.asarray(image.convert('L').resize((9, 8), Image.Resampling.BILINEAR), dtype=np.int16)
        bits = grey[:, 1:] > grey[:, :-1]
        dhash = sum(int(value) << index for index, value in enumerate(bits.flat))
        return {'version': GROUPING_POLICY, 'sha256': hashlib.sha256(data).hexdigest(),
                'aspect': ratio, 'pixels': pixels.flatten().tolist(), 'dhash': f'{dhash:016x}'}
    except (OSError, ValueError, UnidentifiedImageError):
        return None


def group_visual_neighbors(ordered_ids, signatures, vectors=None):
    """Complete-link grouping prevents similarity chains merging distinct scenes.

    Exact previews group directly. Otherwise require matching framing, very close
    thumbnail pixels and dHash, plus high embedding agreement when supplied.
    Missing/low-detail evidence remains separate, never a scene-label merge.
    """
    import numpy as np
    vectors = vectors or {}
    prepared = {}
    for pid, signature in signatures.items():
        if not signature:
            continue
        pixels = np.asarray(signature['pixels'], dtype=float)
        if pixels.shape == (768,):
            prepared[pid] = (pixels, float(pixels.reshape(16, 16, 3).std(axis=(0,1)).mean()))
    def near(left, right):
        a, b = signatures.get(left), signatures.get(right)
        if not a or not b:
            return False
        if a.get('sha256') and a.get('sha256') == b.get('sha256'):
            return True
        if abs(a['aspect'] / b['aspect'] - 1) > .03:
            return False
        if left not in prepared or right not in prepared:
            return False
        x, x_variation = prepared[left]
        y, y_variation = prepared[right]
        # Spatial variation, not RGB channel differences: blue skies stay separate.
        if min(x_variation, y_variation) < 12:
            return False
        if left in vectors and right in vectors and float(np.dot(vectors[left], vectors[right])) < .985:
            return False
        if (int(a['dhash'],16) ^ int(b['dhash'],16)).bit_count() > 4 or np.sqrt(np.mean((x-y)**2)) / 255 > .06:
            return False
        return True
    groups = []
    for pid in dict.fromkeys(ordered_ids):
        group = next((g for g in groups if all(near(pid, other) for other in g['members'])), None)
        if group is None:
            groups.append({'id': 'visual-' + str(len(groups)), 'members': [pid],
                           'reason': 'Distinct visual group or equivalence not established.'})
        else:
            group['members'].append(pid)
            group['reason'] = 'Previews are very similar in framing, structure and color; review this group.'
    return groups


def select_with_category_coverage(ordered_ids, forced_ids, assessments, categories, target, groups=None):
    selected = list(dict.fromkeys(forced_ids))
    ordered = list(dict.fromkeys(pid for pid in ordered_ids if pid not in selected and assessments.get(pid, {}).get('match') == 'yes'))
    eligible_ids = list(dict.fromkeys(selected + ordered))
    eligible_set = set(eligible_ids)
    normalized, member_group = [], {}
    for group in groups or []:
        members = [pid for pid in group.get('members', []) if pid in eligible_set and pid not in member_group]
        if not members:
            continue
        index = len(normalized)
        normalized.append({'id': group.get('id', f'group-{index}'), 'members': members,
                           'reason': group.get('reason', 'Group requires review.')})
        member_group.update({pid: index for pid in members})
    for pid in eligible_ids:
        if pid not in member_group:
            member_group[pid] = len(normalized)
            normalized.append({'id': 'single-' + str(len(normalized)), 'members': [pid],
                               'reason': 'Equivalence not established: image retained as a separate group.'})
    group_map = {index: group for index, group in enumerate(normalized)}
    counts = Counter(member_group[pid] for pid in selected)
    rank = {pid: index for index, pid in enumerate(ordered)}
    def occupancy(pid):
        return counts[member_group[pid]]
    category_ids = [category['id'] for category in categories]
    def covers(pid, category_id):
        return assessments.get(pid, {}).get('category_matches', {}).get(category_id) == 'yes'
    uncovered = {cid for cid in category_ids if not any(covers(pid, cid) for pid in selected)}
    while uncovered:
        candidates = [pid for pid in ordered if any(covers(pid, cid) for cid in uncovered)]
        if not candidates:
            break
        chosen = min(candidates, key=lambda pid: (occupancy(pid), -sum(covers(pid,cid) for cid in uncovered), rank[pid]))
        selected.append(chosen)
        counts[member_group[chosen]] += 1
        ordered.remove(chosen)
        uncovered = {cid for cid in uncovered if not covers(chosen,cid)}
    # Heap heads give one representative per group, then balanced extra rounds.
    queues = {}
    for pid in ordered:
        queues.setdefault(member_group[pid], deque()).append(pid)
    heads = [(counts[group], rank[queue[0]], group) for group, queue in queues.items()]
    heapq.heapify(heads)
    while heads:
        count, _, group = heapq.heappop(heads)
        if count > 0 and len(selected) >= target:
            break
        pid = queues[group].popleft()
        selected.append(pid)
        counts[group] += 1
        if queues[group]:
            heapq.heappush(heads, (counts[group], rank[queues[group][0]], group))
    coverage, warnings = [], []
    eligible = set(ordered_ids) | set(forced_ids)
    for category in categories:
        cid, description = category['id'], category['description']
        representatives = [pid for pid in selected if covers(pid, cid)]
        recognized = [pid for pid, a in assessments.items() if a.get('match') == 'yes' and covers(pid, cid)]
        available = [pid for pid in recognized if pid in eligible]
        uncertain = [pid for pid, a in assessments.items()
                     if a.get('category_matches', {}).get(cid, 'uncertain') == 'uncertain']
        if representatives:
            status = 'represented'
        elif recognized and not available:
            status = 'manual-excluded'
            warnings.append(f'Requested category “{description}” not represented: matching images were excluded by manual decisions.')
        elif not assessments:
            status = 'not-assessed'
            warnings.append(f'Requested category “{description}” not assessed: analysis was not performed.')
        elif uncertain:
            status = 'uncertain'
            warnings.append(f'Requested category “{description}” unconfirmed: uncertain assessments require review, without automatic substitution.')
        else:
            status = 'not-detected'
            warnings.append(f'Requested category “{description}”: no suitable match detected; this does not prove absence from the service.')
        coverage.append({'id': cid, 'description': description, 'selected_ids': representatives,
                         'eligible_count': len(available), 'uncertain_count': len(uncertain), 'status': status})
    if len(selected) > target:
        warnings.append('Indicative quantity exceeded to preserve distinct groups, requested categories or manual decisions: review the trade-off before confirming.')
    if len(selected) > target and len(group_map) > target:
        warnings.append('Indicative quantity exceeded to retain one representative of every distinct visual group; no situation is excluded solely to meet the number.')
    return {'shortlist': selected, 'coverage': coverage, 'warnings': warnings,
            'selection_groups': normalized, 'selection_policy': SELECTION_POLICY}
