export function clipRate(clip, fallback = 44100) {
  return clip.sampleRate || clip.audioBuffer?.sampleRate || fallback;
}

export function clipEditDelta(clip, type, seconds, fallback) {
  const target = Math.round(seconds * clipRate(clip, fallback));
  return target - (type === 'start' ? clip.startSample :
    type === 'left' ? clip.offsetSamples : clip.offsetSamples + clip.durationSamples);
}
