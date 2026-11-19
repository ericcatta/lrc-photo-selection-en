import type {Service} from './api';
export type WorkflowPhase='configure'|'analyze'|'review'|'lightroom'|'outcome';
export const workflowSteps:{id:WorkflowPhase;label:string}[]=[{id:'configure',label:'Configure'},{id:'analyze',label:'Analyse'},{id:'review',label:'Review'},{id:'lightroom',label:'Lightroom'},{id:'outcome',label:'Outcome'}];
export function workflowPhase(service:Service):WorkflowPhase {
  if(service.workflow)return service.workflow.phase;
  if(service.confirmed_batch_id||service.status==='applying')return 'lightroom';
  if(service.receipts.length)return 'outcome';
  if(service.requires_analysis||service.proposal?.stale)return 'configure';
  if(service.job&&['queued','running','failed','interrupted'].includes(service.job.status))return 'analyze';
  if(service.proposal?.shortlist_accepted)return 'lightroom';
  if(service.proposal)return service.settings.mode==='hybrid'&&!service.proposal.api_plan_id?'analyze':'review';
  return 'configure';
}
