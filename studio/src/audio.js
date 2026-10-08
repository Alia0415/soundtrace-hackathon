export const RATE = 44100;
export function encodeWav(buffer) {
  const channels = buffer.numberOfChannels, n = buffer.length;
  const bytes = new ArrayBuffer(44 + n * channels * 2), v = new DataView(bytes);
  const text = (p, s) => [...s].forEach((c, i) => v.setUint8(p + i, c.charCodeAt(0)));
  text(0, 'RIFF'); v.setUint32(4, bytes.byteLength - 8, true); text(8, 'WAVE'); text(12, 'fmt ');
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, channels, true);
  v.setUint32(24, buffer.sampleRate, true); v.setUint32(28, buffer.sampleRate * channels * 2, true);
  v.setUint16(32, channels * 2, true); v.setUint16(34, 16, true); text(36, 'data'); v.setUint32(40, n * channels * 2, true);
  const data = Array.from({length: channels}, (_, c) => buffer.getChannelData(c));
  for (let i = 0, p = 44; i < n; i++) for (let c = 0; c < channels; c++, p += 2) {
    const x = Math.max(-1, Math.min(1, data[c][i])); v.setInt16(p, Math.round(x * (x < 0 ? 32768 : 32767)), true);
  }
  return new Blob([bytes], {type: 'audio/wav'});
}
let decodeContext;
export function context() { return decodeContext ||= new AudioContext({sampleRate: RATE}); }
export async function decode(blob) { return context().decodeAudioData(await blob.arrayBuffer()); }
export function download(blob, name) {
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
}
export function musicBed(style, duration, diary = {}) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./bed-worker.js', import.meta.url), {type: 'module'});
    worker.onerror = e => { worker.terminate(); reject(new Error(e.message || '配乐合成失败')); };
    worker.onmessage = ({data}) => {
      const b = context().createBuffer(2, data[0].length, RATE);
      data.forEach((channel, i) => b.copyToChannel(channel, i)); worker.terminate(); resolve(b);
    };
    worker.postMessage({style, duration, diary, sampleRate: RATE});
  });
}
export const clock = seconds => { const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0; return `${Math.floor(safe / 60)}:${String(Math.floor(safe % 60)).padStart(2, '0')}`; };
