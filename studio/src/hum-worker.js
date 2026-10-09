import {BasicPitch, noteFramesToTime, outputToNotesPoly} from '@spotify/basic-pitch';
import * as tf from '@tensorflow/tfjs';

self.onmessage = async ({data: {samples, modelUrl}}) => {
  try {
    await tf.setBackend('cpu');
    await tf.ready();
    const frames = [], onsets = [];
    const model = new BasicPitch(modelUrl);
    await model.evaluateModel(samples, (f, o) => {
      frames.push(...f); onsets.push(...o);
    }, progress => self.postMessage({progress}));
    const notes = noteFramesToTime(outputToNotesPoly(frames, onsets, .3, .3, 5));
    self.postMessage({notes});
  } catch {
    self.postMessage({error: '哼唱识别失败，请检查网络后重试，或换一段清晰的单人哼唱。'});
  }
};
