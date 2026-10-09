import RasterArt from './RasterArt';
import AudioPreview from './AudioPreview';
import React,{useEffect,useState} from 'react';
import {api,route,runSoundJob} from './api';
import {clock,encodeWav,download} from './audio';
import './diary-flow.css';

export default function SoundLibrary({source,name,memory,onSave,onGenerate,onSelect,busy,refreshKey,onImport,onNew,onRestore,rawSuccess,onDismissSuccess}){
  const [items,setItems]=useState([]),[error,setError]=useState(''),[loading,setLoading]=useState(true),[preview,setPreview]=useState(''),[query,setQuery]=useState(''),[filter,setFilter]=useState('all'),[processing,setProcessing]=useState(''),[separation,setSeparation]=useState(false);
  async function load(){setLoading(true);setError('');try{await window.soundtraceAccountReady;setItems(window.SoundTraceDemo?(await api('/api/memories')).memories:(await api('/api/material-library')).materials);}catch(e){setError(e.message);}finally{setLoading(false);}}
  useEffect(()=>{api('/api/health').then(x=>setSeparation(!!x.stem_separation)).catch(()=>{});},[]);
  async function separate(){setError('');setProcessing('正在提交分离任务…');try{await runSoundJob({memory_id:memory.id,source_ref:memory.audio,type:'separate'},new AbortController().signal,setProcessing);await load();}catch(e){setError(e.message);}finally{setProcessing('');}}
  const visible=items.filter(item=>(filter==='all'||(item.material_kind||'original')===filter)&&((item.title||'')+' '+(item.original_title||'')).toLowerCase().includes(query.toLowerCase()));
  useEffect(()=>{load();window.addEventListener('soundtrace-login',load);return()=>window.removeEventListener('soundtrace-login',load);},[refreshKey]);
  useEffect(()=>{if(!source)return;const url=URL.createObjectURL(encodeWav(source));setPreview(url);return()=>URL.revokeObjectURL(url);},[source]);
  return <section className={`sound-library ${rawSuccess?'raw-success':''}`} aria-label="声音素材库">
    <aside className="library-sidebar">{source&&<div className="library-tools"><button className="quiet" onClick={onImport} disabled={busy||!!processing}>更换素材</button><button className="quiet" onClick={onNew} disabled={busy||!!processing}>清空当前选择</button></div>}{onRestore&&<button className="quiet" onClick={onRestore} disabled={busy||!!processing}>继续上次的手记 ↗</button>}
      <div className="library-heading"><h2>我的素材库</h2><span>{items.length+' 段素材'}</span></div>
      <label className="material-search">查找素材<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="名称或来源"/></label><label className="material-filter">素材类型<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">全部素材</option><option value="original">原始音轨</option><option value="separated">分离声部</option></select></label><div className="library-list">{visible.map((item,index)=><button key={item.material_id||item.id} type="button" className={`library-item ${item.audio===memory?.audio?'is-selected':''}`} disabled={busy||!!processing} aria-pressed={item.audio===memory?.audio} onClick={()=>onSelect(item)}><RasterArt id={["cassette-small-blue","cassette-small-yellow","cassette-small-red"][index%3]}/><span><strong>{item.title}</strong><small>{item.material_kind==='separated'?'分离声部 · '+item.original_title:item.source_type==='video'?'视频提取':'原始音轨'} · {clock(item.duration)}</small></span></button>)}</div>
      {loading&&<p className="library-empty" role="status">正在读取素材…</p>}{error&&<p role="alert" className="error">{error}<button type="button" onClick={load}>重试</button></p>}
    </aside>
    <div className="library-current">{source?<><div className="library-current-info"><span className="library-current-caption">{rawSuccess?'原声已保存':'当前用于创作的素材'}</span><h3>{memory?.title||name}</h3><p>{clock(source.duration)}</p></div>
      <RasterArt id={rawSuccess?'raw-saved':'library-hero'} className="library-sound-mark"/>
      <AudioPreview src={preview} duration={source.duration} label="试听当前原声" busy={busy}/>
      <div className="material-downloads"><button className="quiet" onClick={()=>download(encodeWav(source),(memory?.title||name)+'.wav')}>下载当前声音</button>{memory?.original_file&&<a className="quiet" href={'/'+memory.original_file} download={memory.original_filename}>下载原始{memory.source_type==='video'?'视频':'文件'} ↗</a>}</div>
      {!window.SoundTraceDemo&&memory&&<div className="material-separate"><button className="outline" disabled={!separation||busy||!!processing} onClick={separate}>分离人声与乐器声部</button><p>适合人声与音乐，分离结果存入素材库。</p>{processing&&<p role="status">{processing}</p>}{!separation&&<p>分轨服务尚未配置</p>}</div>}<div className="library-current-actions">{!memory&&<button className="outline" disabled={busy||!!processing} onClick={onSave}>保存素材</button>}<button className="primary" disabled={busy||!!processing} onClick={onGenerate}>下一步：选择音乐风格 →</button></div>
      {rawSuccess&&<div className="raw-success-actions"><button className="outline" onClick={onDismissSuccess}>留在素材库</button><a className="outline" href={route('/album?scene='+memory?.scene)}>查看已保存作品</a><a className="outline" href={route('/capture')}>再录一段</a><button className="outline" onClick={()=>download(encodeWav(source),name+'.wav')}>下载原声</button><a className="raw-home" href={route('/')}>回首页</a></div>}
    </>:<div className="material-empty"><h2>把素材留下，再让它成为音乐。</h2><div className="material-entry-actions"><button className="primary" onClick={onImport} disabled={busy||!!processing}>上传音频或视频</button><a className="outline" href={route('/capture')}>开始录音</a></div><p>最多 60 MB · 5 分钟</p></div>}</div>
    <aside className="library-next"><RasterArt id="library-record"/><h2>让声音成为日记。</h2><p>先选择原声或分离声部，再写下风格与故事，让 AI 围绕素材创作。</p><a className="outline" href={route('/album')}>我的音乐 ↗</a><a className="quiet" href={route('/map')}>声音地图 ↗</a></aside>
    <RasterArt id="library-footer" className="library-bottom-art"/>
  </section>;
}
