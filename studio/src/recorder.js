import {context, RATE} from './audio';
export async function startRecorder(onLevel, onEnded) {
  if(!navigator.mediaDevices?.getUserMedia) throw new Error('请在 localhost 或 HTTPS 页面中录音，也可以导入音频。');
  if(!window.AudioWorkletNode) throw new Error('当前浏览器不支持录音，请在 Chrome 或 Edge 中打开，或导入音频。');
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  try {
    const ctx=context(); await ctx.resume();
    await ctx.audioWorklet.addModule('/assets/studio-recorder.js');
    const source=ctx.createMediaStreamSource(stream), node=new AudioWorkletNode(ctx,'soundtrace-recorder'), silent=ctx.createGain();
    silent.gain.value=0; source.connect(node); node.connect(silent); silent.connect(ctx.destination);
    const chunks=[]; let samples=0, resolveStop, stopped=false;
    const cleanup=()=>{ stream.getTracks().forEach(t=>t.stop()); source.disconnect();node.disconnect();silent.disconnect(); };
    const end=()=>{ if(stopped) return; stopped=true; node.port.postMessage('stop'); };
    stream.getAudioTracks()[0].onended=()=>{end();onEnded?.();};
    node.port.onmessage=({data})=>{
      if(data.samples) { chunks.push(data.samples); samples+=data.samples.length; onLevel(Math.sqrt(data.samples.reduce((s,v)=>s+v*v,0)/data.samples.length),samples/ctx.sampleRate); }
      if(data.done) {
        cleanup(); const b=ctx.createBuffer(1,Math.max(1,samples),ctx.sampleRate); let at=0;
        for(const c of chunks) {b.copyToChannel(c,0,at);at+=c.length;} resolveStop?.(b);
      }
    };
    return {stop:()=>new Promise(resolve=>{resolveStop=resolve;end();}),dispose:()=>{node.port.onmessage=null;cleanup();}};
  } catch(e) {stream.getTracks().forEach(t=>t.stop());throw e;}
}

export async function recorderErrorMessage(error) {
  if(error.name==='NotAllowedError'||error.name==='SecurityError') {
    if(document.permissionsPolicy?.allowsFeature('microphone')===false||document.featurePolicy?.allowsFeature('microphone')===false)
      return '当前页面被浏览器策略禁止使用麦克风，请在独立浏览器打开本页。';
    const state=await navigator.permissions?.query({name:'microphone'}).then(p=>p.state).catch(()=>null);
    if(state==='denied') return '此浏览器已阻止麦克风。请在站点设置中允许本页使用麦克风，然后刷新；内置预览中可改用 Chrome 或 Edge 打开本页。';
    if(state==='granted') return '站点权限显示已允许，但浏览器未提供麦克风输入。请检查系统麦克风设置；若在内置预览中，请改用 Chrome 或 Edge 打开本页。';
    return '浏览器未能取得麦克风权限。请检查权限提示；若内置预览没有提示，请用 Chrome 或 Edge 打开本页并允许麦克风。';
  }
  if(error.name==='NotFoundError') return '没有找到可用的麦克风。请连接输入设备后重试。';
  if(error.name==='NotReadableError') return '麦克风当前无法读取。请关闭占用它的应用后重试。';
  return error.message||'录音无法启动，请重试。';
}
