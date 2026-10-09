import test from 'node:test';
import assert from 'node:assert/strict';
import {api} from '../src/api.js';

test('stalled requests time out, disconnects explain recovery, cancellation remains cancellable',async()=>{
  const oldFetch=globalThis.fetch,oldTimer=globalThis.setTimeout;
  try {
    globalThis.setTimeout=(fn,ms,...args)=>oldTimer(fn,ms===120_000?5:ms,...args);
    globalThis.fetch=async(_,options)=>new Promise((resolve,reject)=>{
      const abort=()=>reject(new DOMException('Aborted','AbortError'));
      options.signal.addEventListener('abort',abort,{once:true});
      if(options.signal.aborted)abort();
    });
    await assert.rejects(api('/api/material-import'),/超时/);
    const controller=new AbortController();controller.abort();
    await assert.rejects(api('/api/music/jobs/test',{signal:controller.signal}),{name:'AbortError'});
    globalThis.fetch=async()=>{throw new TypeError('Failed to fetch');};
    await assert.rejects(api('/api/material-library'),/网络连接中断/);
    globalThis.fetch=async()=>Response.json({detail:'文件没有音轨'},{status:400});
    await assert.rejects(api('/api/material-import'),/文件没有音轨/);
  }finally{globalThis.fetch=oldFetch;globalThis.setTimeout=oldTimer;}
});
