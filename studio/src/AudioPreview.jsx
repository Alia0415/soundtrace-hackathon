import React,{useEffect,useRef,useState} from 'react';
import {clock} from './audio';

/** Playback, progress and volume come from the real audio element. */
export default function AudioPreview({src,label,busy=false,duration=0}){
  const audio=useRef();
  const [playing,setPlaying]=useState(false),[time,setTime]=useState(0),[length,setLength]=useState(duration),[volume,setVolume]=useState(1),[error,setError]=useState('');
  useEffect(()=>{setTime(0);setPlaying(false);setError('');setLength(duration);},[src,duration]);
  useEffect(()=>{if(busy)audio.current?.pause();},[busy]);
  async function toggle(){try{setError('');if(audio.current.paused)await audio.current.play();else audio.current.pause();}catch{setError('音频暂时无法播放，请重新选择素材。');}}
  return <div className="audio-preview" aria-label={label}>
    <audio ref={audio} src={src} preload="metadata" onLoadedMetadata={()=>setLength(audio.current.duration||duration)} onTimeUpdate={()=>setTime(audio.current.currentTime)} onPlay={()=>setPlaying(true)} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)} onError={()=>setError('音频暂时无法读取，请重新选择素材。')}/>
    <button className="preview-play" type="button" aria-label={playing?'暂停原声':'播放原声'} disabled={busy||!src} onClick={toggle}>{playing?'Ⅱ':'▶'}</button>
    <div className="preview-progress"><input type="range" aria-label="原声播放进度" min="0" max={length||1} step=".05" value={Math.min(time,length||1)} onChange={e=>{audio.current.currentTime=Number(e.target.value);setTime(Number(e.target.value));}}/><span><time>{clock(time)}</time><time>{clock(length)}</time></span></div>
    <label className="preview-volume"><span aria-hidden="true">◖))</span><input type="range" aria-label="原声音量" min="0" max="1" step=".01" value={volume} onChange={e=>{const value=Number(e.target.value);audio.current.volume=value;setVolume(value);}}/></label>
    {error&&<p className="preview-error" role="alert">{error}</p>}
  </div>;
}
