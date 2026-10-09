import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('embedded player accepts same-origin demo audio without admitting remote URLs',()=>{
  let receive;
  const parent={postMessage(){}};
  const context={playQueue:[],currentIdx:-1,location:{origin:'https://soundtrace.test'},window:{parent,addEventListener(_,fn){receive=fn;}},setTimeout(){},setInterval(){},playQueueAt(){},dismissSplash(){},coverProxySrc(){},audio:{addEventListener(){}},document:{getElementById(){return null;}}};
  vm.runInNewContext(readFileSync(new URL('../../third_party/Mineradio-paused-main/public/js/soundtrace-bridge.js',import.meta.url),'utf8'),context);
  const blob='blob:https://soundtrace.test/01234567-89ab-cdef-0123-456789abcdef';
  const tracks=['/outputs/seeds/demo-raw-water.wav',blob,'https://evil.test/audio.wav','blob:https://evil.test/01234567-89ab-cdef-0123-456789abcdef','/outputs/../private.wav'].map((audio,id)=>({audio,id}));
  receive({origin:'https://soundtrace.test',source:parent,data:{type:'soundtrace-load',tracks,autoplay:false}});
  assert.equal(context.playQueue.length,2);
  assert.equal(context.playQueue[1].localUrl,blob);
  receive({origin:'https://evil.test',source:parent,data:{type:'soundtrace-load',tracks:[],autoplay:false}});
  assert.equal(context.playQueue.length,2);
});
