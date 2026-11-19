// Synthetic integration smoke only. Requires locally installed Chrome and built web assets.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
await mkdir('.build',{recursive:true});
const profile=await mkdtemp(join(tmpdir(),'lrc-screenshot-chrome-'));
const backend=spawn('.venv/bin/python',['scripts/smoke_fixture.py','--port','18765'],{stdio:'ignore'});
let chrome,ws;
try {
  let ready=false;
  for(let i=0;i<100;i++) {try{ready=(await fetch('http://127.0.0.1:18765/health')).ok;}catch{}if(ready)break;await pause(100);}
  if(!ready)throw new Error('Synthetic backend failed to start');
  chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',[
    '--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run',
    '--no-default-browser-check','--disable-extensions','--disable-background-networking','--disable-sync','about:blank'
  ],{stdio:'ignore'});
  let port;
  for(let i=0;i<200;i++){try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];}catch{}if(port)break;await pause(100);}
  if(!port)throw new Error('Chrome headless did not expose the capture endpoint');
  const target=await (await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
  ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  let next=0;const pending=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const {resolve,reject,timer}=pending.get(m.id);clearTimeout(timer);pending.delete(m.id);m.error?reject(new Error(JSON.stringify(m.error))):resolve(m.result);}});
  function call(method,params={}){return new Promise((resolve,reject)=>{const id=++next;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Timeout '+method));},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});}
  const evaluate=async expression=>(await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result?.value;
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1500,height:1100,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:'http://127.0.0.1:18765/#token=synthetic-ui-test-only'});
  let button=false;
  for(let i=0;i<100;i++){button=await evaluate("Boolean([...document.querySelectorAll('.service-switch option')].find(b=>b.textContent.includes('TEST SINTETICO')))");if(button)break;await pause(100);}
  if(!button)throw new Error('Synthetic service not visible');
  await evaluate("(()=>{const s=document.querySelector('.service-switch select');s.value='synthetic-ui';s.dispatchEvent(new Event('change',{bubbles:true}));})()");
  let count=0;
  for(let i=0;i<100;i++){count=await evaluate("document.querySelectorAll('.grid .card').length");if(count===6)break;await pause(100);}
  if(count!==6)throw new Error('Expected six synthetic cards');
  await evaluate("Promise.all([document.fonts.ready,...[...document.images].map(i=>i.decode().catch(()=>{}))]).then(()=>true)");
  const waitFor=async(expression)=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await pause(100);}throw new Error('UI condition not reached: '+expression+' '+await evaluate("JSON.stringify({workflow:document.querySelector('.workflow-panel')?.textContent,errors:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent)})"));};
  const click=async text=>{const found=await evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)});if(!b||b.disabled)return false;b.click();return true;})()`);if(!found)throw new Error('Button unavailable: '+text);};
  const step=async name=>{const found=await evaluate(`(()=>{const b=[...document.querySelectorAll('.workflow-panel nav button')].find(b=>b.textContent.endsWith(${JSON.stringify(name)}));if(!b)return false;b.click();return true;})()`);if(!found)throw new Error('Workflow step unavailable: '+name);await waitFor(`document.querySelector('.workflow-next h2')?.textContent===${JSON.stringify(name)}`);};
  const request=async(path,method='GET',body)=>await evaluate(`fetch('/api'+${JSON.stringify(path)},{method:${JSON.stringify(method)},headers:{'Content-Type':'application/json'},body:${JSON.stringify(body===undefined?undefined:JSON.stringify(body))}}).then(async r=>({status:r.status,data:await r.json()}))`);
  // Large preview uses only the existing synthetic preview endpoint.
  await evaluate("document.querySelector('.photo-preview-trigger').focus();document.querySelector('.photo-preview-trigger').click()");
  await waitFor("Boolean(document.querySelector('dialog.photo-viewer[open]'))");
  const firstViewer=await evaluate("document.querySelector('dialog.photo-viewer img')?.getAttribute('src')");
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
  await waitFor(`document.querySelector('dialog.photo-viewer img')?.getAttribute('src')!==${JSON.stringify(firstViewer)}`);
  const viewerImage=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile('.build/photo-viewer.png',Buffer.from(viewerImage.data,'base64'));
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await waitFor("!document.querySelector('dialog[open]')");
  await waitFor("document.activeElement?.classList.contains('photo-preview-trigger')");
  await evaluate("(()=>{const select=document.querySelector('.card select');select.value='preferred';select.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent==='Undo decision'&&!b.disabled)");
  await click('Undo decision');
  await waitFor("document.querySelector('.card select').value==='candidate'");
  await click('Redo decision');
  await waitFor("document.querySelector('.card select').value==='preferred'");
  await evaluate("document.querySelector('.secondary-tools').open=true");
  if(await evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent==='Analyse local details')")) {
    await click('Analyse local details');
    await waitFor("fetch('/api/services/synthetic-ui').then(r=>r.json()).then(s=>s.job?.status==='completed')");
    await waitFor("!document.querySelector('.workflow-panel progress')&&[...document.querySelectorAll('button')].some(b=>b.textContent==='Start selection'&&!b.disabled)");
  }
  await evaluate("document.querySelectorAll('.photo-footer input')[0].click();document.querySelectorAll('.photo-footer input')[1].click();");
  await click('Compare (2/2)');
  await waitFor("document.querySelector('dialog[open]')?.textContent.includes('Preview 600 × 400 px')");
  await click('Close');
  await step('Lightroom');
  await waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Review ratings')&&!b.disabled)");
  await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Review ratings')).click()");
  await waitFor("document.querySelector('dialog[open]')?.textContent.includes('Prepare changes preview')");
  await click('Prepare changes preview');
  await waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent==='Confirm list for Lightroom'&&!b.disabled)");
  await click('Confirm list for Lightroom');
  await waitFor("document.querySelector('dialog[open]')?.textContent.includes('Plan confirmed')");
  const plan=await request('/services/synthetic-ui/rating-plan/latest');
  if(plan.status!==200||plan.data.items.length!==5)throw new Error('Unexpected exact rating plan');
  const claimed=await request('/services/synthetic-ui/rating-plan/claim','POST',{batch_id:plan.data.batch_id});
  if(claimed.status!==200)throw new Error('Synthetic claim failed');
  // Simulated SDK receipt: no Lightroom and no ratings written.
  const receipt=await request('/services/synthetic-ui/rating-receipts','POST',{batch_id:plan.data.batch_id,results:plan.data.items.map(i=>({photo_id:i.photo_id,status:'skipped',reason:'SIMULAZIONE: nessun catalogo aperto'}))});
  if(receipt.status!==200)throw new Error('Synthetic receipt failed');
  await waitFor("document.querySelector('dialog[open]')?.textContent.includes('Operation recorded')");
  await click('Close');
  const added=await request('/services/synthetic-ui/append','POST',{schema_version:1,id:'synthetic-append',catalog_id:'synthetic-not-a-real-catalog',photos:[{id:'synthetic-added',uuid:'synthetic-added',local_id:100,filename:'SINTETICO_AGGIUNTO.jpg',baseline_rating:0,baseline_edit_time:100}]});
  if(added.status!==200||added.data.photo_ids.length!==1)throw new Error('Append failed');
  const complete=await request('/services/synthetic-ui/complete','POST',{import_id:'synthetic-append'});
  if(complete.status!==200)throw new Error('Append completion failed');
  await click('Refresh');
  await waitFor("document.querySelectorAll('.grid .card').length===7");
  const current=await request('/services/synthetic-ui');
  if(current.data.decisions['synthetic-0'].state!=='preferred'||current.data.selected_ids.length!==7||!current.data.requires_analysis)throw new Error('Append lost decisions or candidates');
  await evaluate("document.querySelector('.secondary-tools').open=true");
  await click('Archive service');
  await waitFor("document.body.textContent.includes('Service archived.')");
  await click('Reopen service');
  await waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent==='Archive service'&&!b.disabled)");
  console.log(JSON.stringify({review:true,comparison:true,exactPlan:true,simulatedReceipt:true,incrementalImport:true,archiveReopen:true,realCatalogAccess:false}));
  await step('Configure');
  // Show current preset workflow using this isolated synthetic service only.
  await evaluate("(()=>{const label=[...document.querySelectorAll('.config label')].find(x=>x.textContent.startsWith('Start from a preset'));const select=label?.querySelector('select');if(!select)return false;select.value='nature:1';select.dispatchEvent(new Event('change',{bubbles:true}));return true;})()");
  await waitFor("document.querySelector('.config textarea')?.value!==undefined");
  await evaluate("document.querySelector('.app-settings').open=true");
  await click('OpenAI configuration');
  await waitFor("[...document.querySelectorAll('label')].some(x=>x.textContent==='API key')");
  if(await evaluate("document.querySelector('input[type=password]')?.value!==''"))throw new Error('Screenshot must not contain API key');
  const presetDraft=await evaluate("({instructions:[...document.querySelectorAll('.config label')].find(x=>x.textContent.startsWith('Selection instructions'))?.querySelector('textarea')?.value,criteria:[...document.querySelectorAll('.config label')].find(x=>x.textContent.startsWith('Service criteria'))?.querySelector('textarea')?.value})");
  if(!presetDraft.instructions?.includes('Preserve different species')||presetDraft.criteria!==undefined)throw new Error('Preset did not populate unified instructions');
  const metrics=await call('Page.getLayoutMetrics');
  const height=Math.ceil(metrics.cssContentSize.height);
  const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:1500,height,scale:1}});
  await writeFile('.build/webapp-audit.png',Buffer.from(image.data,'base64'));
  console.log(JSON.stringify({file:'.build/webapp-audit.png',width:1500,height,syntheticCards:7}));
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  const mobile=await evaluate('({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})');
  if(mobile.scroll>mobile.width){const overflow=await evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>document.documentElement.clientWidth+1).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,60),right:e.getBoundingClientRect().right})).slice(0,12)");throw new Error('Mobile horizontal overflow: '+JSON.stringify({mobile,overflow}));}
  const mobileImage=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile('.build/webapp-audit-mobile.png',Buffer.from(mobileImage.data,'base64'));
  console.log(JSON.stringify({mobile}));
  await call('Browser.close').catch(()=>{});
} finally {
  if(ws)ws.close();
  if(chrome)chrome.kill('SIGTERM');
  backend.kill('SIGTERM');
}
