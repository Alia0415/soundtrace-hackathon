import {test} from 'node:test';
import assert from 'node:assert/strict';
import {clipRate, clipEditDelta} from '../src/clip-time.js';

test('44.1 kHz clips retain real seconds on 48 kHz output devices', () => {
  const clip = {sampleRate:44100, startSample:0, offsetSamples:44100, durationSamples:7*44100};
  assert.equal((clip.offsetSamples+clip.durationSamples)/clipRate(clip,48000),8);
  assert.equal(clipEditDelta(clip,'right',5,48000),-3*44100);
  assert.equal(clipEditDelta(clip,'left',2,48000),44100);
  assert.equal(clipEditDelta(clip,'start',3,48000),3*44100);
});

test('48 kHz sources keep their own timing with a 44.1 kHz fallback', () => {
  const clip={sampleRate:48000,startSample:48000,offsetSamples:0,durationSamples:8*48000};
  assert.equal(clipEditDelta(clip,'start',2,44100),48000);
  assert.equal(clipEditDelta(clip,'right',8,44100),0);
});
