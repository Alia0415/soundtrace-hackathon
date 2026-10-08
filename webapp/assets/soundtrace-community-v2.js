(() => {
  const scenes = [
    ['sea-window', '海港午后'],
    ['rainy-city', '雨夜街角'],
    ['autumn-lake', '湖畔清晨'],
    ['snow-mountain', '雪山之上'],
    ['spring-meadow', '春日旷野'],
    ['desert-dusk', '暮色沙丘']
  ];
  const sceneNames = Object.fromEntries(scenes);
  const feed = document.getElementById('feed');
  const composer = document.getElementById('communityCompose');
  const composeText = document.getElementById('composeText');
  const composeStatus = document.getElementById('composeStatus');
  const composeSubmit = document.getElementById('composeSubmit');
  const openButton = document.getElementById('openCompose');
  const examples=[
    {id:'sample-wind',example:true,author:'小声',title:'西湖边的晚风',text:'傍晚在西湖边走了一圈，风把树叶和湖面的声音都吹得很温柔。那一刻觉得，生活真好。',created:1775980800,audio:'outputs/seeds/seed_tape_water.wav',art:'lake'},
    {id:'sample-spring',example:true,author:'阿晴',title:'收集一些春天的声音',text:'周末带着相机去公园，风吹树梢、脚踩落叶、远处的孩子在笑……把这些声音都装进了照片里。',created:1775808000,art:'spring'},
    {id:'sample-radio',example:true,author:'阿南',title:'老街里的收音机',text:'路过一家小店，门口还放着一台老收音机。想起小时候和外婆一起度过的下午。',created:1775635200,audio:'outputs/seeds/seed_vinyl.wav'}
  ];
  let posts = [];
  let filter = 'all';
  let chosenScene = scenes[0][0];
  let retryCount = 0;
  let likes;
  try { likes = JSON.parse(localStorage.getItem('soundtrace_likes') || '{}') || {}; }
  catch { likes = {}; }

  function mediaPath(value) {
    if (typeof value !== 'string' || value.includes('..')) return null;
    return /^(outputs|assets)\/[\w./-]+$/.test(value) ? (window.SoundTraceDemo?.media(value) || '/' + value) : null;
  }

  function sceneFor(post) {
    const match = String(post.img || '').match(/scenes-v1\/([\w-]+)\.png$/);
    return match && sceneNames[match[1]] ? match[1] : null;
  }

  function imageFor(post) {
    const scene=sceneFor(post);
    return mediaPath(post.img) || '/assets/scenes-v1/'+(scene||'sea-window')+'.png';
  }

  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#community-' + name);
    svg.append(use);
    return svg;
  }

  function action(name, label, iconName) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'community-action community-' + name;
    button.setAttribute('aria-label', label);
    button.append(icon(iconName));
    const text = document.createElement('span');
    text.textContent = label;
    button.append(text);
    return button;
  }

  function renderPost(post, index) {
    const article = document.createElement('article');
    article.className = 'community-post';
    article.id = 'post-' + String(post.id || index).replace(/[^\w-]/g, '');
    const scene = sceneFor(post);
    const cover = imageFor(post);
    const author = String(post.author || '一位旅人');

    const head = document.createElement('header');
    head.className = 'community-post-head';
    const avatar = document.createElement('img');
    avatar.className = 'community-avatar';
    avatar.src = mediaPath(post.avatar_img) || '/assets/ui-doodle-v1/01-home-mobile.webp';
    avatar.alt = '';
    avatar.loading = 'lazy';
    const byline = document.createElement('div');
    byline.className = 'community-byline';
    const name = document.createElement('strong');
    name.textContent = author;
    const date = document.createElement('time');
    if (Number.isFinite(Number(post.created))) {
      const timestamp = new Date(Number(post.created) * 1000);
      date.dateTime = timestamp.toISOString();
      date.textContent = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(timestamp);
    } else {
      date.textContent = '刚刚';
    }
    byline.append(name, date);
    head.append(mediaPath(post.avatar_img)?avatar:window.SoundTraceArt.create('avatar','community-avatar'), byline);
    if(post.example){const badge=document.createElement('span');badge.className='sample-badge';badge.textContent='示例';head.append(badge);}
    article.append(head);
    if(post.title){const title=document.createElement('h2');title.className='community-story-title';title.textContent=post.title;article.append(title);}

    const copy = document.createElement('p');
    copy.className = 'community-post-text';
    copy.textContent = String(post.text || '');
    article.append(copy);

    const images = Array.isArray(post.images) ? post.images.map(mediaPath).filter(Boolean) : [];
    if (!images.length && mediaPath(post.img)) images.push(cover);
    if (images.length) {
      const media = document.createElement('div');
      media.className = 'community-post-media' + (images.length > 1 ? ' is-grid' : '');
      if(images.length===1 && /cover_(tape|vinyl)|(?:tape|vinyl)_cover/.test(images[0]))media.classList.add('is-generated');
      images.slice(0, 9).forEach((src, imageIndex) => {
        const picture = document.createElement('img');
        picture.src = src;
        picture.alt = images.length === 1 ? (scene ? sceneNames[scene] + '的场景画面' : '分享的图片') : '分享的图片 ' + (imageIndex + 1);
        picture.loading = index === 0 && imageIndex === 0 ? 'eager' : 'lazy';
        media.append(picture);
      });
      article.append(media);
    }

    if(post.art){
      const illustration=document.createElement('div');illustration.className='sample-art sample-art-'+post.art;
      const image=document.createElement('img');image.src='/assets/ui-doodle-v1/25-community-mobile.webp';image.alt=post.art==='lake'?'西湖晚风的手绘相框照片':'春花、公园与猫咪的三张手绘相框照片';illustration.append(image);article.append(illustration);
    }
    const audioPath = mediaPath(post.audio);
    if (audioPath) {
      const player = document.createElement('div');
      player.className = 'community-player';
      const label = document.createElement('span');
      label.textContent = '听听这段声音';
      const audio = document.createElement('audio');
      audio.controls = true;
      audio.preload = 'none';
      audio.src = audioPath;
      audio.setAttribute('aria-label', author + '分享的声音');
      player.append(window.SoundTracePlayer(audioPath,author+'分享的声音'));
      article.append(player);
    }

    if (scene) {
      const topic = document.createElement('a');
      topic.className = 'community-topic';
      topic.href = '/album?scene=' + encodeURIComponent(scene);
      topic.textContent = '# ' + sceneNames[scene];
      article.append(topic);
    }

    const footer = document.createElement('footer');
    footer.className = 'community-actions';
    const like = action('like', '喜欢', 'heart');
    const serverLikes = typeof post.liked === 'boolean';
    const liked = serverLikes ? post.liked : !!likes[post.id];
    like.classList.toggle('is-liked', liked);
    like.setAttribute('aria-pressed', String(liked));
    if (serverLikes) like.querySelector('span').textContent = post.like_count ? '喜欢 ' + post.like_count : '喜欢';
    like.addEventListener('click', async () => {
      if (serverLikes) {
        like.disabled = true;
        try {
          const r = await fetch(`/api/feed/${post.id}/like`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({liked:!post.liked})});
          const value = await r.json(); if (!r.ok) throw new Error(value.detail);
          post.liked = value.liked; post.like_count = value.like_count;
          like.classList.toggle('is-liked', value.liked);like.setAttribute('aria-pressed', String(value.liked));
          like.querySelector('span').textContent = value.like_count ? '喜欢 ' + value.like_count : '喜欢';
        } catch (e) {showNotice(e.message || '暂时无法喜欢这条动态');} finally {like.disabled = false;}
        return;
      }
      likes[post.id] = !likes[post.id];
      try { localStorage.setItem('soundtrace_likes', JSON.stringify(likes)); } catch {}
      like.classList.toggle('is-liked', !!likes[post.id]);
      like.setAttribute('aria-pressed', String(!!likes[post.id]));
    });
    const reply = action('reply', '回应', 'reply');
    reply.addEventListener('click', () => serverLikes ? openReplies(article, post) : showNotice('这是示例动态；你可以分享自己的声音与经历。'));
    const share = action('share', '分享', 'share');
    share.addEventListener('click', async () => {
      const url = new URL('#' + article.id, location.href).href;
      try {
        if (navigator.share) await navigator.share({ title: '声迹 · 社区', text: String(post.text || '').slice(0, 80), url });
        else if (navigator.clipboard) {
          await navigator.clipboard.writeText(url);
          showNotice('链接已复制');
        } else showNotice('可以复制地址栏中的链接分享');
      } catch (error) {
        if (error.name !== 'AbortError') showNotice('暂时无法分享');
      }
    });
    footer.append(like, reply, share);
    if (post.mine) {
      const remove = action('delete', '删除', 'reply');
      remove.addEventListener('click', async () => {
        if (!await window.soundtraceConfirmDeletion(post.title||'这条动态','收藏中的原始记忆会保留。')) return;
        remove.disabled = true;
        try { const r = await fetch('/api/feed/' + encodeURIComponent(post.id), { method:'DELETE' });
          if (!r.ok) throw new Error(); await load(); }
        catch { showNotice('删除失败，请重试'); remove.disabled = false; }
      });
      footer.append(remove);
    }
    article.append(footer);
    return article;
  }

  function showNotice(message) {
    const notice = document.getElementById('communityNotice');
    notice.textContent = message;
    notice.hidden = false;
    clearTimeout(showNotice.timer);
    showNotice.timer = setTimeout(() => { notice.hidden = true; }, 2800);
  }

  async function openReplies(article, post) {
    let panel = article.querySelector('.community-replies');
    if (panel) {panel.hidden = !panel.hidden;if(!panel.hidden)panel.querySelector('textarea').focus();return;}
    panel = document.createElement('section');panel.className = 'community-replies';
    panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','回应');
    const close=document.createElement('button');close.type='button';close.className='replies-close';close.textContent='×';close.setAttribute('aria-label','关闭回应');close.onclick=()=>{panel.hidden=true;article.querySelector('.community-reply').focus();};
    const heading=document.createElement('h2');heading.textContent='回应';
    const original=document.createElement('p');original.className='reply-original';original.textContent=post.title||post.text;
    panel.append(close,heading,original);
    const list = document.createElement('div');list.className='reply-list';
    const form = document.createElement('form');
    const input = document.createElement('textarea');input.maxLength=1000;input.required=true;input.placeholder='留下你的回应';input.setAttribute('aria-label','回应内容');
    const send = document.createElement('button');send.type='submit';send.textContent='发送回应';
    const status = document.createElement('p');status.setAttribute('role','status');
    form.append(input,send,status);panel.append(list,form);article.append(panel);input.focus();
    async function refresh() {
      const r=await fetch(`/api/feed/${post.id}/comments`);const result=await r.json();if(!r.ok)throw new Error(result.detail);
      list.replaceChildren();
      for(const item of result.comments){
        const row=document.createElement('p');const author=document.createElement('strong');author.textContent=item.author+'：';row.append(author,document.createTextNode(item.text));
        if(item.mine){const remove=document.createElement('button');remove.type='button';remove.textContent='删除';remove.onclick=async()=>{const r=await fetch(`/api/comments/${item.id}`,{method:'DELETE'});if(r.ok)await refresh();else status.textContent='删除失败';};row.append(remove);}
        list.append(row);
      }
    }
    form.onsubmit=async event=>{event.preventDefault();send.disabled=true;try{const r=await fetch(`/api/feed/${post.id}/comments`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:input.value.trim()})});const value=await r.json();if(!r.ok)throw new Error(value.detail);input.value='';status.textContent='';await refresh();}catch(e){status.textContent=e.message;}finally{send.disabled=false;}};
    try{await refresh();}catch(e){status.textContent=e.message;}
  }

  function render() {
    const visible = posts.filter(post => {
      const hasAudio = !!mediaPath(post.audio);
      return filter === 'all' || (filter === 'audio' ? hasAudio : !hasAudio);
    });
    if (!visible.length) {
      const empty = document.createElement('div');
      empty.className = 'community-empty';
      empty.textContent = posts.length ? '这里还没有新的分享' : '还没有分享，来留下第一段经历吧';
      feed.replaceChildren(empty);
    } else feed.replaceChildren(...visible.map(renderPost));
  }

  document.querySelectorAll('.community-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      filter = tab.dataset.filter;
      document.querySelectorAll('.community-tab').forEach(other => {
        const active = other === tab;
        other.classList.toggle('is-active', active);
        if (active) other.setAttribute('aria-current', 'page');
        else other.removeAttribute('aria-current');
      });
      render();
    });
  });

  function openComposer(prefix = '') {
    composer.hidden = false;
    openButton.setAttribute('aria-expanded', 'true');
    if (prefix) composeText.value = prefix;
    composeStatus.textContent = '';
    composer.setAttribute('role','dialog');composer.setAttribute('aria-modal','true');
    composeText.focus({ preventScroll: true });
  }
  function closeComposer() {
    composer.hidden = true;
    openButton.setAttribute('aria-expanded', 'false');
    openButton.focus({ preventScroll: true });
  }
  openButton.addEventListener('click', () => composer.hidden ? openComposer() : closeComposer());
  document.getElementById('composeCancel').addEventListener('click', closeComposer);
  document.addEventListener('keydown', event => {
    if(event.key==='Escape'){if(!composer.hidden)closeComposer();document.querySelectorAll('.community-replies:not([hidden])').forEach(panel=>panel.querySelector('.replies-close').click());}
    if(event.key==='Tab'){const surface=!composer.hidden?composer:document.querySelector('.community-replies:not([hidden])');if(!surface)return;const nodes=[...surface.querySelectorAll('button:not(:disabled),textarea,a[href]')].filter(el=>el.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
  });

  const covers = document.getElementById('composeCovers');
  scenes.forEach(([id, title], index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'cover-pick' + (index === 0 ? ' is-selected' : '');
    button.setAttribute('aria-label', title);
    button.setAttribute('aria-pressed', String(index === 0));
    const image = document.createElement('img');
    image.src = '/assets/ui-selected-v3/' + id + '.webp';
    image.alt = '';
    image.loading = 'lazy';
    const label=document.createElement('span');label.textContent=title;button.append(image,label);
    button.addEventListener('click', () => {
      chosenScene = id;
      covers.querySelectorAll('button').forEach(item => {
        const active = item === button;
        item.classList.toggle('is-selected', active);
        item.setAttribute('aria-pressed', String(active));
      });
    });
    covers.append(button);
  });

  composeSubmit.addEventListener('click', async () => {
    const text = composeText.value.trim();
    if (!text) {
      composeStatus.textContent = '写下想分享的内容';
      composeText.focus();
      return;
    }
    composeSubmit.disabled = true;
    composeStatus.textContent = '正在发布…';
    try {
      const response = await fetch('/api/feed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, img: 'assets/ui-selected-v3/' + chosenScene + '.webp' })
      });
      if (!response.ok) throw new Error('publish failed');
      composeText.value = '';
      closeComposer();
      await load();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      composeStatus.textContent = '暂时无法发布，请稍后再试';
    } finally {
      composeSubmit.disabled = false;
    }
  });

  async function load() {
    try {
      const response = await fetch('/api/feed');
      if (!response.ok) throw new Error('feed failed');
      const result = await response.json();
      posts = Array.isArray(result.posts) ? result.posts : [];
      retryCount = 0;
      render();
    } catch {
      if (retryCount < 3) {
        retryCount += 1;
        feed.innerHTML = '<div class="community-empty">正在连接社区…</div>';
        setTimeout(load, 1100 * retryCount);
      } else {
        const empty = document.createElement('div');
        empty.className = 'community-empty';
        empty.textContent = '暂时无法读取动态。';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.textContent = '重试';
        retry.addEventListener('click', () => { retryCount = 0; load(); });
        empty.append(retry);
        feed.replaceChildren(empty);
      }
    }
  }

  const notice = document.createElement('div');
  notice.id = 'communityNotice';
  notice.className = 'community-notice';
  notice.setAttribute('role', 'status');
  notice.hidden = true;
  document.body.append(notice);
  load();
})();
