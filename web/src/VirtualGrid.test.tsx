// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {createRef} from 'react';
import {VirtualGrid,type VirtualGridHandle} from './VirtualGrid';
const items=Array.from({length:5000},(_,index)=>({id:'item-'+index}));
let scrollOffset=0;
let originalScrollY:PropertyDescriptor|undefined;
beforeEach(()=>{
  scrollOffset=0;originalScrollY=Object.getOwnPropertyDescriptor(window,'scrollY');
  Object.defineProperty(window,'scrollY',{configurable:true,get:()=>scrollOffset});
  vi.spyOn(window,'scrollTo').mockImplementation((options:ScrollToOptions|number,y?:number)=>{scrollOffset=typeof options==='number'?y??0:options.top??scrollOffset;window.dispatchEvent(new Event('scroll'));});
  vi.spyOn(HTMLElement.prototype,'clientHeight','get').mockReturnValue(400);
  vi.spyOn(HTMLElement.prototype,'clientWidth','get').mockReturnValue(1000);
  vi.spyOn(HTMLElement.prototype,'offsetHeight','get').mockReturnValue(400);
  vi.spyOn(HTMLElement.prototype,'offsetWidth','get').mockReturnValue(1000);
  vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(function(this:HTMLElement){
    const root=this.classList.contains('grid');
    return {x:0,y:root?600-scrollOffset:0,top:root?600-scrollOffset:0,left:0,right:1000,bottom:root?600-scrollOffset:400,width:1000,height:root?0:400,toJSON:()=>({})};
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks();if(originalScrollY)Object.defineProperty(window,'scrollY',originalScrollY);});
const card=(item:{id:string})=><article tabIndex={0}>{item.id}</article>;
it('limits mounted rows and preserves all item identities without an initial page jump',async()=>{
  const {container,rerender}=render(<VirtualGrid className="grid" items={items} itemKey={item=>item.id} minColumnWidth={200} renderItem={card}/>);
  await waitFor(()=>expect(container.querySelector('.grid')?.getAttribute('data-virtual-columns')).toBe('4'));
  expect(screen.getAllByRole('article').length).toBeLessThan(60);
  expect(container.querySelector('.grid')?.getAttribute('data-virtual-count')).toBe('5000');
  expect(scrollOffset).toBe(0);
  rerender(<VirtualGrid className="grid" items={items} itemKey={item=>item.id} minColumnWidth={300} renderItem={card}/>);
  await waitFor(()=>expect(container.querySelector('.grid')?.getAttribute('data-virtual-columns')).toBe('3'));
  expect(scrollOffset).toBe(0);
});
it('mounts and focuses an offscreen target while keeping the DOM bounded',async()=>{
  const api=createRef<VirtualGridHandle>();
  render(<VirtualGrid apiRef={api} className="grid" items={items} itemKey={item=>item.id} minColumnWidth={200} renderItem={card}/>);
  act(()=>api.current?.focus(4999));
  await waitFor(()=>expect(document.activeElement?.textContent).toBe('item-4999'));
  expect(screen.getAllByRole('article').length).toBeLessThan(80);
  expect(window.scrollTo).toHaveBeenCalled();
});
it('keeps a focused row mounted while scrolling and resets the range after a filter change',async()=>{
  const {rerender}=render(<VirtualGrid className="grid" items={items} itemKey={item=>item.id} minColumnWidth={200} renderItem={card} resetKey="all"/>);
  const first=screen.getByText('item-0');act(()=>first.focus());
  act(()=>window.scrollTo({top:20000}));
  await waitFor(()=>expect(screen.getAllByRole('article').some(item=>item.textContent==='item-0')).toBe(true));
  expect(document.activeElement).toBe(first);
  fireEvent.blur(first,{relatedTarget:document.body});
  rerender(<VirtualGrid className="grid" items={items.slice(4500)} itemKey={item=>item.id} minColumnWidth={200} renderItem={card} resetKey="filtered"/>);
  await screen.findByText('item-4500');
  expect(screen.getAllByRole('article').length).toBeLessThan(80);
});
it('uses the same windowing for a dialog scroller',()=>{
  const {container}=render(<VirtualGrid className="api-photo-picker" items={items} itemKey={item=>item.id} minColumnWidth={210} gap={8} estimatedRowHeight={92} scroll="self" renderItem={item=><label>{item.id}<input type="checkbox"/></label>}/>);
  expect(container.querySelector('.api-photo-picker')?.getAttribute('data-virtual-count')).toBe('5000');
  expect(screen.getAllByRole('checkbox').length).toBeLessThan(100);
});
