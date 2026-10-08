import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {styles} from '../src/theme.js';
import {diaryValue} from '../src/diary-options.js';
const worker=readFileSync(new URL('../src/bed-worker.js',import.meta.url),'utf8');
function render(style,diary={}){let result;const self={postMessage:value=>{result=value;}};runInNewContext(worker,{self,Float32Array,Math});self.onmessage({data:{style,diary,duration:8,sampleRate:8000}});return result;}
function digest(audio){return createHash('sha256').update(Buffer.from(audio[0].buffer)).digest('hex');}
test('ten music directions produce distinct finite bounded audio',()=>{
  const fingerprints=styles.map(([style])=>{const audio=render(style);assert.equal(audio.length,2);assert.equal(audio[0].length,64000);assert.ok(audio[0].every(value=>Number.isFinite(value)&&Math.abs(value)<=1));assert.ok(audio[0].some(value=>Math.abs(value)>.01));return digest(audio);});
  assert.equal(new Set(fingerprints).size,10);
});
test('context affects local arrangement and custom choices remain usable metadata',()=>{
  assert.notEqual(digest(render('piano')),digest(render('piano',{mood:'happy',weather:'rainy',activity:'exercise'})));
  assert.equal(diaryValue({mood:'other',moodOther:'  充满好奇  '},'mood'),'充满好奇');
  assert.equal(diaryValue({weather:'sunny'},'weather'),'晴天');
});
