import RasterArt from './RasterArt';
import {clipRate,clipEditDelta} from './clip-time';
import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Waveform,ClipInteractionProvider,usePlaylistControls,usePlaylistData,usePlaylistState,usePlaybackAnimation} from '@waveform-playlist/browser';
import {useExportWav} from '@waveform-playlist/browser/tone';
import {createTrack,createClipFromSeconds} from '@waveform-playlist/core';
import {clock,decode,encodeWav} from './audio';
import {runSoundJob,runMusicJob} from './api';
import {saveDraft} from './drafts';
import {styles,art} from './theme';
import {masterEffects} from './App';
import SaveDialog from './SaveDialog';
import {diaryValue} from './diary-options';

export default function Editor({tracks,setTracks,style,scene,setScene,ai,soundProcessing,source,busy,setBusy,setError,musicFailed,recording,seconds,record,stopRecording,pick,changeStyle,handle,initial,abortJob,diary,memory,onSaved,onEditDiary}){
  const controls=usePlaylistControls(),data=usePlaylistData(),state=usePlaylistState(),playback=usePlaybackAnimation(),{exportWav,isExporting}=useExportWav();
  const [version,setVersion]=useState(initial?.version||'draft'),[aiMusic,setAiMusic]=useState(initial?.aiMusic||null),[draftMusic,setDraftMusic]=useState(initial?.draftMusic||null);
  const [balance,setBalance]=useState(initial?.balance??40),[saveOpen,setSaveOpen]=useState(false),[savedLocal,setSavedLocal]=useState(''),[jobStatus,setJobStatus]=useState(''),[target,setTarget]=useState(''),[extra,setExtra]=useState(false),[tags,setTags]=useState([]),[switching,setSwitching]=useState(false);
  const [visibleTime,setVisibleTime]=useState(0),[generationFailed,setGenerationFailed]=useState(false);
  const resume=useRef(null),mounted=useRef(true),firstMusic=useRef(null),latest=useRef({tracks,data}),lastClock=useRef(0);
  latest.current={tracks,data};
  const field=tracks.find(t=>t.id==='field'),music=tracks.find(t=>t.id==='music');
  useEffect(()=>{const id='studio-clock';playback.registerFrameCallback(id,({time})=>{const now=Date.now();if(now-lastClock.current>90){lastClock.current=now;setVisibleTime(time);}});return()=>playback.unregisterFrameCallback(id);},[playback.registerFrameCallback,playback.unregisterFrameCallback]);
  useEffect(()=>setVisibleTime(playback.currentTime),[playback.currentTime]);
  useEffect(()=>{if(music&&!firstMusic.current){firstMusic.current=music;if(version==='draft')setDraftMusic(music);}},[music,version]);
  useEffect(()=>()=>{mounted.current=false;abortJob.current?.abort();},[]);
  function switchMusic(track,next){
    if(!track||switching||!data.isReady)return;resume.current={time:Math.max(0,playback.getPlaybackTime()),play:playback.isPlaying};setSwitching(true);controls.pause();
    const current=tracks.find(t=>t.id==='music');if(current){if(version==='draft')setDraftMusic(current);else setAiMusic(current);}
    if(next==='draft')setDraftMusic(track);else setAiMusic(track);
    setTracks([...trackSnapshot.filter(t=>t.id!=='music'),{...track,id:'music',volume:balance/100}]);setVersion(next);
  }
  handle.current={pause:controls.pause,replaceMusic:switchMusic,onReady:()=>{setSwitching(false);const r=resume.current;if(!r)return;resume.current=null;const time=Math.max(0,Math.min(r.time,latest.current.data.duration));controls.seekTo(time);if(r.play)controls.play(time).catch(e=>setError(e.message));}};
  const trackSnapshot=useMemo(()=>tracks.map((t,i)=>({...t,...data.trackStates[i]})),[tracks,data.trackStates]);
  useEffect(()=>{if(!data.isReady||!tracks.length)return;setSavedLocal('');
    const timer=setTimeout(()=>{const alts=[draftMusic&&{...(version==='draft'?music:draftMusic),id:'variant-draft'},aiMusic&&{...(version==='ai'?music:aiMusic),id:'variant-ai'}].filter(Boolean);
      saveDraft([...trackSnapshot,...alts],{style,scene,version,balance,diary,memoryId:memory?.id}).then(()=>{if(mounted.current)setSavedLocal('草稿已保存在此设备');}).catch(()=>{if(mounted.current)setSavedLocal('设备空间不足，请保存或下载作品');});
    },800);return()=>clearTimeout(timer);
  },[trackSnapshot,draftMusic,aiMusic,style,scene,version,balance,data.isReady,diary,memory?.id]);
  function mix(value){setBalance(value);tracks.forEach((t,i)=>controls.setTrackVolume(i,t.id==='music'?value/100:(1-value/100)*.95));}
  async function generate(type='generate'){
    if((type==='generate'?!ai:!soundProcessing)||jobStatus||busy||recording)return;setError('');setGenerationFailed(false);setJobStatus('正在准备声音…');const controller=new AbortController();abortJob.current=controller;
    try{
      const results=type==='extract'?await runSoundJob({memory_id:memory?.id,type:'extract',target},controller.signal,setJobStatus):await runMusicJob({memory_id:memory?.id,style,prompt:diary?.prompt||'',title:diary?.title||memory?.title,notes:diary?.notes,mood:diaryValue(diary,'mood'),weather:diaryValue(diary,'weather'),activity:diaryValue(diary,'activity'),duration:Math.min(120,Math.max(30,Math.ceil(source.duration)))},controller.signal,setJobStatus);
      if(!mounted.current)return;
      const path=type==='generate'?results.generated:type==='hum'?(results.melody||results.synth||results.synthesized):results.denoised;
      if(!path)throw new Error('服务未返回可用的音频，原草稿仍然保留。');
      const response=await fetch('/'+path.replace(/^\//,''),{signal:controller.signal});if(!response.ok)throw new Error('生成的声音暂时无法下载，请重试。');
      const buffer=await decode(await response.blob()),track=createTrack({id:type==='generate'?'music':crypto.randomUUID(),name:type==='generate'?'专属旋律':type==='hum'?'我的哼唱':target||'提取的声音',volume:type==='generate'?balance/100:.5,clips:[createClipFromSeconds({audioBuffer:buffer,startTime:0,fadeIn:{duration:.2},fadeOut:{duration:.4}})]});
      if(type==='generate')switchMusic({...track,id:'music'},'ai');else{const current=latest.current.tracks.map((t,i)=>({...t,...latest.current.data.trackStates[i]}));setTracks([...current.filter(t=>t.id!=='music'),track,...current.filter(t=>t.id==='music')]);}
    }catch(e){if(e.name!=='AbortError'){setGenerationFailed(true);setError(e.message);}}finally{if(mounted.current&&abortJob.current===controller){abortJob.current=null;setJobStatus('');}}
  }
  async function hum(){
    if(jobStatus||busy||recording||!data.isReady)return;
    setError('');setJobStatus('正在加载本机哼唱识别…');
    const controller=new AbortController();abortJob.current=controller;
    try{
      const {transcribeHum}=await import('./hum');
      const {buffer}=await transcribeHum(source,controller.signal,setJobStatus);
      if(!mounted.current||controller.signal.aborted)return;
      const track=createTrack({name:'哼唱旋律',volume:.6,clips:[createClipFromSeconds({audioBuffer:buffer,startTime:0,name:'哼唱旋律'})]});
      const current=latest.current.tracks.map((t,i)=>({...t,...latest.current.data.trackStates[i]}));
      setTracks([...current.filter(t=>t.id!=='hum'),{...track,id:'hum'}]);
    }catch(e){if(e.name!=='AbortError'&&mounted.current)setError(e.message);}
    finally{if(mounted.current&&abortJob.current===controller){abortJob.current=null;setJobStatus('');}}
  }
  async function analyze(){
    if(!soundProcessing||jobStatus||busy||recording)return;
    setError('');setJobStatus('正在辨认声音…');const controller=new AbortController();abortJob.current=controller;
    try{const result=await runSoundJob({memory_id:memory?.id,type:'analyze'},controller.signal,setJobStatus);if(mounted.current)setTags(result.tags||[]);}
    catch(e){if(e.name!=='AbortError'&&mounted.current)setError(e.message);}
    finally{if(mounted.current&&abortJob.current===controller){abortJob.current=null;setJobStatus('');}}
  }
  function cancelJob(){abortJob.current?.abort();abortJob.current=null;setJobStatus('');setError('已停止等待，原声和编辑已保留；服务已开始的生成可能继续运行。');}
  async function render(){if(data.duration>300)throw new Error('作品最长支持 5 分钟，请收拢时间线后保存。');controls.pause();return exportWav(latest.current.tracks,latest.current.data.trackStates,{autoDownload:false,applyEffects:true,effectsFunction:masterEffects,bitDepth:16});}
  const project={version:1,style,scene,diary,selectedVersion:version,tracks:trackSnapshot.map(t=>({id:t.id,name:t.name,volume:t.volume,muted:t.muted,clips:t.clips.map(c=>({startSample:c.startSample,offsetSamples:c.offsetSamples,durationSamples:c.durationSamples,sampleRate:c.sampleRate,gain:c.gain,fadeIn:c.fadeIn,fadeOut:c.fadeOut}))}))};
  function play(){const time=playback.getPlaybackTime();(playback.isPlaying?Promise.resolve(controls.pause()):controls.play(time>=data.duration?0:time)).catch(e=>setError(e.message));}
  return <section className="workbench" aria-label="声音工作台">
    <div className="workbench-top"><div className="editor-illustration"><RasterArt id="editor-hero"/></div><div className={`record-preview ${playback.isPlaying?'spinning':''}`}><RasterArt id="editor-record" label="这次声音的唱片"/></div><div className="workbench-title"><span className="eyebrow">{window.SoundTraceDemo?'DEMO / 演示音乐':music?'AI / 专属旋律':'LIVE / 现场原声'}</span><h2>{diary?.title||field?.clips[0]?.name||'此刻的声音'}</h2><span className="save-state" role="status">{savedLocal||'正在准备草稿'}</span></div><div className="diary-context-summary"><RasterArt id="editor-context"/><span>{['mood','weather','activity'].map(key=>diaryValue(diary,key)).filter(Boolean).join(' · ')}</span><button className="quiet" onClick={()=>{setTracks(trackSnapshot);onEditDiary();}} disabled={recording||!!busy||!!jobStatus}>修改此刻</button></div><button className="primary keep-button desktop-keep" onClick={()=>setSaveOpen(true)} disabled={!data.isReady||isExporting||recording||!!busy}><RasterArt id="icon-heart-white"/>收藏这段声音 ↗</button></div>
    <div className="transport"><button className="play-button transport-play" aria-label={playback.isPlaying?'暂停':'播放'} onClick={play} disabled={!data.isReady||recording||isExporting}>{playback.isPlaying?<RasterArt id="transport-pause"/>:<RasterArt id="icon-play"/ >}</button><span className="time">{clock(Math.min(visibleTime,data.duration))} <span>/ {clock(data.duration)}</span></span><div className="transport-actions"><button className="icon-button transport-start" aria-label="回到开头" onClick={()=>controls.seekTo(0)}><RasterArt id="transport-start"/></button><button className="icon-button transport-undo" aria-label="撤销编辑" disabled={!state.canUndo} onClick={controls.undo}><RasterArt id="transport-undo"/></button><button className="icon-button transport-redo" aria-label="重做编辑" disabled={!state.canRedo} onClick={controls.redo}><RasterArt id="transport-redo"/></button><button className="icon-button transport-zoom-out" aria-label="缩小时间线" disabled={!data.canZoomOut} onClick={controls.zoomOut}><RasterArt id="icon-minus"/></button><button className="icon-button transport-zoom-in" aria-label="放大时间线" disabled={!data.canZoomIn} onClick={controls.zoomIn}><RasterArt id="icon-plus"/></button></div></div>
    <div className="timeline"><ClipInteractionProvider touchOptimized><Waveform interactiveClips touchOptimized showClipHeaders showFades renderTrackControls={i=><div className="track-label" data-track-kind={tracks[i]?.id}><span>{tracks[i]?.id==='field'?'现场':tracks[i]?.id==='music'?'音乐':tracks[i]?.id==='hum'?'旋律':'声源'}</span><button aria-label={`${data.trackStates[i]?.muted?'取消静音':'静音'}${tracks[i]?.name}`} aria-pressed={!!data.trackStates[i]?.muted} onClick={()=>controls.setTrackMute(i,!data.trackStates[i]?.muted)}><RasterArt id="icon-volume"/><span className="sr-only">{data.trackStates[i]?.muted?'取消静音':'静音'}</span></button></div>}/></ClipInteractionProvider></div>
    <div className="seek-strip"><input type="range" min="0" max={data.duration||1} step=".05" value={Math.min(visibleTime,data.duration)} aria-label="播放位置" onChange={e=>controls.seekTo(Number(e.target.value))}/></div>
    <div className="mix-controls"><label className="music-direction-control"><RasterArt id="icon-piano"/>音乐方向<select aria-label="音乐方向" value={style} disabled={!!busy||recording||switching} onChange={e=>changeStyle(e.target.value,data.duration)}>{styles.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label className="balance"><span>现场</span><input aria-label="现场与音乐的平衡" type="range" min="0" max="100" value={balance} onChange={e=>mix(Number(e.target.value))}/><span>音乐</span></label></div>
    <div className="editor-bottom"><div className="add-actions"><button className="quiet" onClick={recording?stopRecording:record} disabled={!!busy}><RasterArt id="icon-microphone"/>{recording?`结束 ${clock(seconds)}`:'重新录音'}</button><button className="quiet" onClick={pick} disabled={recording||!!busy}><RasterArt id="icon-music"/>更换音频 ↗</button><button className="quiet" aria-expanded={extra} onClick={()=>setExtra(!extra)}><RasterArt id="icon-tune"/>细调 {extra?'−':'＋'}</button></div><div className="ai-actions">{aiMusic&&<div className="segmented" aria-label="试听版本"><button aria-pressed={version==='draft'} disabled={switching} onClick={()=>switchMusic(draftMusic,'draft')}>A 草稿</button><button aria-pressed={version==='ai'} disabled={switching} onClick={()=>switchMusic(aiMusic,'ai')}>B 专属旋律</button></div>}<button className="outline" disabled={!ai||!!jobStatus||recording||!!busy||switching} onClick={()=>generate()}>{aiMusic?'再创作一版':'生成专属旋律'} <span aria-hidden="true">✧</span></button></div></div>
    {(musicFailed||generationFailed)&&<section className="music-generation-failure" aria-label="音乐生成失败"><RasterArt id="import-error"/><h3>旋律暂时没有准备好</h3><p>原声与编辑已保留，可以重试。</p><button className="outline" onClick={()=>musicFailed?changeStyle(style,data.duration):generate()} disabled={!!busy||!!jobStatus}>重试生成音乐</button></section>}
    {!ai&&<p className="availability">AI 服务暂未连接，本地录音、编辑和收藏均可使用。</p>}
    {jobStatus&&<div className="job-status" role="status"><span className="pulse-dot"/>{jobStatus}<button className="quiet" onClick={cancelJob}>停止等待</button></div>}
    {extra&&<div className="fine-edit"><h3>细调这一刻</h3><ClipDetails tracks={tracks} engine={data.playoutRef.current} rate={data.sampleRate}/>{<div className="extract">{!soundProcessing&&<p className="availability">声音辨识与提取服务暂未连接；下方哼唱转旋律仍可使用。</p>}<button className="quiet" onClick={analyze} disabled={!soundProcessing||!!jobStatus||!!busy||recording}>辨认录音中的声音</button><div className="tag-row">{tags.map((t,i)=><button key={i} onClick={()=>setTarget(t.en)}>{t.zh||t.en}</button>)}</div><label>想留下的声源<input placeholder="例如：鸟鸣、脚步、雨声" value={target} onChange={e=>setTarget(e.target.value)}/></label><button className="outline" disabled={!soundProcessing||!target.trim()||!!jobStatus||!!busy||recording} onClick={()=>generate('extract')}>提取声音</button><button className="quiet" disabled={!!jobStatus||!!busy||recording||!data.isReady} onClick={hum}>这是我的哼唱</button><p className="availability">哼唱转旋律在本机完成，不需要音乐服务。请使用清晰的单人哼唱。</p></div>}</div>}
    <button className="primary keep-button mobile-keep" onClick={()=>setSaveOpen(true)} disabled={!data.isReady||isExporting||recording||!!busy}><RasterArt id="icon-heart-white"/>收藏这段声音 ↗</button>
    {saveOpen&&<SaveDialog close={()=>setSaveOpen(false)} render={render} scene={scene} setScene={setScene} version={version} project={project} source={source} diary={diary} sourceMemory={memory} onSaved={onSaved}/>}
  </section>;
}
function ClipDetails({tracks,engine,rate}){
  const [selected,setSelected]=useState('');const all=tracks.flatMap(t=>t.clips.map(c=>({t,c})));const item=all.find(x=>x.c.id===selected)||all[0];if(!item)return null;const {t,c}=item;rate=clipRate(c,rate);
  function edit(type,value){if(!engine||!Number.isFinite(value))return;if(type==='start')engine.moveClip(t.id,c.id,clipEditDelta(c,'start',value,rate));else if(type==='left')engine.trimClip(t.id,c.id,'left',clipEditDelta(c,'left',value,rate));else engine.trimClip(t.id,c.id,'right',clipEditDelta(c,'right',value,rate));}
  return <div className="clip-details"><label>片段<select value={item.c.id} onChange={e=>setSelected(e.target.value)}>{all.map(({t,c})=><option key={c.id} value={c.id}>{t.name} · {c.name}</option>)}</select></label>{[['start','出现位置',c.startSample],['left','原声起点',c.offsetSamples],['right','原声终点',c.offsetSamples+c.durationSamples]].map(([key,name,samples])=><label key={key}>{name}<span><input key={`${c.id}-${samples}`} type="number" min="0" step=".1" defaultValue={(samples/rate).toFixed(1)} onBlur={e=>edit(key,Number(e.target.value))} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();}}/> 秒</span></label>)}</div>;
}
