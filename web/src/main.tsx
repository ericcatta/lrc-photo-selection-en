import { createRoot } from 'react-dom/client';
import { useEffect, useRef, useCallback, useState, type CSSProperties } from 'react';
import { api, ApiError, photoPath, servicePath, type Plan, type Face, type Photo, type State, type Service, type Summary, type Settings, type Preset } from './api';
import './style.css';
import { OpenAISettings } from './OpenAISettings';
import { APIReview } from './APIReview';
import { GuideButton } from './Guide';
import {workflowPhase,workflowSteps,type WorkflowPhase} from './workflow';

const labels: Record<State,string> = {candidate:'Candidate',preferred:'Preferred',alternative:'Alternative',excluded:'Excluded',review:'To review'};
const states = Object.keys(labels) as State[];
const running = (s:Service) => s.job?.status === 'running' || s.job?.status === 'queued' || s.status === 'applying';
const message = (e:unknown) => e instanceof Error ? e.message : 'The operation could not be completed.';
function Preview({service, photo, zoom}: {service:Service; photo:Photo; zoom?:number}) {
  return <div className={'preview'+(zoom ? ' zoom' : '')}>{photo.preview_ready ? <img style={zoom ? {width: zoom + '%', maxWidth:'none'} : undefined} src={'/api'+photoPath(service.id,photo.id)+'/preview'} loading={zoom?'eager':'lazy'} alt={photo.filename}/> : <span>Preview unavailable</span>}</div>;
}

export function App() {
  const [services,setServices] = useState<Summary[]>([]);
  const [features,setFeatures]=useState(false);
  const [instructionsAvailable,setInstructionsAvailable]=useState(false);
  const [presets,setPresets] = useState<Preset[]>([]);
  const [service,setService] = useState<Service|null>(null);
  const [login,setLogin] = useState(false);
  const [token,setToken] = useState('');
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  async function load() {
    const [all,available] = await Promise.all([api<Summary[]>('/services'),api<Preset[]>('/presets')]);
    setServices(all); setPresets(available); setLogin(false);
    void api<{features:boolean;instructions?:boolean}>('/capabilities').then(x=>{setFeatures(x.features);setInstructionsAvailable(Boolean(x.instructions));}).catch(()=>{setFeatures(false);setInstructionsAvailable(false);});
  }
  async function connect(value:string) {
    setBusy(true); setError('');
    try { await api('/session','POST',{token:value}); setToken(''); await load(); }
    catch(e) {setLogin(true); setError(message(e));}
    finally {setBusy(false);}
  }
  useEffect(() => {
    const fragment = new URLSearchParams(location.hash.slice(1));
    const initial = fragment.get('token');
    if (initial) { history.replaceState(null,'',location.pathname+location.search); void connect(initial); }
    else void load().catch(e => { if(e instanceof ApiError && [401,403].includes(e.status)) setLogin(true); else setError(message(e)); });
  },[]);
  async function refresh() {
    setError('');
    try { await load(); if(service) updateService(await api<Service>(servicePath(service.id))); }
    catch(e) { setError(message(e)); }
  }
  const dirty=useRef(false);
  const updateService=useCallback((next:Service)=>setService(prev=>prev?.id===next.id&&prev.revision<=next.revision?next:prev),[]);
  async function open(id:string) {
    if(id!==service?.id&&dirty.current&&!window.confirm('Discard unsaved criteria?'))return;
    setBusy(true); setError('');
    try { setService(await api<Service>(servicePath(id))); }
    catch(e) { setError(message(e)); }
    finally {setBusy(false);}
  }
  return <div className="app-shell">
    <header className="appbar">
      <div className="brand"><strong>Selection</strong><span>Extension for Lightroom Classic</span></div>
      {!login && <div className="service-controls">
        <label className="service-switch">Service
          <select value={service?.id ?? ''} disabled={busy} onChange={e => {if(e.target.value)void open(e.target.value);}}>
            <option value="" disabled>{services.length ? 'Choose a service' : 'No service imported'}</option>
            {services.map(item => <option key={item.id} value={item.id}>{item.title} · {item.photo_count} photos{item.archived?' · Archived':''}</option>)}
          </select>
        </label>
        <button onClick={refresh} disabled={busy}>Refresh</button>
      </div>}
      <span className="local-status">{service?`${({local:'Local only',hybrid:'Local + OpenAI',openai:'Directly with OpenAI'} as const)[draftPath(service.settings)]} · ${workflowSteps.find(x=>x.id===workflowPhase(service))?.label}`:'Local only'}</span>
    </header>
    <main>
      {!login&&<details className="app-settings"><summary>OpenAI settings</summary><OpenAISettings/></details>}
      {error && <p role="alert" className="warning">{error}</p>}
      {login ? <form className="panel empty" onSubmit={e => {e.preventDefault();void connect(token);}}>
        <p className="eyebrow">Plugin connection</p><h1>Open the local session</h1>
        <p>Open the app from the Lightroom plugin or paste the access token.</p>
        <label>Token<input type="password" value={token} onChange={e=>setToken(e.target.value)} autoComplete="off" required/></label>
        <button className="primary" disabled={busy}>Sign in</button>
      </form> : service ? <Workspace key={service.id} service={service} update={updateService} presets={presets} setPresets={setPresets} dirty={dirty} refreshSummaries={load} features={features} instructionsAvailable={instructionsAvailable}/> :
      <section className="panel empty"><p className="eyebrow">From Lightroom to selection</p>
        <h1>{services.length?'Open a service':'Import a service from Lightroom'}</h1>
        <p>{services.length?'Choose a service from the menu above.':'In Lightroom, select the photos, run “Prepare service”, then click Refresh.'}</p>
      </section>}
    </main>
  </div>;
}

function draftPath(settings:Settings){return settings.workflow_path??settings.mode;}
function unifiedSettings(settings:Settings):Settings {
  const criteria=settings.service_criteria??settings.preset_snapshot?.criteria??[];
  const additions=[...criteria,...(settings.subject_query?[`Subject to prioritise: ${settings.subject_query}`]:[])];
  return {...settings,instructions:settings.instructions+(additions.length?(settings.instructions?'\n\n':'')+additions.join('\n'):''),service_criteria:[],subject_query:''};
}

function Workspace({service:s,update,presets,setPresets,dirty,refreshSummaries,features,instructionsAvailable}:{service:Service;update:(s:Service)=>void;presets:Preset[];setPresets:(p:Preset[])=>void;dirty:{current:boolean};refreshSummaries:()=>Promise<void>;features:boolean;instructionsAvailable:boolean}) {
  const path=servicePath(s.id);
  const serverPhase=workflowPhase(s);
  const [phase,setPhase]=useState<WorkflowPhase>(serverPhase);
  const [apiOpenRequest,setApiOpenRequest]=useState(0);
  const workflowHeading=useRef<HTMLHeadingElement>(null);
  const previousPhase=useRef(serverPhase);
  useEffect(()=>{if(previousPhase.current!==serverPhase){setPhase(serverPhase);previousPhase.current=serverPhase;}},[serverPhase]);
  function navigate(next:WorkflowPhase){setPhase(next);window.requestAnimationFrame(()=>workflowHeading.current?.focus());}
  const route=draftPath(s.settings);
  const [draft,setDraft]=useState<Settings>(()=>unifiedSettings(s.settings));
  const [base,setBase]=useState(()=>unifiedSettings(s.settings));

  const [focused,setFocused]=useState('');
  const [chronological,setChronological]=useState(false);
  const [linked,setLinked]=useState(true);
  const comparison=useRef<HTMLDivElement>(null);
  const mirrored=useRef<HTMLElement|null>(null);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  const [filter,setFilter]=useState<State|'all'>('all');
  const [shortlistOnly,setShortlistOnly]=useState(Boolean(s.proposal?.shortlist?.length));
  const shortlistKey=JSON.stringify(s.proposal?.shortlist);
  useEffect(()=>{setShortlistOnly(Boolean(s.proposal?.shortlist?.length));},[shortlistKey]);
  const [presetChoice,setPresetChoice]=useState(s.settings.preset_id?s.settings.preset_id+':'+s.settings.preset_version:'');
  const [group,setGroup]=useState('');
  const [compare,setCompare]=useState<string[]>([]);
  const [showCompare,setShowCompare]=useState(false);
  const [viewerId,setViewerId]=useState<string|null>(null);
  const [zoom,setZoom]=useState(100);
  const [thumbnailSize,setThumbnailSize]=useState(230);
  const [plan,setPlan]=useState<Plan|null>(null);
  const [showRating,setShowRating]=useState(false);
  const [showAccept,setShowAccept]=useState(false);
  const [presetEdit,setPresetEdit]=useState(false);
  const [presetName,setPresetName]=useState('');
  const [presetInstructions,setPresetInstructions]=useState('');
  const [presetBase,setPresetBase]=useState<Preset|null>(null);
  const [coverage,setCoverage]=useState<{photo:Photo;state:State;locked:boolean}|null>(null);
  const planReceived=plan!==null&&s.receipts.some(r=>r.batch_id===plan.batch_id);
  const confirmed=plan!==null&&s.confirmed_batch_id===plan.batch_id;
  const polling=running(s)||Boolean(s.confirmed_batch_id);
  useEffect(()=>{
    if(!polling)return;
    let current=true, requested=false;
    const timer=window.setInterval(()=>{
      if(requested)return;
      requested=true;
      void api<Service>(path).then(next=>{if(current)update(next);})
        .catch(e=>{if(current)setError(message(e));}).finally(()=>{requested=false;});
    },1200);
    return()=>{current=false;clearInterval(timer);};
  },[path,polling,s.revision,s.status,update]);
  const busy=pending||running(s)||!!s.archived||s.status!=='ready';
  const proposed=new Set([...(s.proposal?.selected??[]),...(s.proposal?.added_candidates??[])]);
  const reviewIds=new Set(s.proposal?.stale?[]:s.proposal?.review_ids??[]);
  const decision=(p:Photo)=>s.decisions[p.id]??{state:reviewIds.has(p.id)?'review' as const:s.proposal&&!proposed.has(p.id)?'alternative' as const:'candidate' as const,locked:false};
  const selectedIds=new Set(s.selected_ids??s.photos.filter(p=>['candidate','preferred','review'].includes(decision(p).state)).map(p=>p.id));
  const cameras=[...new Set(s.photos.map(p=>p.camera).filter(Boolean))];
  const photoMap=new Map(s.photos.map(p=>[p.id,p]));
  const suggestions=new Map(s.interpretations?.comparisons?.map(x=>[x.photo_id,x.other_photo_id]));
  const groups=s.proposal?.groups??[];
  const groupMap=new Map(groups.flatMap(g=>g.members.map(id=>[id,g] as const)));
  const hasProposalList=s.proposal?.shortlist!==undefined;
  const rawShortlist=new Set(s.proposal?.shortlist??[]);
  const draftSelection=hasProposalList&&!s.proposal?.shortlist_accepted&&!s.proposal?.stale&&!s.requires_analysis;
  const shortlist=new Set(draftSelection?(s.proposal?.effective_shortlist??s.photos.filter(p=>{const manual=s.decisions[p.id];return manual?['candidate','preferred','review'].includes(manual.state):rawShortlist.has(p.id);}).map(p=>p.id)):s.proposal?.shortlist??[]);
  const selectionIds=draftSelection?shortlist:selectedIds;
  const shownReviewCount=[...reviewIds].filter(id=>selectionIds.has(id)).length;
  const cardDecision=(p:Photo)=>s.decisions[p.id]??(draftSelection?{state:shortlist.has(p.id)?reviewIds.has(p.id)?'review' as const:'candidate' as const:'excluded' as const,locked:false}:decision(p));
  const failedProposal=s.job?.status==='failed';
  const emptyProposal=draftSelection&&shortlist.size===0&&!failedProposal;
  const filterProposal=shortlistOnly&&!emptyProposal;
  const visible=s.photos.filter(p=>(failedProposal||!filterProposal||shortlist.has(p.id))&&(filter==='all'||cardDecision(p).state===filter)&&(!group||groupMap.get(p.id)?.id===group));
  if(chronological)visible.sort((a,b)=>{
    const time=(p:Photo)=>p.captured_at===null?Infinity:p.captured_at+(s.settings.camera_offsets[p.camera]??0);
    return time(a)-time(b)||a.id.localeCompare(b.id);
  });
  const viewerIndex=viewerId===null?-1:visible.findIndex(photo=>photo.id===viewerId);
  const viewerPhoto=visible[viewerIndex];
  useEffect(()=>{if(viewerId!==null&&viewerIndex<0)setViewerId(null);},[viewerId,viewerIndex]);
  function moveViewer(offset:number){const photo=visible[viewerIndex+offset];if(photo)setViewerId(photo.id);}
  const needsUnifiedSave=Boolean((s.settings.service_criteria??s.settings.preset_snapshot?.criteria??[]).length||s.settings.subject_query);
  const draftChanged=JSON.stringify(draft)!==JSON.stringify(base)||needsUnifiedSave;
  const settingsChanged=JSON.stringify(base)!==JSON.stringify(unifiedSettings(s.settings));
  const staleDraft=settingsChanged&&draftChanged;
  useEffect(()=>{
    if(settingsChanged&&!draftChanged){setBase(unifiedSettings(s.settings));setDraft(unifiedSettings(s.settings));}
  },[settingsChanged,draftChanged,s.settings]);
  useEffect(()=>{
    dirty.current=draftChanged;
    if(!draftChanged)return;
    const warn=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue='';};
    window.addEventListener('beforeunload',warn);
    return()=>{dirty.current=false;window.removeEventListener('beforeunload',warn);};
  },[dirty,draftChanged]);
  const requestSettings=()=>({target:draft.target,preset_id:draft.preset_id,preset_version:draft.preset_version,mode:draft.mode,workflow_path:draft.workflow_path??draft.mode,instructions:draft.instructions,subject_query:'',service_criteria:[],camera_offsets:draft.camera_offsets});
  async function action(work:()=>Promise<void>) {
    setPending(true);setError('');
    try{await work();}catch(e){setError(message(e));if(e instanceof ApiError&&e.status===409){try{const latest=await api<Service>(path);update(latest);}catch{ /* preserve original error */ }}}
    finally{setPending(false);}
  }
  async function save(start:boolean,prepareAPI=false) {await action(async()=>{
    if(staleDraft)return;
    let current=s;
    if(draftChanged){current=await api<Service>(path+'/settings','PUT',{revision:s.revision,settings:requestSettings()});update(current);setDraft(unifiedSettings(current.settings));setBase(unifiedSettings(current.settings));}
    if(prepareAPI){setApiOpenRequest(x=>x+1);}else if(start){navigate('analyze');if((draft.workflow_path??draft.mode)==='openai')setApiOpenRequest(x=>x+1);else update(await api<Service>(path+'/analyze','POST',{revision:current.revision}));}
  });}
  async function decide(photo:Photo,state:State,locked:boolean,confirm_last=false){await action(async()=>{
    try{const next=await api<Service>(path+'/decisions/'+encodeURIComponent(photo.id),'PATCH',{revision:s.revision,state,locked,confirm_last}); update(next);setCoverage(null);}
    catch(e){if(e instanceof ApiError&&e.status===409&&!confirm_last&&(e.detail as {code?:string})?.code==='last_candidate'){setCoverage({photo,state,locked});return;}throw e;}
  });}
  const changeHistory=(direction:'undo'|'redo')=>action(async()=>{
    update(await api<Service>(path+'/'+direction,'POST',{revision:s.revision}));
  });
  const replace=(from:string,to:string)=>action(async()=>{
    update(await api<Service>(path+'/replace','POST',{revision:s.revision,from_photo_id:from,to_photo_id:to}));
  });
  const archive=()=>action(async()=>{
    update(await api<Service>(path+'/archive','PUT',{revision:s.revision,archived:!s.archived}));
    await refreshSummaries();
  });
  function mirrorScroll(source:HTMLElement) {
    if(!linked)return;
    if(mirrored.current===source){mirrored.current=null;return;}
    const target=Array.from(comparison.current?.querySelectorAll<HTMLElement>('.zoom')??[]).find(el=>el!==source);
    if(!target)return;
    const left=source.scrollLeft/Math.max(1,source.scrollWidth-source.clientWidth)*(target.scrollWidth-target.clientWidth);
    const top=source.scrollTop/Math.max(1,source.scrollHeight-source.clientHeight)*(target.scrollHeight-target.clientHeight);
    if(Math.abs(target.scrollLeft-left)<1&&Math.abs(target.scrollTop-top)<1)return;
    mirrored.current=target;target.scrollLeft=left;target.scrollTop=top;
  }
  useEffect(()=>{
    function onKey(e:KeyboardEvent) {
      const element=e.target instanceof HTMLElement?e.target:null;
      if(viewerId!==null||e.defaultPrevented||e.repeat||element?.closest('input,textarea,select,button,[contenteditable],dialog')||showRating||showAccept||showCompare||presetEdit||coverage)return;
      const key=e.key.toLowerCase();
      if((e.metaKey||e.ctrlKey)&&key==='z'&&!e.altKey){
        if(!busy&&(e.shiftKey?s.can_redo:s.can_undo)){e.preventDefault();void changeHistory(e.shiftKey?'redo':'undo');}
        return;
      }
      if(e.metaKey||e.ctrlKey||e.altKey)return;
      if(key==='v'&&compare.length===2){e.preventDefault();setZoom(100);setShowCompare(true);return;}
      const cards=visible;
      const index=cards.findIndex(p=>p.id===focused);
      if(key==='arrowleft'||key==='arrowright'){
        const photo=cards[Math.min(cards.length-1,Math.max(0,index+(key==='arrowleft'?-1:1)))];
        if(photo){e.preventDefault();document.getElementById('photo-'+photo.id)?.focus();}
        return;
      }
      const photo=cards[index];
      if(!photo)return;
      if(key==='c'){e.preventDefault();chooseCompare(photo.id);}
      if(!busy&&(key==='m'||key==='x')){e.preventDefault();void decide(photo,key==='m'?'candidate':'excluded',decision(photo).locked);}
    }
    window.addEventListener('keydown',onKey);
    return()=>window.removeEventListener('keydown',onKey);
  });
  function chooseCompare(id:string){setCompare(prev=>prev.includes(id)?prev.filter(x=>x!==id):prev.length===2?[prev[1],id]:[...prev,id]);}
  function editPreset(base:Preset|null){setPresetBase(base);setPresetName(base?.name??'');setPresetInstructions(draft.instructions);setPresetEdit(true);}
  async function savePreset(){await action(async()=>{const values={name:presetName.trim(),subject_query:'',instructions:presetInstructions,criteria:[]};const p=presetBase?await api<Preset>('/presets/'+encodeURIComponent(presetBase.id),'PUT',{...values,version:presetBase.version}):await api<Preset>('/presets','POST',values);setPresets([...presets.filter(x=>x.id!==p.id),p]);applyPreset(p);setPresetEdit(false);});}
  const offer=presets.find(p=>p.id+':'+p.version===presetChoice);
  function applyPreset(p:Preset){setPresetChoice(p.id+':'+p.version);setDraft(unifiedSettings({...draft,preset_id:p.id,preset_version:p.version,preset_snapshot:p,service_criteria:[...p.criteria],subject_query:p.subject_query??'',instructions:p.instructions??''}));}
  const snapshot=draft.preset_snapshot;
  const analysisInProgress=s.status==='analyzing'||s.job?.status==='running'||s.job?.status==='queued';
  const outdatedProposal=Boolean(s.requires_analysis||s.proposal?.stale||draftChanged);
  const currentProposal=!analysisInProgress&&!outdatedProposal;
  const draftRoute=draft.workflow_path??draft.mode;
  const apiProposal=Boolean(s.proposal?.api_plan_id);
  const interruptedAPI=s.job?.kind==='openai'&&['interrupted','failed','paused','cancelled'].includes(s.job.status);
  const needsLocal=!instructionsAvailable&&Boolean(draft.instructions.trim())&&draftRoute!=='openai'&&!s.workflow?.blocked;
  const ratingBlocked=busy||Boolean(s.proposal?.shortlist&&!s.proposal.shortlist_accepted)||s.requires_analysis||s.proposal?.stale||!selectedIds.size||draftChanged||s.status!=='ready';
  const effectiveTarget=s.workflow?.target??(apiProposal?s.proposal?.api_target??s.settings.target:s.settings.target);
  const currentCount=draftSelection?shortlist.size:selectedIds.size;
  const currentOutcome=s.workflow?s.workflow.outcome:s.receipts.length?{applied:s.receipts.at(-1)!.results.filter(x=>x.status==='applied').length,skipped:s.receipts.at(-1)!.results.filter(x=>x.status==='skipped').length,conflict:s.receipts.at(-1)!.results.filter(x=>x.status==='conflict').length,uncertain:s.receipts.at(-1)!.results.filter(x=>x.status==='uncertain').length,total:s.receipts.at(-1)!.results.length}:null;
  const valid=Number.isInteger(draft.target)&&draft.target>=1&&draft.target<=s.photos.length;
  return <>
    <div className="workspace">
      <header className="top">
        <div className="service-heading"><p className="eyebrow">Imported service</p><h1>{s.title}</h1><p className="selection-count">{!currentProposal&&s.proposal&&!failedProposal?'Previous results · ':''}{failedProposal?`${s.photos.length} photos available · ${selectedIds.size} current candidates`:s.proposal?.shortlist&&!s.proposal.shortlist_accepted ? `${shortlist.size} proposals to review · ${s.photos.length} photos available` : `${selectedIds.size} candidates out of ${s.photos.length} photos`}</p></div>
        <GuideButton/>
      </header>
      <section className="workflow-panel" aria-label="Service workflow">
        <nav aria-label="Selection steps">{workflowSteps.map((step,index)=><button key={step.id} type="button" aria-current={phase===step.id?'step':undefined} onClick={()=>navigate(step.id)}><span>{index+1}</span>{step.label}</button>)}</nav>
        <div className="workflow-next">
          <div><h2 ref={workflowHeading} tabIndex={-1}>{workflowSteps.find(x=>x.id===phase)?.label}</h2>
            <p>{phase==='configure'?'Choose your instructions and workflow. The contact sheet remains available throughout.':phase==='analyze'?analysisInProgress?'Analysis is running. You can review the contact sheet while you wait.':interruptedAPI?`Analysis interrupted: ${s.job?.completed??0} of ${s.job?.total??0} photos completed. Prepare to resume and check the new estimate.`:route==='hybrid'&&!apiProposal?'Review the local sample, then continue with OpenAI or use the local result.':'Prepare or check the analysis before reviewing your selection.':phase==='review'?emptyProposal?'No photos selected. All photos are visible: edit the criteria or manually include those you want to keep.':`Review the ${currentCount} selected photos, including ${shownReviewCount} to check. Confirm when you are happy with the selection.`:phase==='lightroom'?s.confirmed_batch_id?'List confirmed in the web app. Continue in the Lightroom plugin.':'Prepare the rating list: existing ratings will be preserved.':'Check the receipt from the Lightroom plugin here.'}</p>
            {s.workflow?.blocked&&<div role="alert" className="warning"><strong>Analysis needs clarification: no new selection has been completed.</strong><ul>{s.workflow.blocked_reasons?.map((reason,index)=><li key={index}>{reason}</li>)}</ul><p>Edit the instructions in Configure or manually include photos in the contact sheet. No new analysis starts automatically.</p>{phase!=='configure'&&<button type="button" onClick={()=>navigate('configure')}>Review criteria</button>}</div>}
            {analysisInProgress&&<p role="status">{s.job?.kind==='openai'?'OpenAI':'Local'} · {s.job?.completed??0} / {s.job?.total??s.photos.length}<progress value={s.job?.completed??0} max={s.job?.total||s.photos.length}/></p>}
          </div>
          <div className="workflow-actions">
            {phase==='configure'&&<><button className="primary" disabled={busy||!valid||staleDraft||needsLocal} onClick={()=>void save(true,Boolean(s.workflow?.blocked&&draftRoute!=='local'))}>{s.workflow?.blocked&&draftRoute!=='local'?(draftChanged?'Save criteria and prepare OpenAI estimate':'Prepare a new OpenAI estimate'):draftRoute==='openai'?'Continue to OpenAI estimate':draftRoute==='hybrid'?'Start local selection':'Start selection'}</button>{(!valid||needsLocal||busy||staleDraft)&&<p className="hint">{staleDraft?'Load the saved criteria in Configure before continuing.':!valid?'Set a quantity between 1 and '+s.photos.length+'.':needsLocal?'The local model is unavailable: configure it or choose Directly with OpenAI.':'Wait for the current operation to finish.'}</p>}</>}
            {phase==='analyze'&&analysisInProgress&&s.job?.kind==='openai'&&<button type="button" onClick={()=>setApiOpenRequest(x=>x+1)}>OpenAI details and cancellation</button>}
            {phase==='analyze'&&!analysisInProgress&&<>{route!=='local'&&<button className="primary" disabled={draftChanged||Boolean(s.archived)} onClick={()=>setApiOpenRequest(x=>x+1)}>{interruptedAPI?'Prepare to resume':apiProposal?'Review OpenAI analysis':'Continue with OpenAI'}</button>}{s.proposal&&!s.proposal.stale&&<button className={route==='local'?'primary':''} onClick={()=>navigate('review')}>{route==='hybrid'&&!apiProposal?'Use local result':'Review proposal'}</button>}{(!s.proposal||s.proposal.stale)&&route==='local'&&<button onClick={()=>navigate('configure')}>Review configuration</button>}{draftChanged&&<p className="hint">Return to Configure and save the instructions before preparing the send.</p>}{s.archived&&<p className="hint">Reopen the service in Service options before preparing the send.</p>}</>}
            {phase==='review'&&<>{emptyProposal&&<button type="button" onClick={()=>navigate('configure')}>Review criteria</button>}<button className="primary" disabled={busy||draftChanged||Boolean(s.proposal?.stale)||!currentCount} onClick={()=>{if(s.proposal?.shortlist&&!s.proposal.shortlist_accepted)setShowAccept(true);else navigate('lightroom');}}>Confirm selection</button>{(busy||!currentCount||!s.proposal||s.proposal.stale||draftChanged)&&<p className="hint">{busy?'Wait for the current operation to finish.':!currentCount?'Include at least one photo to confirm the selection.':s.proposal?.stale||draftChanged?'Settings have changed: return to Configure.':'You can confirm the manual selection or start an analysis from Configure.'}</p>}</>}
            {phase==='lightroom'&&!s.confirmed_batch_id&&<><button className="primary" disabled={ratingBlocked} onClick={()=>{setPlan(null);setShowRating(true);}}>Review ratings <span aria-hidden="true">→</span></button>{ratingBlocked&&<p className="hint">{s.proposal?.shortlist&&!s.proposal.shortlist_accepted?'Confirm the selection in the Review step first.':draftChanged||s.requires_analysis||s.proposal?.stale?'Update the proposal from Configure before preparing ratings.':'Wait for the current operation or choose at least one candidate.'}</p>}</>}
            {phase==='outcome'&&<button onClick={()=>navigate('review')}>Return to selection</button>}
          </div>
        </div>
        {phase==='lightroom'&&s.confirmed_batch_id&&<ol className="workflow-checklist"><li>In Lightroom, open Catalog Settings → Metadata and check that automatic XMP writing is off.</li><li>Open Library → Plug-in Extras → Apply stars.</li><li>In the plugin, acknowledge the XMP check, review the list and confirm.</li><li>Wait for the receipt: it will appear in the Outcome step.</li></ol>}
        {phase==='outcome'&&!currentOutcome&&<p className="hint">No Lightroom receipt is available. Complete the Lightroom step first.</p>}
        {phase==='outcome'&&currentOutcome&&<div className="workflow-outcome"><strong>{currentOutcome.applied} ratings applied</strong><p>{currentOutcome.skipped} skipped · {currentOutcome.conflict+currentOutcome.uncertain} to check</p>{currentOutcome.skipped+currentOutcome.conflict+currentOutcome.uncertain>0&&<p className="warning">Partial outcome: open Lightroom results to check the affected photos.</p>}</div>}
      </section>
      <section className="gallery" aria-label="Review area">
        {error&&<p role="alert" className="warning">{error}</p>}
        {s.archived&&<p role="status" className="warning">Service archived. Reopen it to continue reviewing.</p>}
        {s.status==='applying'&&<p role="status" className="warning">Applying ratings. Complete or resume in the plugin.</p>}
        {failedProposal?<p role="alert" className="warning">{s.job?.error??'Analysis failed: no valid new proposal.'} All photos remain available for review. No attempt starts automatically.</p>:analysisInProgress?<p role="status" className="warning">Analysis running · {s.job?.completed??0} / {s.job?.total??s.photos.length}. {s.proposal?'The visible results belong to the previous proposal.':'The new proposal will be available when analysis finishes.'}</p>:outdatedProposal?<p role="status" className="warning">Settings or photos have changed. Start selection to create a new proposal; previous results do not reflect the current criteria.</p>:s.proposal&&s.proposal.warnings.length>0&&<details className="analysis-details"><summary>Analysis details · {s.proposal.warnings.length} {s.proposal.warnings.length===1?'notice':'notices'}</summary>{[...new Set(s.proposal.warnings)].map((w,i)=><p key={i} className="hint">{w}</p>)}</details>}
        {currentProposal&&currentCount<effectiveTarget&&<p className="warning">The current selection is below the requested number ({effectiveTarget}).</p>}
        <div className="reviewhead">
          <div className="review-title"><h2>Contact sheet</h2><span>{visible.length} photos</span></div>
          <div className="review-filters"><label>Show<select value={filterProposal?'proposal':filter==='review'?'review':'all'} onChange={e=>{setShortlistOnly(e.target.value==='proposal');setFilter(e.target.value==='review'?'review':'all');}}><option value="all">All photos</option>{s.proposal?.shortlist&&<option value="proposal" disabled={emptyProposal}>Proposal ({shortlist.size})</option>}<option value="review">To review</option></select></label>
            <label>State<select value={filter} onChange={e=>{setFilter(e.target.value as State|'all');}}><option value="all">All</option>{states.map(x=><option key={x} value={x}>{labels[x]}</option>)}</select></label>
            {groups.length>0&&<label>Group<select value={group} onChange={e=>{setGroup(e.target.value);}}><option value="">All</option>{groups.map((g,i)=><option key={g.id} value={g.id}>Group {i+1} · {g.members.length} photos</option>)}</select></label>}
            <label className="thumbnail-control">Previews<input aria-label="Preview size" type="range" min={170} max={330} step={10} value={thumbnailSize} onChange={e=>setThumbnailSize(e.target.valueAsNumber)}/></label>
            <button disabled={compare.length!==2} onClick={()=>{setZoom(100);setShowCompare(true);}}>Compare ({compare.length}/2)</button>{compare.length!==2&&<span className="hint">Select two photos using Compare.</span>}
          </div>
        </div>
        <div className="review-history">
          {draftSelection&&!failedProposal&&<><span className="hint">{shortlist.size} photos in the selection to confirm · {shownReviewCount} to review</span><span className="hint">Include or exclude photos, then click Confirm selection. No ratings are applied here.</span></>}
          <button title={!s.can_undo?'No decision to undo':undefined} disabled={busy||!s.can_undo} onClick={()=>void changeHistory('undo')}>Undo decision</button>
          <button title={!s.can_redo?'No decision to redo':undefined} disabled={busy||!s.can_redo} onClick={()=>void changeHistory('redo')}>Redo decision</button>
          <label className="check"><input type="checkbox" checked={chronological} onChange={e=>setChronological(e.target.checked)}/>Chronological order</label>
          <details><summary>Shortcuts</summary><p>← → Navigate · M Keep · X Exclude · C Select for comparison · V Open comparison · ⌘Z Undo · ⇧⌘Z Redo</p></details>
        </div>
        {emptyProposal&&<p role="status" className="empty-selection">No photos proposed. You are viewing all {s.photos.length} available photos, with none automatically included. Use Include on photos you want to keep or review the criteria. No files have been deleted.</p>}
        {visible.length===0&&<p className="empty-filter">{shortlistOnly&&shortlist.size===0?'No photos proposed: review the instructions and notices. All photos remain available when you turn off the filter.':'No photos match the filters.'}</p>}
        <div className="grid" style={{'--thumbnail-size': `${thumbnailSize}px`} as CSSProperties}>
          {visible.map((photo,index)=>{
            const d=cardDecision(photo);const included=selectionIds.has(photo.id);const manual=Boolean(s.decisions[photo.id]);const g=groupMap.get(photo.id);const suggestion=suggestions.get(photo.id);
            return <article className={'card state-'+d.state+(included?' selection-included':' selection-outside')+(compare.includes(photo.id)?' is-compared':'')} key={photo.id} id={'photo-'+photo.id} tabIndex={0} onFocus={()=>setFocused(photo.id)}>
              <div className="photo-topline"><span>{String(index+1).padStart(2,'0')}</span><span>{included?'In selection':'Not selected'}{d.locked?' · Locked':''}</span></div>
              {photo.preview_ready?<button className="photo-preview-trigger" type="button" aria-label={'Open preview '+photo.filename} onClick={event=>{event.currentTarget.focus({preventScroll:true});setViewerId(photo.id);}}><Preview service={s} photo={photo}/></button>:<Preview service={s} photo={photo}/>}
              <div className="cardbody">
                <span className="detail-tag selection-tag">{manual?(included?'Manually included':'Manually excluded'):included?(reviewIds.has(photo.id)?'To review · included in proposal':draftSelection?'Automatic proposal':'Candidate'):'Outside selection'}</span>

                <strong className="filename" title={photo.filename}>{photo.filename}</strong>
                <div className="photo-meta"><span title={photo.camera}>{photo.camera||'Camera not specified'}</span><span className="stars" aria-label={photo.baseline_rating+' stars at import'} title="Rating at import">{'★'.repeat(photo.baseline_rating)}{'☆'.repeat(5-photo.baseline_rating)}</span></div>
                <div className="selection-action"><button type="button" aria-label={(included?'Exclude ':'Include ')+photo.filename} aria-pressed={included} disabled={busy||d.locked} title={d.locked?'Unlock the photo to change its selection':undefined} onClick={()=>void decide(photo,included?'excluded':'candidate',d.locked)}>{included?'Exclude':'Include'}</button></div>
                <div className="photo-controls">
                  <label className="sr" htmlFor={'state-'+photo.id}>State {photo.filename}</label>
                  <select id={'state-'+photo.id} value={d.state} disabled={busy} onChange={e=>void decide(photo,e.target.value as State,d.locked)}>{states.map(x=><option key={x} value={x}>{labels[x]}</option>)}</select>
                  <label className="check"><input type="checkbox" checked={d.locked} disabled={busy} onChange={e=>void decide(photo,d.state,e.target.checked)}/>Lock</label>
                </div>
                {suggestion&&photoMap.has(suggestion)&&<button className="text-button" onClick={()=>{setCompare([photo.id,suggestion]);setZoom(100);setShowCompare(true);}}>Suggested comparison</button>}
                <div className="photo-footer"><label className="check"><input type="checkbox" checked={compare.includes(photo.id)} onChange={()=>chooseCompare(photo.id)}/>Compare</label>
                  {(g||s.proposal?.reasons[photo.id]||s.proposal?.shortlist_reasons?.[photo.id])&&<details className="photo-reason"><summary>Reason</summary>
                    {g&&<p>{!g.representative?'Group without candidates':g.representative===photo.id?'Group representative':('Represented by '+(photoMap.get(g.representative)?.filename??'another photo'))}</p>}
                    <p>{s.proposal?.shortlist_reasons?.[photo.id]??s.proposal?.reasons[photo.id]??g?.reason}</p>
                    {g?.representative&&selectedIds.has(g.representative)&&!selectedIds.has(photo.id)&&!d.locked&&!s.decisions[g.representative]?.locked&&<button disabled={busy} onClick={()=>void replace(g.representative!,photo.id)}>Replace representative</button>}
                  </details>}
                </div>
              </div>
            </article>;
          })}
        </div>
        <footer className="gallery-footer"><span>{s.proposal?(apiProposal?'OpenAI proposal · manual review available':'Local proposal · manual review available'):'Manual selection · all photos start as candidates'}</span><span>Excluding does not delete the file</span></footer>
      </section>
      <aside className="inspector" aria-label="Selection tools">
        <form hidden={phase!=='configure'} className="config" onSubmit={e=>{e.preventDefault();void save(true);}}>
          <div className="panel-heading"><h2>Configure selection</h2>{draftChanged&&<span className="unsaved" role="status">Unsaved</span>}</div>
          {staleDraft&&<p role="alert" className="warning">The saved criteria have changed. <button type="button" onClick={()=>{setBase(unifiedSettings(s.settings));setDraft(unifiedSettings(s.settings));}}>Load saved criteria</button></p>}
          <fieldset disabled={busy||staleDraft}>
            <div className="tool-section target-section">
              <div className="target-heading"><label htmlFor="target-count">{draftRoute==='openai'?'Final OpenAI selection':'Local candidates'}</label><input id="target-count" type="number" min={1} max={s.photos.length} value={Number.isNaN(draft.target)?'':draft.target} required onChange={e=>setDraft({...draft,target:e.target.valueAsNumber})}/></div>
              <input aria-label="Adjust candidate count" aria-describedby="target-help" type="range" min={1} max={s.photos.length} step={1} value={Number.isFinite(draft.target)?Math.min(s.photos.length,Math.max(1,draft.target)):1} onChange={e=>setDraft({...draft,target:e.target.valueAsNumber})}/>
              <div className="range-ends"><span>1</span><span>{s.photos.length} photos</span></div>
              <p id="target-help" className="hint">{draftRoute==='openai'?'Final target, also shown in the summary before sending.':draftRoute==='hybrid'?'Local target. The final OpenAI quantity is chosen separately before sending.':'Indicative minimum number of candidates, with uncertain photos kept in addition.'}</p>
            </div>
            <div className="tool-section">
              <label>Start from a preset<select value={presetChoice} onChange={e=>{const p=presets.find(p=>p.id+':'+p.version===e.target.value);if(p)applyPreset(p);else{setPresetChoice('');setDraft({...draft,preset_id:'',preset_version:0,preset_snapshot:null,service_criteria:[],subject_query:'',instructions:''});}}}>
                <option value="">No preset · custom configuration</option>
                {presetChoice&&!offer&&snapshot&&<option value={presetChoice}>{snapshot.name} · v{snapshot.version} (service copy)</option>}
                {presets.map(p=><option key={p.id} value={p.id+':'+p.version}>{p.name} · v{p.version}</option>)}
              </select></label>
              <div className="preset-actions"><button className="text-button" type="button" onClick={()=>editPreset(null)}>Save as new preset</button>{offer&&<button className="text-button" type="button" onClick={()=>editPreset(offer)}>Update preset</button>}</div>
              <p className="hint">{snapshot ? 'Applied base: '+snapshot.name+' · v'+snapshot.version+'. The text below is an editable copy for this service.' : 'No preset applied. You can configure this service directly.'}</p>
              {snapshot&&<button className="text-button" type="button" onClick={()=>{setPresetChoice('');setDraft({...draft,preset_id:'',preset_version:0,preset_snapshot:null,service_criteria:[],subject_query:'',instructions:''});}}>Remove preset and criteria</button>}
              <label>Workflow<select value={draftRoute} onChange={e=>{const workflow_path=e.target.value as 'local'|'hybrid'|'openai';setDraft({...draft,workflow_path,mode:workflow_path==='local'?'local':'hybrid'});}}><option value="local">Local only</option><option value="hybrid">Local + OpenAI</option><option value="openai">Directly with OpenAI</option></select></label>{draftRoute!=='local'&&<button type="button" className="text-button" onClick={()=>{const details=document.querySelector<HTMLDetailsElement>('.app-settings');if(details){details.open=true;details.scrollIntoView({block:'start'});details.querySelector<HTMLElement>('summary')?.focus();}}}>Configure OpenAI key and model</button>}
            </div>
            <section className="tool-section">
              <h2>Service instructions and criteria</h2>
              <label>Selection instructions<textarea rows={5} value={draft.instructions} placeholder="Describe what you want to keep and compare in this service" onChange={e=>setDraft({...draft,instructions:e.target.value})}/></label>
              {needsLocal&&<p className="warning">The local model needed to apply these instructions is unavailable. Instruction-based selection will be available after configuration.</p>}
              <p className="hint">Describe your priorities freely. You will receive a proposal and any notices about ambiguous or conflicting requests.</p>
            </section>
            {cameras.length>0&&<details className="tool-section disclosure"><summary>Camera synchronisation</summary><p className="hint">Offsets in seconds applied to chronological order in the web app.</p><div className="camera-fields">{cameras.map(c=><label key={c}>{c}<input type="number" step="1" value={draft.camera_offsets[c]??0} onChange={e=>setDraft({...draft,camera_offsets:{...draft.camera_offsets,[c]:Number(e.target.value)}})}/></label>)}</div></details>}
            <div className="tool-section run-section"><div className="run-actions"><button type="button" disabled={!draftChanged||!valid} onClick={()=>void save(false)}>Save criteria</button></div><p className="hint">Review the proposal in the contact sheet. Manual decisions and photos retained for coverage remain visible.</p></div>
          </fieldset>
        </form>
        {draft.mode==='hybrid'&&<APIReview service={s} dirty={draftChanged} disabled={busy} update={update} hideEntry openRequest={apiOpenRequest} onStarted={()=>navigate('analyze')}/>}
        <details className="tool-section secondary-tools"><summary>Service options</summary><button disabled={pending||running(s)||draftChanged||s.status!=='ready'} onClick={()=>void archive()}>{s.archived?'Reopen service':'Archive service'}</button>
        {s.criteria.length>0&&<details className="tool-section disclosure criteria-status"><summary>Criteria status<span className="detail-tag">{s.criteria.filter(c=>c.status!=='supported').length} to check</span></summary><ul>{s.criteria.map((c,i)=><li key={i}><strong>{c.text}</strong><span className="criterion-status">{({partial:'Partially supported',unsupported:'Not applied',supported:'Supported',pending:'Pending analysis',ambiguous:'Ambiguous'} as Record<string,string>)[c.status]??c.status}</span><p>{c.reason}</p></li>)}</ul></details>}
        {features&&<section className="tool-section"><button disabled={busy} onClick={()=>void action(async()=>update(await api<Service>(path+'/features','POST',{revision:s.revision})))}>Analyse local details</button></section>}
        </details>
        {phase==='analyze'&&s.job&&<section className="tool-section job-status" aria-live="polite"><h2>{s.job.kind==='openai'?'OpenAI analysis':'Local analysis'}</h2><p>{({running:'Running',queued:'Queued',completed:'Completed',completed_with_warnings:'Completed · cases to review',interrupted:'Interrupted',failed:'Failed'} as Record<string,string>)[s.job.status]??s.job.status} · {s.job.completed} / {s.job.total}</p>{s.job.status==='running'&&<progress value={s.job.completed} max={s.job.total||1}/>} {s.job.error&&<p className="warning">{s.job.error}</p>}</section>}
        {phase==='outcome'&&s.receipts.length>0&&<section className="tool-section"><h2>{currentOutcome?'Lightroom results':'Previous Lightroom results'}</h2>{s.receipts.map(r=><details key={r.batch_id}><summary>{r.results.filter(i=>i.status==='applied').length} ratings applied · {r.results.length} photos checked</summary><ul>{r.results.map(i=><li key={i.photo_id}>{photoMap.get(i.photo_id)?.filename??i.photo_id}: {({applied:'Applied',skipped:'Skipped',conflict:'Conflict',uncertain:'To check'} as Record<string,string>)[i.status]??i.status} — {i.reason}</li>)}</ul></details>)}</section>}
      </aside>
    </div>
    {viewerPhoto&&<Modal title="Photo preview" className="photo-viewer" close={()=>setViewerId(null)} onKeyDownCapture={e=>{if(e.altKey||e.ctrlKey||e.metaKey)return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();e.stopPropagation();moveViewer(e.key==='ArrowLeft'?-1:1);}else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();setViewerId(null);}}}>
      <p className="viewer-caption" aria-live="polite"><strong>{viewerPhoto.filename}</strong><span>{viewerIndex+1} / {visible.length}</span></p>
      <figure className="viewer-image">{viewerPhoto.preview_ready?<img src={'/api'+photoPath(s.id,viewerPhoto.id)+'/preview'} alt={viewerPhoto.filename}/>:<span className="viewer-unavailable">Preview unavailable</span>}</figure>
      <div className="viewer-navigation"><button type="button" aria-label="Previous photo" disabled={viewerIndex<=0} onClick={()=>moveViewer(-1)}>← Previous</button><p className="hint">Local preview · ← → to navigate · Esc to close</p><button type="button" aria-label="Next photo" disabled={viewerIndex>=visible.length-1} onClick={()=>moveViewer(1)}>Next →</button></div>
    </Modal>}
    {showCompare&&<Modal title="Compare previews" close={()=>setShowCompare(false)}><p className="hint">Zoom is relative to the view. Previews may not be sufficient to judge the original’s sharpness.</p><label>Zoom {zoom}%<input type="range" min={100} max={300} step={10} value={zoom} onChange={e=>setZoom(e.target.valueAsNumber)}/></label><label className="check"><input type="checkbox" checked={linked} onChange={e=>{mirrored.current=null;setLinked(e.target.checked);}}/>Link scrolling</label><div className="comparison" ref={comparison}>{compare.map(id=>{const p=photoMap.get(id);return p&&<ComparisonPhoto key={id} service={s} photo={p} zoom={zoom} onScroll={mirrorScroll}/>;})}</div></Modal>}
    {showAccept&&<Modal title="Use proposal as selection" close={()=>setShowAccept(false)}><p>Confirm {shortlist.size} photos in the selection, including your manual changes. Other photos remain accessible outside the proposal; previous manual decisions take priority.</p><p className="warning">This may leave situations without candidates: check before confirming.</p><p>No ratings are applied. You can undo this choice from the contact sheet.</p><button className="primary" disabled={busy||draftChanged||s.proposal?.stale||!shortlist.size} onClick={()=>void action(async()=>{update(await api<Service>(path+'/accept-shortlist','POST',{revision:s.revision,confirm_last:true}));setShowAccept(false);navigate('lightroom');})}>Confirm candidates</button>{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
    {showRating&&<Modal title="Review ratings" close={()=>setShowRating(false)}><p>{selectedIds.size} candidates out of {s.photos.length} photos. {s.proposal?'The proposal includes manual decisions.':'Manual selection; no analysis has been run.'}</p><p>The plugin can assign one star to eligible candidates with zero stars. Before applying, verify that automatic metadata writing to files is disabled.</p>{plan?<><p role="status"><strong>{plan.items.length} proposed changes</strong> · revision {plan.revision}</p><p>{selectedIds.size} candidates: {plan.items.length} new ratings. Existing ratings are preserved.</p>{plan.items.length===0&&<p>No changes needed: no new ratings to assign. Use “Show candidates in Lightroom” to find the selection.</p>}{plan.warnings.map((w,i)=><p className="warning" key={i}>{w}</p>)}{plan.items.length>0&&<><p>Confirm this list and open “Apply stars” in the plugin. Check automatic metadata writing and confirm in Lightroom.</p><ul className="planlist">{plan.items.map(i=><li key={i.photo_id}>{i.filename??photoMap.get(i.photo_id)?.filename??i.photo_id} · ID {i.local_id} · {i.expected_rating} → 1 ★</li>)}</ul>{planReceived?<p role="status">Operation recorded. See Lightroom results.</p>:plan.revision!==s.revision?<p role="alert">Plan out of date. Close and prepare a new preview.</p>:confirmed?<div role="status"><p>Plan confirmed · {plan.batch_id}</p><ol><li>Close this window and return to Lightroom.</li><li>Open Library → Plug-in Extras → Apply stars.</li><li>Check XMP, tick the acknowledgement in the plugin and confirm the list.</li></ol></div>:<button className="primary" disabled={busy||draftChanged} onClick={()=>void action(async()=>{await api(path+'/rating-plan/confirm','POST',{batch_id:plan.batch_id});update(await api<Service>(path));})}>Confirm list for Lightroom</button>}</>}</>:<button className="primary" disabled={busy} onClick={()=>void action(async()=>setPlan(await api<Plan>(path+'/rating-plan','POST',{revision:s.revision})))}>Prepare changes preview</button>}{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
    {presetEdit&&<Modal title={presetBase?'Edit preset':'New preset'} close={()=>setPresetEdit(false)}><form onSubmit={e=>{e.preventDefault();void savePreset();}}><label>Name<input value={presetName} onChange={e=>setPresetName(e.target.value)} required/></label><label>Preset instructions<textarea rows={4} value={presetInstructions} onChange={e=>setPresetInstructions(e.target.value)}/></label><p>Existing services keep their saved revision.</p><button className="primary" disabled={busy||!presetName.trim()}>Save preset</button>{error&&<p role="alert" className="warning">{error}</p>}</form></Modal>}
    {coverage&&<Modal title="Last candidate in group" close={()=>setCoverage(null)}><p>This group will have no candidates after changing {coverage.photo.filename}.</p><button className="primary" disabled={busy} onClick={()=>void decide(coverage.photo,coverage.state,coverage.locked,true)}>Confirm change</button>{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
  </>;
}
function ComparisonPhoto({service,photo,zoom,onScroll}:{service:Service;photo:Photo;zoom:number;onScroll:(el:HTMLElement)=>void}) {
  const [size,setSize]=useState<{width:number;height:number}|null>(null);
  const faces=service.interpretations?.records[photo.id]?.faces?.observations?.filter(validFace)??[];
  return <figure>
    <div className="preview zoom" tabIndex={0} aria-label={'Scroll preview of '+photo.filename} onScroll={e=>onScroll(e.currentTarget)}>
      {photo.preview_ready?<img src={'/api'+photoPath(service.id,photo.id)+'/preview'} style={{width:zoom+'%',maxWidth:'none'}} alt={photo.filename}
        onLoad={e=>setSize({width:e.currentTarget.naturalWidth,height:e.currentTarget.naturalHeight})}/>:<span>Preview unavailable</span>}
    </div>
    <figcaption>{photo.filename}{size&&<span className="hint"> · Preview {size.width} × {size.height} px</span>}</figcaption>
    {photo.preview_ready&&size&&faces.length>0&&<details className="face-details"><summary>Detected face details</summary>
      <div className="face-crops">{faces.map((face,i)=><div className="face-crop" key={i} style={{aspectRatio:face.width*size.width/(face.height*size.height)}}>
        <img alt={'Detected face '+(i+1)} src={'/api'+photoPath(service.id,photo.id)+'/preview'} loading="lazy" style={{width:100/face.width+'%',height:100/face.height+'%',left:-100*face.x/face.width+'%',top:-100*(1-face.y-face.height)/face.height+'%'}}/>
      </div>)}</div>
      <p className="hint">Faces detected locally, not identified. Detection may miss people.</p>
    </details>}
  </figure>;
}
function validFace(face:Face) {
  return [face.x,face.y,face.width,face.height].every(Number.isFinite)&&face.x>=0&&face.y>=0&&face.width>0&&face.height>0&&face.x+face.width<=1.001&&face.y+face.height<=1.001;
}
function Modal({title,close,children,className,onKeyDownCapture}:{title:string;close:()=>void;children:React.ReactNode;className?:string;onKeyDownCapture?:React.KeyboardEventHandler<HTMLDialogElement>}) {
  const [dialog,setDialog]=useState<HTMLDialogElement|null>(null);
  useEffect(()=>{if(!dialog)return;const opener=document.activeElement instanceof HTMLElement?document.activeElement:null;if(!dialog.open)dialog.showModal();return()=>{if(opener?.isConnected)opener.focus({preventScroll:true});};},[dialog]);
  return <dialog ref={setDialog} className={className} onKeyDownCapture={onKeyDownCapture} onCancel={e=>{e.preventDefault();close();}} aria-label={title}><header className="reviewhead"><h2>{title}</h2><button onClick={close}>Close</button></header>{children}</dialog>;
}
const root = document.getElementById('root');
if (root) createRoot(root).render(<App/>);
