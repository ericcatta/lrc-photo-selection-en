// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {OpenAISettings} from './OpenAISettings';

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('keeps the key ephemeral and saves configuration without starting analysis',async()=>{
  const calls:{url:string;body?:Record<string,unknown>}[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;
    calls.push({url,body});
    if(url==='/api/openai/models')return new Response(JSON.stringify({models:[{id:'gpt-5.4-mini-2026-03-17',label:'GPT-5.4 mini',input_per_million:.75,output_per_million:4.5,available:null}],checked_at:null}),{headers:{'Content-Type':'application/json'}});
    return new Response(JSON.stringify({configured:Boolean(body),key_configured:Boolean(body),model:body?.model??'',analysis_enabled:false}),{headers:{'Content-Type':'application/json'}});
  }));
  render(<OpenAISettings/>);
  expect(calls).toHaveLength(0);
  fireEvent.click(screen.getByRole('button',{name:'OpenAI configuration'}));
  await waitFor(()=>expect((screen.getByLabelText('API model') as HTMLInputElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('API model'),{target:{value:'gpt-5.4-mini-2026-03-17'}});
  fireEvent.change(screen.getByLabelText('API key'),{target:{value:'synthetic-api-key'}});
  fireEvent.click(screen.getByRole('button',{name:'Save configuration'}));
  await screen.findByRole('status');
  expect((screen.getByLabelText('API key') as HTMLInputElement).value).toBe('');
  expect(calls.find(call=>call.body)).toEqual({url:'/api/openai/config',body:{model:'gpt-5.4-mini-2026-03-17',api_key:'synthetic-api-key'}});
  expect(calls.every(c=>['/api/openai/config','/api/openai/models'].includes(c.url))).toBe(true);
  expect(localStorage.length).toBe(0);
});

it('checks model availability only on explicit click and keeps unavailable models disabled',async()=>{
  const calls:string[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
    calls.push(url);
    const data=url==='/api/openai/config'?{model:'gpt-5.4-mini',key_configured:true}: {models:[{id:'gpt-5.4-mini',label:'Mini',input_per_million:.75,output_per_million:4.5,available:url.endsWith('/refresh')?false:null}],checked_at:null};
    return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
  }));
  render(<OpenAISettings/>);
  fireEvent.click(screen.getByRole('button',{name:'OpenAI configuration'}));
  await waitFor(()=>expect((screen.getByRole('button',{name:'Check available models'}) as HTMLButtonElement).disabled).toBe(false));
  expect(calls).not.toContain('/api/openai/models/refresh');
  fireEvent.click(screen.getByRole('button',{name:'Check available models'}));
  await screen.findByRole('option',{name:'Mini · unavailable'});
  expect((screen.getByRole('option',{name:'Mini · unavailable'}) as HTMLOptionElement).disabled).toBe(true);
  expect((screen.getByRole('button',{name:'Save configuration'}) as HTMLButtonElement).disabled).toBe(true);
});

it('keeps incompatible discovered models visible but disabled',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/config')?{model:'',key_configured:true}:{models:[{id:'future-model',label:'future-model',supported:false,available:true,input_per_million:null,output_per_million:null}],checked_at:'2026-11-18',stale:false}),{headers:{'Content-Type':'application/json'}})));
  render(<OpenAISettings/>);
  fireEvent.click(screen.getByRole('button',{name:'OpenAI configuration'}));
  const option=await screen.findByRole('option',{name:'future-model'});
  expect((option as HTMLOptionElement).disabled).toBe(true);
  expect(screen.getByRole('group',{name:'Models incompatible with photo analysis'})).toBeTruthy();
});
it('allows replacing a key despite stale unavailability and reloads the local model list',async()=>{
  const calls:{url:string;method:string}[]=[];
  let replaced=false;
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const method=init?.method??'GET';calls.push({url,method});
    if(method==='PUT')replaced=true;
    const data=url==='/api/openai/config'?{model:'gpt-5.4-mini',key_configured:true,configured:true}:{models:[{id:'gpt-5.4-mini',label:'Mini',supported:true,available:replaced?null:false,input_per_million:.75,output_per_million:4.5}],checked_at:null};
    return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
  }));
  render(<OpenAISettings/>);
  fireEvent.click(screen.getByRole('button',{name:'OpenAI configuration'}));
  await screen.findByRole('option',{name:'Mini · unavailable'});
  expect((screen.getByRole('button',{name:'Save configuration'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('API key'),{target:{value:'new-synthetic-key'}});
  fireEvent.click(screen.getByRole('button',{name:'Save configuration'}));
  await screen.findByRole('status');
  expect((screen.getByLabelText('API key') as HTMLInputElement).value).toBe('');
  expect(calls.filter(c=>c.url==='/api/openai/models')).toHaveLength(2);
  expect(calls.some(c=>c.url.endsWith('/refresh'))).toBe(false);
});

it('allows a compatible model without known pricing and keeps the current model until explicitly changed',async()=>{
  const calls:{url:string;body?:Record<string,unknown>}[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    const data=url==='/api/openai/config'?{model:body?.model??'mini',key_configured:true,configured:true}:{models:[
      {id:'mini',label:'Mini',supported:true,available:true,pricing_known:true,input_per_million:.75,output_per_million:4.5,compatibility:'verified'},
      {id:'gpt-6.2',label:'GPT-6.2',supported:true,available:true,pricing_known:false,input_per_million:null,output_per_million:null,compatibility:'family',compatibility_note:'Supporto famiglia GPT.'}
    ],checked_at:'2026-11-19',stale:false};
    return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
  }));
  render(<OpenAISettings/>);
  fireEvent.click(screen.getByRole('button',{name:'OpenAI configuration'}));
  const option=await screen.findByRole('option',{name:'GPT-6.2 · available · pricing unavailable'});
  expect((option as HTMLOptionElement).disabled).toBe(false);
  expect((screen.getByLabelText('API model') as HTMLSelectElement).value).toBe('mini');
  fireEvent.change(screen.getByLabelText('API model'),{target:{value:'gpt-6.2'}});
  expect(screen.getByText(/Pricing is unavailable for this model/)).toBeTruthy();
  expect(screen.getByText(/Compatibility inferred from the model family/)).toBeTruthy();
  expect((screen.getByRole('button',{name:'Save configuration'}) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Save configuration'}));
  await screen.findByRole('status');
  expect(calls.find(c=>c.body)?.body).toEqual({model:'gpt-6.2'});
  expect(calls.every(c=>['/api/openai/config','/api/openai/models'].includes(c.url))).toBe(true);
});
