(() => {
  'use strict';
  const pathname=location.pathname.replace(/^\/demo(?=\/|$)/,'')||'/';
  const page = ['/studio','/capture','/library'].includes(pathname) ? 'studio' : pathname === '/album' ? 'album' : pathname === '/community' ? 'community' : pathname === '/map' ? 'map' : 'home';
  document.body.dataset.stPage = page;
  const demo = /^\/demo(?:\/|$)/.test(location.pathname);
  const modeBar = document.createElement('aside');
  modeBar.className = 'st-mode-bar';
  modeBar.setAttribute('aria-label', '体验模式');
  const destination = new URL(location.href);
  destination.pathname = demo ? pathname : '/demo' + (pathname === '/' ? '' : pathname);
  // Record IDs and playback instructions belong to their own data space.
  ['memory', 'listen', 'demo'].forEach(key => destination.searchParams.delete(key));
  modeBar.innerHTML = `<span><strong>${demo ? '示例模式' : '正式模式'}</strong><small>${demo ? '预置声音与音乐日记 · 修改仅保存在本机' : '先用示例声音，体验一段完整的音乐日记'}</small></span><a data-real-site>${demo ? '返回正式模式' : '切换到示例模式'} ↗</a>`;
  modeBar.querySelector('a').href = destination.pathname + destination.search + destination.hash;
  document.body.prepend(modeBar);
  const modeStyle = document.createElement('style');
  modeStyle.textContent = '.st-mode-bar{position:relative;z-index:98;box-sizing:border-box;width:100%;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 5%;background:#eef8fb;border-bottom:1px solid #d3e7ed;color:#17657f;font:13px/1.5 system-ui;flex:none}.st-mode-bar>span{display:flex;align-items:center;gap:14px}.st-mode-bar small{font-size:12px}.st-mode-bar>a{flex:none;color:#096c91;text-decoration:none;border:1px solid #a8ccd9;border-radius:20px;padding:6px 12px;background:white}.st-mode-bar a:focus-visible{outline:2px solid #087fab;outline-offset:3px}.st-mode-bar .demo-mode-strip{position:relative;left:auto;top:auto;z-index:99}.st-mode-bar .demo-mode-strip>div{left:auto;right:0}.st-mode-bar .demo-mode-strip summary{min-height:0;padding:6px}.st-mode-bar:has(.demo-mode-strip)>span{margin-right:auto}@media(max-width:600px){.st-mode-bar{padding:8px 12px;font-size:12px;gap:8px}.st-mode-bar>span{display:block}.st-mode-bar small{display:none}.st-mode-bar>a{padding:5px 9px}}';
  document.head.append(modeStyle);
  modeStyle.textContent += 'body>.st-account-button{top:76px!important}@media(min-width:761px){body>.st-dock{top:76px!important}}';
  // 创作是核心入口；声音地图仍可从首页探索区域进入。
  const links = [
    ['/', '<path d="m3 10 9-7 9 7v10H3zM9 20v-7h6v7"/>', '首页', 'home'],
    ['/studio', '<path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11Z"/><circle cx="12" cy="10" r="2.5"/>', '创作音乐', 'studio'],
    ['/community', '<path d="M21 11a8 8 0 0 1-8 8H7l-5 3 2-6a8 8 0 1 1 17-5Z"/><path d="M8 10h8M8 14h5"/>', '社区', 'community'],
    ['/album', '<path d="M4 5h16v15H4zM7 2h10M8 9h8M8 13h5"/>', '我的音乐', 'album'],
  ];
  const dock = document.createElement('nav');
  dock.className = 'st-dock';
  dock.setAttribute('aria-label', '声迹主导航');
  links.forEach(([href, icon, label, key]) => {
    const link = document.createElement('a');
    link.href = href;
    link.innerHTML = `<span class="st-dock-icon" aria-hidden="true"><img src="/assets/ui-selected-v3/nav-${key === 'studio' ? 'home' : key}.webp" alt="" draggable="false"></span><span>${label}</span>`;
    if (page === key) link.setAttribute('aria-current', 'page');
    dock.appendChild(link);
  });
  const navigationHost = ['map','community'].includes(page) ? document.querySelector('.doodle-header') : null;
  (navigationHost || document.body).appendChild(dock);
  // 滑动指示条：量测当前项位置，随窗口尺寸重算
  const indicator = document.createElement('span');
  indicator.className = 'st-dock-indicator';
  dock.appendChild(indicator);
  const moveIndicator = () => {
    const current = dock.querySelector('a[aria-current=page]');
    if (!current) { indicator.style.opacity = '0'; return; }
    indicator.style.opacity = '1';
    indicator.style.left = `${current.offsetLeft}px`;
    indicator.style.width = `${current.offsetWidth}px`;
  };
  window.addEventListener('resize', moveIndicator);
  requestAnimationFrame(() => setTimeout(moveIndicator, 60));
  // The legacy modal surfaces share keyboard focus behavior with native dialogs.
  const surfaces=['saveMask','modalBackdrop','listeningStage'];
  let previousFocus=null,activeSurface=null;
  const observe=()=>{
    const current=surfaces.map(id=>document.getElementById(id)).find(el=>el&&!el.hidden&&getComputedStyle(el).display!=='none');
    if(current!==activeSurface){
      if(current){previousFocus=document.activeElement;activeSurface=current;const card=current.querySelector('.save-card,.modal')||current;card.setAttribute('role','dialog');card.setAttribute('aria-modal','true');card.querySelector('button,input,[tabindex="0"]')?.focus();}
      else{activeSurface=null;previousFocus?.isConnected&&previousFocus.focus();}
    }
  };
  new MutationObserver(observe).observe(document.body,{subtree:true,attributes:true,attributeFilter:['hidden']});
  document.addEventListener('keydown',event=>{
    if(!activeSurface||document.querySelector('dialog[open]'))return;
    if(event.key==='Escape'&&activeSurface.id==='saveMask'){
      const saving=document.getElementById('saveGo')?.disabled;
      if(!saving){activeSurface.hidden=true;event.preventDefault();}return;
    }
    if(event.key!=='Tab')return;
    const items=[...activeSurface.querySelectorAll('a[href],button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),[tabindex="0"]')].filter(el=>el.getClientRects().length&&!el.hidden);
    if(!items.length)return;
    if(event.shiftKey&&document.activeElement===items[0]){event.preventDefault();items.at(-1).focus();}
    else if(!event.shiftKey&&document.activeElement===items.at(-1)){event.preventDefault();items[0].focus();}
  });
})();
