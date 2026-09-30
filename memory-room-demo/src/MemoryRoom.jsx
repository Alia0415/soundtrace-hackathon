import React, { useEffect, useRef, useState } from 'react';
import { loadLibrary, saveLibrary, mixMemories, decodeAudio, saveRecord, loadRecord } from './audio.js';
import './room.css';
import './perspective.css';
import {Door, Room, Pool} from './SceneObjects.jsx';
import Cabinet from './PaintedCabinet.jsx';
import entrance from '../assets/painted-entrance.png';
import room from '../assets/painted-room.png';
import pool from '../assets/painted-pool.png';
import orb from '../assets/painted-orb.png';
import paintedCabinet from '../assets/painted-cassette-cabinet.png';
import rain from '../assets/rain.wav';
import sea from '../assets/sea.wav';
import melody from '../assets/melody.wav';
import './painted.css';
const examples = [
  { id:'rain', name:'窗边的雨', kind:'环境', caption:'把那天下午，装进一场雨里。', url:rain, color:'#a8dfea' },
  { id:'sea', name:'海风来信', kind:'环境', caption:'潮汐退去，夏天还留在耳边。', url:sea, color:'#b8e3ce' },
  { id:'melody', name:'未完成的哼唱', kind:'旋律', caption:'还没有名字，却一直记得的旋律。', url:melody, color:'#eed7ac' },
];
const backgrounds={door:entrance,room,cabinet:paintedCabinet,pool,orb};
const chapters={door:'序章 · 一扇门',room:'01 · 记忆之室',cabinet:'02 · 收藏声音',pool:'03 · 记忆交汇',orb:'04 · 留住回响'};
function initialSelection(){try{const v=JSON.parse(localStorage.getItem('soundtrace-room-selection')||'[]');return Array.isArray(v)?v.filter(x=>typeof x==='string').slice(0,3):[];}catch{return [];}}
export function App(){
  const [view,setView]=useState('door'),[library,setLibrary]=useState(examples),[ready,setReady]=useState(false);
  const [selected,setSelected]=useState(initialSelection),[focused,setFocused]=useState('rain');
  const [playing,setPlaying]=useState(null),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const [poured,setPoured]=useState([]),[pouring,setPouring]=useState(null),[result,setResult]=useState(null);
  const [title,setTitle]=useState('属于此刻的回响'),[saved,setSaved]=useState(false);
  const [travel,setTravel]=useState(null),[still,setStill]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const camera=useRef(null),travelling=useRef(false);
  const player=useRef(null),timers=useRef(new Set()),urls=useRef([]),input=useRef(null),lock=useRef(false);
  const picked=selected.map(id=>library.find(x=>x.id===id)).filter(Boolean),focus=library.find(x=>x.id===focused)||library[0];
  function later(fn,ms){const t=setTimeout(()=>{timers.current.delete(t);fn();},ms);timers.current.add(t);}
  function stop(){if(player.current){player.current.pause();player.current=null;}setPlaying(null);}
  function go(next){
    if(travelling.current||next===view)return;
    stop();setNotice('');
    if(still){setView(next);return;}
    travelling.current=true;
    setTravel({from:view,to:next,image:backgrounds[view]});
    later(()=>setView(next),650);
    later(()=>{setTravel(null);travelling.current=false;},1500);
  }
  function look(event){
    if(still||event.pointerType==='touch')return;
    camera.current?.style.setProperty('--look-x',`${(event.clientX/window.innerWidth-.5)*-18}px`);
    camera.current?.style.setProperty('--look-y',`${(event.clientY/window.innerHeight-.5)*-12}px`);
  }
  useEffect(()=>{let cancelled=false;(async()=>{try{
    const imported=await loadLibrary();if(cancelled)return;
    const rows=imported.map(x=>{const url=URL.createObjectURL(x.blob);urls.current.push(url);return {...x,url};});
    setLibrary([...examples,...rows]);setSelected(ids=>ids.filter(id=>[...examples,...rows].some(x=>x.id===id)));
    const record=await loadRecord();if(record&&!cancelled){const url=URL.createObjectURL(record.blob);urls.current.push(url);setResult({...record,url});setTitle(record.title);setSaved(true);}
  }catch{if(!cancelled)setNotice('浏览器暂时无法读取收藏，仍可使用示例。');}finally{if(!cancelled)setReady(true);}})();
  return()=>{cancelled=true;player.current?.pause();timers.current.forEach(clearTimeout);urls.current.forEach(URL.revokeObjectURL);};},[]);
  useEffect(()=>{if(ready)try{localStorage.setItem('soundtrace-room-selection',JSON.stringify(selected));}catch{setNotice('选择暂时无法保存，离开页面前请下载作品。');}},[selected,ready]);
  useEffect(()=>{window.scrollTo(0,0);},[view]);
  async function listen(item){
    if(playing===item.id){player.current?.pause();setPlaying(null);return;}
    let audio=player.current;
    const sourceUrl=new URL(item.url,window.location.href).href;
    if(!audio||audio.src!==sourceUrl){stop();audio=new Audio(sourceUrl);player.current=audio;}
    audio.onended=()=>{if(player.current===audio)setPlaying(null);};
    try{await audio.play();if(player.current===audio)setPlaying(item.id);}catch{if(player.current===audio)setNotice('这段声音暂时无法播放，请重新导入或重试。');}
  }
  function choose(id){if(selected.includes(id))setSelected(selected.filter(x=>x!==id));else if(selected.length<3)setSelected([...selected,id]);else setNotice('随身盒已经装满了。先放回一盒，再选择新的记忆。');}
  async function importFiles(event){const files=Array.from(event.target.files||[]);event.target.value='';if(!files.length)return;setBusy(true);setNotice('正在收好你的声音…');const rows=[],failures=[];
    for(const file of files){try{if(file.size>25*1024*1024)throw new Error('超过 25 MB');const buffer=await decodeAudio(file);if(buffer.duration>180||buffer.duration<.1)throw new Error('请选择 0.1–180 秒的声音');
      const item={id:crypto.randomUUID(),name:file.name.replace(/\.[^.]+$/,''),kind:'我的录音',caption:`${buffer.duration.toFixed(1)} 秒 · 保存在此浏览器`,color:'#dabfe8',blob:file};await saveLibrary(item);const url=URL.createObjectURL(file);urls.current.push(url);rows.push({...item,url});
    }catch(e){failures.push(`${file.name}：${e.message}`);}}
    setLibrary(old=>[...old,...rows]);if(rows.length)setFocused(rows[0].id);setNotice(failures.length?failures.join('；'):`已保存 ${rows.length} 盒新记忆。点击磁带即可试听。`);setBusy(false);
  }
  function enterPool(){if(travelling.current)return;stop();setPoured([]);setPouring(null);setNotice('');go('pool');}
  async function finishMix(items){setBusy(true);setNotice('正在把你选择的声音编织在一起…');try{const [blob]=await Promise.all([mixMemories(items),new Promise(resolve=>later(resolve,still?0:1800))]),url=URL.createObjectURL(blob);urls.current.push(url);setResult({blob,url,names:items.map(x=>x.name),title:'属于此刻的回响'});setTitle('属于此刻的回响');setSaved(false);setNotice('');go('orb');}catch(e){setNotice(`声音融合失败：${e.message}。可以重试，或返回更换素材。`);}finally{setBusy(false);lock.current=false;}}
  function pourMemory(item){if(lock.current||poured.includes(item.id))return;lock.current=true;stop();setPouring(item.id);listen(item);later(()=>{stop();setPouring(null);const next=[...poured,item.id];setPoured(next);if(next.length===3)finishMix(picked);else lock.current=false;},1400);}
  async function keep(){try{await saveRecord({...result,title:title.trim()||'未命名的回响'});setSaved(true);setNotice('记忆球已收藏在此浏览器，下次推门仍能找到它。');}catch{setNotice('收藏空间不足，请先下载 WAV 保存这段记忆。');}}
  return <main ref={camera} onPointerMove={look} onPointerLeave={()=>{camera.current?.style.setProperty('--look-x','0px');camera.current?.style.setProperty('--look-y','0px');}} className={'scene scene-'+view+(travel?' travelling':'')+(still?' still':'')} style={{'--scene':`url(${backgrounds[view]})`}}>
    <div className="world" aria-hidden="true"><div key={view} className="world-image"/><div className="air-particles">{Array.from({length:12},(_,i)=><i key={i} style={{left:`${(i*29+7)%100}%`,top:`${(i*17+11)%100}%`,animationDelay:`-${i*.8}s`}}/>)}</div></div>
    <div className="scene-shade"/><div className="peripheral-shadow" aria-hidden="true"/>
    <button className="motion-toggle ghost" onClick={()=>setStill(!still)} aria-pressed={still}>{still?'开启镜头动画':'减少镜头晃动'}</button>
    {travel&&<div className={'journey journey-'+travel.to+' from-'+travel.from} aria-hidden="true" style={{'--previous':`url(${travel.image})`}}><div className="previous-scene"/><div className="door-leaf left"/><div className="door-leaf right"/><span>{travel.to==='room'?'走进记忆深处':travel.to==='cabinet'?'走近记忆柜':travel.to==='pool'?'带着记忆，走向池边':travel.to==='orb'?'让回响，浮出水面':'回到门前'}</span></div>}
    <header><button className="brand" onClick={()=>!busy&&!pouring&&go('door')}>声迹 <span>SOUNDTRACE</span></button><span className="chapter">{chapters[view]}</span></header>
    {view!=='door'&&view!=='room'&&<button className="back ghost" onClick={()=>go(view==='pool'?'cabinet':'room')} disabled={busy||!!pouring}>← {view==='pool'?'返回记忆柜':'返回房间'}</button>}
    {view==='door'&&<Door ready={ready} onEnter={()=>go('room')}/>}
    {view==='room'&&<Room count={picked.length} onCabinet={()=>go('cabinet')} onPool={enterPool} result={result} onOrb={()=>go('orb')}/>}
    {view==='cabinet'&&<><Cabinet library={library} selected={selected} onListen={listen} onChoose={choose} onPool={enterPool} busy={busy} onImport={()=>input.current.click()}/><input ref={input} className='sr-only' type='file' accept='audio/*' multiple onChange={importFiles} aria-label='导入我的声音'/></>}
    {view==='pool'&&<Pool picked={picked} poured={poured} pouring={pouring} busy={busy} onPour={pourMemory} onListen={listen} onRetry={()=>finishMix(picked)}/>}
    {view==='orb'&&result&&<section className="orb-content"><span className="eyebrow">A LITTLE PIECE OF YOUR WORLD</span><button className={'orb-play '+(playing==='final'?'playing':'')} aria-label={playing==='final'?'暂停记忆球':'播放记忆球'} onClick={()=>listen({id:'final',url:result.url})}><span>✧</span><small>{playing==='final'?'Ⅱ':'▶'}</small></button><h1>声音有了新的形状。</h1><p>你带来的记忆，现在可以一起被听见。</p><label className="title-label">为这颗记忆球取个名字<input value={title} maxLength={40} onChange={e=>{setTitle(e.target.value);setSaved(false);}}/></label><div className="result-tags">{result.names.map((name,i)=><span key={i}>{name}</span>)}</div><small className="mix-note">由所选素材在本机融合 · 24 秒声音拼贴</small><div className="orb-actions"><button className="primary" onClick={keep}>{saved?'✓ 已收藏':'收藏这颗记忆球'}</button><a className="ghost" href={result.url} download={`${title.trim()||'记忆球'}.wav`}>下载 WAV ↓</a></div><button className="text-button" onClick={()=>go('cabinet')}>再酿一段新的记忆 →</button></section>}
    {notice&&<div className="notice" role="status">{notice}<button aria-label="关闭提示" onClick={()=>setNotice('')}>×</button></div>}
    <footer><span>让声音，替你记得。</span><span>私人记忆 · 保存在此浏览器</span></footer>
  </main>;
}
