// Spotify Basic Pitch runs on this device; recorded audio is never sent to a model API.
export async function transcribeHum(source, signal, onStatus) {
  signal.throwIfAborted();
  const mono = new OfflineAudioContext(1, Math.ceil(source.duration * 22050), 22050);
  const input = mono.createBufferSource(); input.buffer = source; input.connect(mono.destination); input.start();
  const samples = (await mono.startRendering()).getChannelData(0);
  signal.throwIfAborted();
  const notes = await new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./hum-worker.js', import.meta.url), {type: 'module'});
    const finish = (error, result) => {
      clearTimeout(timer); signal.removeEventListener('abort', cancel); worker.terminate();
      error ? reject(error) : resolve(result);
    };
    const cancel = () => finish(new DOMException('Aborted', 'AbortError'));
    const timer = setTimeout(() => finish(new Error('本机识别超时，请使用更短的哼唱重试。')), 300000);
    signal.addEventListener('abort', cancel, {once: true});
    worker.onerror = () => finish(new Error('无法加载哼唱模型，请刷新后重试。'));
    worker.onmessage = ({data}) => {
      if (data.error) finish(new Error(data.error));
      else if (data.notes) finish(null, data.notes);
      else onStatus?.(`正在本机识别哼唱 ${Math.round(data.progress * 100)}%`);
    };
    worker.postMessage({samples, modelUrl: new URL('/assets/studio/models/basic-pitch/model.json', location.origin).href}, [samples.buffer]);
  });
  signal.throwIfAborted();
  const usable = notes.filter(n => Number.isFinite(n.pitchMidi) && n.durationSeconds > 0 && n.startTimeSeconds < source.duration);
  if (!usable.length) throw new Error('没有识别出清晰旋律，请录制单人哼唱后重试。');
  const output = new OfflineAudioContext(1, Math.ceil((source.duration + .1) * 44100), 44100);
  for (const note of usable) {
    const start = Math.max(0, note.startTimeSeconds), end = Math.min(source.duration, start + note.durationSeconds);
    if (end <= start) continue;
    const oscillator = output.createOscillator(), gain = output.createGain();
    oscillator.type = 'triangle'; oscillator.frequency.value = 440 * 2 ** ((note.pitchMidi - 69) / 12);
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(Math.min(.25, Math.max(.04, note.amplitude * .25)), start + Math.min(.02, (end - start) / 3));
    gain.gain.setValueAtTime(Math.min(.25, Math.max(.04, note.amplitude * .25)), Math.max(start + (end - start) / 3, end - .04));
    gain.gain.linearRampToValueAtTime(0, end);
    oscillator.connect(gain); gain.connect(output.destination); oscillator.start(start); oscillator.stop(end);
  }
  const buffer = await output.startRendering();
  signal.throwIfAborted();
  return {buffer, notes: usable};
}
