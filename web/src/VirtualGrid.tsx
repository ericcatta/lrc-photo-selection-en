import {Fragment,useCallback,useImperativeHandle,useLayoutEffect,useRef,useState,type CSSProperties,type ReactNode,type Ref} from 'react';
import {defaultRangeExtractor,useVirtualizer,useWindowVirtualizer,type Range} from '@tanstack/react-virtual';

export type VirtualGridHandle={focus:(index:number,selector?:string)=>void};
type Props<T>={items:readonly T[];itemKey:(item:T,index:number)=>string;renderItem:(item:T,index:number)=>ReactNode;minColumnWidth:number;gap?:number;estimatedRowHeight?:number;className?:string;style?:CSSProperties;scroll?:'window'|'self';resetKey?:string;apiRef?:Ref<VirtualGridHandle>};
const THRESHOLD=100;

/** Measure responsive rows, keeping the full filtered list outside the DOM. */
export function VirtualGrid<T>({items,itemKey,renderItem,minColumnWidth,gap:requestedGap,estimatedRowHeight,className='',style,scroll='window',resetKey='',apiRef}:Props<T>){
  const outer=useRef<HTMLDivElement>(null);
  const [width,setWidth]=useState(minColumnWidth);
  const [measuredGap,setMeasuredGap]=useState(requestedGap??12);
  const gap=requestedGap??measuredGap;
  const [margin,setMargin]=useState(0);
  const [focusedIndex,setFocusedIndex]=useState<number|null>(null);
  const [pendingFocus,setPendingFocus]=useState<{index:number;selector?:string}|null>(null);
  const virtual=items.length>THRESHOLD;
  const columns=Math.max(1,Math.floor((width+gap)/(Math.min(width,minColumnWidth)+gap)));
  const columnWidth=Math.max(1,(width-gap*(columns-1))/columns);
  const rowCount=Math.ceil(items.length/columns);
  const anchor=useRef(0);
  const priorColumns=useRef(columns);
  const priorReset=useRef(resetKey);
  const padding=scroll==='window'?(document.querySelector('.workflow-panel')?.getBoundingClientRect().height??0)+8:0;
  const measureOuter=useCallback(()=>{
    const element=outer.current;if(!element)return;
    const rect=element.getBoundingClientRect();
    if(requestedGap===undefined){const value=Number.parseFloat(window.getComputedStyle(element).rowGap);if(Number.isFinite(value))setMeasuredGap(previous=>previous===value?previous:value);}
    if(rect.width>0)setWidth(previous=>Math.abs(previous-rect.width)>.5?rect.width:previous);
    if(scroll==='window'){const top=rect.top+window.scrollY;setMargin(previous=>Math.abs(previous-top)>.5?top:previous);}
  },[scroll,requestedGap]);
  useLayoutEffect(()=>{
    measureOuter();
    const element=outer.current;
    const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(measureOuter);
    if(element)observer?.observe(element);
    window.addEventListener('resize',measureOuter);
    window.addEventListener('scroll',measureOuter,{passive:true});
    return()=>{observer?.disconnect();window.removeEventListener('resize',measureOuter);window.removeEventListener('scroll',measureOuter);};
  },[measureOuter]);
  // Changes above the grid (workflow, filters, notices) can move its document offset.
  useLayoutEffect(measureOuter);
  const rowKey=useCallback((row:number)=>items.slice(row*columns,(row+1)*columns).map((item,offset)=>itemKey(item,row*columns+offset)).join('\u001f'),[items,itemKey,columns]);
  const rangeExtractor=useCallback((range:Range)=>{
    const rows=defaultRangeExtractor(range);
    for(const index of [pendingFocus?.index,focusedIndex]){if(index==null)continue;const row=Math.floor(index/columns);if(row>=0&&row<rowCount&&!rows.includes(row))rows.push(row);}
    return rows.sort((a,b)=>a-b);
  },[pendingFocus,focusedIndex,columns,rowCount]);
  const estimateHeight=estimatedRowHeight??columnWidth*.75+220;
  const options={count:virtual?rowCount:0,estimateSize:()=>estimateHeight,measureElement:(element:HTMLDivElement,entry:ResizeObserverEntry|undefined)=>entry?.borderBoxSize?.[0]?.blockSize||entry?.contentRect.height||element.getBoundingClientRect().height||estimateHeight,getItemKey:rowKey,overscan:3,gap,rangeExtractor,useFlushSync:false,
    onChange:(instance:{getVirtualItems:()=>{index:number;end:number}[];scrollOffset:number|null},sync:boolean)=>{
      if(!sync)return;
      const first=instance.getVirtualItems().find(row=>row.end>(instance.scrollOffset??0)+padding);
      if(first)anchor.current=first.index*priorColumns.current;
    }};
  const windowRows=useWindowVirtualizer<HTMLDivElement>({...options,enabled:virtual&&scroll==='window',scrollMargin:margin,scrollPaddingStart:padding,initialRect:{width,height:window.innerHeight||800}});
  const elementRows=useVirtualizer<HTMLDivElement,HTMLDivElement>({...options,enabled:virtual&&scroll==='self',getScrollElement:()=>outer.current,initialRect:{width,height:Math.max(180,window.innerHeight*.32)}});
  const rows=scroll==='window'?windowRows:elementRows;
  useLayoutEffect(()=>{
    if(!virtual)return;
    const inside=scroll==='window'?window.scrollY>=margin-padding:(outer.current?.scrollTop??0)>0;
    if(priorReset.current!==resetKey){priorReset.current=resetKey;anchor.current=0;if(inside)rows.scrollToIndex(0,{align:'start'});}
    if(priorColumns.current!==columns){const index=anchor.current;priorColumns.current=columns;rows.measure();if(inside)rows.scrollToIndex(Math.floor(Math.min(index,items.length-1)/columns),{align:'start'});}
  },[columns,items.length,resetKey,rows,virtual,scroll,margin,padding]);
  const locate=(index:number,selector?:string)=>{
    const holder=virtual?outer.current?.querySelector<HTMLElement>(`[data-virtual-item-index="${index}"]`):outer.current?.children[index] as HTMLElement|undefined;
    if(!holder)return null;
    if(selector)return holder.matches(selector)?holder:holder.querySelector<HTMLElement>(selector);
    return holder.matches('[tabindex],button,input,select')?holder:holder.querySelector<HTMLElement>('[tabindex],button,input,select');
  };
  useImperativeHandle(apiRef,()=>({focus(index,selector){
    if(index<0||index>=items.length)return;
    const element=locate(index,selector);
    if(element){const rect=element.getBoundingClientRect();if(!virtual){element.focus();return;}if(rect.top>=padding&&rect.bottom<=window.innerHeight){element.focus({preventScroll:true});return;}}
    setPendingFocus({index,selector});
    if(virtual)rows.scrollToIndex(Math.floor(index/columns),{align:'auto'});
  }}));
  useLayoutEffect(()=>{
    if(!pendingFocus)return;
    const element=locate(pendingFocus.index,pendingFocus.selector);
    if(element){element.focus({preventScroll:true});setPendingFocus(null);}
  },[pendingFocus,columns,items,virtual]);
  const content=virtual?<div className="virtual-grid-content" style={{height:rows.getTotalSize(),position:'relative',width:'100%'}}>{rows.getVirtualItems().map(row=><div key={row.key} data-index={row.index} data-virtual-row={row.index} ref={rows.measureElement} className="virtual-grid-row" style={{position:'absolute',top:0,left:0,width:'100%',display:'grid',gridTemplateColumns:`repeat(${columns},minmax(0,1fr))`,gap,alignItems:scroll==='self'?'stretch':'start',transform:`translateY(${row.start-(scroll==='window'?margin:0)}px)`}}>{items.slice(row.index*columns,(row.index+1)*columns).map((item,offset)=>{const index=row.index*columns+offset;return <div key={itemKey(item,index)} data-virtual-item-index={index} style={{minWidth:0}}>{renderItem(item,index)}</div>;})}</div>)}</div>:items.map((item,index)=><Fragment key={itemKey(item,index)}>{renderItem(item,index)}</Fragment>);
  return <div ref={outer} onFocusCapture={event=>{const holder=(event.target as HTMLElement).closest<HTMLElement>('[data-virtual-item-index]');if(holder)setFocusedIndex(Number(holder.dataset.virtualItemIndex));}} onBlurCapture={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node|null))setFocusedIndex(null);}} className={className+(virtual?' virtual-grid':'')} data-virtual-count={items.length} data-virtual-columns={columns} data-virtual-enabled={virtual} style={{...style,...(virtual?{display:'block',...(scroll==='self'?{overflowY:'auto'}:{})}:{})}}>{content}</div>;
}
