export async function api(path, options={}) {
  // Keep each audio request below cloud gateway limits, without changing the WAV.
  if(path.startsWith('/api/memories') && options.body instanceof FormData && !window.SoundTraceDemo) {
    const form=options.body;
    for(const key of ['audio','music_audio']) {
      const file=form.get(key);
      if(!(file instanceof Blob) || file.size<=4_000_000)continue;
      const task=await api('/api/audio-uploads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({size:file.size}),signal:options.signal});
      for(let offset=0,index=0;offset<file.size;offset+=task.chunk_size,index++) {
        await api(`/api/audio-uploads/${task.upload_id}/${index}`,{method:'PUT',headers:{'Content-Type':'application/octet-stream'},body:file.slice(offset,offset+task.chunk_size),signal:options.signal});
      }
      form.delete(key);form.set(key+'_upload_id',task.upload_id);
    }
  }
  const r=await fetch(path,options); let data; try {data=await r.json();} catch {throw new Error('服务暂时未响应，请稍后重试。');}
  if(!r.ok) throw new Error(typeof data.detail==='string'?data.detail:'请求未完成，请重试。'); return data;
}
export async function upload(blob) {const form=new FormData();form.append('file',blob,'recording.wav');return api('/api/upload',{method:'POST',body:form});}
export async function runJob(body, signal, onStatus) {
  const {job_id}=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,auto_register:false}),signal});
  while(true) {
    if(signal.aborted) throw new DOMException('Aborted','AbortError');
    const job=await api(`/api/jobs/${job_id}`,{signal});
    if(job.status==='done') return job.results;
    if(job.status==='failed') throw new Error('这次处理没有完成，原来的声音已保留，可以重试。');
    onStatus?.(job.stage||'正在制作中，仍可继续编辑');
    await new Promise((resolve,reject)=>{const done=()=>{signal.removeEventListener('abort',cancel);resolve();};const timer=setTimeout(done,1500);const cancel=()=>{clearTimeout(timer);reject(new DOMException('Aborted','AbortError'));};signal.addEventListener('abort',cancel,{once:true});});
  }
}
export function commit(blob, metadata) { return api('/api/studio/works',{method:'POST',headers:{'Content-Type':'audio/wav','X-Soundtrace-Metadata':encodeURIComponent(JSON.stringify(metadata))},body:blob}); }
export const route = path => window.SoundTraceRoute?.(path) || path;
export const runMusicJob = (body, signal, onStatus) => runTask('/api/music/jobs', body, signal, onStatus);
export const runSoundJob = (body, signal, onStatus) => runTask('/api/sound/jobs', body, signal, onStatus);
async function runTask(endpoint, body, signal, onStatus) {
  let id;
  try {
    const task=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});id=task.job_id;
    while(true){
      const job=await api(endpoint+'/'+id,{signal});
      if(job.status==='done')return job.results;
      if(job.status==='failed'||job.status==='cancelled')throw new Error(job.stage);
      onStatus?.(job.stage);
      await new Promise((resolve,reject)=>{const done=()=>{signal.removeEventListener('abort',cancel);resolve();};const timer=setTimeout(done,2500);const cancel=()=>{clearTimeout(timer);signal.removeEventListener('abort',cancel);reject(new DOMException('Aborted','AbortError'));};signal.addEventListener('abort',cancel,{once:true});if(signal.aborted)cancel();});
    }
  }catch(error){if(error.name==='AbortError'&&id)await api(endpoint+'/'+id+'/cancel',{method:'POST'}).catch(()=>{});throw error;}
}
