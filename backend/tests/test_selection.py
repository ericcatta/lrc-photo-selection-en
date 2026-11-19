"""Synthetic group evidence and balanced-round selection, without models/photos."""
import io
from copy import deepcopy

import numpy as np
from PIL import Image

from lrc_selection.selection import (group_visual_neighbors, select_with_category_coverage,
                                     visual_signature, SELECTION_POLICY)


def signature(offset=0, *, uniform=False):
    if uniform:
        image = Image.new('RGB', (32, 32), (0, 40 + offset, 200))
    else:
        texture = np.indices((32, 32)).sum(axis=0) % 2 * 140 + 30 + offset
        image = Image.fromarray(np.repeat(texture[:, :, None], 3, axis=2).astype('uint8'))
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    return visual_signature(stream.getvalue())


def assessments(ids):
    return {pid: {'match': 'yes', 'category_matches': {}} for pid in ids}


def test_all_group_representatives_precede_second_and_third_variants():
    order = ['a1','a2','a3','b1','b2','b3','c1','c2','c3']
    groups = [{'members': [prefix + str(n) for n in (1,2,3)]} for prefix in 'abc']
    actual = select_with_category_coverage(order, [], assessments(order), [], 8, groups)
    assert actual['shortlist'] == ['a1','b1','c1','a2','b2','c2','a3','b3']
    assert actual['selection_policy'] == SELECTION_POLICY
    assert select_with_category_coverage(order, [], assessments(order), [], 2, groups)['shortlist'] == ['a1','b1','c1']


def test_manual_choices_count_against_groups_and_categories_still_survive():
    order = ['a1','a2','a3','b1','b2','b3','c1']
    groups = [{'members': ['a1','a2','a3']}, {'members': ['b1','b2','b3']}, {'members': ['c1']}]
    data = assessments(order)
    data['b3']['category_matches'] = {'portrait':'yes'}
    actual = select_with_category_coverage(order, ['a1','a2'], data, [{'id':'portrait','description':'Ritratto'}], 6, groups)
    assert actual['shortlist'] == ['a1','a2','b3','c1','b1','a3']
    assert actual['coverage'][0]['selected_ids'] == ['b3']
    assert 'b2' not in actual['shortlist']


def test_missing_evidence_never_merges_equal_scene_labels_or_truncates_uniques():
    data = {pid: {'match':'yes','scene':'uccelli','category_matches':{}} for pid in ['a','b','c']}
    groups = group_visual_neighbors(list(data), {})
    assert [g['members'] for g in groups] == [['a'],['b'],['c']]
    actual = select_with_category_coverage(list(data), [], data, [], 1, groups)
    assert actual['shortlist'] == ['a','b','c']
    assert any('Indicative quantity exceeded' in warning for warning in actual['warnings'])


def test_uniform_colored_sky_and_tiny_subjects_stay_separate():
    a, b = signature(0, uniform=True), signature(1, uniform=True)
    assert len(group_visual_neighbors(['a','b'], {'a':a,'b':b})) == 2
    # Different tiny subjects against the same blue field cannot justify merging.
    signatures = {}
    for pid, x in [('a',5),('b',25)]:
        image = Image.new('RGB',(32,32),(0,40,200))
        image.putpixel((x,16),(0,0,0))
        stream = io.BytesIO(); image.save(stream,'PNG')
        signatures[pid] = visual_signature(stream.getvalue())
    assert len(group_visual_neighbors(['a','b'], signatures)) == 2


def test_grouping_requires_every_member_not_similarity_chaining():
    # Use textured pixels directly: offsets10 are near; offsets20 are not.
    base = signature()
    base['pixels'] = ([30,30,30,170,170,170] * 128)
    base['dhash'] = '123456789abcdef0'
    signatures = {}
    for index, pid in enumerate('abc'):
        signatures[pid] = dict(base, sha256=pid, pixels=[value + index*10 for value in base['pixels']])
    before = deepcopy(signatures)
    groups = group_visual_neighbors(['a','b','c'], signatures)
    assert [group['members'] for group in groups] == [['a','b'],['c']]
    assert signatures == before


def test_conflicting_embeddings_prevent_near_variant_merge_but_exact_hash_is_evidence():
    a = signature(); a['pixels'] = [30,30,30,170,170,170] * 128
    b = dict(a, sha256='other', pixels=[v + 1 for v in a['pixels']])
    groups = group_visual_neighbors(['a','b'], {'a':a,'b':b}, {'a':np.array([1.,0.]),'b':np.array([0.,1.])})
    assert len(groups) == 2
    assert len(group_visual_neighbors(['a','b'], {'a':a,'b':dict(a)})) == 1


def test_local_valid_jpegs_choose_best_variant_then_every_distinct_context(tmp_path):
    import hashlib
    from lrc_selection.store import Store
    from lrc_selection.semantic import rerank_instruction_shortlist
    from lrc_selection.vlm import proposal_from_assessments
    store = Store(tmp_path)
    (tmp_path/'previews').mkdir()
    photos, signatures, vectors, records = [], {}, {}, {}
    assessments = {}
    for index in range(4):
        y, x = np.indices((64,64))
        pixels = ((x//8)%2)*140+40 if index < 2 else (((y if index==2 else x+y)//8)%2)*140+40
        pixels = pixels + (index if index < 2 else 0)
        image = Image.fromarray(np.repeat(pixels[:,:,None],3,axis=2).astype('uint8'))
        stream = io.BytesIO(); image.save(stream,'JPEG',quality=95)
        data = stream.getvalue(); pid = str(index)
        digest = hashlib.sha256(data).hexdigest()
        store.preview_path('synthetic',pid).write_bytes(data)
        photos.append({'id':pid,'preview_ready':True,'preview_sha256':digest})
        signatures[pid] = visual_signature(data)
        vectors[digest] = [1.,0.,0.] if index < 2 else ([0.,1.,0.] if index==2 else [0.,0.,1.])
        assessments[pid] = {'match':'yes','reason':'Evidenza sintetica','scene':'stessa etichetta generica',
                            'quality_issues':['Leggero mosso'] if index==1 else [],
                            'preference_score':[.8,.95,.6,.4][index], 'category_matches':{}}
        records[pid] = {'assessment':assessments[pid], 'visual_signature':signatures[pid]}
    snapshot = {'id':'synthetic','photos':photos,'settings':{'target':2,'instructions':'Migliori, varietà'},'decisions':{}}
    interpretation = {'requested_categories':[],'ambiguities':[],'unsupported':[]}
    initial = proposal_from_assessments(snapshot,interpretation,assessments,{'synthetic':True},records)
    assert initial['shortlist'] == ['1','2','3']  # unique contexts exceed soft target
    assert initial['selection_groups'][0]['members'] == ['1','0']
    class Encoder:
        identity = {'synthetic':'valid-jpeg-grouping'}
        def encode(self,path): return vectors[hashlib.sha256(path.read_bytes()).hexdigest()]
    ranked = rerank_instruction_shortlist(initial,snapshot,store,Encoder())
    assert ranked['shortlist'] == ['1','2','3']
    assert 'Alternative' in ranked['shortlist_reasons']['0']
    snapshot['settings']['target'] = 4
    assert rerank_instruction_shortlist(initial,snapshot,store,Encoder())['shortlist'] == ['1','2','3','0']
