import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {commitWork,readJson,wavInfo}=require('../../tools/studio-service.cjs');
function wav(){const samples=4410,b=Buffer.alloc(44+samples*2);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVE',8);b.write('fmt ',12);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(44100,24);b.writeUInt32LE(88200,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(samples*2,40);return b;}
test('studio work has durable audio, an edit record, and is idempotent',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'soundtrace-work-'));
  try{const info={title:'海边的午后',scene:'sea-window',collectible:'tape',project:{tracks:[{id:'field'}]}},audio=wav(),a=commitWork(root,audio,info),b=commitWork(root,audio,info);
    assert.equal(a.id,b.id);assert.equal(a.collectible,'tape');assert.equal(wavInfo(fs.readFileSync(path.join(root,a.audio))).duration,.1);
    assert.equal(readJson(path.join(root,'outputs/works.json'),[]).length,1);
    assert.deepEqual(readJson(path.join(root,'outputs/library',a.id,'project.json'),{}).edit,info.project);
    assert.equal(fs.existsSync(path.join(root,'outputs/feed.json')),false);
    commitWork(root,audio,{...info,share:true});assert.equal(readJson(path.join(root,'outputs/feed.json'),[]).length,1);
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('rejects invalid audio before creating a work',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'soundtrace-invalid-'));
  try{assert.throws(()=>commitWork(root,Buffer.from('bad'),{}),/WAV/);assert.equal(fs.existsSync(path.join(root,'outputs/works.json')),false);}finally{fs.rmSync(root,{recursive:true,force:true});}
});
