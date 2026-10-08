const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const MAX_BYTES = 60 * 1024 * 1024;
function readJson(file, fallback) { try { return JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,'')); } catch { return fallback; } }
function writeJson(file,value) { fs.mkdirSync(path.dirname(file),{recursive:true});const tmp=file+'.tmp';fs.writeFileSync(tmp,JSON.stringify(value,null,1));fs.renameSync(tmp,file); }
function wavInfo(bytes) {
  if(bytes.length<44||bytes.toString('ascii',0,4)!=='RIFF'||bytes.toString('ascii',8,12)!=='WAVE')throw new Error('请提交有效的 WAV 音频');
  let format,channels,rate,align,bits,size;
  for(let p=12;p+8<=bytes.length;){const id=bytes.toString('ascii',p,p+4),n=bytes.readUInt32LE(p+4);if(p+8+n>bytes.length)throw new Error('音频文件不完整');if(id==='fmt '&&n>=16){format=bytes.readUInt16LE(p+8);channels=bytes.readUInt16LE(p+10);rate=bytes.readUInt32LE(p+12);align=bytes.readUInt16LE(p+20);bits=bytes.readUInt16LE(p+22);}if(id==='data')size=n;p+=8+n+(n%2);}
  if(format!==1||![1,2].includes(channels)||!rate||![16,24,32].includes(bits)||align!==channels*bits/8||!size||size%align)throw new Error('请使用完整的 PCM WAV 音频');
  const duration=size/align/rate;if(duration>300||duration<.1)throw new Error('请保存 0.1 秒到 5 分钟以内的作品');return {duration,rate,channels};
}
function commitWork(root,bytes,info) {
  const audio=wavInfo(bytes),scenes=['sea-window','rainy-city','autumn-lake','snow-mountain','spring-meadow','desert-dusk'];
  const metadata={title:String(info.title||'此刻的声音').slice(0,80),location:String(info.location||'').slice(0,100),story:String(info.story||'').slice(0,600),scene:scenes.includes(info.scene)?info.scene:'sea-window'};
  if(Number.isFinite(info.lat)&&Number.isFinite(info.lng)&&Math.abs(info.lat)<=90&&Math.abs(info.lng)<=180){metadata.lat=info.lat;metadata.lng=info.lng;}
  const collectible=['vinyl','tape','photo'].includes(info.collectible)?info.collectible:'vinyl';
  const id=crypto.createHash('sha256').update(bytes).update(JSON.stringify({...metadata,collectible})).digest('hex').slice(0,24),file=`outputs/library/${id}/master.wav`,folder=path.join(root,'outputs/library',id);
  fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'master.wav'),bytes);
  const entry={id,kind:'mix',collectible,title:metadata.title,created:Date.now()/1000,metadata,audio:file,duration:audio.duration,img:`assets/scenes-v1/${metadata.scene}.png`,version:info.version==='ai'?'ai':'draft'};
  writeJson(path.join(folder,'project.json'),{...entry,edit:info.project||null});
  const worksFile=path.join(root,'outputs/works.json'),works=readJson(worksFile,[]),existing=works.find(w=>w.id===id);if(!existing){works.push(entry);writeJson(worksFile,works);}
  if(info.share===true){const f=path.join(root,'outputs/feed.json'),feed=readJson(f,[]);if(!feed.some(x=>x.id===`studio-${id}`)){feed.push({id:`studio-${id}`,text:metadata.story||metadata.title,kind:collectible,audio:file,img:entry.img,author:'我',created:entry.created});writeJson(f,feed);}}
  return existing||entry;
}
function createStudioApi(root,aiUrl=process.env.SOUNDTRACE_AI_URL){
  const json=(res,status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
  return async function studioApi(req,res){
    const pathname=new URL(req.url,'http://localhost').pathname;
    if(!pathname.startsWith('/api/studio/')&&!(aiUrl&&(pathname.startsWith('/api/')||pathname.startsWith('/outputs/service_jobs/'))))return false;
    const origin=req.headers.origin;if(origin&&origin!==`http://${req.headers.host}`&&origin!==`https://${req.headers.host}`){json(res,403,{detail:'请从声迹页面发起请求'});return true;}
    if(pathname==='/api/studio/health'){
      let ai=false;if(aiUrl){try{const r=await fetch(new URL('/api/health',aiUrl),{signal:AbortSignal.timeout(1200)});ai=r.ok;}catch{}}
      json(res,200,{editing:true,storage:true,ai});return true;
    }
    if(pathname==='/api/studio/works'&&req.method==='POST'){
      try{let size=0;const chunks=[];for await(const chunk of req){size+=chunk.length;if(size>MAX_BYTES){json(res,413,{detail:'音频文件过大'});return true;}chunks.push(chunk);}const encoded=req.headers['x-soundtrace-metadata']||'%7B%7D';if(encoded.length>24000)throw new Error('作品信息过长');const info=JSON.parse(decodeURIComponent(encoded));json(res,201,commitWork(root,Buffer.concat(chunks),info));}
      catch(e){json(res,400,{detail:e.message||'保存失败，请重试'});}return true;
    }
    if((pathname.startsWith('/api/')||pathname.startsWith('/outputs/service_jobs/'))&&aiUrl){
      try{const opts={method:req.method,signal:AbortSignal.timeout(300000),headers:{}};if(req.headers['content-type'])opts.headers['Content-Type']=req.headers['content-type'];if(!['GET','HEAD'].includes(req.method)){const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>(pathname==='/api/memories'?160*1024*1024:MAX_BYTES))throw new Error('上传文件过大');chunks.push(chunk);}opts.body=Buffer.concat(chunks);}const r=await fetch(new URL(req.url,aiUrl),opts);res.writeHead(r.status,{'Content-Type':r.headers.get('content-type')||'application/json'});res.end(Buffer.from(await r.arrayBuffer()));}catch(e){json(res,503,{detail:e.message==='上传文件过大'?e.message:'服务暂时不可用，请稍后重试。'});}return true;
    }
    json(res,503,{detail:'AI 服务暂未连接，本地录音、编辑和保存仍可使用。'});return true;
  };
}
module.exports={createStudioApi,commitWork,wavInfo,readJson,writeJson};
