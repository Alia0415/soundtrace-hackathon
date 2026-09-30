import React, {useEffect, useRef, useState} from 'react';
import Glass from './MemoryGlass.jsx';
import {Memory} from './SceneObjects.jsx';
import './cabinet.css';
import './glass-cabinet.css';

export default function FirstPersonCabinet({library,selected,onListen,onChoose,onPool,onImport,busy}) {
  const tray=useRef(null);
  const [open,setOpen]=useState(false),[settled,setSettled]=useState(false),[page,setPage]=useState(0);
  const pages=Math.ceil(library.length/9);
  useEffect(()=>{const timer=setTimeout(()=>setOpen(true),1100);return()=>clearTimeout(timer);},[]);
  useEffect(()=>{setSettled(false);if(!open)return;const timer=setTimeout(()=>setSettled(true),1900);return()=>clearTimeout(timer);},[open]);
  return <section className={`first-person-cabinet ${open?'is-open':''} ${settled?'is-settled':''}`} aria-label={open?'打开的记忆柜':'合拢的记忆柜'}>
    <p className="cabinet-whisper" aria-live="polite">{!open?'走近，推开记忆柜。':!settled?'光从柜门之间流出来。':'轻触一瓶声音 · 拖到手边，带走这段记忆'}</p>
    <div className="cabinet-camera"><div className="cabinet-floor" aria-hidden="true"/><div className="cabinet-volume">
      <div className="cabinet-back" aria-hidden="true"><span>THE MEMORY ARCHIVE</span></div>
      <div className="cabinet-wall wall-left" aria-hidden="true"/><div className="cabinet-wall wall-right" aria-hidden="true"/><div className="cabinet-ceiling" aria-hidden="true"/>
      <div className="shelf-collection" inert={!settled}>
        {[0,1,2].map(row=><div className="memory-shelf" key={row}>
          <div className="shelf-lamp" aria-hidden="true"/>
          <div className="shelf-bottles">{[0,1,2].map(col=>{const index=page*9+row*3+col,item=library[index];return <div className="shelf-place" key={col}>
            {item?<Memory item={item} selected={selected.includes(item.id)} disabled={!settled} target={tray} onListen={onListen} onDrop={x=>{if(!selected.includes(x.id))onChoose(x.id);}}/>:<button className="empty-vessel" aria-label={`空瓶 ${row*3+col+1}，装入自己的声音`} disabled={busy||!settled} onClick={onImport}><Glass color={['#a9dcca','#c9d5b4','#bdddea','#e3d6aa'][col]}/><span className="object-name">等待一段新的声音</span></button>}
            <span className="shelf-caption">{item?item.name:'·'}</span>
          </div>;})}</div>
          <div className="shelf-board" aria-hidden="true"><span>{String(row+1).padStart(2,'0')}</span></div>
        </div>)}
      </div>
      <div className="cabinet-frame frame-top" aria-hidden="true"/><div className="cabinet-frame frame-left" aria-hidden="true"/><div className="cabinet-frame frame-right" aria-hidden="true"/><div className="cabinet-frame frame-bottom" aria-hidden="true"/>
      <div className="glass-plinth" aria-hidden="true"><div className="plinth-inset"/><span className="glass-foot foot-left"/><span className="glass-foot foot-right"/></div>
      <div className="glass-sparkles" aria-hidden="true">{Array.from({length:16},(_,i)=><i key={i} style={{left:`${i%2?96:3}%`,top:`${5+(i*23)%88}%`,animationDelay:`-${i*.7}s`}}/>)}</div>
      {['left','right'].map(side=><button key={side} className={`cabinet-door door-${side}`} aria-label={open?'合上记忆柜':'拉开记忆柜门'} onClick={()=>setOpen(!open)}><span className="door-glazing"><span className="door-engraving">{side==='left'?'MEMORIES':'LIVE HERE'}</span></span><span className="cabinet-handle"/><span className="hinge hinge-top"/><span className="hinge hinge-bottom"/></button>)}
    </div></div>
    <div className="cabinet-hands" ref={tray} aria-label="随身托盘">
      <span className="carry-caption">手边的记忆 <i>{selected.length} / 3</i></span>
      <div className="hand-bottles">{[0,1,2].map(i=>{const item=library.find(x=>x.id===selected[i]);return <div className="hand-slot" key={i}>{item?<button aria-label={`放回${item.name}`} onClick={()=>onChoose(item.id)}><Glass color={item.color}/><small>{item.name}</small></button>:<span className="hand-empty"/>}</div>;})}</div>
    </div>
    <div className="cabinet-footnotes"><button className="text-button" onClick={onImport} disabled={busy}>装入自己的声音</button>{pages>1&&<button className="text-button" onClick={()=>setPage((page+1)%pages)}>下一组收藏 · {page+1}/{pages}</button>}<span>空格拿取 · 轻触手边的瓶子放回</span></div>
    {selected.length===3&&settled&&<button className="cabinet-to-pool object-hotspot" aria-label="带着记忆走向池边" onClick={onPool}><span className="touch-glint">↗</span><span className="object-hint">转身，走向池边</span></button>}
  </section>;
}
