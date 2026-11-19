import {useEffect,useRef,useState} from 'react';
import guide from './guide-data.json';

export function GuideButton(){
  const [open,setOpen]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(open&&!dialog.current?.open)dialog.current?.showModal();},[open]);
  return <><button type="button" className="text-button" onClick={()=>setOpen(true)}>Guide</button>{open&&<dialog ref={dialog} aria-label={guide.title} onCancel={e=>{e.preventDefault();setOpen(false);}}><header className="reviewhead"><h2>{guide.title}</h2><button type="button" onClick={()=>setOpen(false)}>Close guide</button></header><p>{guide.intro}</p><ol>{guide.steps.map(step=><li key={step.id}><h3>{step.title}</h3><p>{step.body}</p></li>)}</ol><details><summary>Common questions</summary>{guide.notes.map(note=><section key={note.title}><h3>{note.title}</h3><p>{note.body}</p></section>)}</details></dialog>}</>;
}
