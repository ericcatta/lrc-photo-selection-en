// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {APIReview} from './APIReview';
import type {Service} from './api';

let calls:{url:string;body?:Record<string,unknown>}[];
const original='  Solo uccelli\nPreferisci ali aperte.\n';
const service={id:'synthetic',title:'TEST SINTETICO',revision:4,status:'ready',settings:{mode:'hybrid',instructions:original,target:2},photos:[{id:'p0',filename:'sintetica.jpg',preview_ready:true},{id:'p1',filename:'altra.jpg',preview_ready:true}],proposal:{shortlist:['p0'],stale:false},decisions:{}} as Service;
const initial={job:null,spent_usd:0,reserved_usd:0,budget_usd:null,remaining_usd:null};
function response(value:unknown){return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});}
beforeEach(()=>{
  calls=[];
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','');}});
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    if(url.endsWith('/api-status'))return response(initial);
    if(url.endsWith('/api-estimate'))return response({plan_id:'plan-1',service_id:'synthetic',revision:4,final_target:2,model:'gpt-5.4-mini-2026-03-17',instructions:original,criteria:['Preferisci varianti'],photos:[{id:'p0',filename:'sintetica.jpg',cached:false}],photo_count:1,uncached_count:1,cached_count:0,estimated_cost_usd:.001,reserve_usd:.002,budget_usd:1,spent_usd:0,reserved_usd:0,remaining_usd:1,can_confirm:true,pricing:{input_per_million:.75,output_per_million:4.5,verified_at:'2026-11-18',source:'https://developers.openai.com/api/docs/models/gpt-5.4-mini'},warnings:[]});
    if(url.endsWith('/api-confirm')||url.endsWith('/api-cancel'))return response(initial);
    if(url==='/api/services/synthetic')return response(service);
    throw new Error('Unexpected '+url);
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('estimates locally and only sends after explicit acknowledgement and confirmation',async()=>{
  const started=vi.fn();
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()} onStarted={started}/>);
  expect(calls).toHaveLength(0);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByLabelText('Overall service budget (USD)') as HTMLInputElement).value).toBe(''));
  expect((screen.getByRole('button',{name:'Calculate estimate without sending photos'}) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('Overall service budget (USD)'),{target:{value:'1'}});
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await screen.findByRole('heading',{name:'Summary to confirm'});
  expect(calls.find(c=>c.url.endsWith('/api-estimate'))?.body).toEqual({revision:4,budget_usd:1,photo_ids:['p0'],target:2});
  expect(document.querySelector('.api-original-prompt')?.textContent).toBe(original);
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
  const submit=screen.getByRole('button',{name:'Confirm and send to OpenAI'});
  expect((submit as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('I confirm sending these previews to OpenAI with my original text and the stated cost limit.'));
  fireEvent.click(submit);
  await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(true));
  expect(calls.find(c=>c.url.endsWith('/api-confirm'))?.body).toEqual({plan_id:'plan-1',confirm:true});
  await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());
  expect(started).toHaveBeenCalledTimes(1);
});
it('allows adding alternatives to the exact sample and clears the estimate on budget changes',async()=>{
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByLabelText('Overall service budget (USD)') as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByLabelText('Also show alternatives and other photos'));
  fireEvent.click(screen.getByLabelText(/altra.jpg/));
  fireEvent.change(screen.getByLabelText('Overall service budget (USD)'),{target:{value:'1'}});
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await screen.findByRole('heading',{name:'Summary to confirm'});
  expect(calls.find(c=>c.url.endsWith('/api-estimate'))?.body?.photo_ids).toEqual(['p0','p1']);
  fireEvent.change(screen.getByLabelText('Overall service budget (USD)'),{target:{value:'2'}});
  expect(screen.queryByRole('button',{name:'Confirm and send to OpenAI'})).toBeNull();
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});
it('requires saved criteria but allows direct OpenAI without a local proposal',()=>{
  const {rerender}=render(<APIReview service={service} dirty={true} disabled={false} update={vi.fn()}/>);
  expect((screen.getByRole('button',{name:'Estimate and review OpenAI send'}) as HTMLButtonElement).disabled).toBe(true);
  rerender(<APIReview service={{...service,proposal:null}} dirty={false} disabled={false} update={vi.fn()}/>);
  expect((screen.getByRole('button',{name:'Estimate and review OpenAI send'}) as HTMLButtonElement).disabled).toBe(false);
  expect(calls).toHaveLength(0);
});

it('can inspect and cancel an active API run even while the service is busy',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    return response({...initial,job:{plan_id:'active-plan',status:url.endsWith('/api-cancel')?'cancelled':'running',completed:1,total:3,error:null}});
  }));
  render(<APIReview service={service} dirty={false} disabled={true} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  const cancel=await screen.findByRole('button',{name:'Stop after current request'});
  fireEvent.click(cancel);
  await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/api-cancel'))).toBe(true));
  expect(calls.find(c=>c.url.endsWith('/api-cancel'))?.body).toEqual({plan_id:'active-plan'});
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});
it('shows uncertain reserved cost and omits unknown token counts',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({...initial,job:{plan_id:'uncertain',status:'paused',completed:0,total:1,error:'Timeout'},receipts:[{request_id:'uncertain',plan_id:'uncertain',response_id:null,model:'model',usage:{},cost_usd:0,reserved_usd:.003}],usage:{}})));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await screen.findByText(/Uncertain outcome\/cost, reserve/);
  expect(screen.getByText(/API analysis: Paused/)).toBeTruthy();
  expect(document.body.textContent).not.toContain('undefined');
  expect(document.body.textContent).not.toContain('Recorded tokens:');
});

it('estimates without an entered budget and adjusts final quantity without a new API call',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    if(url.endsWith('/api-status'))return response({...initial,api_target:1,job:{plan_id:'complete-plan',status:'completed',completed:2,total:2,error:null,final_target:1}});
    if(url.endsWith('/api-reselect'))return response({...service,revision:5});
    if(url.endsWith('/api-estimate'))return response({plan_id:'p',revision:4,final_target:2,instructions:original,criteria:[],photos:[],warnings:[],pricing:{},estimated_cost_usd:.01,reserve_usd:.02,budget_usd:null});
    return response(service);
  }));
  render(<APIReview service={{...service,proposal:null}} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await screen.findByRole('button',{name:'Update final count without new calls'});
  fireEvent.change(screen.getByLabelText('Final OpenAI count'),{target:{value:'2'}});
  fireEvent.click(screen.getByRole('button',{name:'Update final count without new calls'}));
  await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/api-reselect'))).toBe(true));
  expect(calls.find(c=>c.url.endsWith('/api-reselect'))?.body).toEqual({revision:4,plan_id:'complete-plan',target:2});
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await screen.findByRole('heading',{name:'Summary to confirm'});
  expect(calls.find(c=>c.url.endsWith('/api-estimate'))?.body).toEqual({revision:4,photo_ids:['p0','p1'],budget_usd:null,target:2});
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});

it('retains the reselected final quantity when reopening the same completed plan',async()=>{
  const originalService={...service,proposal:{...service.proposal!,api_plan_id:'completed-plan',api_target:1}};
  const reselected={...originalService,revision:5,proposal:{...originalService.proposal,api_target:2}};
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    if(url.endsWith('/api-reselect'))return response(reselected);
    return response({...initial,job:{plan_id:'completed-plan',status:'completed',completed:2,total:2,error:null,final_target:1}});
  }));
  const update=vi.fn();
  const {rerender}=render(<APIReview service={originalService} dirty={false} disabled={false} update={update}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await screen.findByRole('button',{name:'Update final count without new calls'});
  fireEvent.change(screen.getByLabelText('Final OpenAI count'),{target:{value:'2'}});
  fireEvent.click(screen.getByRole('button',{name:'Update final count without new calls'}));
  await waitFor(()=>expect(update).toHaveBeenCalledWith(reselected));
  rerender(<APIReview service={reselected} dirty={false} disabled={false} update={update}/>);
  fireEvent.click(screen.getByRole('button',{name:'Close OpenAI send'}));
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByLabelText('Final OpenAI count') as HTMLInputElement).value).toBe('2'));
  expect(calls.filter(c=>c.url.endsWith('/api-reselect'))).toHaveLength(1);
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});

it('makes a previously configured budget visible without clearing it',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({...initial,budget_usd:.1,remaining_usd:.08})));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await screen.findByText(/Optional budget active:/);
  expect((screen.getByLabelText('Overall service budget (USD)') as HTMLInputElement).value).toBe('0.1');
});

it('explains insufficient budget beside confirmation and edits it without sending',async()=>{
  const baseFetch=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const result=await baseFetch(input,init);
    if(!input.endsWith('/api-estimate'))return result;
    const plan=await result.json();
    const body=JSON.parse(String(init?.body));
    return response({...plan,reserve_usd:.6901,budget_usd:body.budget_usd,remaining_usd:body.budget_usd,can_confirm:body.budget_usd===null});
  }));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  const budget=screen.getByLabelText('Overall service budget (USD)') as HTMLInputElement;
  await waitFor(()=>expect(budget.disabled).toBe(false));
  fireEvent.change(budget,{target:{value:'0.05'}});
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  const blocker=await screen.findByRole('alert');
  expect(blocker.textContent).toContain('Send blocked: available budget');
  const checkbox=screen.getByLabelText(/I confirm sending these previews to OpenAI/) as HTMLInputElement;
  await waitFor(()=>expect((screen.getByRole('button',{name:'Edit optional budget'}) as HTMLButtonElement).disabled).toBe(false));
  expect(checkbox.disabled).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'Edit optional budget'}));
  expect(document.activeElement).toBe(budget);
  expect(budget.closest('details')?.open).toBe(true);
  expect(budget.value).toBe('0.05');
  fireEvent.change(budget,{target:{value:''}});
  expect(screen.queryByRole('alert')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await waitFor(()=>expect((screen.getByLabelText(/I confirm sending these previews to OpenAI/) as HTMLInputElement).disabled).toBe(false));
  expect((screen.getByLabelText(/I confirm sending these previews to OpenAI/) as HTMLInputElement).checked).toBe(false);
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});

it('restores compatible interrupted sample without estimating or sending',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    calls.push({url,body:init?.body?JSON.parse(String(init.body)):undefined});
    return response({...initial,resume:{plan_id:'old',compatible:true,reason:'',photo_ids:['p1'],completed:15,total:18,final_target:1},job:{plan_id:'old',status:'paused',completed:15,total:18,error:null}});
  }));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()} openRequest={1} hideEntry/>);
  await screen.findByText(/Resuming previous sample: 15/);
  expect(screen.getByLabelText(/altra.jpg/)).toBeTruthy();
  expect(screen.queryByLabelText(/sintetica.jpg/)).toBeNull();
  expect((screen.getByLabelText('Final OpenAI count') as HTMLInputElement).value).toBe('1');
  expect(calls.every(c=>c.url.endsWith('/api-status'))).toBe(true);
});

it('warns when old sample cannot be reused and does not send',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{calls.push({url});return response({...initial,resume:{plan_id:'old',compatible:false,reason:'Criteria changed: prepare a new estimate.',photo_ids:['p1'],completed:15,total:18,final_target:1}});}));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()} openRequest={1}/>);
  await screen.findByText('Criteria changed: prepare a new estimate.');
  expect(screen.getByLabelText(/sintetica.jpg/)).toBeTruthy();
  expect(calls.every(c=>c.url.endsWith('/api-status'))).toBe(true);
});

it('keeps confirmation open when the server rejects the send',async()=>{
  const originalFetch=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>url.endsWith('/api-confirm')
    ?new Response(JSON.stringify({detail:'Estimate out of date: prepare a new estimate.'}),{status:409})
    :originalFetch(url,init)));
  const started=vi.fn();
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()} onStarted={started}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByRole('button',{name:'Calculate estimate without sending photos'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await screen.findByRole('heading',{name:'Summary to confirm'});
  fireEvent.click(screen.getByLabelText('I confirm sending these previews to OpenAI with my original text and the stated cost limit.'));
  fireEvent.click(screen.getByRole('button',{name:'Confirm and send to OpenAI'}));
  await screen.findByText('Estimate out of date: prepare a new estimate.');
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(started).not.toHaveBeenCalled();
});

it('confirms an unpriced model only with explicit unpriced acknowledgement and preserves the saved budget',async()=>{
  const originalFetch=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const result=await originalFetch(url,init);
    if(url.endsWith('/api-status'))return response({...initial,budget_usd:1,remaining_usd:1});
    if(!url.endsWith('/api-estimate'))return result;
    const plan=await result.json();
    return response({...plan,model:'gpt-6.2',pricing_known:false,pricing:{input_per_million:null,output_per_million:null,source:null,verified_at:null},estimated_cost_usd:null,reserve_usd:null,guard_usd:null,budget_usd:1,can_confirm:true});
  }));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByLabelText('Overall service budget (USD)') as HTMLInputElement).value).toBe('1'));
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await screen.findByText('Pricing unavailable for this model.');
  const summary=screen.getByRole('heading',{name:'Summary to confirm'}).closest('section')!;
  expect(summary.textContent).not.toContain('Estimate:');
  expect(summary.textContent).not.toContain('Authorised limit for this send:');
  expect(screen.getByText(/The service budget/).textContent).toContain('remains saved');
  const acknowledgement=screen.getByLabelText('I confirm sending these previews to OpenAI with my original text, without a cost estimate or a spending limit verifiable in the app.');
  expect((screen.getByRole('button',{name:'Confirm and send to OpenAI'}) as HTMLButtonElement).disabled).toBe(true);
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
  fireEvent.click(acknowledgement);
  fireEvent.click(screen.getByRole('button',{name:'Confirm and send to OpenAI'}));
  await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(true));
  expect(calls.find(c=>c.url.endsWith('/api-confirm'))?.body).toEqual({plan_id:'plan-1',confirm:true,allow_unpriced:true});
  expect(calls.find(c=>c.url.endsWith('/api-estimate'))?.body?.budget_usd).toBe(1);
});
it('labels incomplete cost accounting without displaying a false available budget',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({...initial,pricing_complete:false,unknown_cost_calls:2,budget_usd:1,remaining_usd:1,receipts:[{request_id:'unpriced',plan_id:'plan',response_id:'r',model:'gpt-6.2',usage:{input_tokens:20,output_tokens:10},cost_usd:null,reserved_usd:0,pricing_unknown:true}]})));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await screen.findByText(/2 requests without available pricing/);
  expect(screen.getByText(/Usage with known pricing/).textContent).toContain('Remaining budget not verifiable');
  expect(screen.queryByText(/Available budget/)).toBeNull();
  expect(screen.getByText(/Pricing unavailable, cost not calculated/)).toBeTruthy();
});

it('keeps the total-budget uncertainty visible when a priced estimate follows unpriced requests',async()=>{
  const originalFetch=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const result=await originalFetch(url,init);
    if(!url.endsWith('/api-estimate'))return result;
    return response({...await result.json(),pricing_known:true,pricing_complete:false,unknown_cost_calls:1});
  }));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByRole('button',{name:'Calculate estimate without sending photos'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  await screen.findByText(/The estimate and conservative limit cover this send/);
  expect(screen.getByLabelText('I confirm sending these previews to OpenAI with my original text and the stated cost limit.')).toBeTruthy();
  expect(calls.some(call=>call.url.endsWith('/api-confirm'))).toBe(false);
});

it('states the confirmed analysis perimeter without treating the sample as the complete import',async()=>{
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Estimate and review OpenAI send'}));
  await waitFor(()=>expect((screen.getByRole('button',{name:'Calculate estimate without sending photos'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'Calculate estimate without sending photos'}));
  const perimeter=await screen.findByText(/Variety assessed across 1 photos out of 2 imported/);
  expect(perimeter.textContent).toContain('photos not included do not contribute to the proposal’s variety');
  expect(calls.find(call=>call.url.endsWith('/api-estimate'))?.body?.photo_ids).toEqual(['p0']);
  expect(calls.some(call=>call.url.endsWith('/api-confirm'))).toBe(false);
});
