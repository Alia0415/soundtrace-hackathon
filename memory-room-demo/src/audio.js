let context;
const openDB = () => new Promise((resolve,reject)=>{
  const r=indexedDB.open('soundtrace-memory-room',1);
  r.onupgradeneeded=()=>{r.result.createObjectStore('library',{keyPath:'id'});r.result.createObjectStore('records');};
  r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);
});
async function transaction(store,mode,action){const db=await openDB();try{return await new Promise((resolve,reject)=>{const tx=db.transaction(store,mode),req=action(tx.objectStore(store));tx.oncomplete=()=>resolve(req.result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}finally{db.close();}}
export const loadLibrary=()=>transaction('library','readonly',s=>s.getAll());
export const saveLibrary=item=>transaction('library','readwrite',s=>s.put(item));
export const saveRecord=({blob,title,names})=>transaction('records','readwrite',s=>s.put({blob,title,names},'latest'));
export const loadRecord=()=>transaction('records','readonly',s=>s.get('latest'));
export async function decodeAudio(blob){context??=new (window.AudioContext||window.webkitAudioContext)();return context.decodeAudioData(await blob.arrayBuffer());}
export function normalizationGain(channels){
  let energy=0,count=0;
  for(const channel of channels){for(const sample of channel)energy+=sample*sample;count+=channel.length;}
  const rms=count?Math.sqrt(energy/count):0;
  return rms>0.0001?Math.min(3,0.13/rms):0;
}
export function encodeWav(channels,sampleRate){
  const length=channels[0].length,count=channels.length,view=new DataView(new ArrayBuffer(44+length*count*2));
  const text=(offset,value)=>[...value].forEach((c,i)=>view.setUint8(offset+i,c.charCodeAt(0)));
  text(0,'RIFF');view.setUint32(4,36+length*count*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,count,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*count*2,true);view.setUint16(32,count*2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,length*count*2,true);
  for(let n=0,offset=44;n<length;n++)for(const channel of channels){const v=Math.max(-1,Math.min(1,channel[n]));view.setInt16(offset,Math.round(v*(v<0?32768:32767)),true);offset+=2;}
  return new Blob([view.buffer],{type:'audio/wav'});
}
export async function mixMemories(items){
  const buffers=await Promise.all(items.map(async item=>{const r=await fetch(item.url);if(!r.ok)throw new Error('素材读取失败');return decodeAudio(await r.blob());}));
  const sampleRate=24000,duration=24,offline=new (window.OfflineAudioContext||window.webkitOfflineAudioContext)(2,sampleRate*duration,sampleRate);
  buffers.forEach((buffer,index)=>{
    const source=offline.createBufferSource(),gain=offline.createGain(),pan=offline.createStereoPanner();source.buffer=buffer;source.loop=true;
    const channels=Array.from({length:buffer.numberOfChannels},(_,i)=>buffer.getChannelData(i));
    const level=normalizationGain(channels),start=index*1.4;
    gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(level,start+2);gain.gain.setValueAtTime(level,duration-3);gain.gain.linearRampToValueAtTime(0,duration);
    pan.pan.value=[-.35,.35,0][index]||0;source.connect(gain).connect(pan).connect(offline.destination);source.start(start);source.stop(duration);
  });
  const output=await offline.startRendering(),channels=[output.getChannelData(0),output.getChannelData(1)];let peak=0;
  channels.forEach(c=>{for(const x of c)peak=Math.max(peak,Math.abs(x));});if(peak>.95)channels.forEach(c=>{for(let i=0;i<c.length;i++)c[i]*=.95/peak;});
  return encodeWav(channels,sampleRate);
}
