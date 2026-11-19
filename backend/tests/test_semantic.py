"""Semantic policy checks with synthetic vectors and bytes, no downloaded model."""
import copy
import hashlib

import pytest

from lrc_selection.semantic import build_semantic_proposal
from lrc_selection.store import Store


class Encoder:
    identity = {'adapter': 'synthetic-semantic-v1'}
    def __init__(self):
        self.image_calls, self.text_calls = [], []
    def encode(self, path):
        name = path.read_bytes().decode()
        self.image_calls.append(name)
        return {'bird': [1., 0., 0.], 'bird2': [.99, .01, 0.],
                'person': [0., 1., 0.], 'snow': [0., 0., 1.]}[name]
    def encode_text(self, text):
        self.text_calls.append(text)
        return {'uccelli': [1., 0., 0.], 'persone': [0., 1., 0.]}[text]


def fixture(tmp_path):
    store = Store(tmp_path)
    (tmp_path / 'previews').mkdir()
    photos = []
    for index, name in enumerate(['bird', 'bird2', 'person', 'snow']):
        data = name.encode()
        pid = str(index)
        store.preview_path('synthetic', pid).write_bytes(data)
        photos.append({'id': pid, 'preview_ready': True, 'preview_sha256': hashlib.sha256(data).hexdigest()})
    snapshot = {'id': 'synthetic', 'photos': photos, 'settings': {'target': 2, 'subject_query': 'uccelli'}, 'decisions': {}}
    return store, snapshot, Encoder()


def test_subject_query_retrieval_cache_and_no_mutation(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    original = copy.deepcopy(snapshot)
    progress = []
    result = build_semantic_proposal(store, snapshot, encoder, lambda n, total: progress.append((n, total)))
    assert result['shortlist'] == ['0', '1', '2', '3']
    assert result['query_scores']['0'] > result['query_scores']['2']
    assert len(result['shortlist_reasons']) == 4
    assert snapshot == original
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]
    snapshot['settings']['subject_query'] = 'persone'
    result = build_semantic_proposal(store, snapshot, encoder)
    assert result['shortlist'][0] == '2'
    assert len(encoder.image_calls) == 4
    assert encoder.text_calls == ['uccelli', 'persone']
    build_semantic_proposal(store, snapshot, encoder)
    assert encoder.text_calls == ['uccelli', 'persone']


def test_diversity_and_manual_precedence(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    snapshot['settings']['subject_query'] = ''
    assert build_semantic_proposal(store, snapshot, encoder)['shortlist'] == ['0', '1', '2', '3']
    snapshot['decisions'] = {'0': {'state': 'excluded', 'locked': True},
                             '1': {'state': 'alternative'},
                             '3': {'state': 'preferred', 'locked': True}}
    result = build_semantic_proposal(store, snapshot, encoder)
    assert result['shortlist'] == ['3', '2']
    snapshot['settings']['target'] = 1
    snapshot['decisions']['2'] = {'state': 'candidate'}
    result = build_semantic_proposal(store, snapshot, encoder)
    assert set(result['shortlist']) == {'2', '3'}
    assert any('manual decisions' in warning for warning in result['warnings'])


def test_missing_previews_preserved_and_hash_checked(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    snapshot['photos'][0]['preview_ready'] = False
    snapshot['decisions']['0'] = {'state': 'review', 'locked': True}
    result = build_semantic_proposal(store, snapshot, encoder)
    assert result['shortlist'][0] == '0'
    assert result['interpretations']['records']['0']['error'] == 'Missing preview'
    assert '0' not in result['query_scores']
    assert len(encoder.image_calls) == 3
    store.preview_path('synthetic', '1').write_bytes(b'changed')
    with pytest.raises(ValueError, match='Preview changed'):
        build_semantic_proposal(store, snapshot, encoder)


def test_interruption_reuses_successful_image_cache(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    def interrupt(n, total):
        if n == 2:
            raise RuntimeError('synthetic interruption')
    with pytest.raises(RuntimeError):
        build_semantic_proposal(store, snapshot, encoder, interrupt)
    result = build_semantic_proposal(store, snapshot, encoder)
    assert len(encoder.image_calls) == 4
    assert len(result['shortlist']) == 4


def test_invalid_vector_fails_without_pretending_selection(tmp_path):
    store, snapshot, encoder = fixture(tmp_path)
    encoder.encode = lambda path: [float('nan'), 1.]
    with pytest.raises(ValueError):
        build_semantic_proposal(store, snapshot, encoder)


def instruction_result(matches=('0','1','2','3')):
    return {'shortlist':list(matches[:2]),'shortlist_reasons':{},'warnings':[], 'method':{},
            'assessments':{str(i):{'match':'yes' if str(i) in matches else 'no',
                                 'reason':'synthetic visible evidence','preference_score':.5} for i in range(4)},
            'interpretations':{'records':{}}, 'blocked':False}


def test_instruction_grouping_without_image_evidence_keeps_distinct_inputs(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    result=instruction_result()
    original=copy.deepcopy(result)
    reranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert reranked['shortlist']==['0','1','2','3']
    assert result==original
    assert all(a['match']=='yes' for a in reranked['assessments'].values())
    assert reranked['method']['novelty_weight']==0.
    assert 'embedding' in reranked['interpretations']['records']['0']
    rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert len(encoder.image_calls)==4


def test_instruction_diversity_preserves_forced_decisions_and_never_fills(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    snapshot['decisions']={'3':{'state':'preferred','locked':True},'0':{'state':'excluded','locked':True}}
    result=instruction_result(matches=('0','1','2'))
    reranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert reranked['shortlist']==['3','1','2']
    snapshot['settings']['target']=4
    result=instruction_result(matches=())
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)['shortlist']==['3']
    snapshot['decisions']={}
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)['shortlist']==[]


def test_instruction_preference_can_outweigh_small_diversity_difference(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    result=instruction_result()
    result['assessments']['0']['preference_score']=1.
    result['assessments']['1']['preference_score']=.99
    result['assessments']['2']['preference_score']=.1
    result['assessments']['3']['preference_score']=.1
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)['shortlist']==['0','1','2','3']
    result['blocked']=True
    encoder.encode=lambda path: pytest.fail('blocked instruction must not encode')
    assert rerank_instruction_shortlist(result,snapshot,store,encoder)==result


def test_category_coverage_survives_embedding_rerank_and_prefers_requested_people(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    categories=[{'id':'birds','description':'Uccelli'},{'id':'portraits','description':'Portraits of people'}]
    result=instruction_result()
    result['instruction_interpretation']={'requested_categories':categories}
    for pid,assessment in result['assessments'].items():
        assessment['category_matches']={'birds':'yes' if pid in ('0','1') else 'no',
                                        'portraits':'yes' if pid=='2' else 'no'}
        assessment['preference_score']=1. if pid in ('0','1') else .1
    reranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert reranked['shortlist']==['0','2','1','3']
    assert all(category['status']=='represented' for category in reranked['coverage'])
    snapshot['decisions']={'2':{'state':'excluded','locked':True}}
    reranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert '2' not in reranked['shortlist']
    assert reranked['coverage'][1]['status']=='manual-excluded'
    assert any('manual decisions' in w for w in reranked['warnings'])


def test_category_uncertainty_not_absence_or_filler_and_multicategory_image():
    from lrc_selection.semantic import select_with_category_coverage
    categories=[{'id':'birds','description':'Uccelli'},{'id':'portraits','description':'Ritratti'}]
    assessments={'a':{'match':'yes','category_matches':{'birds':'yes','portraits':'yes'}},
                 'b':{'match':'uncertain','category_matches':{'birds':'no','portraits':'uncertain'}}}
    result=select_with_category_coverage(['a'],[],assessments,categories,1)
    assert result['shortlist']==['a']
    assert all(c['status']=='represented' for c in result['coverage'])
    assessments['a']['category_matches']['portraits']='no'
    result=select_with_category_coverage(['a'],[],assessments,categories,2)
    assert result['shortlist']==['a']
    assert result['coverage'][1]['status']=='uncertain'
    assert any('uncertain assessments' in w for w in result['warnings'])


def test_technical_annotations_cannot_replace_last_requested_portrait(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist
    store,snapshot,encoder=fixture(tmp_path)
    result=instruction_result(matches=('0','1','2'))
    result['instruction_interpretation']={'requested_categories':[
        {'id':'birds','description':'Uccelli'},{'id':'portraits','description':'Portraits of people'}]}
    for pid,assessment in result['assessments'].items():
        assessment['category_matches']={'birds':'yes' if pid in ('0','1') else 'no',
                                        'portraits':'yes' if pid=='2' else 'no'}
        assessment['quality_issues']=['Leggero mosso'] if pid=='2' else []
    first=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert first['shortlist']==['0','2','1']
    result['assessments']['2']['quality_issues']=['Forte mosso', 'Rumore', 'Messa a fuoco incerta']
    second=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert second['shortlist']==first['shortlist']
    assert all(category['status']=='represented' for category in second['coverage'])


def test_local_uncertainty_retention_survives_siglip_rerank_without_fabricating_coverage(tmp_path):
    from lrc_selection.semantic import rerank_instruction_shortlist, LOCAL_UNCERTAINTY_POLICY
    store,snapshot,encoder=fixture(tmp_path)
    snapshot['settings']['target']=1
    result=instruction_result(matches=('0','1'))
    result['method']['uncertainty_policy']=LOCAL_UNCERTAINTY_POLICY
    result['instruction_interpretation']={'requested_categories':[{'id':'subject','description':'Subject'}]}
    for pid,a in result['assessments'].items():
        a['category_matches']={'subject':'yes'}
    result['assessments']['2']['match']='uncertain'
    result['assessments']['3'].update(match='uncertain',error='Invalid response')
    result['review_ids']=['2','3']
    result['shortlist']=['0','2','3']
    result['shortlist_reasons']={'2':'Da rivedere: synthetic uncertainty','3':'Da rivedere: synthetic error'}
    ranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert ranked['shortlist']==['0','1','2','3'] and ranked['review_ids']==['2','3']
    assert ranked['coverage'][0]['selected_ids']==['0','1']
    assert ranked['shortlist_reasons']['2']=='Da rivedere: synthetic uncertainty'
    assert len(encoder.image_calls)==2  # review-only images never treated as ranking evidence
    snapshot['decisions']={'2':{'state':'excluded','locked':True},'3':{'state':'alternative','locked':True}}
    ranked=rerank_instruction_shortlist(result,snapshot,store,encoder)
    assert ranked['shortlist']==['0','1'] and ranked['review_ids']==[]


def test_shared_api_category_selector_keeps_existing_unknown_behavior():
    from lrc_selection.semantic import select_with_category_coverage
    assessments={'yes':{'match':'yes','category_matches':{'subject':'yes'}},
                 'unknown':{'match':'uncertain','category_matches':{'subject':'uncertain'}}}
    result=select_with_category_coverage(['yes','unknown'],[],assessments,
                                        [{'id':'subject','description':'Subject'}],2)
    assert result['shortlist']==['yes']
    assert 'review_ids' not in result
