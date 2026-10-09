import RasterArt from './RasterArt';
import React, {useEffect,useState} from 'react';
import {diaryGroups, diaryValue} from './diary-options';
import {styles} from './theme';
import {api} from './api';
import './diary-flow.css';
const order=['weather','mood','activity'];
const headings=['那天，天气怎么样？','此刻，是什么心情？','你正在做什么？','把这一刻留在纸上。','想把它变成什么音乐？'];
export default function DiarySetup({diary,setDiary,style,setStyle,onContinue,onBack,busy}) {
  const [step,setStep]=useState(0),[error,setError]=useState(''),[locating,setLocating]=useState(false),[urls,setUrls]=useState([]),[artEnabled,setArtEnabled]=useState(false);
  const group=diaryGroups.find(g=>g.id===order[step]);
  const update=(key,value)=>{setDiary(prev=>({...prev,[key]:value}));setError('');};
  useEffect(()=>{window.scrollTo({top:0,behavior:'instant'});},[step]);
  useEffect(()=>{if(!window.SoundTraceDemo)api('/api/art/config').then(c=>setArtEnabled(c.enabled)).catch(()=>{});},[]);
  useEffect(()=>{const next=(diary.images||[]).map(f=>URL.createObjectURL(f));setUrls(next);return()=>next.forEach(URL.revokeObjectURL);},[diary.images]);
  function next(){if(group&&!diaryValue(diary,group.id)){setError('写下你的'+group.title);return;}setStep(s=>Math.min(4,s+1));setError('');}
  function choose(id){update(group.id,id);if(id!=='other')setStep(s=>s+1);}
  function locate(){
    if(window.SoundTraceDemo){setDiary(prev=>({...prev,lat:30.258,lng:120.149,location:'西湖 · 演示点位'}));setError('');return;}
    if(!navigator.geolocation){setError('无法获取位置，可以继续保存。');return;}
    setLocating(true);navigator.geolocation.getCurrentPosition(p=>{setDiary(prev=>prev.includeLocation?({...prev,lat:p.coords.latitude,lng:p.coords.longitude}):prev);setLocating(false);},()=>{setLocating(false);setError('未获得定位权限，仍可继续制作；也可以重试定位。');},{timeout:10000});
  }
  return <section className="diary-setup diary-wizard" aria-label="制作音乐日记">
    <div className="wizard-top"><button className="quiet" disabled={busy} onClick={()=>step?setStep(step-1):onBack()}>← {step?'上一步':'素材库'}</button><span aria-label={`第 ${step+1} 步，共 5 步`}>{step+1} / 5</span></div>
    <div className="wizard-dots" aria-hidden="true">{headings.map((_,i)=><i key={i} className={i<=step?'complete':''}/>)}</div>
    <div className="diary-title"><h2>{headings[step]}</h2><RasterArt id="diary"/></div>
    {group&&<fieldset key={group.id} className="diary-choice-group" disabled={busy}><legend>{group.title}</legend><div className="diary-choice-grid">{[...group.options,['other','其他']].map(([id,label])=><button key={id} type="button" className="diary-choice" aria-pressed={diary[group.id]===id} onClick={()=>choose(id)}><RasterArt id={id==='other'?'other':`${group.id}-${id}`}/><span>{label}</span></button>)}</div>
      {diary[group.id]==='other'&&<div className="diary-other"><label>其他{group.title}<input autoFocus maxLength={32} value={diary[group.id+'Other']||''} onChange={e=>update(group.id+'Other',e.target.value)} onKeyDown={e=>{if(e.key==='Enter')next();}}/></label><button type="button" className="primary" onClick={next}>继续 →</button></div>}
    </fieldset>}
    {step===3&&<div className="diary-story"><label className="field">给这一刻起个名字<input maxLength={80} value={diary.title||''} onChange={e=>update('title',e.target.value)} placeholder="例如：湖边吹来的晚风"/></label><label className="field">写下自己的话<textarea maxLength={1200} value={diary.notes||''} onChange={e=>update('notes',e.target.value)} placeholder="当时发生了什么？"/></label>
      <label className="story-upload">＋ 留下几张照片<input type="file" accept="image/*" multiple onChange={e=>{const remaining=6-(diary.existingImages||[]).length;update('images',[...e.target.files].slice(0,remaining));}}/><small>共可保存 6 张</small></label>
      <div className="media-preview">{(diary.existingImages||[]).map(p=><img key={p} src={'/'+p} alt="原素材照片"/>)}{urls.map((u,i)=><div key={u}><img src={u} alt={'新增照片 '+(i+1)}/><button type="button" aria-label={'移除照片 '+(i+1)} onClick={()=>update('images',diary.images.filter((_,n)=>n!==i))}>×</button></div>)}</div>
      {!!(urls.length || diary.existingImages?.length)&&<fieldset className="story-background"><legend>记忆背景</legend><label><input type="radio" name="background-mode" checked={diary.backgroundMode!=='stylized'} onChange={()=>update('backgroundMode','photo')}/>照片原图</label><label><input type="radio" name="background-mode" disabled={!artEnabled} checked={diary.backgroundMode==='stylized'} onChange={()=>update('backgroundMode','stylized')}/>生成手绘</label><small>{artEnabled?'选择手绘会将第一张照片发送给豆包；原照片保留。':'手绘服务待配置，当前使用原照片。'}</small></fieldset>}
      <label className="share-check"><input type="checkbox" checked={!!diary.includeLocation} onChange={e=>{update('includeLocation',e.target.checked);if(e.target.checked&&diary.lat==null)locate();}}/>{window.SoundTraceDemo?'记录演示位置（西湖，不获取真实定位）':'记录这段记忆的位置'}</label>
      {diary.includeLocation&&<div className="story-location"><label className="field">地点名称<input maxLength={100} value={diary.location||''} onChange={e=>update('location',e.target.value)} placeholder="例如：西湖边"/></label><button type="button" className="quiet" onClick={locate} disabled={locating}>{locating?'正在定位…':diary.lat!=null?'已定位 ✓ · 重新获取':'获取位置'}</button></div>}
      <button className="primary" type="button" disabled={locating} onClick={next}>选择音乐 →</button>
    </div>}
    {step===4&&<fieldset className="diary-choice-group music-directions" disabled={busy}><legend>音乐风格</legend>{!window.SoundTraceDemo&&<p className="material-source-note">选择风格后，将所选音频素材和下方文字一起发送给 Mureka，围绕素材生成伴奏。素材会作为独立音轨保留在成品中，可调整比例。</p>}{window.SoundTraceDemo&&<p className="demo-flow-note">选择一种预制编曲，马上试听；正式版使用音乐生成服务。</p>}{!window.SoundTraceDemo&&<label className="diary-other">想听到的细节<input maxLength={500} value={diary.prompt||''} onChange={e=>update('prompt',e.target.value)} placeholder="可选：温暖的钢琴，轻轻的鼓点"/></label>}<div className="direction-tags">{(window.SoundTraceDemo?.styles||styles).map(([id,label])=><button type="button" key={id} aria-pressed={style===id} onClick={()=>{setStyle(id);onContinue(id);}}><RasterArt id={'style-'+id}/><span>{label}</span></button>)}</div></fieldset>}
    {error&&<p role="alert" className="error">{error}</p>}
  </section>;
}

