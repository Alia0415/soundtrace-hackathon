import test from 'node:test';
import assert from 'node:assert/strict';
import {api} from '../src/api.js';

test('large audio is preserved across bounded requests and failures prevent saving',async()=>{
  const oldFetch=globalThis.fetch,oldWindow=globalThis.window;
  globalThis.window={};
  const raw=new Uint8Array(8_000_013);raw[0]=82;raw[4_000_001]=73;raw[8_000_012]=70;
  let parts=[],saved=false,fail=false;
  globalThis.fetch=async(path,options)=>{
    if(path==='/api/audio-uploads')return Response.json({upload_id:'test',chunk_size:4_000_000});
    if(options.method==='PUT'){
      if(fail)return Response.json({detail:'分段失败'},{status:503});
      assert.ok(options.body.size<=4_000_000);parts.push(new Uint8Array(await options.body.arrayBuffer()));return Response.json({});
    }
    saved=true;assert.equal(options.body.get('music_audio'),null);assert.equal(options.body.get('music_audio_upload_id'),'test');return Response.json({id:'saved'});
  };
  try{
    const form=new FormData();form.set('music_audio',new Blob([raw]),'music.wav');
    assert.equal((await api('/api/memories/owned/music',{method:'POST',body:form})).id,'saved');
    assert.deepEqual(new Uint8Array(await new Blob(parts).arrayBuffer()),raw);
    fail=true;saved=false;
    const retry=new FormData();retry.set('music_audio',new Blob([raw]),'music.wav');
    await assert.rejects(api('/api/memories/owned/music',{method:'POST',body:retry}),/分段失败/);
    assert.equal(saved,false);assert.equal(retry.get('music_audio').size,raw.length);
  }finally{globalThis.fetch=oldFetch;globalThis.window=oldWindow;}
});
