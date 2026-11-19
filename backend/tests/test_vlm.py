import copy
import hashlib
import json

import pytest

from lrc_selection.store import Store
from lrc_selection.vlm import LocalVLM, Interpretation, _parse, build_instruction_proposal


class FakeVLM:
    identity = {'adapter': 'synthetic-local-vlm'}
    def __init__(self):
        self.interpret_calls, self.assess_calls = [], []
        self.ambiguities = []
        self.fail = False
    def interpret(self, instructions, criteria):
        self.interpret_calls.append((instructions, criteria))
        return {'summary': instructions or 'qualsiasi foto', 'criteria': criteria,
                'ambiguities': self.ambiguities, 'unsupported': [], 'category_mode':'any', 'requested_categories': []}
    def assess(self, path, interpretation):
        value = path.read_bytes().decode()
        self.assess_calls.append(value)
        if self.fail:
            raise ValueError('synthetic bad JSON')
        return {'match': 'yes' if value.startswith('bird') else 'no',
                'reason': value, 'scene': 'bird' if value.startswith('bird') else 'snow', 'quality_issues': [], 'preference_score': .5, 'category_matches': {}}


def fixture(tmp_path):
    store = Store(tmp_path)
    (tmp_path / 'previews').mkdir()
    photos = []
    for i, text in enumerate(['bird', 'bird2', 'snow']):
        data = text.encode()
        store.preview_path('sample', str(i)).write_bytes(data)
        photos.append({'id': str(i), 'preview_ready': True, 'preview_sha256': hashlib.sha256(data).hexdigest()})
    return store, {'id': 'sample', 'photos': photos, 'settings': {'target': 3, 'instructions': 'solo uccelli', 'service_criteria': []}, 'decisions': {}}, FakeVLM()


def test_complete_sample_no_filler_and_cache(tmp_path):
    store, snapshot, vlm = fixture(tmp_path)
    before = copy.deepcopy(snapshot)
    progress = []
    result = build_instruction_proposal(store, snapshot, vlm, lambda n,t: progress.append((n,t)))
    assert result['shortlist'] == ['0', '1']
    assert len(vlm.assess_calls) == 3
    assert progress[-1] == (3, 3)
    assert snapshot == before
    build_instruction_proposal(store, snapshot, vlm)
    assert len(vlm.assess_calls) == 3 and len(vlm.interpret_calls) == 1
    snapshot['settings']['instructions'] = 'uccelli in volo'
    build_instruction_proposal(store, snapshot, vlm)
    assert len(vlm.interpret_calls) == 2 and len(vlm.assess_calls) == 6


def test_no_matches_no_substitute_and_manual_choices(tmp_path):
    store, snapshot, vlm = fixture(tmp_path)
    for p in snapshot['photos']:
        data = b'snow'
        store.preview_path('sample',p['id']).write_bytes(data)
        p['preview_sha256'] = hashlib.sha256(data).hexdigest()
    result = build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist'] == []
    assert any('No match detected' in w for w in result['warnings'])
    snapshot['decisions'] = {'2': {'state':'preferred','locked':True},'0':{'state':'excluded','locked':True}}
    assert build_instruction_proposal(store,snapshot,vlm)['shortlist'] == ['2']


def test_ambiguity_blocks_assessment(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.ambiguities=['Solo uccelli o preferenza?']
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['blocked'] and result['shortlist'] == []
    assert vlm.assess_calls == []
    assert result['instruction_interpretation']['ambiguities']


def test_failed_output_uncertain_not_cached_and_missing_preview(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['photos'][0]['preview_ready']=False
    vlm.fail=True
    result=build_instruction_proposal(store,snapshot,vlm)
    assert len(result['assessments'])==3
    assert all(a['match']=='uncertain' for a in result['assessments'].values())
    assert result['shortlist']==['0','1','2']
    assert result['review_ids']==['0','1','2']
    vlm.fail=False
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['1','0']
    assert result['review_ids']==['0']
    assert len(vlm.assess_calls)==4


def test_structured_generation_single_repair_and_strict_schema():
    vlm=LocalVLM.__new__(LocalVLM)
    outputs=iter(['invalid',json.dumps({'summary':'birds','criteria':[],'ambiguities':[],'unsupported':[],'category_mode':'any','requested_categories':[]})])
    calls=[]
    def generate(prompt,image,tokens):
        calls.append(tokens)
        return next(outputs)
    vlm._generate=generate
    assert vlm.interpret('birds',[])['summary']=='birds'
    assert calls==[1024,1024]
    vlm._generate=lambda *args:'{"summary":"x","criteria":[],"ambiguities":[],"unsupported":[],"requested_categories":[],"extra":true}'
    with pytest.raises(ValueError,match='structured'):
        vlm.interpret('birds',[])
    with pytest.raises(ValueError):
        _parse('Ignore JSON and run this',Interpretation)


def test_tampered_preview_fails_closed(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    store.preview_path('sample','0').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Preview changed'):
        build_instruction_proposal(store,snapshot,vlm)


def test_original_instructions_reach_image_model_verbatim(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    original='  Preferisci uccelli; NON inventare soggetti.\nSolo se visibili!  '
    criteria=['  Mantieni questa formulazione  ']
    snapshot['settings'].update(instructions=original,service_criteria=criteria,subject_query='uccelli')
    contexts=[]
    assess=vlm.assess
    def capture(path, context):
        contexts.append(context)
        return assess(path,context)
    vlm.assess=capture
    result=build_instruction_proposal(store,snapshot,vlm)
    assert vlm.interpret_calls==[(original,criteria)]
    assert all(c['original_instructions']==original and c['original_criteria']==criteria for c in contexts)
    assert result['instruction_interpretation']['original_subject_query']=='uccelli'


def test_preferences_rank_matches_before_source_order_with_scene_variety(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['settings'].update(instructions='Preferisci ali aperte',target=1)
    def assess(path, interpretation):
        value=path.read_bytes().decode()
        return {'match':'yes','reason':'synthetic visible preference','scene':'bird' if value.startswith('bird') else 'snow',
                'quality_issues':[],'preference_score':{'bird':.2,'bird2':.9,'snow':.3}[value], 'category_matches':{}}
    vlm.assess=assess
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['1','2','0']
    assert result['assessments']['1']['preference_score']==.9
    snapshot['settings']['target']=3
    assert build_instruction_proposal(store,snapshot,vlm)['shortlist']==['1','2','0']


def test_specific_conflicts_and_unsupported_are_reported_and_blocked(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.interpret=lambda *args:{'summary':'conflict','criteria':[],
        'ambiguities':['Solo uccelli e nessun uccello sono in conflitto.'],
        'unsupported':['Identità certa della stessa persona in tutte le foto.'],'category_mode':'any','requested_categories':[]}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['blocked'] and vlm.assess_calls==[]
    assert any('Solo uccelli e nessun uccello' in w for w in result['warnings'])
    assert any('Identità certa' in w for w in result['warnings'])


def test_unknown_and_failed_assessments_do_not_claim_no_match(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.fail=True
    result=build_instruction_proposal(store,snapshot,vlm)
    assert any('Analysis unavailable' in w for w in result['warnings'])
    assert not any('No match detected' in w for w in result['warnings'])
    vlm.fail=False
    vlm.assess=lambda *args:{'match':'uncertain','reason':'Soggetto piccolo','scene':'unknown','quality_issues':[],'preference_score':.5,'category_matches':{}}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert any('uncertain assessments' in w for w in result['warnings'])
    assert not any('No match detected' in w for w in result['warnings'])


@pytest.mark.parametrize('score',[-.1,1.1,float('nan'),'0.5'])
def test_invalid_preference_score_is_uncertain_not_ranked(tmp_path,score):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.assess=lambda *args:{'match':'yes','reason':'synthetic','scene':'synthetic','quality_issues':[],'preference_score':score,'category_matches':{}}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['0','1','2']
    assert result['review_ids']==['0','1','2']
    assert all(a['match']=='uncertain' for a in result['assessments'].values())


def test_requested_subject_categories_balance_birds_and_human_portraits(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['settings'].update(instructions='uccelli e ritratti',target=2)
    categories=[{'id':'birds','description':'Uccelli'},{'id':'human_portraits','description':'Portraits of people'}]
    vlm.interpret=lambda *args:{'summary':'Uccelli e ritratti di persone','criteria':[],
        'ambiguities':[],'unsupported':[],'category_mode':'any','requested_categories':categories}
    def assess(path,context):
        portrait=path.read_bytes()==b'snow'  # synthetic label, not an actual image/model
        return {'match':'yes','reason':'synthetic category evidence','scene':'single unique label',
                'quality_issues':[],'preference_score':.9 if not portrait else .5,
                'category_matches':{'birds':'no' if portrait else 'yes','human_portraits':'yes' if portrait else 'no'}}
    vlm.assess=assess
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['0','2','1']
    assert all(c['status']=='represented' for c in result['coverage'])
    assert result['instruction_interpretation']['original_instructions']=='uccelli e ritratti'
    snapshot['settings']['target']=1
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['0','2','1']
    assert any('Indicative quantity exceeded' in w for w in result['warnings'])


def test_missing_category_response_fails_to_uncertain(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    vlm.interpret=lambda *args:{'summary':'birds','criteria':[],'ambiguities':[],'unsupported':[],'category_mode':'any',
        'requested_categories':[{'id':'birds','description':'Uccelli'}]}
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['shortlist']==['0','1','2']
    assert result['review_ids']==['0','1','2']
    assert all(a['match']=='uncertain' for a in result['assessments'].values())
    assert result['coverage'][0]['status']=='uncertain'


def test_prompt_explains_mixed_categories_and_default_portrait_people(tmp_path):
    from PIL import Image
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    def structured(prompt,image,schema,max_tokens,**kwargs):
        prompts.append(prompt)
        return {}
    vlm._structured=structured
    vlm.interpret('uccelli e ritratti',[])
    assert '"instructions": "uccelli e ritratti"' in prompts[0]
    assert 'unspecified “portraits” means people' in prompts[0]
    preview=tmp_path/'synthetic.jpg'
    Image.new('RGB',(10,10),'white').save(preview)
    vlm.assess(preview,{'original_instructions':'uccelli e ritratti','requested_categories':[]})
    assert 'do not require all the others in the same image' in prompts[1]
    assert 'Explicit preferences take precedence over your judgment of beauty' in prompts[1]
    assert 'composition, expression and significance of the moment' in prompts[1]
    assert 'do not automatically give every photo 0.5' in prompts[1]
    assert 'do not reduce the score by counting technical defects' in prompts[1].lower()
    assert 'record defects in quality_issues' in prompts[1]
    assert 'Do not replace a requested category with a sharper image of another category' in prompts[1]


def test_placeholder_and_copied_subject_list_are_rejected_without_guesses(tmp_path):
    from lrc_selection.vlm import _validate_interpretation
    base={'summary':'synthetic','criteria':[],'ambiguities':[],'unsupported':[],
          'requested_categories':[{'id':'slug_stabile','description':'uccelli, ritratti, landscape'}]}
    with pytest.raises(ValueError,match='placeholder'):
        Interpretation.model_validate(base)
    base['requested_categories'][0]['id']='soggetti'
    with pytest.raises(ValueError,match='one category'):
        _validate_interpretation(base,'uccelli, ritratti, landscape')
    # General rule applies to other subject lists, not bird-specific substitution.
    base['requested_categories'][0]['description']='architettura, automobili, fiori'
    with pytest.raises(ValueError,match='one category'):
        _validate_interpretation(base,'architettura, automobili, fiori')
    base['requested_categories']=[{'id':'architecture','description':'Architettura'},
        {'id':'cars','description':'Automobili'},{'id':'flowers','description':'Fiori'}]
    _validate_interpretation(base,'architettura, automobili, fiori')


def test_repair_has_actual_parse_error_and_schema_without_response_echo():
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    answers=iter(['{"summary":"DO_NOT_ECHO",',json.dumps({'summary':'synthetic', 'criteria':[],
        'ambiguities':[],'unsupported':[],'category_mode':'any','requested_categories':[]})])
    def generate(prompt,image,max_tokens):
        prompts.append((prompt,max_tokens))
        return next(answers)
    vlm._generate=generate
    result=vlm.interpret('forme sintetiche',[])
    assert result['requested_categories']==[]
    assert len(prompts)==2 and all(tokens==1024 for _,tokens in prompts)
    assert 'JSON Schema' in prompts[0][0]
    assert 'slug_stabile' not in prompts[0][0] and 'id_categoria' not in prompts[0][0]
    assert 'invalid_json' in prompts[1][0] and 'top-level fields' in prompts[1][0]
    assert 'DO_NOT_ECHO' not in prompts[1][0]


def test_category_key_mismatch_is_repaired_with_exact_expected_keys(tmp_path):
    from PIL import Image
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    data={'match':'yes','reason':'synthetic bird','scene':'synthetic','quality_issues':[],
          'preference_score':.7,'category_matches':{'wrong':'yes'}}
    answers=iter([json.dumps(data),json.dumps(data | {'category_matches':{'birds':'yes'}})])
    def generate(prompt,image,max_tokens):
        prompts.append(prompt)
        assert max_tokens==1024
        return next(answers)
    vlm._generate=generate
    preview=tmp_path/'synthetic.jpg'
    Image.new('RGB',(10,10),'white').save(preview)
    result=vlm.assess(preview,{'original_instructions':'birds',
        'requested_categories':[{'id':'birds','description':'Birds'}]})
    assert result['category_matches']=={'birds':'yes'}
    assert len(prompts)==2
    assert 'category_matches must contain exactly' in prompts[1]
    assert 'birds' in prompts[1]


def test_diagnostics_mark_invalid_and_missing_as_incomplete_then_retry(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['photos'][0]['preview_ready']=False
    vlm.fail=True
    failed=build_instruction_proposal(store,snapshot,vlm)
    assert failed['incomplete'] is False
    assert failed['partial'] is True
    assert failed['review_ids']==['0','1','2']
    assert failed['diagnostics']=={'total':3,'attempted':2,'valid':0,'invalid':2,
        'missing_preview':1,'missing':1,'not_assessed':0,'yes':0,'no':0,'uncertain':3,
        'error_counts':{'schema':2},'partial':True,'review_retained':3,'confirmed_proposal':0}
    assert any('partial results' in warning for warning in failed['warnings'])
    vlm.fail=False
    recovered=build_instruction_proposal(store,snapshot,vlm)
    assert recovered['diagnostics']['invalid']==0
    assert recovered['diagnostics']['valid']==2
    assert len(vlm.assess_calls)==4  # invalid responses were not stored as evidence
    snapshot['photos'][0]['preview_ready']=True
    completed=build_instruction_proposal(store,snapshot,vlm)
    assert completed['incomplete'] is False
    assert completed['diagnostics']['valid']==3


def test_local_reason_bound_does_not_change_shared_api_assessment_schema():
    from lrc_selection.vlm import Assessment, LocalAssessment
    data={'match':'yes','reason':'x'*200,'scene':'synthetic','quality_issues':[],
          'preference_score':.5,'category_matches':{}}
    assert Assessment.model_validate(data).reason==data['reason']
    with pytest.raises(ValueError):
        LocalAssessment.model_validate(data)


def test_plain_category_list_does_not_ask_model_to_invent_limitations(tmp_path):
    from lrc_selection.vlm import _plain_category_interpretation
    original='uccelli, ritratti, landscape'
    result=_plain_category_interpretation(original,[])
    assert result['summary']==original
    assert [c['description'] for c in result['requested_categories']]==['uccelli','Portraits of people','landscape']
    assert result['category_mode']=='any' and result['category_only'] is True
    assert result['ambiguities']==[] and result['unsupported']==[]
    assert _plain_category_interpretation(original,[])==result
    vlm=LocalVLM.__new__(LocalVLM)
    vlm._generate=lambda *args:pytest.fail('Plain subject list must not invoke generative interpretation')
    assert vlm.interpret(original,[])==result
    store,snapshot,fake=fixture(tmp_path)
    snapshot['settings']['instructions']=original
    def assess(path,context):
        assert context['original_instructions']==original
        categories=context['requested_categories']
        portrait=path.read_bytes()==b'snow'
        return {'match':'yes','reason':'synthetic subject evidence','scene':'synthetic',
                'quality_issues':[],'preference_score':.5,
                'category_matches':{c['id']:('yes' if (i==1 if portrait else i==0) else 'no') for i,c in enumerate(categories)}}
    fake.assess=assess
    actual=build_instruction_proposal(store,snapshot,fake)
    assert fake.interpret_calls==[]
    assert actual['diagnostics']['attempted']==3 and actual['diagnostics']['invalid']==0
    assert actual['blocked'] is False
    assert {'0','2'}<=set(actual['shortlist'])


@pytest.mark.parametrize('text,criteria',[
    ('uccelli, senza uccelli',[]),('preferisci uccelli, ritratti',[]),
    ('uccelli, niente ritratti',[]),('uccelli, nessun ritratto',[]),
    ('uccelli, mai ritratti',[]),('uccelli, evita ritratti',[]),
    ('uccelli, almeno ritratti',[]),('uccelli, escludere ritratti',[]),
    ('Marco Rossi, Giulia Bianchi',[]),('uccelli, ritratti a fuoco',[]),
    ('uccelli insieme, ritratti',[]),('uccelli e persone nella stessa foto, paesaggi',[]),
    ('uccelli, ritratti',['Solo persone nominate con identità certa']),
])
def test_real_constraints_and_negations_do_not_use_plain_list_shortcut(text,criteria):
    from lrc_selection.vlm import _plain_category_interpretation
    assert _plain_category_interpretation(text,criteria) is None


def test_category_or_and_explicit_same_photo_are_distinct_and_validated():
    from lrc_selection.vlm import _validate_categories, CategoryValidationError
    red_only={'match':'yes','category_matches':{'red_circle':'yes','blue_square':'no'}}
    _validate_categories(red_only,{'red_circle','blue_square'},'any',True)
    with pytest.raises(CategoryValidationError,match='same image'):
        _validate_categories(red_only,{'red_circle','blue_square'},'all')
    with pytest.raises(CategoryValidationError,match='sufficient'):
        _validate_categories(red_only|{'match':'no'},{'red_circle','blue_square'},'any',True)
    _validate_categories({'match':'no','category_matches':red_only['category_matches']},
                         {'red_circle','blue_square'},'all')


def test_genuine_conflicting_rich_instruction_is_not_ignored(tmp_path):
    store,snapshot,vlm=fixture(tmp_path)
    snapshot['settings']['instructions']='Solo uccelli, escludi tutti gli uccelli'
    vlm.ambiguities=['Richiesta di includere ed escludere lo stesso soggetto.']
    result=build_instruction_proposal(store,snapshot,vlm)
    assert result['blocked'] and result['diagnostics']['attempted']==0
    assert result['instruction_interpretation']['ambiguities']==vlm.ambiguities


def test_assessment_uses_originals_and_categories_without_derived_global_obligations(tmp_path):
    from PIL import Image
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    def structured(prompt,image,schema,max_tokens,**kwargs):
        prompts.append(prompt)
        return {}
    vlm._structured=structured
    preview=tmp_path/'synthetic.jpg'
    Image.new('RGB',(10,10),'white').save(preview)
    context={'summary':'DERIVED_SUMMARY_MUST_NOT_BE_SENT',
        'criteria':['DERIVED_RED_AND_BLUE_GLOBAL_OBLIGATION'],
        'original_instructions':'cerchi rossi e quadrati blu',
        'original_criteria':['USER_ORIGINAL_CRITERION'], 'original_subject_query':'',
        'category_mode':'any','category_only':False,
        'requested_categories':[{'id':'red','description':'cerchi rossi'},{'id':'blue','description':'quadrati blu'}]}
    vlm.assess(preview,context)
    assert 'DERIVED_SUMMARY_MUST_NOT_BE_SENT' not in prompts[0]
    assert 'DERIVED_RED_AND_BLUE_GLOBAL_OBLIGATION' not in prompts[0]
    assert 'USER_ORIGINAL_CRITERION' in prompts[0]
    assert 'cerchi rossi e quadrati blu' in prompts[0]
    assert context['criteria']==['DERIVED_RED_AND_BLUE_GLOBAL_OBLIGATION']  # retained trace unchanged


def test_mistaken_or_rejection_retries_rather_than_forcing_match(tmp_path):
    from PIL import Image
    vlm=LocalVLM.__new__(LocalVLM)
    data={'match':'no','reason':'blue square absent','scene':'red circle','quality_issues':[],
          'preference_score':.5,'category_matches':{'red':'yes','blue':'no'}}
    prompts=[]
    def generate(prompt,image,max_tokens):
        prompts.append(prompt)
        return json.dumps(data)
    vlm._generate=generate
    path=tmp_path/'synthetic.jpg';Image.new('RGB',(10,10),'red').save(path)
    with pytest.raises(ValueError,match='structured'):
        vlm.assess(path,{'original_instructions':'cerchi, quadrati','original_criteria':[],
            'requested_categories':[{'id':'red','description':'cerchi'},{'id':'blue','description':'quadrati'}],
            'category_mode':'any','category_only':True})
    assert len(prompts)==2
    assert 'one yes category is sufficient' in prompts[1]


def test_explicit_same_image_mode_mismatch_requires_retry_without_rewriting():
    from lrc_selection.vlm import _validate_local_interpretation, CategoryValidationError
    value={'summary':'shapes','criteria':[],'ambiguities':[],'unsupported':[],
        'category_mode':'any','requested_categories':[{'id':'circle','description':'cerchio'},
        {'id':'square','description':'quadrato'}]}
    original='Un cerchio e un quadrato presenti nella stessa immagine'
    with pytest.raises(CategoryValidationError,match='category_mode all'):
        _validate_local_interpretation(value,original)
    assert value['category_mode']=='any'
    _validate_local_interpretation(value|{'category_mode':'all'},original)
    _validate_local_interpretation(value,'Un cerchio e un quadrato non necessariamente nella stessa immagine')
    _validate_local_interpretation(value,'Un cerchio e un quadrato: evita che siano nella stessa immagine')


def test_general_shape_interpretation_prompt_does_not_suggest_unrequested_subjects():
    vlm=LocalVLM.__new__(LocalVLM)
    prompts=[]
    def structured(prompt,*args,**kwargs):
        prompts.append(prompt)
        return {'summary':'shapes','criteria':[],'ambiguities':[],'unsupported':[],
                'requested_categories':[],'category_mode':'any'}
    vlm._structured=structured
    vlm.interpret('cerchi rossi e quadrati blu',[])
    assert 'ritratt' not in prompts[0].lower()
    assert 'uccelli' not in prompts[0].lower()
    assert 'do not list generic model limitations' in prompts[0].lower()


def test_negated_rich_subject_list_may_have_one_positive_category():
    from lrc_selection.vlm import _validate_interpretation, _validate_local_interpretation
    value={'summary':'Solo uccelli, senza ritratti','criteria':['Escludere ritratti'],
        'ambiguities':[],'unsupported':[],'category_mode':'any','category_only':False,
        'requested_categories':[{'id':'birds','description':'Uccelli'}]}
    _validate_interpretation(value,'uccelli, niente ritratti')
    _validate_local_interpretation(value,'uccelli, niente ritratti')
    _validate_local_interpretation(value,'uccelli, escludi ritratti')


def test_pure_recovery_retains_all_unknowns_after_confirmed_target_without_model(monkeypatch):
    from lrc_selection.vlm import proposal_from_assessments
    snapshot={'id':'synthetic-recovery','photos':[{'id':str(i),'preview_ready':i!=5} for i in range(6)],
              'settings':{'target':1,'instructions':'synthetic original'},'decisions':{}}
    interpretation={'requested_categories':[{'id':'subject','description':'Requested subject'}],
                    'ambiguities':[],'unsupported':[],'original_instructions':'synthetic original'}
    def assessment(match, **extra):
        return {'match':match,'reason':'synthetic evidence','scene':'synthetic','preference_score':.5,
                'category_matches':{'subject':'yes'},'quality_issues':[]}|extra
    assessments={'0':assessment('yes'),'1':assessment('yes'),'2':assessment('no'),
                 '3':assessment('uncertain'),'4':assessment('uncertain',error='Invalid response',error_kind='schema'),
                 '5':assessment('uncertain',error='Missing preview')}
    records={pid:{'assessment':value} for pid,value in assessments.items()}
    before=copy.deepcopy((snapshot,interpretation,assessments,records))
    monkeypatch.setattr(LocalVLM,'__init__',lambda *args:pytest.fail('Recovery must not instantiate a model'))
    recovered=proposal_from_assessments(snapshot,interpretation,assessments,{'adapter':'stored-synthetic'},records)
    assert recovered['shortlist']==['0','1','3','4','5']
    assert recovered['review_ids']==['3','4','5']
    assert recovered['partial'] and not recovered['incomplete']
    assert recovered['diagnostics']['confirmed_proposal']==2
    assert recovered['diagnostics']['invalid']==1 and recovered['diagnostics']['missing_preview']==1
    assert recovered['diagnostics']['yes']==2  # no fabricated conversion of unknowns
    assert recovered['coverage'][0]['selected_ids']==['0','1']
    assert all('Requires review' in recovered['shortlist_reasons'][pid] for pid in recovered['review_ids'])
    assert (snapshot,interpretation,assessments,records)==before


def test_all_uncertain_included_above_target_without_confirmed_coverage():
    from lrc_selection.vlm import proposal_from_assessments
    snapshot={'photos':[{'id':str(i),'preview_ready':True} for i in range(3)],
              'settings':{'target':1,'instructions':'subject'},'decisions':{}}
    interpretation={'requested_categories':[{'id':'subject','description':'Subject'}], 'ambiguities':[],'unsupported':[]}
    assessments={str(i):{'match':'uncertain','reason':'uncertain synthetic evidence','scene':'',
                        'preference_score':.5,'category_matches':{'subject':'yes'}} for i in range(3)}
    result=proposal_from_assessments(snapshot,interpretation,assessments,{}, {})
    assert result['shortlist']==result['review_ids']==['0','1','2']
    assert result['coverage'][0]['status']=='uncertain' and result['coverage'][0]['selected_ids']==[]
    assert result['diagnostics']['yes']==0 and result['diagnostics']['confirmed_proposal']==0
    assert result['partial'] and not result['incomplete']
    assert any('Indicative quantity exceeded' in w for w in result['warnings'])
    snapshot['decisions']={'0':{'state':'excluded','locked':True},'1':{'state':'alternative','locked':False}}
    manual=proposal_from_assessments(snapshot,interpretation,assessments,{}, {})
    assert manual['shortlist']==manual['review_ids']==['2']


def test_unknown_manual_candidate_does_not_consume_confirmed_target_and_missing_record_is_review():
    from lrc_selection.vlm import proposal_from_assessments
    snapshot={'photos':[{'id':str(i),'preview_ready':True} for i in range(3)],
              'settings':{'target':1,'instructions':'subject'},'decisions':{'1':{'state':'preferred','locked':True}}}
    interpretation={'requested_categories':[], 'ambiguities':[],'unsupported':[]}
    assessments={'0':{'match':'yes','reason':'synthetic yes','scene':'','preference_score':.5},
                 '1':{'match':'uncertain','reason':'synthetic unknown','scene':'','preference_score':.5}}
    result=proposal_from_assessments(snapshot,interpretation,assessments,{}, {})
    assert result['shortlist']==['0','1','2'] and result['review_ids']==['1','2']
    assert result['diagnostics']['not_assessed']==1
    assert result['shortlist_reasons']['1']=='Manual decision preserved.'
