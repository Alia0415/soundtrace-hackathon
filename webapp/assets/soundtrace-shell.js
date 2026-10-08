(() => {
  'use strict';
  const pathname=location.pathname.replace(/^\/demo(?=\/|$)/,'')||'/';
  const page = pathname === '/studio' ? 'studio' : pathname === '/album' ? 'album' : pathname === '/community' ? 'community' : pathname === '/map' ? 'map' : 'home';
  document.body.dataset.stPage = page;
  // 我的=收藏间（功能合并页）；记录页经首页”录一段声音”进入，导航位由声音地图接替
  const links = [
    ['/', '<path d="m3 10 9-7 9 7v10H3zM9 20v-7h6v7"/>', '此刻', 'home'],
    ['/map', '<path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11Z"/><circle cx="12" cy="10" r="2.5"/>', '声音地图', 'map'],
    ['/community', '<path d="M21 11a8 8 0 0 1-8 8H7l-5 3 2-6a8 8 0 1 1 17-5Z"/><path d="M8 10h8M8 14h5"/>', '社区', 'community'],
    ['/album', '<path d="M4 5h16v15H4zM7 2h10M8 9h8M8 13h5"/>', '我的', 'album'],
  ];
  const dock = document.createElement('nav');
  dock.className = 'st-dock';
  dock.setAttribute('aria-label', '声迹主导航');
  links.forEach(([href, icon, label, key]) => {
    const link = document.createElement('a');
    link.href = href;
    link.innerHTML = `<span class="st-dock-icon" aria-hidden="true"><img src="/assets/ui-selected-v3/nav-${key}.webp" alt="" draggable="false"></span><span>${label}</span>`;
    if (page === key || (page === 'studio' && key === 'home')) link.setAttribute('aria-current', 'page');
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
