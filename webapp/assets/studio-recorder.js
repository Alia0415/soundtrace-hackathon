class SoundtraceRecorder extends AudioWorkletProcessor {
  constructor() {
    super(); this.chunk = new Float32Array(4096); this.used = 0; this.active = true;
    this.port.onmessage = e => { if(e.data === 'stop') { this.flush(); this.active=false; this.port.postMessage({done:true}); } };
  }
  flush() { if(this.used) this.port.postMessage({samples:this.chunk.slice(0,this.used)}); this.used=0; }
  process(inputs) {
    const channels=inputs[0];
    if(!this.active || !channels?.length) return true;
    for(let i=0;i<channels[0].length;i++) {
      let sample=0; for(const c of channels) sample+=c[i]/channels.length;
      this.chunk[this.used++]=sample; if(this.used===4096) this.flush();
    }
    return true;
  }
}
registerProcessor('soundtrace-recorder',SoundtraceRecorder);
