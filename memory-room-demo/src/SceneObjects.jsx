import React, {useRef, useState} from 'react';
import './objects.css';
import Glass from './MemoryGlass.jsx';

// Pointer capture supports mouse and touch; a click auditions, a drop acts.
export function Memory({item,onListen,onDrop,target,selected,disabled=false}) {
  const [drag,setDrag]=useState(null), origin=useRef(null), moved=useRef(false);
  function release(e){
    const start=origin.current;if(!start)return;
    origin.current=null;setDrag(null);
    if(!moved.current){onListen(item);return;}
    const r=target.current?.getBoundingClientRect();
    if(r&&e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom)onDrop(item);
  }
  return <button className={'memory-object '+(selected?'taken ':'')+(drag?'held':'')} disabled={disabled} aria-label={`试听${item.name}`} onPointerDown={e=>{if(e.button!==0)return;origin.current={x:e.clientX,y:e.clientY};moved.current=false;e.currentTarget.setPointerCapture(e.pointerId);}}
    onPointerMove={e=>{const o=origin.current;if(!o)return;const x=e.clientX-o.x,y=e.clientY-o.y;if(Math.hypot(x,y)>8)moved.current=true;if(moved.current)setDrag({x,y});}}
    onPointerUp={release} onPointerCancel={()=>{origin.current=null;setDrag(null);}}
    onClick={e=>{if(e.detail===0)onListen(item);}} onKeyDown={e=>{if(e.key===' '){e.preventDefault();onDrop(item);}}}
    style={drag?{transform:`translate(${drag.x}px,${drag.y}px) scale(1.15)`}:undefined}>
    <Glass color={item.color}/><span className="object-name">{item.name}{selected?' · 已拿取':''}</span>
  </button>;
}

export function Door({ready,onEnter}) {return <section className="door-stage"><div className="scene-whisper"><h1>记忆之室</h1><p>有些瞬间，一直有声音。</p></div><button className="door-touch object-hotspot" aria-label="推开房门" disabled={!ready} onClick={onEnter}><span className="touch-glint">✧</span><span className="object-hint">轻推这扇门</span></button><p className="gesture-guide">触碰门上的光，走进你的记忆</p></section>;}

export function Room({count,onCabinet,onPool,result,onOrb}) {return <section className="room-stage"><p className="scene-whisper">声音还在这里。走近，听一听。</p><button className="cabinet-touch object-hotspot" aria-label="走近记忆柜" onClick={onCabinet}><span className="touch-glint">✧</span><span className="object-hint">记忆柜</span></button><button className="pool-touch object-hotspot" aria-label="走向记忆池" onClick={onPool} disabled={count!==3}><span className="touch-glint">✧</span><span className="object-hint">{count===3?'走向池边':`先带上三瓶记忆 · ${count}/3`}</span></button>{result&&<button className="saved-orb-object" aria-label="聆听收藏的记忆球" onClick={onOrb}>✧</button>}<p className="gesture-guide">触碰左侧的柜子，挑选三瓶声音</p></section>;}

export function Pool({picked,poured,pouring,busy,onPour,onListen,onRetry}) {
  const water=useRef(null);
  return <section className="object-pool-stage"><p className="scene-whisper">{busy?'三段回响，正在凝结…':'把瓶子举到池水上方，再松开手。'}</p><div ref={water} className={'water-drop '+(pouring?'active ':'')+(busy?'forming':'')} role="region" aria-label="记忆池水面"><div className="ripple"/><div className="ripple second"/>{busy&&<div className="rising-orb">✧</div>}{pouring&&<div className="pour-stream"/>}<span className="water-hint">{busy?'':`${poured.length} / 3 · 记忆已融入`}</span></div>
    <div className="pool-inventory">{picked.map(item=><div key={item.id} className={(poured.includes(item.id)?'emptied ':'')+(pouring===item.id?'pouring-object':'')}><Memory item={item} disabled={busy||!!pouring||poured.includes(item.id)} target={water} onListen={onListen} onDrop={onPour}/></div>)}</div>
    {poured.length===3&&!busy&&<button className="text-button retry-mix" onClick={onRetry}>重新融合</button>}
    <p className="gesture-guide">拖动瓶子到水面 · 轻触试听 · 键盘空格倒入</p>
  </section>;
}
