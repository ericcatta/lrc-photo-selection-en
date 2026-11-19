import {useEffect,useState,useRef,type ReactNode} from 'react';
import {api,photoPath,servicePath,type Service} from './api';
import {VirtualGrid} from './VirtualGrid';

type Job={plan_id:string;status:string;completed:number;total:number;error:string|null;final_target?:number};
type Resume={plan_id:string;photo_ids:string[];compatible:boolean;reason:string;completed:number;total:number;final_target:number};
type Usage={unknown_cost_calls?:number;pricing_complete?:boolean;resume?:Resume|null;job:Job|null;spent_usd:number;reserved_usd:number;budget_usd:number|null;remaining_usd:number|null;api_target?:number;usage?:{input_tokens:number;output_tokens:number};receipts?:{request_id:string;plan_id:string;response_id:string|null;model:string;usage:{input_tokens:number;output_tokens:number}|null;cost_usd:number|null;reserved_usd:number;pricing_unknown?:boolean}[];cost_basis?:string};
type Estimate={pricing_complete?:boolean;unknown_cost_calls?:number;plan_id:string;service_id:string;revision:number;model:string;instructions:string;criteria:string[];photos:{id:string;filename:string;preview_sha256:string;cached:boolean}[];photo_count:number;uncached_count:number;cached_count:number;pricing_known?:boolean;estimated_cost_usd:number|null;reserve_usd:number|null;guard_usd?:number|null;final_target:number;request_count?:number;interpretation_request_count?:number;collection_request_count?:number;collection_sheet_count?:number;budget_usd:number|null;spent_usd:number;reserved_usd:number;remaining_usd:number|null;can_confirm:boolean;pricing:{input_per_million:number|null;output_per_million:number|null;verified_at:string|null;source:string|null};warnings:string[]};
const usd=(value:number|null|undefined)=>typeof value==="number"&&Number.isFinite(value)?new Intl.NumberFormat('en-GB',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:4}).format(value):'unavailable';
const active=(job:Job|null|undefined)=>Boolean(job&&['queued','running','cancel_requested'].includes(job.status));
const jobLabel:Record<string,string>={estimated:'Estimate ready',queued:'Queued',running:'Running',cancel_requested:'Cancellation requested',completed:'Completed',blocked:'Request needs clarification',paused:'Paused',cancelled:'Interrupted'};
const validUsage=(usage:unknown):usage is {input_tokens:number;output_tokens:number}=>Boolean(usage&&typeof usage==='object'&&Number.isFinite((usage as {input_tokens?:number}).input_tokens)&&Number.isFinite((usage as {output_tokens?:number}).output_tokens));
const describe=(e:unknown)=>e instanceof Error?e.message:'The operation could not be completed.';

export function APIReview({service:s,dirty,disabled,update,openRequest=0,hideEntry=false,entryLabel,onStarted}:{service:Service;dirty:boolean;disabled:boolean;update:(s:Service)=>void;openRequest?:number;hideEntry?:boolean;entryLabel?:string;onStarted?:()=>void}){
  const path=servicePath(s.id);
  const openedRequest=useRef(0);
  const summary=useRef<HTMLElement>(null);
  const budgetDetails=useRef<HTMLDetailsElement>(null);
  const budgetInput=useRef<HTMLInputElement>(null);
  function editBudget(){if(budgetDetails.current)budgetDetails.current.open=true;budgetInput.current?.focus();}
  const [open,setOpen]=useState(false),[budget,setBudget]=useState(''),[selected,setSelected]=useState<string[]>([]);
  const [usage,setUsage]=useState<Usage|null>(null),[estimate,setEstimate]=useState<Estimate|null>(null);
  const [ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [showAll,setShowAll]=useState(false);
  const [showExactList,setShowExactList]=useState(false);
  const [target,setTarget]=useState(s.proposal?.api_target??s.settings.target);
  const eligible=s.photos.filter(p=>p.preview_ready);
  const eligibleIds=new Set(eligible.map(photo=>photo.id));
  const selectedIds=new Set(selected);
  const pickerPhotos=eligible.filter(photo=>showAll||selectedIds.has(photo.id));
  const readyForAPI=s.status==='ready'||s.status==='analyzing'||active(usage?.job);
  const validTarget=Number.isInteger(target)&&target>=1&&target<=s.photos.length;
  useEffect(()=>{setEstimate(null);setAck(false);setShowExactList(false);},[s.revision,dirty]);
  async function status(){const next=await api<Usage>(path+'/api-status');setUsage(next);return next;}
  useEffect(()=>{
    if(!open&&!active(usage?.job))return;
    let alive=true;
    const timer=window.setInterval(()=>{void api<Usage>(path+'/api-status').then(next=>{if(!alive)return;setUsage(next);if(!active(next.job))void api<Service>(path).then(update).catch(()=>{});}).catch(e=>{if(alive)setError(describe(e));});},1200);
    return()=>{alive=false;window.clearInterval(timer);};
  },[open,path,usage?.job?.status,update]);
  async function show(){
    setOpen(true);setError('');setEstimate(null);setAck(false);setBusy(true);
    const initial=s.settings.workflow_path==='openai'?s.photos.map(p=>p.id):s.proposal?.effective_shortlist??s.proposal?.shortlist??s.selected_ids??s.photos.map(p=>p.id);
    setSelected(initial.filter(id=>eligibleIds.has(id)));
    try{const next=await status();if(next.resume?.compatible){setSelected(next.resume.photo_ids.filter(id=>eligibleIds.has(id)));}setBudget(next.budget_usd==null?'':String(next.budget_usd));const currentTarget=next.job&&s.proposal?.api_plan_id===next.job.plan_id?s.proposal.api_target:undefined;setTarget(currentTarget??(next.resume?.compatible?next.resume.final_target:undefined)??next.job?.final_target??next.api_target??s.proposal?.api_target??Math.min(s.settings.target,eligible.length||1));}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  useEffect(()=>{if(openRequest>0&&openedRequest.current!==openRequest){openedRequest.current=openRequest;void show();}},[openRequest]);
  useEffect(()=>{if(estimate)summary.current?.focus();},[estimate]);
  function changeSelection(ids:string[]){setSelected(ids);setEstimate(null);setAck(false);}
  async function calculate(){
    setBusy(true);setError('');setAck(false);setEstimate(null);setShowExactList(false);
    try{setEstimate(await api<Estimate>(path+'/api-estimate','POST',{revision:s.revision,budget_usd:budget.trim()?Number(budget):null,photo_ids:selected,target}));await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  async function confirm(){
    if(!estimate||!ack||!estimate.can_confirm||dirty||estimate.revision!==s.revision)return;
    setBusy(true);setError('');
    try{await api(path+'/api-confirm','POST',{plan_id:estimate.plan_id,confirm:true,...(!estimatePriced?{allow_unpriced:true}:{})});setEstimate(null);setAck(false);setOpen(false);onStarted?.();await status();update(await api<Service>(path));}catch(e){setError(describe(e));setEstimate(null);setAck(false);}finally{setBusy(false);}
  }
  async function cancel(){
    if(!usage?.job)return;
    setBusy(true);setError('');try{await api(path+'/api-cancel','POST',{plan_id:usage.job.plan_id});await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  async function reselect(){
    if(!usage?.job||!validTarget)return;setBusy(true);setError('');try{update(await api<Service>(path+'/api-reselect','POST',{revision:s.revision,plan_id:usage.job.plan_id,target}));await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  const estimatePriced=Boolean(estimate&&estimate.pricing_known!==false&&typeof estimate.pricing.input_per_million==="number"&&typeof estimate.pricing.output_per_million==="number"&&estimate.reserve_usd!==null);
  const validBudget=!budget.trim()||(Number.isFinite(Number(budget))&&Number(budget)>0);
  return <section className="tool-section api-review-entry">
    <button hidden={hideEntry} type="button" disabled={Boolean(s.archived)||dirty||!readyForAPI} onClick={()=>void show()}>{entryLabel??"Estimate and review OpenAI send"}</button>
    <p hidden={hideEntry} className="hint">You can send imported previews directly or start with the local proposal. Choose the photos and always confirm the summary before sending.</p>
    {dirty&&<p className="hint">Save the service criteria first.</p>}
    {!open&&error&&<p role="alert" className="warning">{error}</p>}
    {open&&<ReviewDialog close={()=>{setOpen(false);setEstimate(null);setAck(false);}}>
      <div className="modal-heading"><h2 id="api-review-title">Send to OpenAI · {s.title}</h2><button type="button" aria-label="Close OpenAI send" onClick={()=>{setOpen(false);setEstimate(null);setAck(false);}}>Close</button></div>
      <p>Only the listed previews and derived contact sheets will be sent to OpenAI after your confirmation. No ratings are applied.</p>
      {usage&&<p>{usage.pricing_complete===false?'Usage with known pricing':'Recorded usage'}: {usd(usage.spent_usd)} · Reserved or uncertain: {usd(usage.reserved_usd)}{usage.pricing_complete===false?' · Remaining budget not verifiable'+(usage.budget_usd==null?'':' · Saved budget: '+usd(usage.budget_usd)):usage.remaining_usd==null?' · No overall budget set':' · Available budget: '+usd(usage.remaining_usd)}</p>}
      {Boolean(usage?.unknown_cost_calls)&&<p className="warning">{usage?.unknown_cost_calls} requests without available pricing: the app cannot verify the total cost or remaining budget.</p>}
      <details><summary>Usage and request log</summary>{validUsage(usage?.usage)&&<p className="hint">Recorded tokens: {usage.usage.input_tokens} input · {usage.usage.output_tokens} output. {usage.cost_basis}</p>}
      {Boolean(usage?.receipts?.length)&&<details><summary>API request log</summary><ul>{usage?.receipts?.map(r=><li key={r.request_id}>{r.model} · {r.response_id??'uncertain outcome'} · {r.reserved_usd>0?'Uncertain outcome/cost, reserve '+usd(r.reserved_usd):r.pricing_unknown?'Pricing unavailable, cost not calculated':r.cost_usd===null?'Uncertain cost, reserve retained':usd(r.cost_usd)}{validUsage(r.usage)?' · '+r.usage.input_tokens+' input / '+r.usage.output_tokens+' output':''}</li>)}</ul></details>}
      </details>
      {usage?.resume&&<p role="status" className={usage.resume.compatible?"hint":"warning"}>{usage.resume.compatible?`Resuming previous sample: ${usage.resume.completed} assessments completed out of ${usage.resume.total}. The estimate checks which results can be reused.`:usage.resume.reason}</p>}
      {usage?.job&&<div aria-live="polite"><p>API analysis: {jobLabel[usage.job.status]??usage.job.status} · {usage.job.completed}/{usage.job.total}</p>{usage.job.error&&<p className="warning">{usage.job.error}</p>}{active(usage.job)&&<button type="button" disabled={busy} onClick={()=>void cancel()}>Stop after current request</button>}</div>}
      <fieldset disabled={busy||active(usage?.job)}>
        <label>Final OpenAI count<input type="number" min={1} max={s.photos.length} value={Number.isNaN(target)?'':target} onChange={e=>{setTarget(e.target.valueAsNumber);setEstimate(null);setAck(false);}}/></label>
        <p className="hint">Independent of local candidates. After analysis, you can change it using saved assessments without sending again.</p>
        {usage?.job?.status==='completed'&&<button type="button" disabled={!validTarget||dirty||disabled} onClick={()=>void reselect()}>Update final count without new calls</button>}
        <details ref={budgetDetails}><summary>{budget.trim()&&Number.isFinite(Number(budget))?'Optional budget active: '+usd(Number(budget)):'Optional overall budget'}</summary><label>Overall service budget (USD)<input ref={budgetInput} type="number" min="0" step="0.01" placeholder="No additional limit" value={budget} onChange={e=>{setBudget(e.target.value);setEstimate(null);setAck(false);}}/></label><p className="hint">You can leave this blank. With available pricing, the budget includes previous usage and the estimate’s conservative limit also applies. Without pricing, the app cannot verify or enforce a monetary limit. Your OpenAI credit balance is not checked.</p></details>
        <details open={!estimate}><summary>Sample to analyse · {selected.length} previews</summary><div className="api-selection-actions"><button type="button" onClick={()=>changeSelection(eligible.map(p=>p.id))}>All imported previews</button><button type="button" onClick={()=>changeSelection((s.proposal?.effective_shortlist??s.proposal?.shortlist??[]).filter(id=>eligibleIds.has(id)))}>Local proposal only</button><button type="button" onClick={()=>changeSelection([])}>Deselect all</button><label className="check"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>Also show alternatives and other photos</label></div>
        <VirtualGrid className="api-photo-picker" items={pickerPhotos} itemKey={photo=>photo.id} minColumnWidth={210} gap={8} estimatedRowHeight={92} scroll="self" resetKey={String(showAll)} renderItem={p=><label className="api-photo-choice"><input type="checkbox" checked={selectedIds.has(p.id)} onChange={e=>changeSelection(e.target.checked?[...selected,p.id]:selected.filter(id=>id!==p.id))}/><img src={'/api'+photoPath(s.id,p.id)+'/preview'} width={56} height={48} decoding="async" alt='' loading={pickerPhotos.length>100?'eager':"lazy"}/><span>{p.filename}<small>ID {p.id}</small></span></label>}/>

        <p>{selected.length} previews selected</p></details>
        <button type="button" disabled={disabled||!validBudget||!validTarget||!selected.length||dirty||!readyForAPI} onClick={()=>void calculate()}>Calculate estimate without sending photos</button>
        {(!validTarget||!selected.length||!validBudget||dirty||disabled||!readyForAPI)&&<p className="hint" role="status">{dirty?'Save the criteria before preparing the estimate.':!validTarget?`Choose a quantity from 1 to ${s.photos.length}.`:!selected.length?'Select at least one preview.':!validBudget?'Leave the budget blank or enter an amount greater than zero.':'Wait for the current operation to finish.'}</p>}
      </fieldset>
      {estimate&&<section ref={summary} tabIndex={-1} className="api-estimate"><h3>Summary to confirm</h3><p className="hint">Variety assessed across {estimate.photo_count} photos out of {s.photos.length} imported. The comparison covers only this confirmed sample: photos not included do not contribute to the proposal’s variety.</p><p>Model: <strong>{estimate.model}</strong> · {estimate.photo_count} previews · Final target: {estimate.final_target} · New assessments: {estimate.uncached_count} · Cached results: {estimate.cached_count}</p><p>Estimated requests: {estimate.request_count??estimate.uncached_count}{estimate.interpretation_request_count?' · '+estimate.interpretation_request_count+' to interpret the text':''}{estimate.collection_request_count?' · '+estimate.collection_request_count+' to compare the collection':''}</p>{Boolean(estimate.collection_request_count)&&<p className="hint">The collection comparison uses all confirmed previews in {estimate.collection_sheet_count??0} derived contact sheets, together with individual photo assessments. No other photos are included.</p>}{estimatePriced?<><p>Estimate: {usd(estimate.estimated_cost_usd)} · Conservative reserve: <strong>{usd(estimate.reserve_usd)}</strong> · Authorised limit for this send: {usd(estimate.guard_usd??estimate.reserve_usd)}{estimate.budget_usd==null?'':' · Overall budget: '+usd(estimate.budget_usd)}</p><p className="hint">Estimate, not a guaranteed cost. Pricing checked on {estimate.pricing.verified_at}: input {estimate.pricing.input_per_million} USD / million tokens; output {estimate.pricing.output_per_million} USD / million. {estimate.pricing.source&&<a href={estimate.pricing.source} target="_blank" rel="noreferrer">Pricing source</a>}</p></>:<div className="warning" role="alert" id='api-unpriced-warning'><strong>Pricing unavailable for this model.</strong><p>The app cannot calculate an estimate, reserve or verifiable spending limit for this send. OpenAI may charge for the requests.</p>{estimate.budget_usd!=null&&<p>The service budget ({usd(estimate.budget_usd)}) remains saved, but cannot be checked or enforced for calls without pricing.</p>}</div>}

        {estimatePriced&&estimate.pricing_complete===false&&<p className="warning">The estimate and conservative limit cover this send. Some previous requests have no available pricing: the app cannot verify the total cost or remaining overall budget.</p>}
        <details><summary>Original text OpenAI will receive</summary><pre className="api-original-prompt">{estimate.instructions}</pre>{estimate.criteria.length>0&&<><p>Additional service criteria</p><ul>{estimate.criteria.map((c,i)=><li key={i}>{c}</li>)}</ul></>}</details>
        <details open={showExactList} onToggle={event=>setShowExactList(event.currentTarget.open)}><summary>Exact list: {estimate.photos.length} previews</summary>{showExactList&&<ul>{estimate.photos.map(p=><li key={p.id}>{p.filename} · ID {p.id}{p.cached?' · cached result':''}</li>)}</ul>}</details>
        <details><summary>Estimate details and limits</summary>{estimate.warnings.map((warning,i)=><p className="hint" key={i}>{warning}</p>)}</details>
        {!estimate.can_confirm&&<div className="warning" role="alert" id='api-confirm-blocker'>
          <p>{estimatePriced?`Send blocked: available budget (${usd(estimate.remaining_usd??0)}) is below the required reserve (${usd(estimate.reserve_usd)}). You can reduce the previews or change the optional budget, leaving it blank if you do not want an overall limit. Then recalculate the estimate and confirm the send.`:'Sending unavailable. Check the configuration and prepare a new summary before confirming.'}</p>
          {estimatePriced&&<button type="button" disabled={busy} onClick={editBudget}>Edit optional budget</button>}
        </div>}
        <label className="check"><input aria-describedby={!estimate.can_confirm?'api-confirm-blocker':!estimatePriced?'api-unpriced-warning':undefined} type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} disabled={!estimate.can_confirm||busy}/>{estimatePriced?'I confirm sending these previews to OpenAI with my original text and the stated cost limit.':'I confirm sending these previews to OpenAI with my original text, without a cost estimate or a spending limit verifiable in the app.'}</label>
        <button className="primary" type="button" disabled={!ack||!estimate.can_confirm||busy||dirty||estimate.revision!==s.revision} onClick={()=>void confirm()}>Confirm and send to OpenAI</button>
      </section>}
      {error&&<p className="warning" role="alert">{error}</p>}
      <p className="hint">You can close this and continue locally. To resume the API, prepare a new estimate and confirm: valid saved results will be reused.</p>
    </ReviewDialog>}
  </section>;
}

function ReviewDialog({children,close}:{children:ReactNode;close:()=>void}){
  const [dialog,setDialog]=useState<HTMLDialogElement|null>(null);
  useEffect(()=>{if(dialog&&!dialog.open)dialog.showModal();},[dialog]);
  return <dialog ref={setDialog} className="api-review-modal" aria-labelledby="api-review-title" onCancel={e=>{e.preventDefault();close();}}>{children}</dialog>;
}
