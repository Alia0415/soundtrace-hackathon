import React, {useRef, useState} from 'react';
import cassette from '../assets/painted-cassette.png';
import cabinetArt from '../assets/painted-cassette-cabinet.png';

export default function PaintedCabinet({library, selected, onListen, onChoose, onPool, onImport, busy}) {
  const [page,setPage]=useState(0), [focus,setFocus]=useState(null);
  const dragStart=useRef(null), tray=useRef(null);
  const pages=Math.max(1,Math.ceil(library.length/9));
  function release(event,item) {
    const start=dragStart.current;dragStart.current=null;
    if(!start)return;
    const bounds=tray.current?.getBoundingClientRect();
    if(Math.hypot(event.clientX-start.x,event.clientY-start.y)>10 && bounds && event.clientY>=bounds.top && event.clientY<=bounds.bottom && event.clientX>=bounds.left && event.clientX<=bounds.right){
      if(!selected.includes(item.id))onChoose(item.id);
    } else {setFocus(item);onListen(item);}
  }
  return <section className="painted-cabinet" aria-label="手绘记忆柜">
    <div className="painted-cabinet-stage"><img className="painted-cabinet-art" src={cabinetArt} alt="海边日光里的蓝色手绘柜，三层架子上摆着九盒记忆磁带" draggable={false}/><div className="painted-heading"><h1>记忆柜</h1><p>听一听，带走三段记忆</p></div><div className="painted-hotspots">{Array.from({length:9},(_,index)=>{
      const item=library[page*9+index];
      return <button key={item?.id||index} className={'painted-spot '+(item&&selected.includes(item.id)?'chosen':'')} style={{left:`${[32.3,49.8,67.7][index%3]}%`,top:`${[47.7,64.7,81.5][Math.floor(index/3)]}%`}}
        aria-label={item?`试听${item.name}`:'导入新的记忆'} disabled={busy}
        onPointerDown={event=>{if(!item)return;dragStart.current={x:event.clientX,y:event.clientY};event.currentTarget.setPointerCapture(event.pointerId);}}
        onPointerUp={event=>item?release(event,item):onImport()}
        onPointerCancel={()=>{dragStart.current=null;}}
        onClick={event=>{if(event.detail===0){if(item){setFocus(item);onListen(item);}else onImport();}}}
        onKeyDown={event=>{if(event.key===' '&&item){event.preventDefault();onChoose(item.id);}}}>
        {item?<span>{item.name}</span>:<span>装入声音</span>}
      </button>;
    })}</div></div>
    <aside ref={tray} className="painted-tray">
      {focus&&<div className="painted-detail"><span>{focus.name}</span><button onClick={()=>onChoose(focus.id)}>{selected.includes(focus.id)?'放回柜中':'收进随身盒'}</button></div>}
      <div className="painted-tray-title"><h2>随身记忆</h2><span>{selected.length} / 3</span></div>
      <div className="painted-slots">{[0,1,2].map(index=>{const item=library.find(value=>value.id===selected[index]);return <button key={index} aria-label={item?`放回${item.name}`:'选择一盒记忆'} onClick={()=>item?onChoose(item.id):setFocus(null)} className={item?'filled':''}>{item?<><img src={cassette} alt=""/><span>{item.name}</span></>:<><b>+</b><span>待选择</span></>}</button>;})}</div>
      <p className="painted-help">轻点磁带试听 · 拖入托盘或点按带走</p>
      <button className="painted-continue" disabled={selected.length!==3||busy} onClick={onPool}>前往记忆池 <span>→</span></button>
      <div className="painted-tools"><button disabled={busy} onClick={onImport}>录入自己的声音</button>{pages>1&&<button onClick={()=>setPage((page+1)%pages)}>下一组 {page+1}/{pages}</button>}</div>
    </aside>
  </section>;
}
