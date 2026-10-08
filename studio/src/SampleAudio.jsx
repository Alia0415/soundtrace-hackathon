import React, {useEffect, useRef, useState} from 'react';
import {api} from './api';
import {clock, context, decode, encodeWav} from './audio';
import './sample-audio.css';

export default function SampleAudio({disabled, onUse, onPreview, setBusy, setError}) {
  const [sample, setSample] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const input = useRef(), player = useRef(), revision = useRef(0);

  async function refresh() {
    const version = ++revision.current;
    setLoading(true);
    try {
      await window.soundtraceAccountReady;
      const result = await api('/api/studio/sample');
      if (version === revision.current) {setSample(result.sample); setFailed(false);}
    } catch {
      if (version === revision.current) setFailed(true);
    } finally {
      if (version === revision.current) setLoading(false);
    }
  }
  useEffect(() => {
    refresh();
    window.addEventListener('soundtrace-login', refresh);
    return () => {revision.current++; window.removeEventListener('soundtrace-login', refresh);};
  }, []);
  useEffect(() => {if (disabled) player.current?.pause();}, [disabled]);

  async function upload(file) {
    if (!file) return;
    player.current?.pause();
    setError(''); setBusy('正在保存示例音频…');
    try {
      if (file.size > 50 * 1024 * 1024) throw new Error('请选择小于 50 MB 的音频。');
      await context().resume();
      let buffer;
      try {buffer = await decode(file);} catch {throw new Error('无法读取这个音频，请试试 WAV、MP3 或 M4A。');}
      if (buffer.duration < .25 || buffer.duration > 120) throw new Error('请选择 0.25 秒到 2 分钟的音频。');
      if (buffer.numberOfChannels > 2) throw new Error('请使用单声道或立体声音频。');
      const name = file.name.replace(/\.[^.]+$/, '').slice(0, 120) || '我的示例音频';
      const form = new FormData();
      form.append('name', name); form.append('audio', encodeWav(buffer), 'sample.wav');
      const result = await api('/api/studio/sample', {method: 'PUT', body: form});
      revision.current++; setLoading(false); setFailed(false); setSample(result.sample);
      await onUse(buffer, name);
    } catch (error) {setError(error.message);} finally {setBusy('');}
  }
  async function reuse() {
    player.current?.pause();
    setError(''); setBusy('正在打开示例音频…');
    try {
      await context().resume();
      const response = await fetch('/' + sample.audio);
      if (!response.ok) throw new Error('示例音频暂时无法读取，请重试或替换音频。');
      await onUse(await decode(await response.blob()), sample.name);
    } catch (error) {setError(error.message);} finally {setBusy('');}
  }
  async function remove() {
    player.current?.pause();
    setError(''); setBusy('正在删除示例音频…');
    try {
      await api('/api/studio/sample', {method: 'DELETE'});
      revision.current++; setSample(null);
    } catch (error) {setError(error.message);} finally {setBusy('');}
  }
  return <section className="sample-audio" aria-labelledby="sampleTitle" aria-busy={loading}>
    <div className="sample-description"><h2 id="sampleTitle">我的示例音频</h2>
      <p>{loading ? '正在读取…' : failed ? '暂时无法读取已保存的音频' : sample ? `${sample.name} · ${clock(sample.duration)} · 已保存到账号` : '上传一次，下次直接用。仅自己可见。'}</p>
    </div>
    {sample && <audio key={sample.id} ref={player} controls preload="metadata" src={'/' + sample.audio} aria-label="试听我的示例音频" onPlay={() => {if (disabled) player.current?.pause(); else onPreview?.();}} onError={() => setError('音频暂时无法播放，请重试。')}/>}
    <div className="sample-actions">
      {failed && <button className="quiet" disabled={disabled || loading} onClick={refresh}>重试</button>}
      {sample && <button className="outline" disabled={disabled || loading} onClick={reuse}>使用此音频</button>}
      <button className={sample ? 'quiet' : 'outline'} disabled={disabled || loading} onClick={() => input.current.click()}>{sample ? '替换' : '上传示例音频'}</button>
      {sample && <button className="quiet" disabled={disabled || loading} onClick={remove}>删除</button>}
    </div>
    <input ref={input} type="file" hidden accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac" aria-label="选择示例音频" onChange={event => {const file = event.target.files[0]; event.target.value = ''; upload(file);}}/>
  </section>;
}
