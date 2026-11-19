// Generated synthetic shapes only. No Lightroom, real photos or cloud requests.
// Run PYTHONPATH=backend node scripts/scale_browser_smoke.mjs [--baseline] [--english]
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const baseline=process.argv.includes('--baseline'),english=process.argv.includes('--english');
const labels=english?{undo:'Undo decision',redo:'Redo decision',exclude:'Exclude',include:'Include',all:'All photos',excluded:'Excluded',close:'Close',confirm:'Confirm change',configure:'Configure',continueAPI:'Continue to OpenAI estimate',deselect:'Deselect all',selectAll:'All imported previews',estimate:'Calculate estimate without sending photos',exact:'Exact list:'}:{undo:'Annulla decisione',redo:'Ripristina decisione',exclude:'Escludi',include:'Includi',all:'Tutte le foto',excluded:'Esclusa',close:'Chiudi',confirm:'Conferma modifica',configure:'Configura',continueAPI:'Continua alla stima OpenAI',deselect:'Deseleziona tutte',selectAll:'Tutte le anteprime importate',estimate:'Calcola stima senza inviare foto',exact:'Elenco esatto:'};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
await mkdir('.build',{recursive:true});
const profile=await mkdtemp(join(tmpdir(),'lrc-scale-chrome-'));
const backend=spawn('.venv/bin/python',['scripts/scale_smoke_fixture.py','--port','18767'],{stdio:'ignore'});
let chrome,ws;
const report={syntheticPhotos:5000,baseline,english,realPhotoAccess:false,realCatalogAccess:false};
try {
  let ready=false;
  for(let i=0;i<200;i++){try{ready=(await fetch('http://127.0.0.1:18767/health')).ok;}catch{}if(ready)break;await pause(100);}
  if(!ready)throw new Error('Synthetic scale backend failed to start');
  chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-extensions','--disable-background-networking','--disable-sync','about:blank'],{stdio:'ignore'});
  let port;
  for(let i=0;i<200;i++){try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];}catch{}if(port)break;await pause(100);}
  if(!port)throw new Error('Chrome debugging endpoint unavailable');
  const target=await(await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
  ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  let next=0;const pending=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}});
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++next;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Timeout '+method));},45000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text+' '+r.exceptionDetails.exception?.description);return r.result?.value;};
  const waitFor=async expression=>{for(let i=0;i<200;i++){if(await evaluate(expression))return;await pause(100);}throw new Error('Condition failed: '+expression+' '+JSON.stringify(await evaluate("({alerts:[...document.querySelectorAll('[role=alert]')].map(x=>x.textContent),dialog:document.querySelector('dialog[open]')?.textContent,card:document.getElementById('photo-scale-0')?.className})")));};
  const click=async text=>{if(!await evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)}&&!b.disabled);if(!b)return false;b.click();return true;})()`))throw new Error('Button unavailable: '+text);};
  const key=async(name,code)=>{await call('Input.dispatchKeyEvent',{type:'keyDown',key:name,code:name,windowsVirtualKeyCode:code});await call('Input.dispatchKeyEvent',{type:'keyUp',key:name,code:name,windowsVirtualKeyCode:code});};
  const request=async path=>evaluate(`fetch('/api/services/synthetic-scale-ui'+${JSON.stringify(path)}).then(r=>r.json())`);
  await call('Page.enable');await call('Network.enable');
  let externalRequests=0,previewRequests=0;
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.method==='Network.requestWillBeSent'){const url=m.params.request.url;if(url.includes('/preview'))previewRequests++;if(/^https?:/.test(url)&&!url.startsWith('http://127.0.0.1:18767/'))externalRequests++;}});
  await call('Page.addScriptToEvaluateOnNewDocument',{source:`window.__scaleLongTasks=[];new PerformanceObserver(list=>window.__scaleLongTasks.push(...list.getEntries().map(x=>x.duration))).observe({type:'longtask',buffered:true});`});
  await call('Emulation.setDeviceMetricsOverride',{width:1500,height:1100,deviceScaleFactor:1,mobile:false});
  const loadStarted=performance.now();
  await call('Page.navigate',{url:'http://127.0.0.1:18767/#token=synthetic-scale-ui-only'});
  await waitFor("Boolean(document.querySelector('.service-switch option[value=\"synthetic-scale-ui\"]'))");
  await evaluate("(()=>{const s=document.querySelector('.service-switch select');s.value='synthetic-scale-ui';s.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await waitFor("Boolean(document.getElementById('photo-scale-0'))");
  report.initialRenderMs=Math.round(performance.now()-loadStarted);
  report.initialScrollY=await evaluate('window.scrollY');
  if(!baseline&&report.initialScrollY>1)throw new Error('Initial grid unexpectedly changed page scroll: '+report.initialScrollY);
  await evaluate("document.getElementById('photo-scale-0').scrollIntoView({block:'center'})");
  await waitFor("document.getElementById('photo-scale-0')?.querySelector('img')?.naturalWidth===600");
  report.initial=await evaluate("({cards:document.querySelectorAll('.grid .card').length,nodes:document.querySelectorAll('*').length,longTasks:window.__scaleLongTasks.length,maxLongTaskMs:Math.round(Math.max(0,...window.__scaleLongTasks))})");
  report.initial.previewRequests=previewRequests;console.log(JSON.stringify({initial:report}));
  if(!baseline){
    await evaluate('window.scrollTo(0,0)');
    await pause(100);
    const screenshot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(`.build/scale-${english?'english':'italian'}-desktop.png`,Buffer.from(screenshot.data,'base64'));
  }
  if(!baseline&&report.initial.cards>150)throw new Error('Grid mounted too many cards: '+report.initial.cards);
  if(!baseline){
    const originalHeight=await evaluate("document.querySelector('.grid [data-virtual-row=\"0\"]').getBoundingClientRect().height");
    // Generated DOM-only expansion exercises ResizeObserver without changing any
    // service, interpretation, decision, model result or real photograph.
    await evaluate("(()=>{const d=document.createElement('details');d.id='synthetic-row-expansion';const summary=document.createElement('summary');summary.textContent='Synthetic expandable explanation';const body=document.createElement('div');body.style.height='320px';body.textContent='Generated layout test only';d.append(summary,body);document.getElementById('photo-scale-0').append(d);d.open=true;})()");
    await waitFor(`(()=>{const a=document.querySelector('.grid [data-virtual-row="0"]')?.getBoundingClientRect();const b=document.querySelector('.grid [data-virtual-row="1"]')?.getBoundingClientRect();return a&&b&&a.height>${originalHeight}+200&&b.top>=a.bottom-1;})()`);
    await evaluate("document.getElementById('synthetic-row-expansion').remove()");
    await waitFor(`Math.abs(document.querySelector('.grid [data-virtual-row="0"]').getBoundingClientRect().height-${originalHeight})<2`);
    report.variableRowHeight=true;
  }
  const actionStarted=performance.now();
  await evaluate("(()=>{const b=[...document.getElementById('photo-scale-0').querySelectorAll('button')].find(b=>b.textContent.trim()==="+JSON.stringify(labels.exclude)+");b.click();})()");
  await waitFor("Boolean(document.querySelector('dialog[open]'))||document.getElementById('photo-scale-0')?.classList.contains('state-excluded')");
  if(await evaluate("Boolean(document.querySelector('dialog[open]'))"))await click(labels.confirm);
  await waitFor("document.getElementById('photo-scale-0')?.classList.contains('state-excluded')");
  report.excludeMs=Math.round(performance.now()-actionStarted);
  if((await request('')).decisions['scale-0']?.state!=='excluded')throw new Error('Exclusion was not persisted');
  await click(labels.undo);await waitFor("document.getElementById('photo-scale-0')?.classList.contains('state-candidate')");
  await click(labels.redo);await waitFor("Boolean(document.querySelector('dialog[open]'))||document.getElementById('photo-scale-0')?.classList.contains('state-excluded')");
  if(await evaluate("Boolean(document.querySelector('dialog[open]'))"))await click(labels.confirm);
  await waitFor("document.getElementById('photo-scale-0')?.classList.contains('state-excluded')");
  await click(labels.undo);await waitFor("document.getElementById('photo-scale-0')?.classList.contains('state-candidate')");
  report.undoRedo=true;
  if(!baseline){
    // Filter by excluded after making one decision, then return to the full list.
    await evaluate("(()=>{const b=[...document.getElementById('photo-scale-0').querySelectorAll('button')].find(b=>b.textContent.trim()==="+JSON.stringify(labels.exclude)+");b.click();})()");
    await waitFor("Boolean(document.querySelector('dialog[open]'))||document.getElementById('photo-scale-0')?.classList.contains('state-excluded')");
  if(await evaluate("Boolean(document.querySelector('dialog[open]'))"))await click(labels.confirm);
  await waitFor("document.getElementById('photo-scale-0')?.classList.contains('state-excluded')");
    await evaluate("(()=>{const s=document.querySelectorAll('.review-filters select')[1];s.value='excluded';s.dispatchEvent(new Event('change',{bubbles:true}));})()");
    await waitFor("document.querySelectorAll('.grid .card').length===1");
    await evaluate("(()=>{const s=document.querySelectorAll('.review-filters select')[1];s.value='all';s.dispatchEvent(new Event('change',{bubbles:true}));})()");
    await waitFor("document.querySelectorAll('.grid .card').length>1");
    report.filters=true;
    // Jump to the final rows and ensure they render without keeping earlier rows.
    await evaluate("window.scrollTo(0,document.documentElement.scrollHeight)");
    await waitFor("Boolean(document.getElementById('photo-scale-4999'))");
    report.bottomCards=await evaluate("document.querySelectorAll('.grid .card').length");
    if(report.bottomCards>150)throw new Error('Bottom window is unbounded');
    await evaluate("(()=>{const s=document.querySelector('.thumbnail-control input');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(s,'330');s.dispatchEvent(new Event('input',{bubbles:true}));s.dispatchEvent(new Event('change',{bubbles:true}));})()");
    await pause(200);await evaluate("window.scrollTo(0,document.documentElement.scrollHeight)");
    await waitFor("Boolean(document.getElementById('photo-scale-4999'))");
    report.resize=true;
    // Focus the last mounted middle row, then move beyond the current window.
    await evaluate("window.scrollTo(0,document.documentElement.scrollHeight/2)");
    await pause(300);
    const boundary=await evaluate("Math.max(...[...document.querySelectorAll('.grid .card')].map(e=>Number(e.id.slice('photo-scale-'.length))))");
    if(boundary>=4999||boundary<1)throw new Error('Unable to identify a middle window boundary');
    await evaluate(`document.getElementById('photo-scale-${boundary}').focus({preventScroll:true})`);
    await key('ArrowRight',39);
    await waitFor(`document.activeElement?.id==='photo-scale-${boundary+1}'`);
    report.keyboardCrossWindow=true;
    await evaluate("window.scrollTo(0,document.documentElement.scrollHeight)");
    await waitFor("Boolean(document.getElementById('photo-scale-4999'))");
    await evaluate("document.getElementById('photo-scale-4998').focus()");
    await key('ArrowRight',39);await waitFor("document.activeElement?.id==='photo-scale-4999'");
    // Open a photo in the final window; viewer navigation spans the full list.
    await evaluate("document.getElementById('photo-scale-4999').querySelector('.photo-preview-trigger').click()");
    await waitFor("Boolean(document.querySelector('dialog.photo-viewer[open]'))");
    await key('ArrowLeft',37);await waitFor("document.querySelector('.viewer-caption strong')?.textContent==='SYNTHETIC_04998.jpg'");
    await key('Escape',27);await waitFor("!document.querySelector('dialog[open]')");
    report.keyboardAndViewer=true;
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
    await evaluate("window.scrollTo(0,document.documentElement.scrollHeight)");await pause(200);
    const mobile=await evaluate("({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,cards:document.querySelectorAll('.grid .card').length})");
    if(mobile.scroll>mobile.width||mobile.cards>150)throw new Error('Mobile overflow or unbounded grid: '+JSON.stringify(mobile));
    report.mobile=mobile;
    await waitFor("Boolean(document.getElementById('photo-scale-4999'))");
    await evaluate("(()=>{const b=document.getElementById('photo-scale-4999').querySelector('.photo-preview-trigger');b.focus();b.click();})()");
    await waitFor("Boolean(document.querySelector('dialog.photo-viewer[open]'))");
    await key('ArrowLeft',37);
    await waitFor("document.querySelector('.viewer-caption strong')?.textContent==='SYNTHETIC_04998.jpg'");
    await key('Escape',27);
    await waitFor("document.activeElement?.classList.contains('photo-preview-trigger')");
    report.mobile.viewerFocusRestored=true;
    const mobileScreenshot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(`.build/scale-${english?'english':'italian'}-mobile.png`,Buffer.from(mobileScreenshot.data,'base64'));
    const final=await request('');
    if(Object.keys(final.decisions).length!==1||final.decisions['scale-0']?.state!=='excluded'||final.selected_ids.length!==4999)throw new Error('Scale interactions altered unrelated decisions');
    report.decisionsPreserved=true;
    await call('Emulation.setDeviceMetricsOverride',{width:1500,height:1100,deviceScaleFactor:1,mobile:false});
    await evaluate(`(()=>{const b=[...document.querySelectorAll('.workflow-panel nav button')].find(b=>b.textContent.endsWith(${JSON.stringify(labels.configure)}));b.click();})()`);
    await waitFor("Boolean(document.querySelector('.config'))");
    await evaluate("(()=>{const s=[...document.querySelectorAll('.config select')].find(s=>[...s.options].some(o=>o.value==='openai'));s.value='openai';s.dispatchEvent(new Event('change',{bubbles:true}));})()");
    await click(labels.continueAPI);
    await waitFor("Boolean(document.querySelector('dialog.api-review-modal[open]'))");
    await waitFor("document.querySelectorAll('.api-photo-choice').length>0");
    const pickerCount=await evaluate("document.querySelectorAll('.api-photo-choice').length");
    if(pickerCount>150)throw new Error('API picker mounted too many choices: '+pickerCount);
    report.apiPickerInitialChoices=pickerCount;
    await click(labels.deselect);
    // Reveal all alternatives and select two distant photos through the UI.
    await evaluate("document.querySelector('.api-selection-actions input[type=checkbox]').click()");
    await waitFor("document.querySelectorAll('.api-photo-choice').length>0");
    await evaluate("document.querySelector('.api-photo-choice input').click()");
    await evaluate("(()=>{const p=document.querySelector('.api-photo-picker');p.scrollTop=p.scrollHeight;})()");
    await waitFor("[...document.querySelectorAll('.api-photo-choice')].some(e=>e.textContent.includes('SYNTHETIC_04999.jpg'))");
    await evaluate("[...document.querySelectorAll('.api-photo-choice')].find(e=>e.textContent.includes('SYNTHETIC_04999.jpg')).querySelector('input').click()");
    await evaluate("document.querySelector('.api-selection-actions input[type=checkbox]').click()");
    await waitFor("document.querySelectorAll('.api-photo-choice').length===2");
    if(!await evaluate("[...document.querySelectorAll('.api-photo-choice input')].every(e=>e.checked)"))throw new Error('API selection was lost across scroll/filter');
    await click(labels.selectAll);
    await waitFor("document.querySelector('dialog.api-review-modal').textContent.includes('5000')");
    await click(labels.deselect);
    await evaluate("document.querySelector('.api-selection-actions input[type=checkbox]').click()");
    await waitFor("document.querySelectorAll('.api-photo-choice').length>0");
    await evaluate("document.querySelector('.api-photo-choice input').click()");
    // A one-photo local estimate exercises the summary without a cloud request;
    // the real API contract intentionally caps a single sample at 1,000 photos.
    await evaluate("(()=>{const i=document.querySelector('dialog.api-review-modal input[type=number]');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(i,'1');i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}));})()");
    await click(labels.estimate);
    await waitFor("Boolean(document.querySelector('.api-estimate'))");
    const exact=await evaluate(`(()=>{const d=[...document.querySelectorAll('.api-estimate details')].find(d=>d.querySelector('summary')?.textContent.startsWith(${JSON.stringify(labels.exact)}));return {open:d?.open,rows:d?.querySelectorAll('li').length??-1};})()`);
    if(exact.open||exact.rows!==0)throw new Error('Closed exact estimate list remains mounted: '+JSON.stringify(exact));
    const transport=await evaluate("fetch('/api/synthetic-scale-transport').then(r=>r.json())");
    if(transport.mock_calls!==0||transport.real_network_calls!==0)throw new Error('API picker interaction initiated analysis');
    report.apiPicker={bounded:true,selectionPreserved:true,closedExactListUnmounted:true,...transport};
  }
  if(externalRequests)throw new Error('Unexpected external HTTP request');
  report.externalRequests=externalRequests;
  await writeFile(`.build/scale-${baseline?'baseline':english?'english':'italian'}.json`,JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
  await call('Browser.close').catch(()=>{});
}finally{if(ws)ws.close();if(chrome)chrome.kill('SIGTERM');backend.kill('SIGTERM');}
