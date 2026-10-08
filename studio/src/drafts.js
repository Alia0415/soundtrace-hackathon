import {encodeWav, decode} from './audio';
async function db() {
  await window.soundtraceAccountReady;
  const databaseName = window.soundtraceAccountReady ? 'soundtrace-studio-' + (window.soundtraceUser?.id || 'guest') : 'soundtrace-studio';
  return new Promise((resolve,reject)=>{ const r=indexedDB.open(databaseName,1); r.onupgradeneeded=()=>r.result.createObjectStore('drafts');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error); });
}
async function transaction(mode, action) {
  const d=await db();
  return new Promise((resolve,reject)=>{const tx=d.transaction('drafts',mode),r=action(tx.objectStore('drafts'));tx.oncomplete=()=>{resolve(r.result);d.close();};tx.onerror=()=>{reject(tx.error);d.close();};});
}
const bufferCache=new WeakMap();
export async function saveDraft(tracks, info) {
  const packed=tracks.map(t=>({...t,effects:undefined,clips:t.clips.map(c=>{
    let wav=bufferCache.get(c.audioBuffer); if(!wav){wav=encodeWav(c.audioBuffer);bufferCache.set(c.audioBuffer,wav);}
    return {...c,audioBuffer:undefined,waveformData:undefined,wav};
  })}));
  await transaction('readwrite',s=>s.put({tracks:packed,info,updated:Date.now()},'current'));
}
export const readDraft=()=>transaction('readonly',s=>s.get('current'));
export const clearDraft=()=>transaction('readwrite',s=>s.delete('current'));
export async function unpackDraft(draft) {
  const tracks=await Promise.all(draft.tracks.map(async t=>({...t,clips:await Promise.all(t.clips.map(async c=>{
    const audioBuffer=await decode(c.wav);bufferCache.set(audioBuffer,c.wav);return {...c,wav:undefined,audioBuffer};
  }))})));
  return {tracks,info:draft.info};
}
