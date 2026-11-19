"""Conservative baseline: only byte-identical derived previews are equivalent.

No claim of scene/person recognition. Without calibrated evidence, every distinct
preview is kept. Optional embedding extraction is separate from selection policy.
"""
from collections import defaultdict

SELECTED = {'candidate', 'preferred', 'review'}

def effective_selected(service):
    selected = set(service['proposal']['selected']) if service.get('proposal') else {p['id'] for p in service['photos']}
    if service.get('proposal'):
        selected.update(service['proposal'].get('added_candidates', ()))
    for pid, decision in service['decisions'].items():
        if decision['state'] in SELECTED:
            selected.add(pid)
        else:
            selected.discard(pid)
    return [p['id'] for p in service['photos'] if p['id'] in selected]

def effective_shortlist(service):
    """Review proposal with explicit manual choices taking precedence."""
    proposal = service.get('proposal') or {}
    selected = set(proposal.get('shortlist', []))
    for pid, decision in service.get('decisions', {}).items():
        if decision['state'] in SELECTED:
            selected.add(pid)
        else:
            selected.discard(pid)
    return [photo['id'] for photo in service['photos'] if photo['id'] in selected]


def analyze(service):
    buckets = defaultdict(list)
    for photo in service['photos']:
        # Missing previews must never become evidence for equivalence.
        key = photo.get('preview_sha256') or ('missing:' + photo['id'])
        buckets[key].append(photo['id'])
    groups, selected, reasons = [], [], {}
    for i, members in enumerate(buckets.values()):
        positive = [p for p in members if service['decisions'].get(p, {}).get('state') in SELECTED]
        allowed = [p for p in members if service['decisions'].get(p, {}).get('state') not in {'excluded', 'alternative'}]
        rep = (positive or allowed or members)[0]
        reason = ('Byte-identical JPEG previews; equivalence of visible content, not of the originals.'
                  if len(members) > 1 else 'No equivalence established: image retained.')
        groups.append({'id': f'exact-{i}', 'members': members, 'representative': rep, 'reason': reason,
                       'kind': 'preview-equivalence', 'confidence': 'exact-preview' if len(members) > 1 else 'unknown'})
        if allowed:
            selected.append(rep)
        for pid in members:
            reasons[pid] = reason
    target = service['settings']['target']
    from .selection import select_with_category_coverage
    allowed = [photo['id'] for photo in service['photos']
               if service['decisions'].get(photo['id'], {}).get('state') not in {'excluded', 'alternative'}]
    forced = [pid for pid in allowed if service['decisions'].get(pid, {}).get('state') in SELECTED]
    balanced = select_with_category_coverage(allowed, forced,
        {pid: {'match': 'yes', 'category_matches': {}} for pid in allowed}, [], target, groups=groups)
    selected = balanced['shortlist']
    for group in groups:
        chosen = [pid for pid in selected if pid in group['members']]
        for pid in chosen[1:]:
            if pid not in forced:
                reasons[pid] = 'Variation added by distributing alternatives across groups to reach the requested quantity.'
    proposal = {'selected': selected, 'groups': groups, 'reasons': reasons,
                'warnings': ['The baseline engine recognizes only identical previews; scenes, people and poses have not been recognized.'],
                'engine': 'exact-preview-v1', 'selection_policy': balanced['selection_policy'],
                'selection_groups': balanced['selection_groups']}
    working = dict(service, proposal=proposal)
    proposal['selected'] = effective_selected(working)
    if len(proposal['selected']) < target:
        proposal['warnings'].append('Target cannot be reached without changing manual decisions: review required.')
    if len(proposal['selected']) > target:
        proposal['warnings'].append('Target exceeded: insufficient evidence to safely reduce further images.')
    for g in groups:
        if not set(g['members']) & set(proposal['selected']):
            proposal['warnings'].append('A group has no candidates because of manual decisions.')
    return proposal
