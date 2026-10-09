(() => {
  'use strict';

  const SCENES = [
    { id:'sea-window', name:'海港午后', accent:'#237a9d', top:'#8ec9d3', front:'#28799c', side:'#16546f', sample:'海边的午后' },
    { id:'rainy-city', name:'雨夜城市', accent:'#715d86', top:'#9c80a2', front:'#62517f', side:'#35365e', sample:'雨夜街角' },
    { id:'autumn-lake', name:'秋日湖畔', accent:'#9f6040', top:'#d7a36c', front:'#927951', side:'#5f583e', sample:'湖边的秋天' },
    { id:'snow-mountain', name:'雪山清晨', accent:'#587da5', top:'#c1d6df', front:'#7fa6c8', side:'#547391', sample:'雪山的清晨' },
    { id:'spring-meadow', name:'春日花野', accent:'#618966', top:'#cbd69b', front:'#92ae8d', side:'#607c68', sample:'花野里的风' },
    { id:'desert-dusk', name:'沙漠黄昏', accent:'#aa695e', top:'#ebb595', front:'#bc786b', side:'#755073', sample:'日落之前' },
  ];
  const SEA_FILES = { vinyl:'vinyl.png', tape:'cassette.png', photo:'photo.png', mailbox:'mailbox.png' };
  const $ = id => document.getElementById(id);
  const state = { scene:SCENES[0], photos:[], works:[], materials:[], dragItem:null, touch:null, ghost:null, suppressClickUntil:0, lastFocus:null, stageQueue:[], stageIndex:0, stageFrame:0, audioContext:null, analyser:null, memoryShelf:null, beatMeter:null, engineReady:false, enginePlaying:false, stageRequestedAutoplay:false, engineFallbackTimer:0, sceneScrollFrame:0 };
  let toastTimer;

  async function api(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) { const detail = await response.json().catch(()=>null); throw new Error(typeof detail?.detail === 'string' ? detail.detail : `请求失败：${response.status}`); }
    return response.json();
  }
  function mediaUrl(path) {
    if (typeof path !== 'string' || !/^outputs\/[\w./-]+$/.test(path) || path.includes('..')) return null;
    return window.SoundTraceDemo?.media(path) || '/' + path;
  }
  function node(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text != null) result.textContent = text;
    return result;
  }
  function notify(message) {
    const toast = $('toast');
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 3400);
  }
  function applyArt(element, kind) { window.SoundTraceArt.fill(element, kind); }
  function scrollToScene(index, behavior = 'smooth') {
    const room = $('room'), slide = $('sceneTrack').children[index];
    if (!slide) return;
    room.scrollTo({ left:slide.offsetLeft + slide.offsetWidth / 2 - room.clientWidth / 2, behavior });
  }
  function nearestSceneIndex() {
    const room = $('room');
    return Array.from($('sceneTrack').children).reduce((best, slide, index) => {
      const distance = Math.abs(slide.offsetLeft + slide.offsetWidth / 2 - room.scrollLeft - room.clientWidth / 2);
      return distance < best.distance ? { index, distance } : best;
    }, { index:0, distance:Infinity }).index;
  }
  function updateSceneOrbit() {
    const room = $('room');
    const center = room.scrollLeft + room.clientWidth / 2;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    Array.from($('sceneTrack').children).forEach(slide => {
      const distance = (slide.offsetLeft + slide.offsetWidth / 2 - center) / slide.offsetWidth;
      const turn = reduced ? 0 : Math.max(-13, Math.min(13, -distance * 11));
      const scale = reduced ? 1 : 1 - Math.min(1.5, Math.abs(distance)) * .055;
      slide.style.setProperty('--scene-turn', `${turn.toFixed(2)}deg`);
      slide.style.setProperty('--scene-scale', scale.toFixed(3));
    });
  }
  function setScene(id, options = {}) {
    const scene = SCENES.find(item => item.id === id) || SCENES[0];
    const index = SCENES.indexOf(scene);
    if ($('roomContent').parentElement?.dataset.scene !== scene.id) $('sceneTrack').children[index].appendChild($('roomContent'));
    Array.from($('sceneTrack').children).forEach((slide, slideIndex) => slide.classList.toggle('is-active', slideIndex === index));
    state.scene = scene;
    document.documentElement.style.setProperty('--scene-image', `url('scenes-v1/${scene.id}.png')`);
    document.documentElement.style.setProperty('--scene-accent', scene.accent);
    document.documentElement.style.setProperty('--cabinet-top', scene.top);
    document.documentElement.style.setProperty('--cabinet-front', scene.front);
    document.documentElement.style.setProperty('--cabinet-side', scene.side);
    $('listeningStage').style.setProperty('--stage-scene-image', `url('/assets/scenes-v1/${scene.id}.png')`);
    $('listeningStage').style.setProperty('--stage-accent', scene.accent);
    $('stageSceneName').textContent = scene.name;
    $('sceneDescription').textContent = scene.name;
    $('sceneIndex').textContent = `${String(index + 1).padStart(2, '0')} / ${String(SCENES.length).padStart(2, '0')}`;
    Array.from($('sceneProgress').children).forEach((mark, markIndex) => mark.classList.toggle('active', markIndex === index));
    if (options.scroll) scrollToScene(index, options.scroll === true ? 'smooth' : options.scroll);
    applyArt($('drawerArt'), 'delivery-box');
    renderItems();
    renderBackgrounds();
    try { localStorage.setItem(window.SoundTraceDemo?'soundtrace-demo-room-scene':'soundtrace-room-scene', scene.id); } catch (_) { /* storage may be unavailable */ }
  }
  function buildSceneCarousel() {
    const room = $('room'), track = $('sceneTrack');
    SCENES.forEach((scene, index) => {
      const backdrop = new Image();
      backdrop.src = `/assets/ui-raster-v2/collection-desktop.png`;
      const slide = index === 0 ? track.children[0] : node('article', 'scene-slide');
      slide.dataset.scene = scene.id;
      if(window.SoundTraceDemo && index===0)slide.classList.add('scene-original-background');
      slide.style.backgroundImage = '';
      slide.appendChild(window.SoundTraceArt.create(scene.id,'scene-window'));
      const mailbox=window.SoundTraceArt.create('mailbox','scene-mailbox');
      mailbox.tabIndex=0;mailbox.setAttribute('role','button');mailbox.setAttribute('aria-label','打开信箱');
      mailbox.addEventListener('click',()=>$('inboxBtn').click());
      mailbox.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();$('inboxBtn').click();}});
      slide.appendChild(mailbox);
      if (index !== 0) {
        slide.appendChild(node('span', 'scene-slide-label', scene.name));
        track.appendChild(slide);
      }
      const mark = node('span'); $('sceneProgress').appendChild(mark);
      slide.addEventListener('click', event => {
        if (event.target.closest('.memory-object,button')) return;
        if (index !== nearestSceneIndex()) scrollToScene(index);
      });
    });
    room.addEventListener('scroll', () => {
      cancelAnimationFrame(state.sceneScrollFrame);
      state.sceneScrollFrame = requestAnimationFrame(() => {
        updateSceneOrbit();
        const next = SCENES[nearestSceneIndex()];
        if (next.id !== state.scene.id) setScene(next.id);
      });
    }, { passive:true });
    window.addEventListener('resize', () => {scrollToScene(SCENES.indexOf(state.scene),'instant');updateSceneOrbit();});
    let drag = null;
    room.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'mouse' || event.target.closest('.memory-object,button')) return;
      drag = { x:event.clientX, left:room.scrollLeft, moved:false };
      room.setPointerCapture(event.pointerId);
    });
    room.addEventListener('pointermove', event => {
      if (!drag) return;
      const shift = event.clientX - drag.x;
      if (Math.abs(shift) > 5) drag.moved = true;
      if (drag.moved) { room.classList.add('is-dragging'); room.scrollLeft = drag.left - shift; }
    });
    const finish = () => {
      if (!drag) return;
      const moved = drag.moved; drag = null; room.classList.remove('is-dragging');
      if (moved) scrollToScene(nearestSceneIndex());
    };
    room.addEventListener('pointerup', finish); room.addEventListener('pointercancel', finish);
    room.addEventListener('keydown', event => {
      if (event.target !== room || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      scrollToScene(Math.max(0, Math.min(SCENES.length - 1, nearestSceneIndex() + (event.key === 'ArrowRight' ? 1 : -1))));
    });
  }
  function demo(kind) {
    const title = state.scene.sample;
    return { kind, id:`demo-${kind}`, title: kind === 'photo' ? '照片占位 · 等你收藏' : kind === 'vinyl' ? '唱片占位 · 等你创作' : '磁带占位 · 等你录音', story:'这里会展示你亲自留下的声音记忆。', demo:true };
  }
  function makeItem(item) {
    const kindName = { photo:'照片', vinyl:'唱片', tape:'磁带' }[item.kind];
    const card = node('div', `memory-object ${item.kind}`);
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `${kindName}：${item.title}，${mediaUrl(item.audio) ? '点击聆听' : '点击查看'}`);
    card.draggable = true;
    const art = node('span', 'object-art');
    applyArt(art, item.kind);
    const cover = mediaUrl(item.cover || (item.kind === 'vinyl' ? item.cover_vinyl : item.kind === 'tape' ? item.cover_tape : null));
    if (cover && item.kind !== 'photo') {
      const print = node('span', 'cover-print');
      print.style.backgroundImage = `url("${cover}")`;
      art.appendChild(print);
    }
    card.appendChild(art);
    if(window.SoundTraceDemo&&item.kind==='photo'&&item.metadata?.example){
      card.classList.add('has-photo');const print=window.SoundTraceArt.create(item.metadata.scene || state.scene.id,'demo-photo-landscape');print.setAttribute('aria-label','这段记忆的示例风景');card.appendChild(print);
    }
    if (item.kind === 'photo' && mediaUrl(item.img)) {
      const actual = node('img', 'actual-photo');
      actual.src = mediaUrl(item.img);
      actual.alt = '';
      actual.loading = 'lazy';
      card.classList.add('has-photo');card.appendChild(actual);
    }
    card.appendChild(node('span', 'object-title', item.title || kindName));
    const send = node('button', 'send-shortcut');
    send.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/></svg>';
    send.type = 'button';
    send.draggable = false;
    send.setAttribute('aria-label', `寄出${item.title || kindName}`);
    send.addEventListener('click', event => { event.stopPropagation(); showSend(item); });
    card.appendChild(send);
    if (item.kind === 'tape' && item.metadata?.id && !item.demo) {
      const compose = node('button', 'send-shortcut compose-shortcut', '♫');
      compose.type = 'button'; compose.draggable = false;
      compose.style.right = '48px';
      compose.setAttribute('aria-label', `用${item.title || kindName}生成音乐日记`);
      compose.addEventListener('click', event => {event.stopPropagation();location.href = (window.SoundTraceRoute?.('/studio?memory='+encodeURIComponent(item.metadata.id)+'#rec') || '/studio?memory='+encodeURIComponent(item.metadata.id)+'#rec');});
      card.appendChild(compose);
    }
    const activate = () => mediaUrl(item.audio) ? openStage(item) : showDetail(item);
    card.addEventListener('click', () => { if (Date.now() > state.suppressClickUntil) activate(); });
    card.addEventListener('keydown', event => {
      if (event.target !== card) return;
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
    });
    card.addEventListener('dragstart', event => {
      state.dragItem = item;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', `${item.kind}:${item.id}`);
      showDrawer();
    });
    card.addEventListener('dragend', () => setTimeout(() => { if (state.dragItem === item) finishDrag(); }, 120));
    bindTouchDrag(card, item);
    return card;
  }
  function renderItems() {
    const wall = $('photoLine'), cabinet = $('cabinetObjects');
    wall.replaceChildren(); cabinet.replaceChildren();
    const sceneWorks = state.works.filter(w => !w.metadata?.scene || w.metadata.scene === state.scene.id);
    const photos = [...state.photos.filter(p => !p.metadata?.scene || p.metadata.scene === state.scene.id).map(p => ({...p, kind:'photo'})),
      ...sceneWorks.filter(w => w.collectible === 'photo').map(w => ({...w, kind:'photo'}))];
    if (!photos.length) photos.push(demo('photo'));
    photos.forEach((item, index) => {
      const card = makeItem(item);
      card.style.setProperty('--tilt', `${[-3, 2, -1, 3, -2][index % 5]}deg`);
      wall.appendChild(card);
    });
    const works = sceneWorks.filter(w => !w.collectible || w.collectible === 'vinyl').map(w => ({...w, kind:'vinyl'}));
    const materials = [...state.materials.filter(m => !m.metadata?.scene || m.metadata.scene === state.scene.id).map(m => ({...m, kind:'tape', title:m.name || '一段声音'})),
      ...sceneWorks.filter(w => w.collectible === 'tape').map(w => ({...w, kind:'tape'}))];
    if (!works.length) works.push(demo('vinyl'));
    if (!materials.length) materials.push(demo('tape'));
    [[works,'vinyl','唱片'],[materials,'tape','磁带']].forEach(([items,kind,label])=>{
      const shelf=node('div',`cabinet-shelf ${kind}-shelf`);
      shelf.tabIndex=0;shelf.setAttribute('role','group');shelf.setAttribute('aria-label',label+'层架，左右滚动浏览');
      items.forEach(item=>shelf.appendChild(makeItem(item)));cabinet.appendChild(shelf);
    });
  }
  async function loadData() {
    const urls = ['/api/photos', '/api/works', '/api/materials'];
    const results = await Promise.allSettled(urls.map(url => api(url)));
    if (results[0].status === 'fulfilled') state.photos = results[0].value.photos || [];
    if (results[1].status === 'fulfilled') state.works = (results[1].value.works || []).slice().reverse();
    if (results[2].status === 'fulfilled') state.materials = results[2].value.materials || [];
    renderItems();
    renderBackgrounds();
    watchArtJobs();
    if (results.some(result => result.status === 'rejected')) {
      notify(location.protocol === 'file:'
        ? '本地视觉预览：当前展示示例物件。'
        : '部分收藏暂时无法加载，页面正在显示示例物件。');
    }
  }
  const backgroundSelection = {};
  const artJobs = new Map();
  let artConfig = {enabled:false}, artBusy = false;
  function sceneMemories(scene) {
    return state.materials.map(m=>m.metadata).filter(m=>m?.id && (m.scene || 'sea-window') === scene.id);
  }
  function backgroundMemory(scene) {
    const memories = sceneMemories(scene);
    return memories.find(m=>m.id===backgroundSelection[scene.id]) || memories[0];
  }
  function renderBackgrounds() {
    if (!window.SoundTraceDemo) {
      SCENES.forEach(scene=>{
        const windowEl = $('sceneTrack').querySelector(`[data-scene="${scene.id}"] .scene-window`);
        if (!windowEl) return;
        windowEl.replaceChildren();
        const memory = backgroundMemory(scene);
        const source = memory?.background_source || memory?.images?.[0];
        const drawn = memory?.background_mode === 'stylized' && memory?.scene_art_source === source;
        const url = mediaUrl(drawn ? memory.scene_art : source);
        windowEl.classList.toggle('has-memory-background',!!url);
        if (url) {
          const photo = node('img','memory-background');photo.src=url;photo.alt=drawn?'根据原照片生成的手绘背景':'这段记忆的真实照片';
          photo.draggable=false;photo.loading='lazy';windowEl.appendChild(photo);
        } else if (memory) {
          const paper = node('span','memory-background-text', memory.notes || memory.title);
          windowEl.appendChild(paper);
        }
      });
    }
    renderBackgroundTools();
  }
  function renderBackgroundTools() {
    const host = $('backgroundTools'); if (!host) return;
    host.replaceChildren();host.hidden=true;
    if (window.SoundTraceDemo) return;
    const memory = backgroundMemory(state.scene);
    if (!memory?.images?.length) return;
    host.hidden=false;
    const memories=sceneMemories(state.scene).filter(m=>m.images?.length);
    const picker=node('select');picker.setAttribute('aria-label','选择背景记忆');
    memories.forEach(m=>{const option=node('option','',m.title);option.value=m.id;picker.appendChild(option);});
    picker.value=memory.id;picker.disabled=artBusy;
    picker.addEventListener('change',()=>{backgroundSelection[state.scene.id]=picker.value;renderBackgrounds();});
    if(memories.length>1)host.appendChild(picker);
    const photoPicker=node('select');photoPicker.setAttribute('aria-label','选择背景照片');
    memory.images.forEach((ref,index)=>{const option=node('option','',`照片 ${index+1}`);option.value=index;photoPicker.appendChild(option);});
    const index=Math.max(0,memory.images.indexOf(memory.background_source || memory.images[0]));photoPicker.value=index;
    photoPicker.disabled=artBusy;
    photoPicker.addEventListener('change',()=>changeBackground(memory,'photo',Number(photoPicker.value)));
    if(memory.images.length>1)host.appendChild(photoPicker);
    const original=node('button','','照片');original.type='button';original.disabled=artBusy;
    original.setAttribute('aria-pressed',String(memory.background_mode!=='stylized'));
    original.addEventListener('click',()=>changeBackground(memory,'photo',index));host.appendChild(original);
    const existing=memory.scene_art && memory.scene_art_source===memory.images[index];
    const job=artJobs.get(memory.scene_art_job);
    const running=job && ['queued','running'].includes(job.status);
    const draw=node('button','',running?'正在绘制…':existing?'手绘':job?.status==='failed'?'重试手绘':'生成手绘');
    draw.type='button';draw.disabled=artBusy || running || (!existing && !artConfig.enabled);
    draw.setAttribute('aria-pressed',String(memory.background_mode==='stylized' && !!existing));
    draw.addEventListener('click',()=>existing?changeBackground(memory,'stylized',index):requestArt(memory,index));host.appendChild(draw);
    if(existing && !running){const redo=node('button','', '重新绘制');redo.type='button';redo.disabled=artBusy || !artConfig.enabled;redo.addEventListener('click',()=>requestArt(memory,index));host.appendChild(redo);}
    const hint=node('small','background-status',job?.status==='failed'?job.stage:running?job.stage:existing?'AI 手绘 · 原照片已保留':artConfig.enabled?'生成手绘会将所选照片发送给豆包。':'手绘服务待配置，当前显示原照片');
    hint.setAttribute('role','status');host.appendChild(hint);
  }
  async function changeBackground(memory,mode,index) {
    artBusy=true;renderBackgroundTools();
    try {await api(`/api/memories/${encodeURIComponent(memory.id)}/background`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,image_index:index})});await loadData();}
    catch(error){notify(error.message);}finally{artBusy=false;renderBackgroundTools();}
  }
  async function requestArt(memory,index) {
    artBusy=true;renderBackgroundTools();
    try {
      await api('/api/art/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({memory_id:memory.id,image_index:index,consent:true})});
      await loadData();
    } catch(error){notify(error.message);}finally{artBusy=false;renderBackgroundTools();}
  }
  function watchArtJobs() {
    if(window.SoundTraceDemo)return;
    state.materials.forEach(material=>{
      const jid=material.metadata?.scene_art_job;
      if(!jid || artJobs.has(jid))return;
      artJobs.set(jid,{status:'queued',stage:'正在读取生成进度'});
      const poll=async()=>{
        try {
          const job=await api('/api/art/jobs/'+encodeURIComponent(jid));artJobs.set(jid,job);renderBackgroundTools();
          if(['queued','running'].includes(job.status)){setTimeout(poll,2000);return;}
          if(job.status==='done')await loadData();
        }catch(error){artJobs.set(jid,{status:'failed',stage:'生成进度暂时无法读取，请刷新重试'});renderBackgroundTools();}
      };poll();
    });
  }
  function showDrawer() {
    $('mailDrawer').classList.add('open');
    $('mailDrawer').setAttribute('aria-hidden', 'false');
    document.body.classList.add('dragging');
  }
  function finishDrag() {
    state.dragItem = null;
    $('mailDrawer').classList.remove('open');
    $('mailDrawer').setAttribute('aria-hidden', 'true');
    $('dropZone').classList.remove('over');
    document.body.classList.remove('dragging');
    if (state.ghost) { state.ghost.remove(); state.ghost = null; }
  }
  function pointInside(element, x, y) {
    const rect = element.getBoundingClientRect();
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }
  function bindTouchDrag(card, item) {
    card.addEventListener('pointerdown', event => {
      if (event.pointerType === 'mouse' || event.target.closest('button')) return;
      state.touch = { card, item, x:event.clientX, y:event.clientY, active:false };
      card.setPointerCapture(event.pointerId);
    });
    card.addEventListener('pointermove', event => {
      const touch = state.touch;
      if (!touch || touch.card !== card) return;
      if (!touch.active && Math.hypot(event.clientX - touch.x, event.clientY - touch.y) < 10) return;
      if (!touch.active) {
        touch.active = true;
        state.dragItem = item;
        state.ghost = card.cloneNode(true);
        state.ghost.classList.add('drag-ghost');
        state.ghost.style.width = `${card.getBoundingClientRect().width}px`;
        document.body.appendChild(state.ghost);
        showDrawer();
      }
      event.preventDefault();
      state.ghost.style.left = `${event.clientX - card.getBoundingClientRect().width / 2}px`;
      state.ghost.style.top = `${event.clientY - card.getBoundingClientRect().height / 2}px`;
      $('dropZone').classList.toggle('over', pointInside($('dropZone'), event.clientX, event.clientY));
    });
    const stop = event => {
      const touch = state.touch;
      if (!touch || touch.card !== card) return;
      if (touch.active) {
        state.suppressClickUntil = Date.now() + 400;
        const accepted = event.type === 'pointerup' && pointInside($('dropZone'), event.clientX, event.clientY);
        finishDrag();
        if (accepted) showSend(item);
      }
      state.touch = null;
    };
    card.addEventListener('pointerup', stop);
    card.addEventListener('pointercancel', stop);
  }
  function openModal(content) {
    if ($('modalBackdrop').hidden) state.lastFocus = document.activeElement;
    document.querySelector('#modalBackdrop .modal').dataset.surface=content.dataset.surface||'detail';
    $('modalContent').replaceChildren(content);
    $('modalBackdrop').hidden = false;
    $('closeModal').focus();
  }
  function closeModal() {
    $('modalContent').querySelectorAll('audio').forEach(audio => audio.pause());
    $('modalBackdrop').hidden = true;
    $('modalContent').replaceChildren();
    if (state.lastFocus && state.lastFocus.isConnected) state.lastFocus.focus();
  }
  function modalStart(title, surface='detail') {
    const wrap = node('div');wrap.dataset.surface=surface;
    const heading = node('h2', '', title);
    heading.id = 'modalTitle';
    wrap.appendChild(heading);
    return wrap;
  }
  function addAudio(wrap, raw) {
    const src = mediaUrl(raw);
    if (!src) return;
    const audio = node('audio');
    audio.controls = true;audio.setAttribute('aria-label','播放这段记忆');
    audio.src = src;
    wrap.appendChild(audio);
  }
  function playableItems() {
    if (!window.SoundTraceDemo && new URLSearchParams(location.search).get('demo') === '1') {
      const audio = 'outputs/seeds/demo-raw-lakeside.wav', finished = 'outputs/seeds/demo-mix-lakeside.wav';
      const metadata = { location:state.scene.name };
      return [
        { kind:'photo', id:'listen-demo-photo', title:state.scene.sample, story:'听一听，声音把你带回了哪里？', audio, metadata, demo:true },
        { kind:'vinyl', id:'listen-demo-vinyl', title:`《湖畔风声与鸟鸣》`, story:'前两秒是风声与鸟鸣，随后钢琴进入。素材混合示例，非西湖实地录音。', audio:finished, metadata, demo:true },
        { kind:'tape', id:'listen-demo-tape', title:`湖畔风声与鸟鸣`, story:'一盘留给下一次创作的声音磁带。', audio, metadata, demo:true },
      ];
    }
    return [
      ...state.photos.map(item => ({ ...item, kind:'photo' })),
      ...state.works.map(item => ({ ...item, kind:item.collectible || 'vinyl' })),
      ...state.materials.map(item => ({ ...item, kind:'tape', title:item.name || '一段声音' })),
    ].filter(item => mediaUrl(item.audio));
  }
  function stageArt(item) {
    if (item.kind === 'photo' && mediaUrl(item.img)) return mediaUrl(item.img);
    if (mediaUrl(item.cover || item.cover_vinyl || item.cover_tape || item.img))
      return mediaUrl(item.cover || item.cover_vinyl || item.cover_tape || item.img);
    const file = state.scene.id === 'sea-window' ? SEA_FILES[item.kind] : `${item.kind}.png`;
    return state.scene.id === 'sea-window'
      ? `/assets/visual-v1/${file}`
      : `/assets/object-sets-v2/${state.scene.id}/${file}`;
  }
  function postEngine(message) {
    const target = $('mineradioEngine').contentWindow;
    if (target) target.postMessage(message, location.origin);
  }
  function syncEngineQueue(autoplay) {
    if (!state.engineReady || $('listeningStage').hidden) return;
    postEngine({ type:'soundtrace-load', index:state.stageIndex, autoplay,
      tracks:state.stageQueue.map((track, index) => ({
        id:track.id || index,
        title:track.title || track.name || '一段声音',
        artist:track.kind==='vinyl'?'音乐成品 · 声迹':'现场原声 · 声迹',
        location:track.metadata?.location || state.scene.name,
        audio:mediaUrl(track.audio),
        cover:new URL(stageArt(track), location.href).pathname,
      })) });
  }
  function formatTime(seconds) {
    if (!Number.isFinite(seconds)) return '--:--';
    return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
  }
  function updateStageTime() {
    const audio = $('stageAudio');
    const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
    $('stageTime').textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    $('stageProgress').value = duration ? Math.round(audio.currentTime / duration * 1000) : 0;
  }
  function updateStagePlay() {
    const playing = state.engineReady ? state.enginePlaying : !$('stageAudio').paused;
    $('stagePlay').textContent = playing ? 'Ⅱ' : '▶';
    $('stagePlay').setAttribute('aria-label', playing ? '暂停' : '播放');
    $('listeningStage').classList.toggle('is-playing', playing);
  }
  function renderStageShelf() {
    const shelf = $('stageShelf');
    shelf.replaceChildren();
    state.stageQueue.forEach((item, index) => {
      const button = node('button');
      button.type = 'button';
      button.classList.toggle('active', index === state.stageIndex);
      button.setAttribute('aria-label', `聆听${{photo:'照片原声',tape:'现场原声',vinyl:'音乐成品'}[item.kind]||''}：${item.title || item.name || '一段声音'}`);
      button.setAttribute('aria-current', index === state.stageIndex ? 'true' : 'false');
      const picture = node('img'); picture.src = stageArt(item); picture.alt = '';
      button.append(picture, node('span', '', ({photo:'照片原声 · ',tape:'现场原声 · ',vinyl:'音乐成品 · '}[item.kind]||'')+(item.title || item.name || '一段声音')));
      button.addEventListener('click', () => selectStageTrack(index, true));
      shelf.appendChild(button);
    });
  }
  function selectStageTrack(index, autoplay) {
    if (!state.stageQueue.length) return;
    state.stageIndex = (index + state.stageQueue.length) % state.stageQueue.length;
    const item = state.stageQueue[state.stageIndex];
    const related=track=>item.metadata?.id?track.metadata?.id===item.metadata.id:item.id?.startsWith('listen-demo-')&&track.id?.startsWith('listen-demo-');
    const rawIndex=state.stageQueue.findIndex(track=>related(track)&&track.kind==='tape');
    const mixIndex=state.stageQueue.findIndex(track=>related(track)&&track.kind==='vinyl');
    $('stageCompare').hidden=rawIndex<0||mixIndex<0;
    if(rawIndex>=0&&mixIndex>=0){$('stageRaw').onclick=()=>selectStageTrack(rawIndex,true);$('stageMix').onclick=()=>selectStageTrack(mixIndex,true);$('stageRaw').setAttribute('aria-pressed',String(item.kind!=='vinyl'));$('stageMix').setAttribute('aria-pressed',String(item.kind==='vinyl'));}
    const memoryImage = mediaUrl(item.metadata?.images?.[0] || (item.kind === 'photo' ? item.img : null));
    const memoryVideo = mediaUrl(item.metadata?.videos?.[0]);
    const video = $('stageMemoryVideo');
    video.pause();
    if (memoryVideo) { video.src = memoryVideo; video.hidden = false; video.play().catch(() => {}); }
    else { video.hidden = true; video.removeAttribute('src'); }
    $('listeningStage').style.setProperty('--stage-scene-image', memoryImage ? `url("${memoryImage}")` : 'none');
    const audio = $('stageAudio');
    audio.pause();
    if (!state.engineReady) {
      audio.src = mediaUrl(item.audio);
      audio.load();
    }
    $('stageKind').textContent = { photo:'01 / 照片原声', vinyl:'02 / 音乐成品', tape:'03 / 现场原声' }[item.kind];
    $('stageTitle').textContent = item.title || item.name || '一段声音';
    $('stageStory').textContent = item.story || item.metadata?.story || '把这段声音重新放进耳边，回到当时的场景。';
    $('stageLocation').textContent = item.metadata?.location || state.scene.name;
    updateStageTime();
    updateStagePlay();
    renderStageShelf();
    if (state.memoryShelf) state.memoryShelf.setActive(state.stageIndex);
    if (autoplay) playStage();
  }
  async function playStage() {
    if (state.engineReady) {
      postEngine({ type:'soundtrace-select', index:state.stageIndex });
      return;
    }
    const audio = $('stageAudio');
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass && !state.audioContext) {
        state.audioContext = new AudioContextClass();
        state.analyser = state.audioContext.createAnalyser();
        state.analyser.fftSize = 2048;
        const source = state.audioContext.createMediaElementSource(audio);
        source.connect(state.analyser);
        state.analyser.connect(state.audioContext.destination);
      }
      if (state.audioContext?.state === 'suspended') await state.audioContext.resume();
      await audio.play();
      updateStagePlay();
    } catch (_) {
      $('stageLocation').textContent = '音频暂时无法播放，请返回收藏间重试。';
      updateStagePlay();
    }
  }
  function drawStage() {
    if ($('listeningStage').hidden) return;
    const canvas = $('stageCanvas');
    const bounds = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(bounds.width * dpr));
    const height = Math.max(1, Math.round(bounds.height * dpr));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, width, height);
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const data = state.analyser ? new Uint8Array(state.analyser.frequencyBinCount) : null;
    if (data) state.analyser.getByteFrequencyData(data);
    const playing = !$('stageAudio').paused;
    if (!state.beatMeter && window.createSoundTraceBeatMeter) state.beatMeter = window.createSoundTraceBeatMeter();
    const response = state.beatMeter?.update(data, state.audioContext?.sampleRate || 44100, state.analyser?.fftSize || 2048, playing) || { bass:0, mid:0, treble:0, energy:0, beat:0 };
    if (state.memoryShelf) state.memoryShelf.setAudioResponse(response);
    const activity = response.energy;
    const time = reduced ? 0 : performance.now() * .00018;
    ctx.lineWidth = Math.max(1, dpr);
    for (let i = 0; i < 72; i++) {
      const angle = i * Math.PI * 2 / 72;
      const frequency = data && playing ? data[Math.min(data.length - 1, Math.floor(i * data.length / 72))] / 255 : 0;
      const radius = Math.min(width, height) * (.24 + frequency * .025 + response.bass * .04 + response.beat * .018);
      const cx = width * .42, cy = height * .46;
      ctx.strokeStyle = `rgba(136,211,213,${.065 + frequency * .17 + response.treble * .18 + response.beat * .12})`;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
      ctx.lineTo(cx + Math.cos(angle) * (radius + (5 + frequency * 40 + response.mid * 22) * dpr), cy + Math.sin(angle) * (radius + (5 + frequency * 40 + response.mid * 22) * dpr));
      ctx.stroke();
    }
    for (let i = 0; i < 58; i++) {
      const x = ((i * 79.7 + time * (i % 3 + 1) * 26) % 100) / 100 * width;
      const y = ((i * 37.3 + (reduced ? 0 : Math.sin(time * 9 + i) * 2)) % 100) / 100 * height;
      ctx.fillStyle = `rgba(211,233,225,${.12 + activity * .2})`;
      ctx.beginPath(); ctx.arc(x, y, (i % 4 === 0 ? 1.5 : .7) * dpr, 0, Math.PI * 2); ctx.fill();
    }
    if (!reduced) state.stageFrame = requestAnimationFrame(drawStage);
  }
  function openStage(item) {
    state.stageReturnFocus = document.activeElement;
    state.stageQueue = playableItems();
    if (!state.stageQueue.length) { notify('先录下一段声音，或制作一张唱片，再进入聆听舞台。'); return; }
    const index = item ? state.stageQueue.findIndex(track => track.kind === item.kind && track.id === item.id) : 0;
    if (!$('modalBackdrop').hidden) closeModal();
    const player=$('mineradioEngine');if(!player.hasAttribute('src'))player.src=player.dataset.src;
    $('listeningStage').hidden = false;
    state.stageRequestedAutoplay = true;
    document.body.classList.add('stage-open');
    document.querySelector('.topbar').inert = true;
    document.querySelector('main').inert = true;
    const shelfHost = $('stageShelf3d');
    if (getComputedStyle(shelfHost).display !== 'none' && window.createSoundTraceMineRadioShelf) {
      if (!state.memoryShelf) state.memoryShelf = window.createSoundTraceMineRadioShelf(shelfHost, index => selectStageTrack(index, true));
      if (state.memoryShelf) {
        $('listeningStage').classList.remove('no-3d');
        state.memoryShelf.setItems(state.stageQueue.map(track => ({ kind:track.kind, title:track.title || track.name || '一段声音', sub:track.metadata?.location || state.scene.name, tag:{ photo:'声音照片', vinyl:'完成的唱片', tape:'声音磁带' }[track.kind], cover:stageArt(track) })));
        state.memoryShelf.start();
      } else $('listeningStage').classList.add('no-3d');
    }
    selectStageTrack(index < 0 ? 0 : index, false);
    if (state.engineReady) syncEngineQueue(true);
    else {
      clearTimeout(state.engineFallbackTimer);
      state.engineFallbackTimer = setTimeout(() => {
        if (!state.engineReady && !$('listeningStage').hidden && state.stageRequestedAutoplay) playStage();
      }, 8000);
    }
    $('stageClose').focus();
    cancelAnimationFrame(state.stageFrame);
    if (!state.engineReady) drawStage();
  }
  function closeStage() {
    $('stageAudio').pause();
    $('stageMemoryVideo').pause();
    clearTimeout(state.engineFallbackTimer);
    if (state.engineReady) postEngine({ type:'soundtrace-pause' });
    if (state.memoryShelf) state.memoryShelf.stop();
    $('listeningStage').hidden = true;
    document.body.classList.remove('stage-open');
    document.querySelector('.topbar').inert = false;
    document.querySelector('main').inert = false;
    cancelAnimationFrame(state.stageFrame);
    const returnFocus = state.stageReturnFocus;
    (returnFocus && returnFocus.isConnected ? returnFocus : $('enterStage')).focus();
  }
  function showDetail(item) {
    const label = { photo:'一张照片', vinyl:'一张唱片', tape:'一盘磁带' }[item.kind];
    const wrap = modalStart(item.title || label);
    if (item.kind === 'photo' && mediaUrl(item.img)) {
      const img = node('img'); img.src = mediaUrl(item.img); img.alt = item.title || '声音记忆照片'; wrap.appendChild(img);
    }
    const story = item.story || (item.metadata && item.metadata.story) || `${label}，收藏着一次真实的声音经历。`;
    wrap.appendChild(node('p', '', story));
    const location = item.metadata && item.metadata.location;
    if (location) wrap.appendChild(node('p', '', `地点：${location}`));
    addAudio(wrap, item.audio);
    if (item.demo) wrap.appendChild(node('p', 'disclosure', '这是展示画风的示例。录制或上传后，你的内容会出现在这里。'));
    const row = node('div', 'controls');
    if (mediaUrl(item.audio)) {
      const listen = node('button', 'action', '沉浸聆听'); listen.type = 'button'; listen.addEventListener('click', () => openStage(item)); row.appendChild(listen);
    }
    const send = node('button', 'action', '放进信箱'); send.type = 'button'; send.addEventListener('click', () => showSend(item)); row.appendChild(send);
    const close = node('button', 'secondary', '关闭'); close.type = 'button'; close.addEventListener('click', closeModal); row.appendChild(close);
    wrap.appendChild(row); openModal(wrap);
  }
  function showSend(item) {
    const kindName = { photo:'照片', vinyl:'唱片', tape:'磁带' }[item.kind];
    const wrap = modalStart(`寄出这${item.kind === 'tape' ? '盘' : '张'}${kindName}`, 'send');
    wrap.appendChild(node('p', '', `「${item.title}」`));
    if (item.demo) {
      wrap.appendChild(node('p', 'disclosure', '这是场景示例物件。先记录真实声音或制作唱片，再来寄出自己的记忆。'));
      const link = node('a', 'action', '去记录'); link.href = '/studio#rec'; link.style.display = 'inline-block'; link.style.marginTop = '12px'; wrap.appendChild(link);
      openModal(wrap); return;
    }
    const illustration=window.SoundTraceArt.create('mailbox','mail-send-art');wrap.appendChild(illustration);
    wrap.appendChild(node('p', 'disclosure', window.SoundTraceDemo?'在演示空间里体验声音交换。':'加入交换后，将匹配另一位愿意交换声音的旅人。'));
    const feedLabel = node('label');
    const feed = node('input'); feed.type = 'checkbox'; feedLabel.append(feed, document.createTextNode('同时加入声音交换，接收远方来信'));
    const reuseLabel = node('label');
    const reuse = node('input'); reuse.type = 'checkbox'; reuse.checked = true; reuseLabel.append(reuse, document.createTextNode('允许收到的人使用这段素材进行二次创作'));
    wrap.append(feedLabel, reuseLabel);
    const row = node('div', 'controls');
    const submit = node('button', 'action', '发送给远方的有缘人'); submit.type = 'button';
      submit.onclick=async()=>{
        submit.disabled=true;
        try{
          const mid=item.metadata?.id||item.memory_id||item.id;
          const result=await apiJSON('/api/memories/'+encodeURIComponent(mid)+'/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:item.kind||'vinyl',allow_reuse:reuse.checked,receive_mail:feed.checked})});
          loadProfileStrip();closeModal();notify(result.status==='delivered'?'已送达远方旅人的信箱。':'已放进信箱，等待另一位愿意交换声音的旅人。');
        }catch(e){notify(e.message||'寄出失败，请重试。');submit.disabled=false;}
      };
    const cancel = node('button', 'secondary', '取消'); cancel.type = 'button'; cancel.addEventListener('click', closeModal);
    row.append(submit, cancel); wrap.appendChild(row); openModal(wrap);
  }
  async function openInbox() {
    const wrap = modalStart('收件箱', 'inbox');
    const illustration=window.SoundTraceArt.create('mailbox','mail-send-art');wrap.appendChild(illustration);
    wrap.appendChild(node('p', 'disclosure', '一段声音，一封远方来信。'));
    const tabs=node('div','inbox-tabs'),receivedTab=node('button','','收到'),sentTab=node('button','','寄出');
    receivedTab.type=sentTab.type='button';receivedTab.setAttribute('aria-pressed','true');sentTab.setAttribute('aria-pressed','false');tabs.append(receivedTab,sentTab);wrap.append(tabs);
    const receivedContent=node('div','inbox-content'),sentContent=node('div','inbox-content');sentContent.hidden=true;wrap.append(receivedContent,sentContent);
    const switchTab=sent=>{receivedContent.hidden=sent;sentContent.hidden=!sent;receivedTab.setAttribute('aria-pressed',String(!sent));sentTab.setAttribute('aria-pressed',String(sent));};
    receivedTab.onclick=()=>switchTab(false);sentTab.onclick=()=>switchTab(true);
    try {
      const result = await api('/api/inbox');
      const items = result.items || [];
      if (!items.length) receivedContent.appendChild(node('p', '', '收件箱还没有来信。'));
      items.forEach(item => {
        const letter = node('div', 'inbox-letter');
        letter.appendChild(node('strong', '', item.title || '一封来信'));
        letter.appendChild(node('p', '', `来自：${item.from || '匿名旅人'} · ${item.allow_reuse ? '允许二次创作' : '未经授权不可二次创作'}`));
        if (item.story) letter.appendChild(node('p', '', item.story));
        if(mediaUrl(item.img)){const img=node('img','letter-photo');img.src=mediaUrl(item.img);img.alt='来信中的记忆照片';letter.appendChild(img);}
        addAudio(letter, item.audio);
        receivedContent.appendChild(letter);
      });
    } catch (_) { receivedContent.appendChild(node('p', '', '暂时无法读取收件箱。')); }
    // 我寄出的（“我的”与收藏间合并后，寄出清单归入信箱）
    try {
      const result = await api('/api/exchange');
      const sent = (result.items || []).filter(x => x.dir === 'out');
      const kindName = { photo: '照片', vinyl: '唱片', tape: '磁带' };
      if (sent.length) {
        sentContent.appendChild(node('h3', '', '我寄出的'));
        sent.forEach(item => sentContent.appendChild(node('div', 'inbox-letter',
          `${kindName[item.kind] || item.kind}「${item.title}」 · ${item.status==='waiting'?'等待有缘人':'已送达'} · ${item.allow_reuse ? '已授权二创' : '禁止二创'}`)));
      } else sentContent.appendChild(node('p','','还没有寄出的声音。'));
    } catch (_) { /* 寄出清单读取失败不阻塞收件箱 */ }
    openModal(wrap);
  }
  function setup() {
    window.addEventListener('message', event => {
      if (event.origin !== location.origin || event.source !== $('mineradioEngine').contentWindow) return;
      const message = event.data || {};
      if (message.type === 'soundtrace-engine-ready') {
        state.engineReady = true;
        clearTimeout(state.engineFallbackTimer);
        $('stageAudio').pause();
        $('listeningStage').classList.add('engine-ready');
        cancelAnimationFrame(state.stageFrame);
        syncEngineQueue(true);
      } else if (message.type === 'soundtrace-engine-error') {
        if (!$('listeningStage').hidden) notify('音频暂时无法读取，请换一件藏品再试。');
      } else if (message.type === 'soundtrace-engine-state') {
        state.enginePlaying = !!message.playing;
        const elapsed=Number.isFinite(message.currentTime)?message.currentTime:0;
        const length=Number.isFinite(message.duration)?message.duration:0;
        $('stageTime').textContent=`${formatTime(elapsed)} / ${formatTime(length)}`;
        $('stageProgress').value=length?Math.round(elapsed/length*1000):0;
        const stage = $('listeningStage');
        for (const key of ['bass','beat','energy']) {
          const value = Number.isFinite(message[key]) ? Math.max(0, Math.min(1, message[key])) : 0;
          stage.style.setProperty(`--stage-${key}`, value.toFixed(3));
        }
        if (state.memoryShelf) state.memoryShelf.setAudioResponse(message);
        if (!$('listeningStage').hidden && message.index >= 0 && message.index < state.stageQueue.length && message.index !== state.stageIndex) selectStageTrack(message.index, false);
        updateStagePlay();
      }
    });
    buildSceneCarousel();
    let initial = SCENES[0].id;
    try { initial = localStorage.getItem(window.SoundTraceDemo?'soundtrace-demo-room-scene':'soundtrace-room-scene') || initial; } catch (_) { /* storage may be unavailable */ }
    const requested = new URLSearchParams(location.search).get('scene');
    if (SCENES.some(scene => scene.id === requested)) initial = requested;
    // The global smooth-scroll rule otherwise animates through earlier scenes
    // on load, which can make autoplay capture the wrong scene's cover art.
    setScene(initial, { scroll:'instant' });
    requestAnimationFrame(updateSceneOrbit);
    const zone = $('dropZone');
    zone.addEventListener('dragover', event => { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; zone.classList.add('over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('over'));
    zone.addEventListener('drop', event => {
      event.preventDefault();
      const item = state.dragItem;
      finishDrag();
      if (item) showSend(item);
    });
    $('inboxBtn').addEventListener('click', openInbox);
    $('stripAva').addEventListener('click', () => openProfile());
    $('stripCheckin').addEventListener('click', async event => {
      event.target.disabled = true;
      try { await apiJSON('/api/user/checkin', { method: 'POST' }); } catch (_) {}
      event.target.disabled = false;
      loadProfileStrip();
    });
    loadProfileStrip();
    $('enterStage').addEventListener('click', () => openStage());
    $('stageClose').addEventListener('click', closeStage);
    $('stagePlay').addEventListener('click', () => { const audio = $('stageAudio'); if (audio.paused) playStage(); else audio.pause(); });
    $('stagePrevious').addEventListener('click', () => selectStageTrack(state.stageIndex - 1, true));
    $('stageNext').addEventListener('click', () => selectStageTrack(state.stageIndex + 1, true));
    $('stageProgress').addEventListener('input', () => { const audio = $('stageAudio'); if (Number.isFinite(audio.duration)) audio.currentTime = audio.duration * Number($('stageProgress').value) / 1000; });
    $('stageAudio').addEventListener('timeupdate', updateStageTime);
    $('stageAudio').addEventListener('loadedmetadata', updateStageTime);
    $('stageAudio').addEventListener('play', updateStagePlay);
    $('stageAudio').addEventListener('pause', updateStagePlay);
    $('stageAudio').addEventListener('ended', () => { if (state.stageQueue.length > 1) selectStageTrack(state.stageIndex + 1, true); else updateStagePlay(); });
    $('closeModal').addEventListener('click', closeModal);
    $('modalBackdrop').addEventListener('click', event => { if (event.target === $('modalBackdrop')) closeModal(); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !$('listeningStage').hidden) closeStage();
      else if (event.key === 'Escape' && !$('modalBackdrop').hidden) closeModal();
      else if (event.code === 'Space' && !$('listeningStage').hidden && event.target.tagName !== 'BUTTON' && event.target.tagName !== 'INPUT') {
        event.preventDefault(); $('stagePlay').click();
      }
    });
    if(!window.SoundTraceDemo)api('/api/art/config').then(config=>{artConfig=config;renderBackgroundTools();}).catch(()=>{});
    loadData().then(() => {
      const params = new URLSearchParams(location.search);
      if(params.get('saved')){
        api('/api/memories/'+encodeURIComponent(params.get('saved'))).then(memory=>{
          const wrap=modalStart('音乐已保存');
          wrap.append(node('p','',memory.title),node('p','disclosure','作品已保存到“我的音乐”，下次可从底部导航回来重听。原声素材仍然保留。'));
          if(params.has('art_unavailable'))wrap.append(node('p','disclosure','记忆已保存；手绘服务尚未就绪，当前保留原照片。可在收藏间稍后生成。'));
          wrap.append(window.SoundTraceArt.create('vinyl','mail-send-art'));
          const row=node('div','saved-memory-actions');
          const publish=node('button','secondary','分享到社区（可选）');
          publish.onclick=async()=>{publish.disabled=true;try{await apiJSON('/api/memories/'+encodeURIComponent(memory.id)+'/publish',{method:'POST'});publish.textContent='已同步到社区 ✓';}catch(e){notify(e.message||'同步失败，请重试');publish.disabled=false;}};
          const send=node('button','secondary','发送给远方的有缘人');send.onclick=()=>showSend({...memory,kind:'vinyl',metadata:memory});
          const view=node('button','action','查看我的音乐');view.onclick=closeModal;
          const map=node('a','secondary','声音地图 ↗');map.href='/map';
          row.append(view,publish,send,map);wrap.append(row);openModal(wrap);
          history.replaceState(null,'',window.SoundTraceRoute?.('/album?scene='+encodeURIComponent(memory.scene||'sea-window')) || '/album?scene='+encodeURIComponent(memory.scene||'sea-window'));
        }).catch(()=>notify('记忆暂时无法读取，请重试。'));
      } else if (params.get('listen') === '1') {
        const item = playableItems().find(track => String(track.id) === params.get('item') && track.kind === params.get('kind'));
        openStage(item);
      } else if (params.get('profile') === '1') {
        openProfile();
      }
    });
  }

  // —— 我的记忆（已并入收藏间页面：intro 档案条 + 编辑弹窗）——
  async function loadProfileStrip() {
    try {
      const [user, exchange] = await Promise.all([apiJSON('/api/user'), apiJSON('/api/exchange')]);
      const sent = (exchange.items || []).filter(x => x.dir === 'out');
      const stripAvatar = document.querySelector('#stripAva');
      if (user.avatar_img && mediaUrl(user.avatar_img)) {
        stripAvatar.replaceChildren(Object.assign(document.createElement('img'), { src:mediaUrl(user.avatar_img), alt:'' }));
      } else stripAvatar.replaceChildren(window.SoundTraceArt.create('avatar-'+Math.max(0,PROFILE_AVAS.indexOf(user.avatar))));
      document.querySelector('#stripName').textContent = user.name || '旅行者';
      document.querySelector('#stripSub').textContent = `连续签到 ${user.streak || 0} 天 · 寄出 ${sent.length} 件`;
    } catch (_) { /* 静默：档案条显示默认文案 */ }
  }
  const PROFILE_AVAS = ['🎧','🏔','🌊','🐦','🍁','🚂','🎸','🌙'];
  async function apiJSON(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error('暂时无法保存，请稍后重试');
    return response.json();
  }
  async function openProfile() {
    state.lastFocus = document.activeElement;
    const wrap = modalStart('编辑个人资料', 'profile');
    document.querySelector('#modalBackdrop .modal').dataset.surface='profile';
    const panel = node('div', 'profile-panel');
    panel.innerHTML = `
      <div class="profile-bg" id="pBg"></div>
      <div class="profile-head"><span class="profile-ava" id="pAva">🎧</span>
        <div><strong id="pName">…</strong><small id="pLogin"></small></div></div>
      <div class="profile-edit"><label>昵称 <input id="pNameIn" maxlength="16"></label>
        <button type="button" id="pSave">保存</button></div>
      <div class="profile-uploads">
        <label class="profile-upload" aria-label="上传头像">上传头像<svg class="avatar-upload-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h4l2-3h4l2 3h4v14H4z"/><circle cx="12" cy="12" r="4"/></svg><input type="file" id="pAvaFile" accept="image/*" hidden></label>
        <label class="profile-upload">上传背景<input type="file" id="pBgFile" accept="image/*" hidden></label>
      </div>
      <h3 class="profile-avatar-title">选择头像</h3><div class="profile-avas" id="pAvas"></div>
      <div class="profile-stats" id="pStats"></div>
      <button type="button" class="profile-checkin" id="pCheckin">今日签到</button>
      <div class="profile-sent"><span class="st-section-title">寄出的声音</span><div id="pSents">…</div></div>
      <p class="profile-feedback" id="pFeedback" role="status"></p>`;
    wrap.appendChild(panel);
    $('modalContent').replaceChildren(wrap);
    $('modalBackdrop').hidden = false;
    $('closeModal').focus();

    const render = (user, sent) => {
      // 真实头像图片（上传过的优先于 emoji）
      if (user.avatar_img) {
        $('pAva').replaceChildren(Object.assign(document.createElement('img'), { src: '/' + user.avatar_img }));
        $('pAva').classList.add('has-img');
      } else {
        $('pAva').classList.remove('has-img');
        $('pAva').replaceChildren(window.SoundTraceArt.create('avatar-'+Math.max(0,PROFILE_AVAS.indexOf(user.avatar))));
      }
      if (user.background_img) {
        $('pBg').style.backgroundImage = `url('/${user.background_img}')`;
        $('pBg').style.display = 'block';
      } else { $('pBg').style.removeProperty('display');$('pBg').style.removeProperty('background-image');}
      $('pName').textContent = user.name || '旅行者';
      $('pNameIn').value = user.name || '';
      $('pLogin').textContent = user.logged_in ? '已登录' : '编辑资料，开启声音档案';
      $('pAvas').innerHTML = PROFILE_AVAS.map((a,index) =>
        `<button type="button" aria-label="头像 ${a}" data-avatar="${a}" data-art="avatar-${index}" aria-pressed="${a === user.avatar}"></button>`).join('');
      $('pAvas').querySelectorAll('button').forEach(btn => btn.appendChild(window.SoundTraceArt.create(btn.dataset.art)));
      $('pAvas').querySelectorAll('button').forEach(btn => btn.addEventListener('click', async () => {
        try { await apiJSON('/api/user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ avatar: btn.dataset.avatar }) }); refresh(); }
        catch (error) { $('pFeedback').textContent = error.message; }
      }));
      $('pStats').innerHTML = `<div><img src="/assets/ui-selected-v3/profile-stats.webp" alt=""><span>连续签到<b>${user.streak || 0}<small>天</small></b></span></div><div><img src="/assets/ui-selected-v3/send-stats.webp" alt=""><span>寄出<b>${sent.length}</b></span></div>`;
      const kindName = { photo: '照片', vinyl: '唱片', tape: '磁带' };
      $('pSents').innerHTML = sent.map(s =>
        `<div class="it">${kindName[s.kind] || s.kind}「${escapeItem(s.title)}」 → ${escapeItem(s.to || '同好')}
          <span class="tag">${s.allow_reuse ? '已授权二创' : '禁止二创'}</span></div>`).join('')
        || '<div class="it empty"><img src="/assets/ui-selected-v3/profile-empty.webp" alt=""><p>尚未寄出</p></div>';
    };
    const escapeItem = value => String(value ?? '').replace(/[&<>"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[character]));
    async function refresh() {
      try {
        const [user, exchange] = await Promise.all([apiJSON('/api/user'), apiJSON('/api/exchange')]);
        render(user, (exchange.items || []).filter(x => x.dir === 'out'));
        loadProfileStrip();
      } catch (error) { $('pFeedback').textContent = '暂时无法读取资料'; }
    }
    $('pSave').addEventListener('click', async () => {
      const value = $('pNameIn').value.trim();
      if (!value) return;
      try {
        await apiJSON('/api/user', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: value, logged_in: true }) });
        $('pFeedback').textContent = '已保存'; refresh();      } catch (error) { $('pFeedback').textContent = error.message; }
    });
    // 真实头像/背景上传
    const uploadImage = async (input, endpoint) => {
      const file = input.files && input.files[0];
      if (!file) return;
      $('pFeedback').textContent = '上传中…';
      try {
        const body = new FormData(); body.append('file', file);
        const response = await fetch(endpoint, { method: 'POST', body });
        if (!response.ok) throw new Error('上传失败');
        $('pFeedback').textContent = '已更新'; input.value = '';
        refresh();
      } catch (error) { $('pFeedback').textContent = error.message; }
    };
    $('pAvaFile').addEventListener('change', e => uploadImage(e.target, '/api/user/avatar'));
    $('pBgFile').addEventListener('change', e => uploadImage(e.target, '/api/user/background'));
    $('pCheckin').addEventListener('click', async event => {
      event.target.disabled = true;
      try { $('pFeedback').textContent = (await apiJSON('/api/user/checkin', { method: 'POST' })).msg || '已签到'; refresh(); }
      catch (error) { $('pFeedback').textContent = error.message; }
      event.target.disabled = false;
    });
    panel.querySelectorAll('.profile-upload').forEach(label=>{label.tabIndex=0;label.setAttribute('role','button');label.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();label.querySelector('input').click();}});});
    refresh();
  }
  setup();
})();
