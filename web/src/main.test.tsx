// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import type { Preset, Service } from './api';

const preset: Preset = {id:'wedding',name:'Matrimonio',version:1,criteria:['Preservare varianti'],subject_query:'uccelli',instructions:'Conserva varianti del volo'};
let service: Service;
let calls: {path:string;method:string;body:Record<string,any>|undefined}[];
function json(value:unknown,status=200){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});}

beforeEach(()=>{
  history.replaceState(null,'','/');
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','');}});
  service={id:'synthetic',title:'TEST SINTETICO',catalog_id:'fake',revision:1,status:'ready',
    settings:{target:2,preset_id:'wedding',preset_version:1,preset_snapshot:preset,mode:'local',instructions:'',service_criteria:[],subject_query:'',camera_offsets:{}},
    photos:[0,1].map(i=>({id:'p'+i,uuid:'u'+i,local_id:i,filename:'sintetica-'+i+'.jpg',camera:'Simulata',captured_at:0,baseline_rating:i?3:0,baseline_edit_time:1,preview_ready:false})),
    decisions:{},proposal:null,job:null,receipts:[],criteria:[]};
  calls=[];
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const path=String(input).replace('/api','');
    const method=init?.method??'GET';
    const body=init?.body?JSON.parse(String(init.body)):undefined;
    calls.push({path,method,body});
    if(path==='/session')return json({ok:true});
    if(path==='/services')return json([{id:service.id,title:service.title,photo_count:2,revision:service.revision,status:service.status,archived:service.archived},{id:'second',title:'SECONDO SINTETICO',photo_count:2,revision:1,status:'ready'}]);
    if(path==='/capabilities')return json({features:false,instructions:true});
    if(path==='/presets'&&method==='POST')return json({...body,id:'new-preset',version:1});
    if(path==='/presets/wedding'&&method==='PUT')return json({...body,id:'wedding',version:2});
    if(path==='/presets')return json([preset]);
    if(path.endsWith('/accept-shortlist'))return json({...service,revision:service.revision+1});
    if(path==='/services/synthetic')return json(service);
    if(path.endsWith('/settings')){service={...service,revision:service.revision+1,settings:{...body.settings,preset_snapshot:preset}};return json(service);}
    if(path.includes('/decisions/')){
      if(body.state==='excluded'&&!body.confirm_last)return json({detail:{code:'last_candidate',message:'Confirm removing the last candidate?'}},409);
      service={...service,revision:service.revision+1,decisions:{...service.decisions,[path.split('/').at(-1)!]:{state:body.state,locked:body.locked}}};return json(service);
    }
    if(path.endsWith('/replace')||path.endsWith('/undo')||path.endsWith('/redo')){
      const undone=path.endsWith('/undo');
      const selected=undone?'p0':'p1';
      service={...service,revision:service.revision+1,selected_ids:[selected],can_undo:!undone,can_redo:undone,
        decisions:undone?{}:{p0:{state:'alternative',locked:false},p1:{state:'preferred',locked:false}},
        proposal:{...service.proposal!,groups:[{...service.proposal!.groups[0],representative:selected}]}};
      return json(service);
    }
    if(path.endsWith('/analyze'))return json({...service,job:{status:'completed',completed:2,total:2,error:null}});
    if(path.endsWith('/rating-plan/confirm')){service={...service,confirmed_batch_id:body.batch_id};return json({batch_id:body.batch_id});}
    if(path.endsWith('/archive')){service={...service,revision:service.revision+1,archived:body.archived};return json(service);}
    if(path.endsWith('/rating-plan'))return json({batch_id:'b',service_id:service.id,catalog_id:'fake',revision:service.revision,warnings:[],items:[{photo_id:'p0',uuid:'u0',local_id:0,expected_rating:0,expected_edit_time:1,target_rating:1}]});
    throw new Error('Unexpected endpoint '+path);
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
async function workspace(){render(<App/>);await screen.findByRole('option',{name:/TEST SINTETICO/});fireEvent.change(screen.getByLabelText('Service'),{target:{value:'synthetic'}});await screen.findByRole('heading',{name:'TEST SINTETICO'});}

describe('Review without real data',()=>{
  it('applies the preset to the draft and keeps service criteria editable',async()=>{
    service={...service,settings:{...service.settings,preset_id:'',preset_version:0,preset_snapshot:null,service_criteria:[],subject_query:''}};
    await workspace();
    fireEvent.change(screen.getByLabelText('Start from a preset'),{target:{value:'wedding:1'}});
    expect((screen.getByLabelText('Selection instructions') as HTMLTextAreaElement).value).toBe('Conserva varianti del volo\n\nPreservare varianti\nSubject to prioritise: uccelli');
    expect(screen.queryByLabelText('Service criteria, one per line')).toBeNull();
    fireEvent.change(screen.getByLabelText('Selection instructions'),{target:{value:'Conservare il volo'}});
    fireEvent.click(screen.getByRole('button',{name:'Save criteria'}));
    await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/settings'))).toBe(true));
    expect(calls.find(c=>c.path.endsWith('/settings'))?.body?.settings).toMatchObject({instructions:'Conservare il volo',service_criteria:[],subject_query:''});
    expect(calls.some(c=>c.path.startsWith('/presets')&&c.method!=='GET')).toBe(false);
    fireEvent.click(screen.getByRole('button',{name:'Remove preset and criteria'}));
    expect((screen.getByLabelText('Selection instructions') as HTMLTextAreaElement).value).toBe('');
  });
  it('filters the proposal without changing decisions or ratings',async()=>{
    service={...service,proposal:{selected:['p0','p1'],shortlist:['p1'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
    await workspace();
    expect((screen.getByLabelText('Show') as HTMLSelectElement).value).toBe('proposal');
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByText('sintetica-1.jpg')).toBeTruthy();
    expect(calls.some(c=>c.method!=='GET')).toBe(false);
  });
  it('saves a new preset from the service instructions and criteria',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Selection instructions'),{target:{value:'Conserva una photos per azione'}});
    fireEvent.click(screen.getByRole('button',{name:'Save as new preset'}));
    const dialog=await screen.findByRole('dialog',{name:'New preset'});
    expect((within(dialog).getByLabelText('Preset instructions') as HTMLTextAreaElement).value).toBe('Conserva una photos per azione');
    fireEvent.change(within(dialog).getByLabelText('Name'),{target:{value:'Azioni'}});
    fireEvent.click(within(dialog).getByRole('button',{name:'Save preset'}));
    await waitFor(()=>expect(calls.some(c=>c.path==='/presets'&&c.method==='POST')).toBe(true));
    expect(calls.find(c=>c.path==='/presets'&&c.method==='POST')?.body).toMatchObject({name:'Azioni',instructions:'Conserva una photos per azione',criteria:[]});
  });
  it('requires confirmation before adopting the proposal without applying ratings',async()=>{
    service={...service,proposal:{selected:['p0','p1'],shortlist:['p1'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
    await workspace();
    fireEvent.click(screen.getByRole('button',{name:'Confirm selection'}));
    const dialog=await screen.findByRole('dialog',{name:'Use proposal as selection'});
    expect(calls.some(c=>c.path.endsWith('/accept-shortlist'))).toBe(false);
    fireEvent.click(within(dialog).getByRole('button',{name:'Confirm candidates'}));
    await waitFor(()=>expect(calls.find(c=>c.path.endsWith('/accept-shortlist'))?.body).toEqual({revision:1,confirm_last:true}));
    expect(calls.some(c=>c.path.includes('/rating-'))).toBe(false);
  });
  it('saves criteria without implicitly starting analysis',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Local candidates'),{target:{value:'1'}});
    fireEvent.click(screen.getByRole('button',{name:'Save criteria'}));
    await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/settings'))).toBe(true));
    expect(calls.some(c=>c.path.endsWith('/analyze'))).toBe(false);
    await waitFor(()=>expect((screen.getByRole('button',{name:'Start selection'}) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button',{name:'Start selection'}));
    await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/analyze'))).toBe(true));
  });
  it('synchronises the slider and numeric input without starting selection',async()=>{
    await workspace();
    const slider=screen.getByRole('slider',{name:'Adjust candidate count'}) as HTMLInputElement;
    const number=screen.getByLabelText('Local candidates') as HTMLInputElement;
    expect(slider.min).toBe('1');expect(slider.max).toBe('2');
    fireEvent.change(slider,{target:{value:'1'}});
    expect(number.value).toBe('1');
    expect(screen.getByText('Unsaved')).toBeTruthy();
    fireEvent.change(number,{target:{value:'2'}});
    expect(slider.value).toBe('2');
    fireEvent.change(number,{target:{value:'3'}});
    expect((screen.getByRole('button',{name:'Start selection'}) as HTMLButtonElement).disabled).toBe(true);
    expect(calls.some(c=>c.path.endsWith('/settings')||c.path.endsWith('/analyze'))).toBe(false);
  });
  it('requires confirmation for the last candidate even before analysis',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('State sintetica-0.jpg'),{target:{value:'excluded'}});
    const dialog=await screen.findByRole('dialog',{name:'Last candidate in group'});
    expect(service.decisions.p0).toBeUndefined();
    fireEvent.click(within(dialog).getByRole('button',{name:'Confirm change'}));
    await waitFor(()=>expect(service.decisions.p0?.state).toBe('excluded'));
    await screen.findByText(/1 candidates out of 2 photos/);
  });
  it('only prepares the rating plan and never applies ratings from the browser',async()=>{
    await workspace();
    fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
    fireEvent.click(screen.getByRole('button',{name:'Review ratings'}));
    const dialog=await screen.findByRole('dialog',{name:'Review ratings'});
    expect(within(dialog).getByText(/Manual selection; no analysis has been run/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button',{name:'Prepare changes preview'}));
    await within(dialog).findByText('1 proposed changes');
    expect(calls.some(c=>c.path.endsWith('/rating-plan/confirm'))).toBe(false);
    fireEvent.click(within(dialog).getByRole('button',{name:'Confirm list for Lightroom'}));
    await within(dialog).findByText('Plan confirmed · b');
    expect(calls.find(c=>c.path.endsWith('/rating-plan/confirm'))?.body).toEqual({batch_id:'b'});
    expect(calls.some(c=>c.path.endsWith('/rating-plan/claim')||c.path.endsWith('/rating-receipts'))).toBe(false);
  });
  it('includes photos to review in the candidate count',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('State sintetica-0.jpg'),{target:{value:'review'}});
    await waitFor(()=>expect(service.decisions.p0?.state).toBe('review'));
    expect(screen.getByText(/2 candidates out of 2 photos/)).toBeTruthy();
  });
  it('opens comparison only after two choices and provides zoom',async()=>{
    await workspace();
    const choices=screen.getAllByRole('checkbox',{name:'Compare'});
    fireEvent.click(choices[0]);fireEvent.click(choices[1]);
    fireEvent.click(screen.getByRole('button',{name:'Compare (2/2)'}));
    const dialog=await screen.findByRole('dialog',{name:'Compare previews'});
    fireEvent.change(within(dialog).getByRole('slider'),{target:{value:'200'}});
    expect(within(dialog).getByText('Zoom 200%')).toBeTruthy();
  });
  it('protects the draft when switching services after a concurrent update',async()=>{
    await workspace();
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);
    try {
      fireEvent.change(screen.getByLabelText('Local candidates'),{target:{value:'1'}});
      fireEvent.change(screen.getByLabelText('Service'),{target:{value:'second'}});
      expect(confirm).toHaveBeenCalled();
      expect(calls.some(c=>c.path.endsWith('/second'))).toBe(false);
      service={...service,revision:2,settings:{...service.settings,instructions:'Refreshte altrove'}};
      fireEvent.click(screen.getByRole('button',{name:'Refresh'}));
      await screen.findByText('The saved criteria have changed.');
      expect((screen.getByLabelText('Local candidates') as HTMLInputElement).value).toBe('1');
      fireEvent.click(screen.getByRole('button',{name:'Load saved criteria'}));
      expect((screen.getByLabelText('Local candidates') as HTMLInputElement).value).toBe('2');
    } finally {confirm.mockRestore();}
  });
  it('reopens an archived service while preserving revision checks',async()=>{
    await workspace();
    fireEvent.click(screen.getByText('Service options'));
    fireEvent.click(screen.getByRole('button',{name:'Archive service'}));
    await screen.findByText(/Service archived/);
    fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
    expect((screen.getByRole('button',{name:'Review ratings'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'Reopen service'}));
    await waitFor(()=>expect(service.archived).toBe(false));
    expect(calls.filter(c=>c.path.endsWith('/archive')).map(c=>c.body?.revision)).toEqual([1,2]);
  });
  it('applies contact-sheet shortcuts and leaves form fields editable',async()=>{
    await workspace();
    fireEvent.keyDown(document.body,{key:'ArrowRight'});
    const first=screen.getAllByRole('article')[0];
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(screen.getByLabelText('Selection instructions'),{key:'x'});
    fireEvent.keyDown(screen.getByLabelText('Local candidates'),{key:'ArrowRight'});
    expect(document.activeElement).toBe(first);
    expect(calls.some(c=>c.path.includes('/decisions/'))).toBe(false);
    fireEvent.keyDown(first,{key:'x'});
    await screen.findByRole('dialog',{name:'Last candidate in group'});
    expect(calls.find(c=>c.path.endsWith('/decisions/p0'))?.body).toMatchObject({state:'excluded'});
  });
  it('replaces the representative with one request and uses service history',async()=>{
    service={...service,selected_ids:['p0'],proposal:{selected:['p0'],groups:[{id:'g',members:['p0','p1'],representative:'p0',reason:'Previews identiche'}],reasons:{},warnings:[],engine:'test'}};
    await workspace();
    const alternative=screen.getAllByRole('article')[1];
    fireEvent.click(within(alternative).getByText('Reason'));
    fireEvent.click(within(alternative).getByRole('button',{name:'Replace representative'}));
    await waitFor(()=>expect((screen.getByLabelText('State sintetica-1.jpg') as HTMLSelectElement).value).toBe('preferred'));
    fireEvent.click(screen.getByRole('button',{name:'Undo decision'}));
    await waitFor(()=>expect((screen.getByLabelText('State sintetica-0.jpg') as HTMLSelectElement).value).toBe('candidate'));
    fireEvent.click(screen.getByRole('button',{name:'Redo decision'}));
    await waitFor(()=>expect((screen.getByLabelText('State sintetica-1.jpg') as HTMLSelectElement).value).toBe('preferred'));
    const mutations=calls.filter(c=>c.method==='POST');
    expect(mutations.map(c=>c.path.split('/').at(-1))).toEqual(['replace','undo','redo']);
    expect(mutations.map(c=>c.body)).toEqual([{revision:1,from_photo_id:'p0',to_photo_id:'p1'},{revision:2},{revision:3}]);
  });
  it('stops polling after receiving the Lightroom receipt',async()=>{
    service={...service,confirmed_batch_id:'b'};
    const intervals=vi.spyOn(window,'setInterval');
    const clear=vi.spyOn(window,'clearInterval');
    try {
      await workspace();
      const index=intervals.mock.calls.findIndex(([,ms])=>ms===1200);
      expect(index).toBeGreaterThanOrEqual(0);
      const [poll]=intervals.mock.calls[index];
      const timer=intervals.mock.results[index].value;
      service={...service,revision:2,confirmed_batch_id:undefined,receipts:[{batch_id:'b',results:[{photo_id:'p0',status:'applied',reason:'',before:0,after:1}]}]};
      await act(async()=>{(poll as ()=>void)();});
      await screen.findByRole('heading',{name:'Lightroom results'});
      expect(clear).toHaveBeenCalledWith(timer);
      expect(intervals.mock.calls.filter(([,ms])=>ms===1200)).toHaveLength(1);
    } finally {intervals.mockRestore();clear.mockRestore();}
  });
  it('shows preview resolution and crops detected faces from bottom-origin coordinates',async()=>{
    service={...service,photos:service.photos.map(p=>({...p,preview_ready:true})),interpretations:{records:{p0:{faces:{observations:[
      {x:0.125,y:0.5,width:0.25,height:0.25,confidence:0.9},
      {x:0,y:0,width:2,height:0.25,confidence:0.9},
    ]}}}}};
    await workspace();
    const choices=screen.getAllByRole('checkbox',{name:'Compare'});
    fireEvent.click(choices[0]);fireEvent.click(choices[1]);
    fireEvent.click(screen.getByRole('button',{name:'Compare (2/2)'}));
    const dialog=await screen.findByRole('dialog',{name:'Compare previews'});
    const preview=within(dialog).getByRole('img',{name:'sintetica-0.jpg'});
    Object.defineProperties(preview,{naturalWidth:{value:1200},naturalHeight:{value:800}});
    fireEvent.load(preview);
    expect(within(dialog).getByText(/Preview 1200 × 800 px/)).toBeTruthy();
    fireEvent.click(within(dialog).getByText('Detected face details'));
    const [crop]=within(dialog).getAllByRole('img',{name:/Detected face/}) as HTMLImageElement[];
    expect(within(dialog).getAllByRole('img',{name:/Detected face/})).toHaveLength(1);
    expect(crop.style.left).toBe('-50%');
    expect(crop.style.top).toBe('-100%');
    expect(crop.getAttribute('src')).toBe(preview.getAttribute('src'));
  });
  it('removes the token from the URL fragment after connection',async()=>{
    history.replaceState(null,'','/#token=synthetic-connection-token');
    render(<App/>);
    await screen.findByRole('option',{name:/TEST SINTETICO/});
    expect(location.hash).toBe('');
    expect(calls[0].path).toBe('/session');
  });
});


it('hides previous proposal notices after criteria change',async()=>{
  const obsolete='Il motore iniziale riconosce solo previews identiche';
  service={...service,requires_analysis:true,proposal:{selected:['p0','p1'],groups:[],reasons:{},warnings:[obsolete],engine:'exact-preview-v1',stale:true}};
  await workspace();
  expect(screen.queryByText(obsolete)).toBeNull();
  expect(screen.getByText(/Settings or photos have changed/).textContent).toContain('Start selection to create a new proposal');
  expect(screen.getByText(/Previous results ·/)).toBeTruthy();
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('shows progress and previous-result context during a new analysis',async()=>{
  const obsolete='Old quantity exceeded';
  service={...service,status:'analyzing',job:{status:'running',completed:1,total:2,error:null},proposal:{selected:['p0','p1'],groups:[],reasons:{},warnings:[obsolete],engine:'exact-preview-v1'}};
  await workspace();
  expect(screen.queryByText(obsolete)).toBeNull();
  expect(screen.getByText(/Analysis running · 1 \/ 2/).textContent).toContain('previous proposal');
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});


it('combines legacy criteria into one field while preserving the original prefix',async()=>{
  const original='  Solo uccelli\nPreferisci ali aperte!  \n';
  service={...service,settings:{...service.settings,instructions:original,service_criteria:['Conservare varianti'],subject_query:'uccelli in volo'}};
  await workspace();
  const text=screen.getByLabelText('Selection instructions') as HTMLTextAreaElement;
  expect(text.value.startsWith(original)).toBe(true);
  expect(text.value).toContain('Conservare varianti');
  expect(text.value).toContain('Subject to prioritise: uccelli in volo');
  expect(screen.queryByLabelText('Service criteria, one per line')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Save criteria'}));
  await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/settings'))).toBe(true));
  expect(calls.find(c=>c.path.endsWith('/settings'))?.body?.settings).toMatchObject({instructions:text.value,service_criteria:[],subject_query:''});
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('keeps all filtered photos scrollable beyond the old 48-photo page',async()=>{
  const template=service.photos[0];
  service={...service,photos:Array.from({length:60},(_,i)=>({...template,id:'p'+i,uuid:'u'+i,local_id:i,filename:'scroll-'+i+'.jpg',preview_ready:true}))};
  await workspace();
  const cards=screen.getAllByRole('article');
  expect(cards).toHaveLength(60);
  expect(screen.queryByRole('button',{name:/Show more photos/})).toBeNull();
  expect(screen.getByAltText('scroll-59.jpg').getAttribute('loading')).toBe('lazy');
  act(()=>cards[47].focus());
  fireEvent.keyDown(cards[47],{key:'ArrowRight'});
  expect(document.activeElement).toBe(cards[48]);
  fireEvent.change(screen.getByLabelText('State'),{target:{value:'excluded'}});
  expect(screen.queryAllByRole('article')).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('State'),{target:{value:'all'}});
  expect(screen.getAllByRole('article')).toHaveLength(60);
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});

it('shows all photos and the error after failed analysis with an old shortlist',async()=>{
  const template=service.photos[0];
  const photos=Array.from({length:160},(_,i)=>({...template,id:'p'+i,uuid:'u'+i,local_id:i,filename:'failed-'+i+'.jpg',preview_ready:true}));
  service={...service,photos,requires_analysis:true,job:{status:'failed',completed:160,total:160,error:'150 invalid responses out of 160. Review the model configuration.'},proposal:{selected:photos.map(p=>p.id),shortlist:['p0','p1'],groups:[],reasons:{},warnings:['Outdated invalid notice'],engine:'old-test',stale:true}};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(160);
  expect(screen.getByText('160 photos available · 160 current candidates')).toBeTruthy();
  expect(screen.queryByText(/2 proposte to review/)).toBeNull();
  expect(screen.queryByRole('checkbox',{name:'Proposta to review (2)'})).toBeNull();
  expect(screen.queryByRole('button',{name:'Use this proposal (2)'})).toBeNull();
  const gallery=screen.getByRole('region',{name:'Review area'});
  expect(within(gallery).getByRole('alert').textContent).toContain('150 invalid responses out of 160');
  expect(screen.queryByText('Outdated invalid notice')).toBeNull();
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('shows the initial error without turning candidates into zero selected',async()=>{
  service={...service,requires_analysis:true,job:{status:'failed',completed:0,total:2,error:'Analysis not started: instructions need clarification.'},proposal:null};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByText('2 photos available · 2 current candidates')).toBeTruthy();
  const gallery=screen.getByRole('region',{name:'Review area'});
  expect(within(gallery).getByRole('alert').textContent).toContain('Analysis not started');
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('keeps uncertain photos in the proposal and review filter without decisions',async()=>{
  service={...service,job:{status:'completed_with_warnings',completed:2,total:2,error:null},proposal:{selected:['p0','p1'],shortlist:['p0','p1'],review_ids:['p1'],shortlist_reasons:{p1:'Invalid response: kept for review.'},groups:[],reasons:{},warnings:['One photo kept for review.'],engine:'synthetic'}};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByText('To review · included in proposal')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('State'),{target:{value:'review'}});
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByText('sintetica-1.jpg')).toBeTruthy();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});

function workflow(phase:NonNullable<Service['workflow']>['phase'],path:'local'|'hybrid'|'openai'='local'):NonNullable<Service['workflow']>{
  return {schema_version:1,path,phase,local_completed:false,proposal_ready:false,proposal_accepted:false,requires_analysis:false,confirmed_batch_id:null,active_batch_id:null,selected_count:2,target:2,outcome:null};
}
it('restores the service phase and navigates without starting operations',async()=>{
  service={...service,workflow:workflow('review'),proposal:{selected:['p0','p1'],shortlist:['p0','p1'],groups:[],reasons:{},warnings:['Dettaglio tecnico sintetico'],engine:'test'}};
  await workspace();
  expect(screen.getByRole('button',{name:'Confirm selection'})).toBeTruthy();
  expect(screen.queryByRole('heading',{name:'Configure selection'})).toBeNull();
  const navigation=screen.getByRole('navigation',{name:'Selection steps'});
  fireEvent.click(within(navigation).getByRole('button',{name:/Configure/}));
  expect(screen.getByRole('heading',{name:'Configure selection'})).toBeTruthy();
  fireEvent.click(within(navigation).getByRole('button',{name:/Review/}));
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
  expect(screen.getByText('Dettaglio tecnico sintetico').closest('details')?.open).toBe(false);
});
it('distinguishes three workflows without starting analysis on change',async()=>{
  await workspace();
  const path=screen.getByLabelText('Workflow');
  expect(within(path).getAllByRole('option').map(x=>x.textContent)).toEqual(['Local only','Local + OpenAI','Directly with OpenAI']);
  fireEvent.change(path,{target:{value:'openai'}});
  expect(screen.getByRole('button',{name:'Continue to OpenAI estimate'})).toBeTruthy();
  expect(screen.getByLabelText('Final OpenAI selection')).toBeTruthy();
  expect(screen.queryByLabelText('Local candidates')).toBeNull();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});
it('guides the hybrid workflow to OpenAI or local review',async()=>{
  service={...service,workflow:workflow('analyze','hybrid'),settings:{...service.settings,mode:'hybrid',workflow_path:'hybrid'},proposal:{selected:['p0','p1'],shortlist:['p0','p1'],groups:[],reasons:{},warnings:[],engine:'test'}};
  await workspace();
  expect(screen.getByRole('button',{name:'Continue with OpenAI'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Use local result'}));
  expect(screen.getByRole('button',{name:'Confirm selection'})).toBeTruthy();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});
it('explains how to resume interrupted sending without new calls',async()=>{
  service={...service,workflow:workflow('analyze','hybrid'),settings:{...service.settings,mode:'hybrid',workflow_path:'hybrid'},job:{kind:'openai',status:'interrupted',completed:15,total:18,error:'Invalid response'}};
  await workspace();
  expect(screen.getByRole('button',{name:'Prepare to resume'})).toBeTruthy();
  expect(screen.getByText(/Analysis interrupted: 15 of 18/)).toBeTruthy();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});
it('does not show a historical receipt as current selection completion',async()=>{
  service={...service,workflow:workflow('review'),receipts:[{batch_id:'old',results:[{photo_id:'p0',status:'applied',reason:'',before:0,after:1}]}]};
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/5Outcome/}));
  expect(screen.getByText(/No Lightroom receipt is available/)).toBeTruthy();
  expect(screen.queryByText('1 ratings applied')).toBeNull();
});
it('keeps the API target separate and shows partial receipt outcomes',async()=>{
  service={...service,workflow:{...workflow('outcome','hybrid'),target:1,outcome:{applied:1,skipped:0,conflict:1,uncertain:0,total:2}},selected_ids:['p0'],settings:{...service.settings,target:2},proposal:{selected:['p0'],shortlist:['p0'],shortlist_accepted:true,api_target:1,api_plan_id:'api',groups:[],reasons:{},warnings:[],engine:'test'},receipts:[{batch_id:'latest',results:[{photo_id:'p0',status:'applied',reason:'',before:0,after:1},{photo_id:'p1',status:'conflict',reason:'Rating changed',before:3,after:3}]}]};
  await workspace();
  expect(screen.getByText(/Partial outcome:/)).toBeTruthy();
  expect(screen.queryByText(/below the requested number/)).toBeNull();
});

it('explains that a plan with no new ratings does not require applying',async()=>{
  const original=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const result=await original(input,init);
    if(!String(input).endsWith('/rating-plan'))return result;
    const plan=await result.json();return json({...plan,items:[]});
  }));
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
  fireEvent.click(screen.getByRole('button',{name:'Review ratings'}));
  const dialog=await screen.findByRole('dialog',{name:'Review ratings'});
  fireEvent.click(within(dialog).getByRole('button',{name:'Prepare changes preview'}));
  await within(dialog).findByText(/No changes needed/);
  expect(within(dialog).queryByRole('button',{name:'Confirm list for Lightroom'})).toBeNull();
  expect(calls.some(x=>x.path.endsWith('/rating-plan/confirm'))).toBe(false);
});
it('prevents confirmation of an outdated rating plan',async()=>{
  const original=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const result=await original(input,init);
    if(!String(input).endsWith('/rating-plan'))return result;
    const plan=await result.json();return json({...plan,revision:0});
  }));
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
  fireEvent.click(screen.getByRole('button',{name:'Review ratings'}));
  const dialog=await screen.findByRole('dialog',{name:'Review ratings'});
  fireEvent.click(within(dialog).getByRole('button',{name:'Prepare changes preview'}));
  await within(dialog).findByText(/Plan out of date/);
  expect(within(dialog).queryByRole('button',{name:'Confirm list for Lightroom'})).toBeNull();
  expect(calls.some(x=>x.path.endsWith('/rating-plan/confirm'))).toBe(false);
});
it('focuses the step heading and keeps the contact sheet accessible',async()=>{
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/3Review/}));
  const heading=screen.getByRole('heading',{name:'Review'});
  await waitFor(()=>expect(document.activeElement).toBe(heading));
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(calls.some(x=>x.method!=='GET')).toBe(false);
});

it('shows zero proposals accurately and keeps all photos reviewable',async()=>{
  service={...service,workflow:workflow('review'),selected_ids:['p0','p1'],proposal:{selected:['p0','p1'],shortlist:[],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  expect(screen.getByText('0 proposals to review · 2 photos available')).toBeTruthy();
  expect(screen.getByText(/No photos selected\. All photos are visible/)).toBeTruthy();
  expect(screen.queryByText(/Review the 2 selected photos/)).toBeNull();
  expect((screen.getByRole('button',{name:'Confirm selection'}) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getAllByText('Not selected')).toHaveLength(2);
  expect((screen.getByLabelText('Show') as HTMLSelectElement).value).toBe('all');
  expect(screen.getByRole('button',{name:'Review criteria'})).toBeTruthy();
  expect(calls.some(x=>x.method!=='GET')).toBe(false);
});
it('manually includes a photo from an empty proposal and confirms the effective count',async()=>{
  service={...service,workflow:workflow('review'),selected_ids:['p0','p1'],proposal:{selected:['p0','p1'],shortlist:[],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:'Include sintetica-1.jpg'}));
  await screen.findByText('Manually included');
  expect(screen.getByText('1 proposals to review · 2 photos available')).toBeTruthy();
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect((screen.getByLabelText('Show') as HTMLSelectElement).value).toBe('all');
  expect((screen.getByRole('button',{name:'Confirm selection'}) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Confirm selection'}));
  const dialog=await screen.findByRole('dialog',{name:'Use proposal as selection'});
  expect(within(dialog).getByText(/Confirm 1 photos in the selection, including your manual changes/)).toBeTruthy();
  expect(calls.find(x=>x.path.endsWith('/decisions/p1'))?.body).toEqual({revision:1,state:'candidate',locked:false,confirm_last:false});
  expect(calls.some(x=>x.path.includes('/rating-')||x.path.endsWith('/api-confirm'))).toBe(false);
});
it('overlays manual decisions on proposal filters and badges',async()=>{
  service={...service,workflow:workflow('review'),decisions:{p0:{state:'excluded',locked:false},p1:{state:'candidate',locked:false}},proposal:{selected:['p0','p1'],shortlist:['p0'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByText('sintetica-1.jpg')).toBeTruthy();
  expect(screen.getByText('1 proposals to review · 2 photos available')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Show'),{target:{value:'all'}});
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByText('Manually included')).toBeTruthy();
  expect(screen.getByText('Manually excluded')).toBeTruthy();
  expect(screen.getByRole('button',{name:'Include sintetica-0.jpg'})).toBeTruthy();
  expect(screen.getByRole('button',{name:'Exclude sintetica-1.jpg'})).toBeTruthy();
});
it('shows blocked-analysis reasons and offers criteria correction',async()=>{
  service={...service,workflow:{...workflow('configure','hybrid'),blocked:true,blocked_reasons:['Specify whether you want a general selection.']},settings:{...service.settings,mode:'hybrid',workflow_path:'hybrid'},job:{kind:'openai',status:'blocked',completed:0,total:2,error:'Instructions need clarification'}};
  await workspace();
  const reason=screen.getByText('Specify whether you want a general selection.');
  expect(reason.closest('[role=alert]')).toBeTruthy();
  expect(reason.closest('details')).toBeNull();
  expect(screen.getByRole('heading',{name:'Configure selection'})).toBeTruthy();
  expect(calls.some(x=>x.method!=='GET')).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Prepare a new OpenAI estimate'}));
  await waitFor(()=>expect(calls.some(x=>x.path.endsWith('/api-status'))).toBe(true));
  expect(calls.some(x=>x.path.endsWith('/analyze')||x.path.endsWith('/api-confirm'))).toBe(false);
});

it('opens a large preview and navigates boundaries with focus restoration and no decisions',async()=>{
  service={...service,photos:service.photos.map(photo=>({...photo,preview_ready:true}))};
  await workspace();
  const opener=screen.getByRole('button',{name:'Open preview sintetica-0.jpg'});
  act(()=>opener.focus());
  fireEvent.click(opener);
  const dialog=await screen.findByRole('dialog',{name:'Photo preview'});
  expect(within(dialog).getByRole('img',{name:'sintetica-0.jpg'}).getAttribute('src')).toBe('/api/services/synthetic/photos/p0/preview');
  expect(within(dialog).getByText('1 / 2')).toBeTruthy();
  expect((within(dialog).getByRole('button',{name:'Previous photo'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(within(dialog).getByRole('button',{name:'Next photo'}));
  expect(within(dialog).getByRole('img',{name:'sintetica-1.jpg'})).toBeTruthy();
  expect(within(dialog).getByText('2 / 2')).toBeTruthy();
  expect((within(dialog).getByRole('button',{name:'Next photo'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.keyDown(dialog,{key:'ArrowLeft'});
  expect(within(dialog).getByRole('img',{name:'sintetica-0.jpg'})).toBeTruthy();
  fireEvent.keyDown(dialog,{key:'x'});
  fireEvent.keyDown(document.body,{key:'m'});
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
  fireEvent.keyDown(dialog,{key:'Escape'});
  expect(screen.queryByRole('dialog',{name:'Photo preview'})).toBeNull();
  expect(document.activeElement).toBe(opener);
});
it('navigates only visible photos in filtered chronological order',async()=>{
  const template=service.photos[0];
  service={...service,workflow:workflow('review'),photos:[30,10,20].map((time,index)=>({...template,id:'p'+index,uuid:'u'+index,local_id:index,filename:'ordine-'+index+'.jpg',captured_at:time,preview_ready:true})),proposal:{selected:['p0','p1','p2'],shortlist:['p0','p2'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  fireEvent.click(screen.getByRole('checkbox',{name:'Chronological order'}));
  const articles=screen.getAllByRole('article');
  expect(within(articles[0]).getByRole('button',{name:'Open preview ordine-2.jpg'})).toBeTruthy();
  fireEvent.click(within(articles[0]).getByRole('button',{name:'Open preview ordine-2.jpg'}));
  const dialog=await screen.findByRole('dialog',{name:'Photo preview'});
  expect(within(dialog).getByRole('img',{name:'ordine-2.jpg'})).toBeTruthy();
  fireEvent.keyDown(within(dialog).getByRole('button',{name:'Next photo'}),{key:'ArrowRight'});
  expect(within(dialog).getByRole('img',{name:'ordine-0.jpg'})).toBeTruthy();
  expect(within(dialog).queryByRole('img',{name:'ordine-1.jpg'})).toBeNull();
  expect(within(dialog).getByText('2 / 2')).toBeTruthy();
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
});
it('keeps card controls separate from opening the preview',async()=>{
  service={...service,photos:service.photos.map(photo=>({...photo,preview_ready:true}))};
  await workspace();
  fireEvent.click(screen.getAllByRole('checkbox',{name:'Compare'})[0]);
  expect(screen.queryByRole('dialog',{name:'Photo preview'})).toBeNull();
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
});

it('shows a message when preview navigation reaches a photo without a preview',async()=>{
  service={...service,photos:service.photos.map((photo,index)=>({...photo,preview_ready:index===0}))};
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:'Open preview sintetica-0.jpg'}));
  const dialog=await screen.findByRole('dialog',{name:'Photo preview'});
  fireEvent.click(within(dialog).getByRole('button',{name:'Next photo'}));
  expect(within(dialog).getByText('sintetica-1.jpg')).toBeTruthy();
  expect(within(dialog).getByText('Preview unavailable')).toBeTruthy();
  expect(within(dialog).queryByRole('img')).toBeNull();
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
});
