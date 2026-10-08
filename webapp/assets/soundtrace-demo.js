/* Standalone interactive sample space. All API writes stay in this browser's IndexedDB. */
(() => {
  'use strict';
  const nativeFetch=window.fetch.bind(window), mediaURLs=new Map();
  const route=p=>p.startsWith('/demo')?p:'/demo'+(p==='/'?'':p);
  window.SoundTraceRoute=route;
  const scenes=['sea-window','rainy-city','autumn-lake','snow-mountain','spring-meadow','desert-dusk'];
  const titles=['西湖边的晚风','老街里的收音机','湖水慢慢的','雪山来信','收集一些春天','落日之前'];
  const stories=['风吹过湖面，也吹走了今天的一点疲惫。','路过一家小店，想起和外婆一起度过的下午。','把散步时听到的声音，装进一张唱片。','在安静的雪山脚下，听见自己的呼吸。','树梢上有鸟，脚边是新长出来的草。','天色变暖，风也慢慢停了下来。'];
  const audio=['seed_tape_water.wav','seed_vinyl.wav','seed_tape_water.wav','seed_tape_water.wav','seed_tape_birds.wav','seed_tape_water.wav'];
  function initial(){
    const memories=scenes.map((scene,i)=>({id:'demo-memory-'+i,title:titles[i],notes:stories[i],scene,created:1775980800-i*86400,captured_at:1775980800-i*86400,
      location:['断桥边','老街','湖畔','雪山脚下','苏堤','沙丘'][i],lat:[30.258,30.254,30.230,30.263,30.238,30.219][i],lng:[120.149,120.166,120.149,120.129,120.136,120.160][i],
      mood:['平静','怀念','思念','期待','开心','平静'][i],weather:['晴天','下雨','多云','下雪','有风','晴天'][i],activity:'散步',example:true,images:[],videos:[],audio_files:[],
      audio:'outputs/seeds/'+audio[i],music_audio:'outputs/seeds/seed_vinyl.wav',music_style:'piano',duration:30}));
    return {user:{id:'soundtrace-demo-user',name:'小声',username:'demo',avatar:'🎧',logged_in:true,streak:7},memories,
      posts:[{id:'demo-post-0',title:titles[0],text:stories[0],author:'小声',art:'lake',audio:memories[0].audio,created:1775980800,liked:false,likes:12,comments:2,mine:true},
        {id:'demo-post-1',title:titles[4],text:stories[4],author:'阿晴',art:'spring',created:1775808000,liked:false,likes:8,comments:1},
        {id:'demo-post-2',title:titles[1],text:stories[1],author:'阿南',audio:'outputs/seeds/seed_vinyl.wav',created:1775635200,liked:false,likes:24,comments:1}],
      comments:{'demo-post-0':[{id:'demo-comment-0',author:'阿晴',text:'好像也听到了湖边的风。',mine:false}]},
      inbox:[{id:'demo-letter',dir:'in',from:'远方的旅人',title:'春日的一封来信',story:stories[4],audio:memories[4].audio,kind:'tape',status:'delivered',allow_reuse:true}],sent:[],sample:null};
  }
  let state, database;
  const ready=new Promise((resolve,reject)=>{
    const open=indexedDB.open('soundtrace-interactive-demo-v1',1);
    open.onupgradeneeded=()=>{open.result.createObjectStore('state');open.result.createObjectStore('media');};
    open.onerror=()=>reject(open.error);
    open.onsuccess=()=>{database=open.result;const tx=database.transaction(['state','media']);const request=tx.objectStore('state').get('current');
      request.onsuccess=()=>{state=request.result||initial();};
      const cursor=tx.objectStore('media').openCursor();cursor.onsuccess=()=>{const c=cursor.result;if(c){mediaURLs.set(c.key,URL.createObjectURL(c.value));c.continue();}};
      tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);
    };
  });
  function persist(){return new Promise((resolve,reject)=>{const tx=database.transaction('state','readwrite');tx.objectStore('state').put(state,'current');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}
  async function store(blob){const ref='outputs/demo/'+crypto.randomUUID();await new Promise((resolve,reject)=>{const tx=database.transaction('media','readwrite');tx.objectStore('media').put(blob,ref);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});mediaURLs.set(ref,URL.createObjectURL(blob));return ref;}
  window.SoundTraceDemo={ready,media:ref=>mediaURLs.get(ref)||'/'+ref};
  const reply=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
  window.fetch=async(input,options={})=>{
    const url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);
    if(url.origin!==location.origin)return nativeFetch(input,options);
    await ready;
    if(url.pathname.startsWith('/outputs/demo/')){const blob=mediaURLs.get(url.pathname.slice(1));return blob?nativeFetch(blob):reply({detail:'演示文件未找到'},404);}
    if(!url.pathname.startsWith('/api/'))return nativeFetch(input,options);
    // Every /api request is handled here. Unknown endpoints fail closed, never fall through to real accounts.
    const p=url.pathname, request=input instanceof Request?input:null, method=(options.method||request?.method||'GET').toUpperCase();
    let form=options.body instanceof FormData?options.body:null,body={};
    try{
      if(request&&method!=='GET'&&method!=='HEAD'){
        const copy=request.clone();const type=copy.headers.get('content-type')||'';
        if(type.includes('multipart/form-data'))form=await copy.formData();
        else if(type.includes('application/json'))body=await copy.json();
      }else if(typeof options.body==='string')body=JSON.parse(options.body);
    }catch{return reply({detail:'参数无效'},400);}
    if(p==='/api/auth/session')return reply({user:state.user});
    if(p.startsWith('/api/auth/'))return reply({user:state.user,ok:true});
    if(p.endsWith('/health'))return reply({editing:true,storage:true,accounts:true,ai:false,demo:true});
    if(p==='/api/user'){
      if(method==='POST'){Object.assign(state.user,body);await persist();}return reply(state.user);
    }
    if(p==='/api/user/avatar'||p==='/api/user/background'){const k=p.endsWith('avatar')?'avatar_img':'background_img';state.user[k]=await store(form.get('file'));await persist();return reply({[k]:state.user[k]});}
    if(p==='/api/user/checkin'){state.user.streak++;await persist();return reply({msg:'演示签到成功'});}
    if(p==='/api/memories'&&method==='GET')return reply({memories:state.memories});
    if(p==='/api/materials')return reply({materials:state.memories.map(m=>({id:'memory-tape-'+m.id,name:m.title,audio:m.audio,metadata:{...m,story:m.notes},img:m.cover_tape}))});
    if(p==='/api/works')return reply({works:state.memories.filter(m=>m.music_audio).map(m=>({id:'memory-vinyl-'+m.id,title:m.title,audio:m.music_audio,img:m.cover_vinyl,metadata:{...m,story:m.notes}}))});
    if(p==='/api/photos')return reply({photos:state.memories.flatMap(m=>(m.images.length?m.images:[null]).map((img,i)=>({id:'memory-photo-'+m.id+'-'+i,title:m.title,img,audio:m.music_audio||m.audio,metadata:{...m,story:m.notes}})))});
    if(p==='/api/memories'&&method==='POST'){
      if(!form?.get('audio'))return reply({detail:'请选择音频'},400);
      const m={id:crypto.randomUUID(),title:form.get('title')||'此刻的声音',scene:form.get('scene')||scenes[0],notes:'',created:Date.now()/1000,captured_at:Date.now()/1000,audio:await store(form.get('audio')),images:[],videos:[],audio_files:[],music_audio:null};state.memories.unshift(m);await persist();return reply(m,201);
    }
    const match=p.match(/^\/api\/memories\/([^/]+)(?:\/(music|publish|send))?$/);
    if(match){const m=state.memories.find(m=>m.id===match[1]);if(!m)return reply({detail:'演示记忆不存在'},404);
      if(match[2]==='music'){
        for(const k of ['title','notes','mood','weather','activity','location','music_style','music_prompt'])if(form.has(k))m[k]=form.get(k);
        if(form.get('include_location')==='true'){m.lat=Number(form.get('lat'));m.lng=Number(form.get('lng'));}else{m.lat=null;m.lng=null;m.location='';}
        for(const img of form.getAll('images'))m.images.push(await store(img));m.images=m.images.slice(0,6);
        m.music_audio=await store(form.get('music_audio'));m.scene=form.get('scene')||m.scene;await persist();return reply(m);
      }
      if(match[2]==='publish'){
        let post=state.posts.find(x=>x.memory_id===m.id);if(!post){post={id:crypto.randomUUID(),memory_id:m.id,mine:true,likes:0,comments:0,liked:false};state.posts.unshift(post);}
        Object.assign(post,{author:state.user.name,title:m.title,text:m.notes,audio:m.music_audio||m.audio,images:m.images,img:m.images[0],created:Date.now()/1000});await persist();return reply(post);
      }
      if(match[2]==='send'){const id=crypto.randomUUID();state.sent.unshift({id,dir:'out',to:'远方的旅人',title:m.title,story:m.notes,audio:m.music_audio||m.audio,kind:body.kind||'vinyl',status:'delivered'});await persist();return reply({id,status:'delivered'});}
      if(method==='DELETE'){state.memories=state.memories.filter(x=>x!==m);await persist();return reply({ok:true});}return reply(m);
    }
    if(p==='/api/feed'){
      if(method==='POST'){const post={id:crypto.randomUUID(),author:state.user.name,text:body.text||body.content||'',img:body.img,created:Date.now()/1000,mine:true,liked:false,likes:0,comments:0};state.posts.unshift(post);await persist();return reply(post,201);}return reply({posts:state.posts.map(p=>({...p,like_count:p.likes,comment_count:(state.comments[p.id]||[]).length}))});
    }
    const feed=p.match(/^\/api\/feed\/([^/]+)(?:\/(like|comments))?$/);
    if(feed){const post=state.posts.find(x=>x.id===feed[1]);if(!post)return reply({detail:'动态不存在'},404);
      if(feed[2]==='like'){post.likes+=(body.liked?1:0)-(post.liked?1:0);post.liked=!!body.liked;await persist();return reply({liked:post.liked,like_count:post.likes});}
      if(feed[2]==='comments'){const items=state.comments[post.id]||=[];if(method==='POST'){items.push({id:crypto.randomUUID(),author:state.user.name,text:body.text,mine:true,created:Date.now()/1000});post.comments=items.length;await persist();}return reply({comments:items});}
      if(method==='DELETE'){state.posts=state.posts.filter(x=>x!==post);await persist();return reply({ok:true});}
    }
    if(p.startsWith('/api/comments/')&&method==='DELETE'){Object.values(state.comments).forEach(items=>{const index=items.findIndex(x=>x.id===p.split('/').pop());if(index>=0)items.splice(index,1);});await persist();return reply({ok:true});}
    if(p==='/api/inbox')return reply({items:state.inbox});if(p==='/api/exchange')return reply({items:state.sent});
    if(p==='/api/studio/sample'){
      if((method==='POST'||method==='PUT')){state.sample={id:crypto.randomUUID(),name:form.get('name')||'示例音频',audio:await store(form.get('audio'))};await persist();}
      if(method==='DELETE'){state.sample=null;await persist();}return reply({sample:state.sample});
    }
    return reply({detail:'演示中不调用外部 AI 服务；可以体验示例音乐与编辑。'},503);
  };
  function rewrite(){document.querySelectorAll('a[href]').forEach(a=>{const url=new URL(a.getAttribute('href'),location.href);if(url.origin===location.origin&&/^\/(?:studio|capture|album|map|community|me)?\/?$/.test(url.pathname)&&!a.hasAttribute('data-real-site'))a.href=route(url.pathname)+url.search+url.hash;});document.querySelectorAll('img[src],audio[src],video[src]').forEach(e=>{const u=new URL(e.getAttribute('src'),location.href);const blob=mediaURLs.get(u.pathname.slice(1));if(blob)e.src=blob;});}
  document.addEventListener('DOMContentLoaded',()=>{
    document.body.dataset.demo='true';const strip=document.createElement('details');strip.className='demo-mode-strip';strip.innerHTML='<summary>演示空间 ⌄</summary><div><button type="button">重置示例</button><a href="/" data-real-site>进入正式版 ↗</a></div>';document.body.append(strip);
    strip.querySelector('button').onclick=async()=>{if(!confirm('重置演示空间？你的正式账号不受影响。'))return;state=initial();await persist();location.href='/demo';};
    const style=document.createElement('style');style.textContent='.demo-mode-strip{position:fixed;left:calc(5vw + 110px);top:28px;z-index:97;font:12px system-ui;color:#087fab}.demo-mode-strip summary{cursor:pointer;list-style:none;padding:10px 6px;min-height:40px}.demo-mode-strip summary::-webkit-details-marker{display:none}.demo-mode-strip>div{position:absolute;left:0;top:44px;width:160px;display:flex;flex-direction:column;gap:10px;background:#fffef7;padding:14px;border:1.5px solid #222;border-radius:9px 4px 11px 5px;box-shadow:2px 3px 0 #2222}.demo-mode-strip a{color:#087fab;text-decoration:none;padding:6px 0}.demo-mode-strip button{border:0;background:none;cursor:pointer;color:#777;font:inherit;text-align:left;padding:6px 0}@media(max-width:600px){.demo-mode-strip{top:24px;left:112px;font-size:11px}}';document.head.append(style);
    let scheduled=false;const observer=new MutationObserver(()=>{if(!scheduled){scheduled=true;queueMicrotask(()=>{scheduled=false;rewrite();});}});observer.observe(document.body,{childList:true,subtree:true});rewrite();
  });
})();
