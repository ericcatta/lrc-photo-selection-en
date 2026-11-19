import { useState } from 'react';
import { api } from './api';

type AvailableModel={id:string;label:string;input_per_million:number|null;output_per_million:number|null;available:boolean|null;supported?:boolean;pricing_known?:boolean;compatibility?:'verified'|'family';compatibility_note?:string};
type ModelList={models:AvailableModel[];checked_at:string|null;stale?:boolean;error?:string|null};
type Configuration = {configured:boolean;key_configured:boolean;model:string;analysis_enabled:boolean;error?:string|null};

export function OpenAISettings() {
  const [open,setOpen]=useState(false);
  const [configuration,setConfiguration]=useState<Configuration|null>(null);
  const [model,setModel]=useState('');
  const [models,setModels]=useState<ModelList>({models:[],checked_at:null});
  const [key,setKey]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [saved,setSaved]=useState(false);
  async function show() {
    if(open){setOpen(false);setKey('');return;}
    setOpen(true);setBusy(true);setError('');setSaved(false);
    try {const [result,list]=await Promise.all([api<Configuration>('/openai/config'),api<ModelList>('/openai/models')]);setConfiguration(result);setModel(result.model);setModels(list);}
    catch(e){setError(e instanceof Error?e.message:'Configuration unavailable.');}
    finally{setBusy(false);}
  }
  async function save() {
    setBusy(true);setError('');setSaved(false);
    const submittedKey=key;
    setKey('');
    try {
      const result=await api<Configuration>('/openai/config','PUT',{model,...(submittedKey?{api_key:submittedKey}:{})});
      setConfiguration(result);if(submittedKey)setModels(await api<ModelList>('/openai/models'));setSaved(true);
    } catch(e){setError(e instanceof Error?e.message:'Configuration not saved.');}
    finally{setBusy(false);}
  }
  async function refreshModels(){
    setBusy(true);setError('');try{setModels(await api<ModelList>('/openai/models/refresh','POST',{}));}catch(e){setError(e instanceof Error?e.message:'Model availability check failed.');}finally{setBusy(false);}
  }
  const selectedModel=models.models.find(item=>item.id===model);
  const priceKnown=selectedModel?.pricing_known!==false&&typeof selectedModel?.input_per_million==='number'&&typeof selectedModel?.output_per_million==='number';
  const compatible=models.models.find(item=>item.id===model&&item.supported!==false&&(item.available!==false||Boolean(key)));
  return <section className="openai-settings">
    <button className="text-button" type="button" aria-expanded={open} onClick={()=>void show()}>OpenAI configuration</button>
    {open&&<form onSubmit={e=>{e.preventDefault();void save();}}>
      <h2>Optional OpenAI API</h2>
      <p className="hint">The local backend stores the key in macOS Keychain.</p>
      <label>API model<select value={model} disabled={busy} onChange={e=>setModel(e.target.value)}><option value="">Choose a model</option>{model&&!models.models.some(item=>item.id===model)&&<option value={model}>{model} · refresh the list to check access</option>}{models.models.filter(item=>item.supported!==false).map(item=><option key={item.id} value={item.id} disabled={item.available===false}>{item.label} · {item.available===true?'available':item.available===false?'unavailable':'access needs checking'}{item.pricing_known===false||item.input_per_million===null||item.output_per_million===null?' · pricing unavailable':''}</option>)}{models.models.some(item=>item.supported===false)&&<optgroup label="Models incompatible with photo analysis">{models.models.filter(item=>item.supported===false).map(item=><option key={item.id} value={item.id} disabled>{item.label}</option>)}</optgroup>}</select></label>
      <button type="button" disabled={busy||!configuration?.key_configured} onClick={()=>void refreshModels()}>Check available models</button>
      <p className="hint">This check updates the list from your OpenAI account without sending photos. Models compatible with photo analysis are selectable even without available pricing. Incompatible models are listed separately and cannot be selected.{models.checked_at?' Last checked: '+models.checked_at+'.':''}{models.stale?' List needs refreshing.':''}</p>
      {selectedModel&&<div className="model-details"><p className="hint">{selectedModel.compatibility==='family'?'Compatibility inferred from the model family; actual availability is checked by the API when sending.':'Model compatible with photographic preview analysis.'}{selectedModel.compatibility_note?' '+selectedModel.compatibility_note:''}</p>{priceKnown?<p className="hint">Available pricing: input {selectedModel.input_per_million} USD / million tokens · output {selectedModel.output_per_million} USD / million tokens.</p>:<p className="warning">Pricing is unavailable for this model. You can select it, but before sending you must acknowledge that no estimate or verifiable spending limit is available.</p>}</div>}
      {models.error&&<p className="warning">{models.error}</p>}
      <label>API key<input type="password" value={key} autoComplete="off" spellCheck={false} placeholder={configuration?.key_configured?'Already saved · enter only to replace':'Enter the API key'} disabled={busy} onChange={e=>setKey(e.target.value)}/></label>
      <button type="submit" disabled={busy||!compatible||(!configuration?.key_configured&&!key)}>Save configuration</button>
      {saved&&<p role="status">Configuration saved. Next, prepare the estimate and confirm the send.</p>}
      <p className="hint">Saving the configuration does not send photos. Choose an OpenAI workflow and confirm the send summary. The overall budget is optional. Your credit balance is not checked and no credits are purchased.</p>
      {configuration?.error&&<p className="warning">{configuration.error}</p>}
      {error&&<p className="warning" role="alert">{error}</p>}
    </form>}
  </section>;
}
