import test from 'node:test';
import assert from 'node:assert/strict';
import { encodeWav, normalizationGain } from '../src/audio.js';

test('right-only stereo is audible and channel order does not affect normalization',()=>{
  const silence=new Float32Array(4),voice=new Float32Array([.2,-.2,.2,-.2]);
  assert.ok(normalizationGain([silence,voice])>0);
  assert.equal(normalizationGain([silence,voice]),normalizationGain([voice,silence]));
  assert.equal(normalizationGain([silence,silence]),0);
  assert.equal(normalizationGain([new Float32Array([.001])]),3);
});

test('WAV export has correct stereo PCM metadata and interleaved clipped samples', async()=>{
  const blob=encodeWav([new Float32Array([0,2,-2]),new Float32Array([.5,-.5,0])],24000);
  const bytes=await blob.arrayBuffer(),v=new DataView(bytes);
  assert.equal(blob.type,'audio/wav');
  assert.equal(new TextDecoder().decode(bytes.slice(0,4)),'RIFF');
  assert.equal(v.getUint16(22,true),2);
  assert.equal(v.getUint32(24,true),24000);
  assert.equal(v.getUint32(40,true),12);
  assert.equal(bytes.byteLength,56);
  assert.deepEqual(Array.from({length:6},(_,i)=>v.getInt16(44+i*2,true)),[0,16384,32767,-16384,-32768,0]);
});
