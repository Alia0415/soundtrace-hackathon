import RasterArt from './RasterArt';
import React,{useEffect,useRef,useState} from 'react';
import {art,scenes} from './theme';
import {api,route} from './api';
import {download,encodeWav} from './audio';
import {startRecorder} from './recorder';
import {diaryValue} from './diary-options';

const moods=['宁静','思念','雀跃','忧郁','治愈','冒险'];
export default function SaveDialog({close,render,scene,setScene,version,project,source,rawOnly=false,onSaved,onGenerate,initialName='',diary,sourceMemory}){
  const dialog=useRef(),[title,setTitle]=useState(''),[locationName,setLocationName]=useState(''),[geo,setGeo]=useState({}),[notes,setNotes]=useState(''),[mood,setMood]=useState(''),[weather,setWeather]=useState(''),[images,setImages]=useState([]),[videos,setVideos]=useState([]),[audioFiles,setAudioFiles]=useState([]),[share,setShare]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(null),[blob,setBlob]=useState(null),[speaking,setSpeaking]=useState(false),[speechEnabled,setSpeechEnabled]=useState(false);
  const recordedAt=useRef(Date.now()),speech=useRef();
  useEffect(()=>{setTitle(diary?.title||sourceMemory?.title||initialName);setNotes(diary?.notes??sourceMemory?.notes??'');setLocationName(diary?.location??sourceMemory?.location??'');setImages(diary?.images||[]);setMood(diaryValue(diary,'mood')||sourceMemory?.mood||'');setWeather(diaryValue(diary,'weather')||sourceMemory?.weather||'');if(diary?diary.includeLocation&&diary.lat!=null:sourceMemory?.lat!=null)setGeo({lat:diary?.lat??sourceMemory?.lat,lng:diary?.lng??sourceMemory?.lng});if(sourceMemory?.captured_at)recordedAt.current=sourceMemory.captured_at*1000;},[]);
  useEffect(()=>{dialog.current.showModal();return()=>{speech.current?.dispose();dialog.current?.close();};},[]);
  useEffect(()=>{api('/api/health').then(x=>setSpeechEnabled(!!x.speech_to_text)).catch(()=>{});},[]);
  function locate(){
    if(window.SoundTraceDemo){setGeo({lat:30.258,lng:120.149});setLocationName('西湖 · 演示点位');setWeather(value=>value||'晴天');return;}
    if(!navigator.geolocation){setError('此浏览器无法定位，请手动填写地点。');return;}
    navigator.geolocation.getCurrentPosition(async p=>{
      const lat=p.coords.latitude,lng=p.coords.longitude;setGeo({lat,lng});
      try{const r=await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,weather_code&timezone=auto`);if(r.ok){const data=await r.json();setWeather(`${Math.round(data.current?.temperature_2m)}°C`);}}catch{}
    },()=>setError('未能获取位置，可以手动填写地点。'),{timeout:10000});
  }
  async function dictate(){
    setError('');setSpeaking(true);
    try{
      speech.current=await startRecorder(()=>{},()=>{});
      await new Promise(resolve=>setTimeout(resolve,5500));
      const buffer=await speech.current.stop();speech.current=null;
      const form=new FormData();form.append('file',encodeWav(buffer),'description.wav');
      const result=await api('/api/transcribe',{method:'POST',body:form});
      if(result.text)setTitle(value=>[value,result.text].filter(Boolean).join(' '));
      else setError('没有听清，请再说一次或直接输入。');
    }catch(e){setError(e.name==='NotAllowedError'?'请先允许使用麦克风，也可以直接输入。':e.message||'语音识别暂时不可用。');}
    finally{speech.current?.dispose();speech.current=null;setSpeaking(false);}
  }
  async function save(skip=false){
    setBusy(true);setError('');
    try{
      if(!source)throw new Error('找不到录音原声，请重新录制。');
      const original=encodeWav(source),form=new FormData();
      if(!sourceMemory)form.append('audio',original,'original.wav');
      if(!rawOnly){const mix=await render();form.append('music_audio',mix.blob,'music.wav');}
      form.append('captured_at',String(recordedAt.current/1000));form.append('scene',scene);
      form.append('project',JSON.stringify(project));
        if(sourceMemory?.audio)form.append('music_source_ref',sourceMemory.audio);
      if(!rawOnly){form.set('mood',mood);form.set('weather',weather);form.append('activity',diaryValue(diary,'activity'));form.append('music_prompt',diary?.prompt||'');form.append('music_style',project?.style||'ambient');form.append('include_location',String(geo.lat!=null));form.append('background_mode',diary?.backgroundMode==='stylized'?'stylized':'photo');}
      if(!skip){
        form.append('title',title.trim());form.append('notes',notes.trim());form.set('mood',mood);
        form.append('location',locationName.trim());form.set('weather',weather);
        if(geo.lat!=null){form.append('lat',String(geo.lat));form.append('lng',String(geo.lng));}
        images.forEach(file=>form.append('images',file));
        videos.forEach(file=>form.append('videos',file));
        audioFiles.forEach(file=>form.append('audio_files',file));
        form.append('share',String(share));
      }
      const memory=await api(sourceMemory?`/api/memories/${sourceMemory.id}/music`:'/api/memories',{method:'POST',body:form});
      setBlob(original);setSaved(memory);onSaved?.(memory);
      let artUnavailable=false;
      if(!rawOnly && !window.SoundTraceDemo && diary?.backgroundMode==='stylized' && memory.images?.length){
        try{await api('/api/art/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({memory_id:memory.id,image_index:0,consent:true})});}
        catch{artUnavailable=true;}
      }
      if(!rawOnly)window.location.assign(route(`/album?scene=${encodeURIComponent(scene)}&saved=${encodeURIComponent(memory.id)}${artUnavailable?'&art_unavailable=1':''}`));
    }catch(e){setError(e.message||'保存失败，录音仍保留在此设备。');}
    finally{setBusy(false);}
  }
  return <dialog ref={dialog} className="save-dialog" onCancel={e=>{e.preventDefault();if(!busy)close();}}>
    <button className="dialog-close" aria-label="关闭保存窗口" disabled={busy} onClick={close}>×</button>
    <div className="save-art"><RasterArt id={rawOnly?'tape':'vinyl'} label={rawOnly?"原声磁带":"音乐日记唱片"}/></div>
    <div className="save-content">{saved?<><h2>{rawOnly?'原声已存入素材库':'音乐日记已保存'}</h2><p>{rawOnly?'随时可以用这段声音制作音乐日记。':'磁带保留原声，唱片保存音乐与这段记忆。'}</p>{rawOnly&&<><button className="primary" onClick={onGenerate}>生成音乐日记 →</button><button className="quiet" onClick={close}>留在素材库</button></>}<a className={rawOnly?'quiet':'primary'} href={`/album?scene=${scene}`}>打开我的音乐 ↗</a><button className="quiet" onClick={()=>download(blob,`${saved.title}.wav`)}>下载原声</button></>:<>
      <h2>{rawOnly?'这是什么声音？':'保存音乐'}</h2>
      <p>{rawOnly?'留下一句话，或直接保存。其他内容选填。':'音乐将保存到“我的音乐”。下面的信息均为选填，分享默认关闭。'}</p>
      <div className="save-answer"><label className="field">声音的名字<input maxLength={80} value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：下雨前的风" autoFocus/></label><button type="button" className="outline" onClick={dictate} disabled={!speechEnabled||speaking||busy} title={speechEnabled?'录音后转为文字':'语音识别尚未启用，请直接输入'}>{speaking?'正在听你说…':speechEnabled?'说给我听':'请直接输入'}</button></div>
      <div className="save-meta"><span>{new Date(recordedAt.current).toLocaleString('zh-CN',{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'})}</span><span>{weather||'天气未获取'}</span>{<button type="button" className="quiet" onClick={locate} disabled={busy}>{geo.lat!=null?'位置已记录 ✓':window.SoundTraceDemo?'使用演示位置（西湖）':'获取位置与天气'}</button>}</div>
      <label className="field">地点<input maxLength={100} value={locationName} onChange={e=>setLocationName(e.target.value)} placeholder="在哪里录的？"/></label>
      {rawOnly?<div className="mood-picks" aria-label="此刻心情">{moods.map(value=><button type="button" key={value} aria-pressed={mood===value} onClick={()=>setMood(mood===value?'':value)}>{value}</button>)}</div>:<p>{[weather,mood,diaryValue(diary,'activity')].filter(Boolean).join(' · ')} · {geo.lat!=null?'位置已记录':'不记录位置'}</p>}
      <label className="field">补充笔记<textarea maxLength={1200} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="当时发生了什么？"/></label>
      {!sourceMemory&&<div className="save-media"><label>照片<input type="file" accept="image/*" multiple onChange={e=>setImages([...e.target.files].slice(0,6))}/><small>{images.length?images.length+' 张已选':'最多 6 张'}</small></label><label>视频<input type="file" accept="video/mp4,video/webm,video/quicktime" multiple onChange={e=>setVideos([...e.target.files].slice(0,2))}/><small>{videos.length?videos.length+' 段已选':'最多 2 段'}</small></label><label>补充音频<input type="file" accept="audio/*" multiple onChange={e=>setAudioFiles([...e.target.files].slice(0,4))}/><small>{audioFiles.length?audioFiles.length+' 段已选':'最多 4 段'}</small></label></div>}
      <MediaPreview files={images}/>
      {sourceMemory?.images?.length>0&&<><p>沿用素材中的 {sourceMemory.images.length} 张照片。</p><div className="media-preview">{sourceMemory.images.map(path=><img src={'/'+path} alt="素材中的记忆照片" key={path} loading="lazy"/>)}</div></>}
      <p className="scene-picker-label">选择一个场景</p><div className="scene-picker" aria-label="收藏场景">{scenes.map(([id,name])=><button key={id} title={name} aria-label={name} aria-pressed={scene===id} onClick={()=>setScene(id)}><RasterArt id={id}/></button>)}</div>
      {<label className="share-check"><input type="checkbox" checked={share} onChange={e=>setShare(e.target.checked)}/>同时分享到社区</label>}
      <div className="save-actions">{rawOnly&&<button className="quiet" onClick={()=>save(true)} disabled={busy}>跳过直接保存</button>}<button className="primary" onClick={()=>save(false)} disabled={busy}>{busy?'正在保存…':rawOnly?'保存素材':'保存到我的音乐 ↗'}</button></div>
      {error&&<div className="error" role="alert">{error}</div>}
    </>}</div>
  </dialog>;
}
function MediaPreview({files}) {
  const [urls,setUrls]=useState([]);
  useEffect(()=>{const next=files.map(file=>URL.createObjectURL(file));setUrls(next);return()=>next.forEach(url=>URL.revokeObjectURL(url));},[files]);
  if(!urls.length)return null;
  return <div className="media-preview" aria-label="已选择的照片">{urls.map((url,index)=><img key={url} src={url} alt={'已选择照片 '+(index+1)}/>)}</div>;
}
