(async()=>{
 const $=id=>document.getElementById(id), media=v=>typeof v==='string'&&/^(outputs|assets)\/[\w./-]+$/.test(v)&&!v.includes('..')?(window.SoundTraceDemo?.media(v)||'/'+v):'';
 const make=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e;};
 const examples=[
 {id:'example-wind',title:'西湖边的晚风',location:'断桥边',weather:'晴天',mood:'平静',notes:'风吹过湖面，也吹走了今天的一点疲惫。',lat:30.258,lng:120.149,audio:'outputs/seeds/seed_tape_water.wav',example:true},
 {id:'example-birds',title:'收集一些春天',location:'苏堤',weather:'多云',mood:'开心',notes:'树梢上有鸟，脚边是新长出来的草。',lat:30.238,lng:120.136,audio:'outputs/seeds/seed_tape_birds.wav',example:true},
 {id:'example-music',title:'湖水慢慢的',location:'湖畔',weather:'晴天',mood:'怀念',notes:'把散步时听到的声音，装进一张唱片。',lat:30.230,lng:120.149,audio:'outputs/seeds/seed_vinyl.wav',example:true}
 ];
 let memories=[],works=[];
 try{const r=await Promise.all([fetch('/api/memories').then(r=>{if(!r.ok)throw Error();return r.json();}),fetch('/api/works').then(r=>r.json())]);memories=r[0].memories||[];works=(r[1].works||[]).filter(w=>!String(w.id).startsWith('memory-vinyl-')).map(w=>({...w,...w.metadata,notes:w.metadata?.story,images:w.img?[w.img]:[]}));}
 catch{$('mapMode').textContent='足迹加载失败';const retry=make('button','','重试');retry.onclick=()=>location.reload();$('list').append(retry);return;}
 const own=[...memories,...works].sort((a,b)=>(b.captured_at||b.created||0)-(a.captured_at||a.created||0)),demo=!!window.SoundTraceDemo,items=own;
 $('mapMode').textContent=demo?'示例足迹':'我的足迹';$('footprintCount').textContent=items.length+' 段声音';
 const located=items.filter(m=>m.lat!=null&&m.lng!=null&&Number.isFinite(Number(m.lat))&&Number.isFinite(Number(m.lng)));
 const mobile=matchMedia('(max-width:760px)').matches;
 let map=null,converted=new Map(),MemoryMarker;
 if(demo){
  map=L.map('geoMap',{crs:L.CRS.Simple,minZoom:-4,maxZoom:3,zoomSnap:0,zoomControl:false,attributionControl:false});L.control.zoom({position:'topleft'}).addTo(map);
  const bounds=mobile?[[0,0],[1448,1086]]:[[0,0],[1086,1448]];
  L.imageOverlay('/assets/ui-raster-v2/map-'+(mobile?'mobile':'desktop')+'-paper.png',bounds).addTo(map);
  map.fitBounds(bounds,{padding:[0,0]});map.setZoom(map.getBoundsZoom(bounds,true));map.setMaxBounds(L.latLngBounds(bounds).pad(.4));
  $('atlasCaption').textContent='西湖 · 手绘示意 / 示例声音';
 }else{
  try{
    const response=await fetch('/api/map/config');if(!response.ok)throw Error('无法读取地图配置');const config=await response.json();
    if(!config.enabled)throw Error('真实地图待启用：需要配置腾讯地图 Key');
    window._TMapSecurityConfig={serviceHost:location.origin+config.service_host};
    await new Promise((resolve,reject)=>{
      if(window.TMap?.Map){resolve();return;}
      const script=document.createElement('script');
      const done=error=>{clearTimeout(timer);delete window.soundtraceTencentReady;error?reject(error):resolve();};
      const timer=setTimeout(()=>done(Error('腾讯地图加载超时，请检查网络与域名白名单')),20000);
      window.soundtraceTencentReady=()=>done();
      script.src='https://map.qq.com/api/gljs?v=1&callback=soundtraceTencentReady';
      script.onerror=()=>done(Error('腾讯地图加载失败，请检查网络与域名白名单'));document.head.append(script);
    });
    if(located.length){
      for(let start=0;start<located.length;start+=40){
        const chunk=located.slice(start,start+40);
        const response=await fetch('/api/map/coordinates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({locations:chunk.map(m=>[Number(m.lat),Number(m.lng)])})});
        const result=await response.json();
        if(!response.ok)throw Error(result.detail||'位置转换失败，足迹仍保留在列表中');
        if(!Array.isArray(result.locations)||result.locations.length!==chunk.length)throw Error('位置转换结果不完整，足迹仍保留在列表中');
        chunk.forEach((m,i)=>converted.set(m.id,new TMap.LatLng(result.locations[i].lat,result.locations[i].lng)));
      }
    }
    map=new TMap.Map('geoMap',{zoom:4,center:new TMap.LatLng(35.8,104.1),viewMode:'2D',...(config.style?{mapStyleId:config.style}:{})});
    MemoryMarker=class extends TMap.DOMOverlay{
      onInit(options){this.position=options.position;this.pin=options.pin;}
      createDOM(){return this.pin;}
      updateDOM(){const p=this.getMap().projectToContainer(this.position);this.pin.style.cssText=`position:absolute;left:${p.x}px;top:${p.y}px;transform:translate(-32px,-72px)`;}
      getContent(){return this.pin;}
      onDestroy(){this.pin.onclick=null;this.pin.onkeydown=null;}
    };
    $('atlasCaption').textContent='腾讯地图 · 我的声音足迹';
  }catch(error){
    map?.destroy();map=null;converted.clear();$('mapMode').textContent='我的足迹';const message=make('div','map-service-state');message.append(make('strong','',error.message));const retry=make('button','','重试连接');retry.onclick=()=>location.reload();const preview=make('a','','看看演示地图 ↗');preview.href='/demo/map';message.append(retry,preview);$('geoMap').replaceChildren(message);$('atlasCaption').textContent='你的足迹数据仍保留在右侧列表';
  }
 }
 const markers=new Map();
 function picture(m,cls=''){
   const e=make('span','atlas-photo '+cls);const src=media(m.images?.[0]||m.cover_vinyl||m.cover_tape);
   if(src){const img=make('img');img.src=src;img.alt=m.title||'记忆照片';e.append(img);}
   else if(m.example){e.classList.add('example-landscape');}
   else{e.classList.add('atlas-text-photo');e.textContent=m.notes||m.title||'此刻的声音';}
   return e;
 }
 function select(m){
   document.querySelectorAll('.work').forEach(e=>e.classList.toggle('selected',e.dataset.id===m.id));
   markers.forEach((marker,id)=>(demo?marker.getElement():marker.getContent())?.classList.toggle('selected',id===m.id));
   $('mapMemory').querySelectorAll('audio').forEach(a=>a.pause());$('mapMemory').replaceChildren();$('mapMemory').hidden=false;
   const close=make('button','memory-close','×');close.setAttribute('aria-label','关闭足迹详情');close.onclick=()=>{$('mapMemory').querySelectorAll('audio').forEach(a=>a.pause());$('mapMemory').hidden=true;};
   const title=make('h2','',m.title),meta=make('p','popmeta',[m.location,m.weather,m.mood,m.example?'示例':m.lat==null?'未添加位置':''].filter(Boolean).join(' · '));
   const date=make('time','popmeta',m.captured_at||m.created?new Date((m.captured_at||m.created)*1000).toLocaleString('zh-CN'):'');
   $('mapMemory').append(close,title,meta,date,picture(m,'memory-print'),make('p','popstory',m.notes||''));
   if(!m.images?.length&&media(m.videos?.[0])){const video=make('video','memory-video');video.controls=true;video.preload='metadata';video.src=media(m.videos[0]);$('mapMemory').querySelector('.memory-print').replaceWith(video);}
   const src=media(m.music_audio||m.audio);if(src)$('mapMemory').append(SoundTracePlayer(src,m.title));
   if(!m.example){const link=make('a','memory-open','查看收藏 ↗');link.href='/album?scene='+encodeURIComponent(m.scene||'sea-window');$('mapMemory').append(link);}
 }
 const displayPoint=m=>demo?[((m.lat-30.209)/.067)*(mobile?1448:1086),((m.lng-120.112)/.064)*(mobile?1086:1448)]:[m.lat,m.lng];
 items.forEach(m=>{
  const row=make('article','work');row.dataset.id=m.id;
  const btn=make('button','footprint-open');btn.setAttribute('aria-label','查看足迹：'+m.title);const text=make('span','footprint-copy');text.append(make('b','',m.title),make('small','meta',[m.location||'未添加位置',m.example?'示例':new Date((m.captured_at||m.created)*1000).toLocaleDateString('zh-CN')].join(' · ')));btn.append(picture(m),text);btn.onclick=()=>select(m);row.append(btn);
  const src=media(m.music_audio||m.audio);if(src)row.append(SoundTracePlayer(src,m.title));$('list').append(row);
  if(map&&located.includes(m)&&(demo||converted.has(m.id))){
   const pin=make('div','scene-orb');pin.append(picture(m));let marker;
   if(demo){const icon=L.divIcon({className:'atlas-pin',html:pin.outerHTML,iconSize:[64,76],iconAnchor:[32,72]});marker=L.marker(displayPoint(m),{icon,title:m.title,keyboard:true}).addTo(map).on('click',()=>select(m));}
   else{pin.tabIndex=0;pin.setAttribute('role','button');pin.setAttribute('aria-label',m.title);pin.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(m);}};pin.onclick=()=>select(m);marker=new MemoryMarker({map,position:converted.get(m.id),pin,isStopPropagation:true});}
   markers.set(m.id,marker);
  }else if(!located.includes(m)){const b=make('button','unlocated-memory');b.setAttribute('aria-label','未添加位置：'+m.title);b.append(picture(m));b.onclick=()=>select(m);$('unlocated').append(b);}
 });
 if(demo&&located.length>1)L.polyline(located.slice().reverse().map(displayPoint),{color:'#222',weight:2,dashArray:'5 10',opacity:.45,interactive:false}).addTo(map);
 if(!demo&&markers.size){const points=[...converted.values()],bounds=new TMap.LatLngBounds(points[0],points[0]);points.slice(1).forEach(p=>bounds.extend(p));map.fitBounds(bounds,{padding:80,maxZoom:14});}
 if(!items.length)$('list').append(make('p','meta','还没有声音足迹。录下一段声音，在制作日记时选择记录位置。'));
 $('mapMemory').hidden=true;if(demo&&map)new ResizeObserver(()=>map.invalidateSize()).observe($('mapWrap'));
})().catch(()=>{document.getElementById('mapMode').textContent='地图暂时无法显示，请刷新重试';});
