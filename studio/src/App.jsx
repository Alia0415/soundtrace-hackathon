import RasterArt from './RasterArt';
import React,{useCallback,useEffect,useRef,useState} from 'react';
import {WaveformPlaylistProvider} from '@waveform-playlist/browser';
import {createClipFromSeconds,createTrack} from '@waveform-playlist/core';
import {Limiter} from 'tone';
import {context,decode,encodeWav,clock} from './audio';
import {startRecorder,recorderErrorMessage} from './recorder';
import {readDraft,unpackDraft,clearDraft} from './drafts';
import {api,route,runMusicJob} from './api';
import {theme} from './theme';
import Editor from './Editor';
import SoundLibrary from './SoundLibrary';
import DiarySetup from './DiarySetup';
import {blankDiary,diaryFromMemory,diaryValue} from './diary-options';

export const masterEffects=(input,output)=>{const limiter=new Limiter(-1);input.connect(limiter);limiter.connect(output);return ()=>limiter.dispose();};
// Keep engine configuration stable when retrying adds a music track. Changing
// the zoom-level list during an incremental add disposes the loaded playout.
const zoomLevels=[256,512,1024,2048,4096,8192,16384,32768,65536];
function makeTrack(buffer,name,id,color,volume=1){return {...createTrack({name,color,volume,clips:[createClipFromSeconds({audioBuffer:buffer,startTime:0,name,fadeIn:{duration:.15},fadeOut:{duration:.35}})]}),id};}
export default function App(){
  const recordingEntry=location.pathname.replace(/^\/demo(?=\/|$)/,'')==='/capture';
  const [tracks,setTracks]=useState([]),[style,setStyle]=useState('ambient'),[scene,setScene]=useState('sea-window');
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[recording,setRecording]=useState(false),[level,setLevel]=useState(0),[seconds,setSeconds]=useState(0);
  const [draft,setDraft]=useState(null),[ai,setAi]=useState(false),[soundProcessing,setSoundProcessing]=useState(false),[source,setSource]=useState(null),[draftInfo,setDraftInfo]=useState(null),[epoch,setEpoch]=useState(0);
  const [promptSave,setPromptSave]=useState(false),[micError,setMicError]=useState(false),[musicFailed,setMusicFailed]=useState(false);
  const [phase,setPhase]=useState('library'),[sourceName,setSourceName]=useState('此刻的声音'),[memory,setMemory]=useState(null),[diary,setDiary]=useState({...blankDiary}),[libraryRevision,setLibraryRevision]=useState(0);
  const projectSeconds=Math.max(source?.duration||15,...tracks.flatMap(t=>t.clips.map(c=>(c.startSample+c.durationSamples)/(c.sampleRate||44100))));
  const timelineWidth=window.innerWidth>760?Math.min(window.innerWidth,1505)-window.innerWidth*.08-88:window.innerWidth-145;
  const requestedZoom=Math.max(256,Math.ceil(projectSeconds*44100/Math.max(140,timelineWidth)));
  const initialZoom=zoomLevels.find(value=>value>=requestedZoom)||zoomLevels.at(-1);
  const pick=useRef(),rec=useRef(),editor=useRef(),musicToken=useRef(0),abortJob=useRef();
  const onPlaybackError=useCallback(()=>setError('播放引擎暂时无法启动，请刷新恢复草稿。'),[]);
  const onEngineReady=useCallback(()=>editor.current?.onReady?.(),[]);
  useEffect(()=>{window.scrollTo({top:0,behavior:'instant'});},[phase]);
  useEffect(()=>{readDraft().then(setDraft).catch(()=>{});api('/api/studio/health').then(x=>{setAi(!!x.ai);setSoundProcessing(!!x.sound_analysis);}).catch(()=>setAi(false));return ()=>{rec.current?.dispose();abortJob.current?.abort();};},[]);
  useEffect(()=>{const id=new URLSearchParams(location.search).get('memory');if(!id)return;
    (async()=>{await window.soundtraceAccountReady;const saved=await api('/api/memories/'+encodeURIComponent(id));await selectMemory(saved,true);})().catch(e=>setError(e.message));
  },[]);
  useEffect(()=>{if(recording&&seconds>=120) stopRecording();},[seconds,recording]);
  async function useBuffer(buffer,name){
    if(buffer.duration<.25) throw new Error('声音太短，请至少录下半秒。');
    if(buffer.duration>300) throw new Error('每次可导入最多 5 分钟的声音，请先截取想留下的部分。');
    editor.current?.pause();abortJob.current?.abort();setDraftInfo(null);setEpoch(x=>x+1);
    musicToken.current++;setSource(buffer);setSourceName(name);setMemory(null);setTracks([]);setPhase('library');setDiary({...blankDiary});setDraft(null);setPromptSave(false);setMicError(false);setMusicFailed(false);
  }
  async function changeBed(next,duration,initial){
    const token=++musicToken.current;setStyle(next);setError('');setMusicFailed(false);
    if(!window.SoundTraceDemo&&!ai){setError('音乐服务尚未配置，当前可微调原声；配置完成后可生成专属旋律。');return;}
    setBusy(window.SoundTraceDemo?'正在打开演示音乐…':'正在制作专属旋律…');
    const controller=new AbortController();abortJob.current=controller;
    try {let path=window.SoundTraceDemo?.bed(next)||'outputs/seeds/seed_vinyl.wav';
      if(!window.SoundTraceDemo){const result=await runMusicJob({memory_id:memory?.id,source_ref:memory?.audio,style:next,duration,title:diary.title||sourceName,notes:diary.notes,prompt:diary.prompt,mood:diaryValue(diary,'mood'),weather:diaryValue(diary,'weather'),activity:diaryValue(diary,'activity')},controller.signal,setBusy);path=result.generated;}
      const response=await fetch('/'+path,{signal:controller.signal});if(!response.ok)throw new Error('无法读取生成音乐');const bed=await decode(await response.blob());if(token!==musicToken.current)return;
      const track=makeTrack(bed,window.SoundTraceDemo?(window.SoundTraceDemo.styles.find(x=>x[0]===next)?.[1]||'钢琴')+' · 演示编曲':'专属旋律','music','#91b9ca',.4);
      if(initial){setTracks([...initial,track]);setDraftInfo({version:window.SoundTraceDemo?'demo':'ai'});}else editor.current?.replaceMusic(track,window.SoundTraceDemo?'demo':'ai');
      return true;
    }catch(e){if(token===musicToken.current&&e.name!=='AbortError'){setMusicFailed(true);setError(e.message);}}finally{if(token===musicToken.current)setBusy('');}
  }
  async function selectMemory(saved,setup=false){setBusy('正在打开声音素材…');setError('');
    if(setup&&saved.music_source_ref)saved={...saved,audio:saved.music_source_ref};
    try{const response=await fetch('/'+saved.audio);if(!response.ok)throw new Error('声音素材暂时无法读取，请重试。');
      await useBuffer(await decode(await response.blob()),saved.title);setMemory(saved);setScene(saved.scene||'sea-window');setDiary(diaryFromMemory(saved));setStyle(saved.music_style||'ambient');if(setup)setPhase('setup');
    }catch(e){setError(e.message);}finally{setBusy('');}
  }
  function savedRaw(saved){setMemory(previous=>previous?.id===saved.id?{...saved,audio:previous.audio,duration:previous.duration,material_id:previous.material_id,material_kind:previous.material_kind}:saved);setSourceName(saved.title);setDiary(diaryFromMemory(saved));setLibraryRevision(x=>x+1);}
  async function saveRaw(buffer=source,name=sourceName){const form=new FormData();form.append('audio',encodeWav(buffer),'original.wav');form.append('title',name);form.append('duration',String(buffer.duration));form.append('scene',scene);form.append('captured_at',String(Date.now()/1000));const saved=await api('/api/memories',{method:'POST',body:form});savedRaw(saved);return saved;}
  async function saveMaterial(){setBusy('正在保存原声…');setError('');try{await saveRaw();setPromptSave(true);}catch(e){setError(e.message);}finally{setBusy('');}}
  async function beginDiary(){setError('');setBusy('正在准备音乐日记…');
    try{if(!memory)await saveRaw();
      setPromptSave(false);setPhase('setup');
    }catch(e){setError(e.message);}finally{setBusy('');}
  }
  async function createDiary(nextStyle=style){const base=tracks.length?tracks.filter(track=>track.id!=='music'):[makeTrack(source,sourceName,'field','#3a9bc4',.57)];setEpoch(x=>x+1);setDraftInfo(null);setTracks(base);if(await changeBed(nextStyle,source.duration,base))setPhase('editor');}
  async function importFile(file){if(!file)return;setError('');setBusy('正在打开声音…');
    try{await context().resume();if(file.size>60_000_000)throw new Error('请选择不超过 60 MB 的音频或视频。');
      if(window.SoundTraceDemo){await useBuffer(await decode(file),file.name.replace(/\.[^.]+$/,''));}
      else{await window.soundtraceAccountReady;const form=new FormData();form.append('file',file,file.name);form.append('filename',file.name);form.append('title',file.name.replace(/\.[^.]+$/,''));setBusy('正在上传素材并提取音轨…');const saved=await api('/api/material-import',{method:'POST',body:form});await selectMemory(saved);setLibraryRevision(x=>x+1);}
    }
    catch(e){setError(e.message||'这个音频无法打开，请试试 WAV、MP3 或 M4A。');}finally{setBusy('');}
  }
  async function record(){setMicError(false);setError('');setBusy('请允许使用麦克风');editor.current?.pause();
    try{rec.current=await startRecorder((l,t)=>{setLevel(l);setSeconds(t);},()=>stopRecording());setSeconds(0);setRecording(true);}
    catch(e){setMicError(true);setError(await recorderErrorMessage(e));}finally{setBusy('');}
  }
  async function stopRecording(){if(!rec.current)return;const active=rec.current;rec.current=null;setRecording(false);setBusy('正在留下声音…');
    try{const buffer=await active.stop();await useBuffer(buffer,'此刻的声音');await saveRaw(buffer,'此刻的声音');setPromptSave(true);}catch(e){setError(e.message+'；声音仍在当前素材栏，可以重试保存。');}finally{setBusy('');}}
  async function example(sample=window.SoundTraceDemo?.samples[0]){if(!sample)return;setBusy('正在打开演示原声…');setError('');try{await context().resume();const r=await fetch('/'+sample.audio);if(!r.ok)throw new Error('演示原声暂时不可用，请重试。');await useBuffer(await decode(await r.blob()),sample.title);setStyle(sample.style);setScene(sample.key==='rain'?'rainy-city':sample.key==='birds'?'spring-meadow':'autumn-lake');setDiary(prev=>({...prev,title:sample.title,notes:sample.hint}));}catch(e){setError(e.message);}finally{setBusy('');}}
  async function restore(){setBusy('正在恢复草稿…');try{const saved=await unpackDraft(draft);setTracks(saved.tracks.filter(t=>!t.id.startsWith('variant-')));setSource(saved.tracks.find(t=>t.id==='field')?.clips[0]?.audioBuffer);setSourceName(saved.tracks.find(t=>t.id==='field')?.name||'此刻的声音');setStyle(saved.info.style||'ambient');setScene(saved.info.scene||'sea-window');setDiary(saved.info.diary||{...blankDiary});if(saved.info.memoryId){const entry=await api('/api/memories/'+encodeURIComponent(saved.info.memoryId)).catch(()=>null);setMemory(entry&&saved.info.sourceRef?{...entry,audio:saved.info.sourceRef}:entry);}setDraftInfo({...saved.info,draftMusic:saved.tracks.find(t=>t.id==='variant-draft'),aiMusic:saved.tracks.find(t=>t.id==='variant-ai')});setDraft(null);setPhase('editor');}catch{setError('草稿暂时无法恢复，请重试。');}finally{setBusy('');}}
  async function newProject(){editor.current?.pause();abortJob.current?.abort();musicToken.current++;setPromptSave(false);setTracks([]);setSource(null);setMemory(null);setDiary({...blankDiary});setPhase('library');setDraftInfo(null);setEpoch(x=>x+1);setError('');history.replaceState(null,'',route(recordingEntry?'/capture':'/studio#rec'));await clearDraft().catch(()=>{});}
  return <>
    <header className="studio-header"><a className="brand" href={route('/')} aria-label="声迹首页"><span className="brand-mark">◉</span> 声迹 <small>SOUNDTRACE</small></a><a className="collection-link" href={route('/library')}>素材库 <span aria-hidden="true">↗</span></a><a className="collection-link" href={route('/album')}>我的音乐 <span aria-hidden="true">↗</span></a></header>
    <main id="rec" className={`studio-main ${tracks.length?'has-audio':''} phase-${phase} ${recordingEntry&&!source?'capture-entry':''} ${recording?'is-recording':''} ${micError?'mic-error':''}`}>
      <nav className="creation-steps" aria-label="音乐创作进度"><ol>{['上传素材','生成音乐','试听与保存'].map((label,index)=><li key={label} aria-current={index===({library:0,setup:1,editor:2}[phase])?'step':undefined}><span>{index+1}</span>{label}</li>)}</ol><p>{phase==='library'?'上传音频或视频，也可以录音。选好一段素材后，继续生成音乐。':phase==='setup'?'选一种风格并点击生成；天气、心情和故事都可以选填。':'先试听，再点击“保存音乐”。保存后可在“我的音乐”中找到作品。'}</p></nav><div className="studio-heading"><div><h1>{phase==='library'?!recordingEntry&&!source?(window.SoundTraceDemo?'把声音做成日记':'导入音频或视频'):'声音手记':phase==='setup'?'选择风格，生成音乐':'试听并保存音乐'}</h1></div>{phase==='library'&&!recordingEntry&&<RasterArt id="library" className="library-header-art"/>}{phase==='editor'&&<button className="quiet editor-back" onClick={()=>{editor.current?.pause();setPhase('library');}} disabled={recording||!!busy}>‹ 声音库</button>}{source&&phase!=='library'&&<button className="quiet" onClick={newProject} disabled={recording||!!busy}>重新创作</button>}</div>
      {phase==='library'&&!source&&!recordingEntry&&window.SoundTraceDemo&&<section className="audio-import-scene" aria-label="导入音频或视频"><RasterArt id={error?'import-error':'import-empty'} className="audio-import-art"/><div className="audio-import-actions"><button className="primary" type="button" onClick={()=>pick.current.click()} disabled={!!busy}>上传音频或视频</button>{draft&&<button className="restore" onClick={restore} disabled={!!busy}>继续上次的手记 ↗</button>}{window.SoundTraceDemo&&<button className="quiet" type="button" onClick={()=>example()} disabled={!!busy}>使用湖畔风声与鸟鸣</button>}</div></section>}
      {phase==='library'&&!source&&window.SoundTraceDemo&&<section className="demo-samples" aria-label="演示原声"><p className="demo-flow-note">01 选择素材 → 02 选择编曲 → 03 试听与保存</p><h2>先选一个声音，再听见它的另一种模样。</h2><div className="demo-sample-grid">{window.SoundTraceDemo.samples.map(sample=><button type="button" key={sample.key} disabled={!!busy} onClick={()=>example(sample)}><span className="demo-sample-icon" aria-hidden="true">{sample.key==='lakeside'?'≈':sample.key==='rain'?'☂':'♬'}</span><strong>{sample.title}</strong><small>{sample.hint}</small><span>使用这段原声 ↗</span></button>)}</div><p>预制演示素材 · 无需麦克风或等待生成 · 作品仅保存在此浏览器</p></section>}
      {phase==='library'&&!source&&recordingEntry&&<section className="capture-scene" aria-label="录制声音">
        <div className="capture-status"><h2>{micError?<>记录，<br/>你的声音。</>:recording?'正在录音':'留下一段声音'}</h2>{!micError&&<time className="capture-clock">{clock(seconds)}</time>}</div>
        <div className="capture-photo"><RasterArt id={micError?'capture-permission':recording?'capture-recording':'capture-idle-art'}/>{recording&&<div className="live-level" style={{'--level':Math.min(1,level*5+.01)}} aria-label="实时录音音量"><i/><i/><i/><i/><i/></div>}</div>
        <div className="capture-actions">{micError?<><h3>未获得麦克风输入</h3><p>可以检查权限，或导入已有声音。</p>{error&&<p className="capture-error-detail" role="alert">{error}</p>}<a className="primary original-art-button permission-import" href={route('/studio#rec')}><RasterArt id="permission-import-button"/><span className="sr-only">导入音频或视频</span></a><button className="outline" onClick={record} disabled={!!busy}>重试录音</button></>:<><button className={`record-orb ${recording?'recording':''}`} aria-label={recording?'结束录音':'开始录音'} onClick={recording?stopRecording:record} disabled={!!busy}>{recording?<span aria-hidden="true">■</span>:<RasterArt id="capture-idle-button"/>}</button><span className={`record-label ${recording?"":"sr-only"}`}>{recording?'结束并保存':'点击录音'}</span>{!recording&&<div className="capture-links"><a className="outline original-art-button capture-import" href={route('/studio#rec')}><RasterArt id="capture-import-button"/><span className="sr-only">导入音频或视频 ↗</span></a><span className="capture-ready"><RasterArt id="capture-ready"/><span className="sr-only">准备好了</span></span></div>}</>}{draft&&<button className="restore" onClick={restore} disabled={!!busy||recording}>继续上次的手记 ↗</button>}</div>
      </section>}
      {phase==='library'&&(source||(!recordingEntry&&!window.SoundTraceDemo))&&<SoundLibrary source={source} name={sourceName} memory={memory} onSave={saveMaterial} onGenerate={beginDiary} onSelect={selectMemory} busy={recording||!!busy} refreshKey={libraryRevision} onImport={()=>pick.current.click()} onNew={newProject} onRestore={draft?restore:undefined} rawSuccess={promptSave} onDismissSuccess={()=>setPromptSave(false)}/>}
      {phase==='setup'&&<><DiarySetup diary={diary} setDiary={setDiary} style={style} setStyle={setStyle} onContinue={createDiary} onBack={()=>setPhase('library')} busy={!!busy}/>{!ai&&!window.SoundTraceDemo&&<div className="availability"><p>音乐生成服务暂不可用，你仍可编辑并保存原声。</p><button className="outline" disabled={!!busy} onClick={()=>{setTracks([makeTrack(source,sourceName,'field','#3a9bc4',.57)]);setDraftInfo(null);setEpoch(x=>x+1);setError('');setPhase('editor');}}>仅编辑原声</button></div>}</>}
      {phase==='editor'&&<WaveformPlaylistProvider tracks={tracks} onTracksChange={setTracks} theme={theme} effects={masterEffects} waveHeight={76} mono controls={{show:true,width:88}} samplesPerPixel={initialZoom} zoomLevels={zoomLevels} sampleRate={44100} barWidth={2} barGap={2} roundedBars onReady={onEngineReady} onError={onPlaybackError}>
        <Editor key={epoch} tracks={tracks} setTracks={setTracks} style={style} scene={scene} setScene={setScene} ai={ai} soundProcessing={soundProcessing} source={source} busy={busy} setBusy={setBusy} setError={setError} musicFailed={musicFailed} recording={recording} seconds={seconds} record={record} stopRecording={stopRecording} pick={()=>pick.current.click()} changeStyle={changeBed} handle={editor} initial={draftInfo} abortJob={abortJob} diary={diary} memory={memory} onSaved={savedRaw} onEditDiary={()=>{editor.current?.pause();setPhase('setup');}}/>
      </WaveformPlaylistProvider>}
      {!!busy&&phase==='setup'&&ai&&<button className="quiet" onClick={()=>abortJob.current?.abort()}>停止等待</button>}
      {recording&&<div className="record-meter" aria-label="录音音量"><div style={{transform:`scaleX(${Math.min(1,level*5+.01)})`}}/></div>}
      <div className="notice" role="status" aria-live="polite">{busy}</div>{error&&!(micError&&recordingEntry&&!source)&&<div className="error" role="alert">{error}{!recordingEntry&&!source&&<button className="upload-retry" onClick={()=>pick.current.click()} disabled={!!busy}>重新上传</button>}<button aria-label="关闭提示" onClick={()=>setError('')}>×</button></div>}
      <input ref={pick} hidden type="file" accept="audio/*,video/*,.wav,.mp3,.m4a,.ogg,.flac,.mp4,.mov,.webm,.mkv" aria-label="选择音频或视频素材" onChange={e=>{importFile(e.target.files[0]);e.target.value='';}}/>
    </main>
    <footer className="studio-footer"><span>此刻的声音，值得被记住。</span><a href="/map">声音地图 ↗</a></footer>
  </>;
}
