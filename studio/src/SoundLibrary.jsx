import RasterArt from './RasterArt';
import AudioPreview from './AudioPreview';
import React,{useEffect,useState} from 'react';
import {api,route} from './api';
import {clock,encodeWav,download} from './audio';
import './diary-flow.css';

export default function SoundLibrary({source,name,memory,onSave,onGenerate,onSelect,busy,refreshKey,onImport,onNew,onRestore,rawSuccess,onDismissSuccess}){
  const [items,setItems]=useState([]),[error,setError]=useState(''),[loading,setLoading]=useState(true),[preview,setPreview]=useState('');
  async function load(){setLoading(true);setError('');try{await window.soundtraceAccountReady;setItems((await api('/api/memories')).memories);}catch(e){setError(e.message);}finally{setLoading(false);}}
  useEffect(()=>{load();window.addEventListener('soundtrace-login',load);return()=>window.removeEventListener('soundtrace-login',load);},[refreshKey]);
  useEffect(()=>{if(!source)return;const url=URL.createObjectURL(encodeWav(source));setPreview(url);return()=>URL.revokeObjectURL(url);},[source]);
  return <section className={`sound-library ${rawSuccess?'raw-success':''}`} aria-label="声音素材库">
    <aside className="library-sidebar"><div className="library-tools"><a href={route('/capture')} className="primary">开始录音</a><button className="quiet" onClick={onImport} disabled={busy}>导入音频 ↗</button><button className="quiet" onClick={onNew} disabled={busy}>新建手记</button>{onRestore&&<button className="quiet" onClick={onRestore} disabled={busy}>继续上次的手记 ↗</button>}</div>
      <div className="library-heading"><h2>我的原始素材</h2><span>{memory?'原声已保存':'原声已准备好'}</span></div>
      <div className="library-list">{items.slice(0,12).map(item=><button key={item.id} type="button" className={`library-item ${item.id===memory?.id?'is-selected':''}`} disabled={busy} aria-pressed={item.id===memory?.id} onClick={()=>onSelect(item)}><RasterArt id="tape"/><span><strong>{item.title}</strong><small>{new Date(item.captured_at*1000).toLocaleDateString('zh-CN')} · {clock(item.duration)}</small></span></button>)}</div>
      {loading&&<p className="library-empty" role="status">正在读取素材…</p>}{error&&<p role="alert" className="error">{error}<button type="button" onClick={load}>重试</button></p>}
    </aside>
    <div className="library-current"><div className="library-current-info"><span className="library-current-caption">{rawSuccess?'原声已保存':'当前选择的原始素材'}</span><h3>{memory?.title||name}</h3><p>{clock(source.duration)}</p></div>
      <RasterArt id={rawSuccess?'raw-saved':'library-hero'} className="library-sound-mark"/>
      <AudioPreview src={preview} duration={source.duration} label="试听当前原声" busy={busy}/>
      <div className="library-current-actions">{!memory&&<button className="outline" disabled={busy} onClick={onSave}>保存素材</button>}<button className="primary" disabled={busy} onClick={onGenerate}>生成音乐日记 →</button></div>
      {rawSuccess&&<div className="raw-success-actions"><button className="outline" onClick={onDismissSuccess}>留在素材库</button><a className="outline" href={route('/album?scene='+memory?.scene)}>去收藏间看看</a><a className="outline" href={route('/capture')}>再录一段</a><button className="outline" onClick={()=>download(encodeWav(source),name+'.wav')}>下载原声</button><a className="raw-home" href={route('/')}>回首页</a></div>}
    </div>
    <aside className="library-next"><RasterArt id="library"/><h2>让声音成为日记。</h2><p>把照片、心情和这一刻的声音放在一起。</p><a className="outline" href={route('/album')}>我的收藏 ↗</a><a className="quiet" href={route('/map')}>声音地图 ↗</a></aside>
    <RasterArt id="library-footer" className="library-bottom-art"/>
  </section>;
}
