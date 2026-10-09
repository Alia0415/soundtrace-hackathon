(() => {
  'use strict';
  const nativeFetch = window.fetch.bind(window);
  let pendingLogin, resolveLogin, mode = 'login';
  const styles = document.createElement('style');
  styles.textContent = `
    .st-account-button{position:fixed;right:16px;top:16px;z-index:98;padding:9px 16px;min-height:42px;background:#fff;color:#155978;border:1px solid #8ed0ef;border-radius:999px;font:600 13px system-ui;cursor:pointer}
    .st-account-dialog{width:min(440px,calc(100% - 32px));max-height:85dvh;overflow:auto;padding:28px;border:1px solid #dcebf2;border-radius:20px;background:#fff;color:#173a50;font-family:system-ui;z-index:200}
    .st-account-dialog::backdrop{background:#153a5066;backdrop-filter:blur(4px)}.st-account-dialog a{color:#155978}
    .st-account-dialog h2{margin:0 36px 18px 0;font-size:23px}.st-account-dialog label{display:block;margin:14px 0;font-size:13px}.st-account-dialog input{display:block;width:100%;margin-top:7px;padding:12px;border:1px solid #aacddd!important;border-radius:10px;background:#fff!important;color:#173a50!important}
    .st-account-dialog button{cursor:pointer;min-height:42px;padding:9px 16px;border:1px solid #8ed0ef;border-radius:999px;background:#eef9ff;color:#155978;font:600 13px system-ui}.st-account-dialog button:disabled{opacity:.55;cursor:wait}.st-account-dialog .st-account-primary{background:#59bdf0;color:#073e59}.st-account-close{float:right}.st-account-error{min-height:24px;color:#a71d30;font-size:13px;white-space:pre-wrap}.st-account-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.st-account-row{padding:14px 0;border-bottom:1px solid #dcebf2}.st-account-row strong{display:block;margin-bottom:10px}.st-account-row button{margin-right:6px}.st-account-dialog :focus-visible{outline:2px solid #1599d7!important;outline-offset:3px}
    @media(max-width:600px){.st-account-button{top:10px;right:10px;padding:8px 12px;font-size:12px}}
  `;
  document.head.append(styles);
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'st-account-button'; button.textContent = '登录';
  const dialog = document.createElement('dialog');
  dialog.className = 'st-account-dialog'; dialog.setAttribute('aria-labelledby', 'stAccountTitle');
  document.body.append(button, dialog);
  function shell(title, surface = 'management') {
    dialog.dataset.surface = surface;
    dialog.replaceChildren();
    const close = document.createElement('button'); close.type = 'button'; close.className = 'st-account-close';
    close.textContent = '×'; close.setAttribute('aria-label', '关闭账号窗口'); close.onclick = () => dialog.close();
    const heading = document.createElement('h2'); heading.id = 'stAccountTitle'; heading.textContent = title;
    dialog.append(close, heading);
  }
  async function refresh() {
    const response = await nativeFetch('/api/auth/session');
    if (!response.ok) { button.hidden = true; return null; }
    const {user} = await response.json(); window.soundtraceUser = user;
    button.textContent = user ? user.name : '登录'; button.hidden = false;
    return user;
  }
  function field(form, name, label, type = 'text') {
    const item = document.createElement('label'); item.textContent = label;
    const input = document.createElement('input'); input.name = name; input.type = type; input.required = true;
    if (name === 'username') {input.autocomplete = 'username';input.maxLength = 32;input.pattern = '[A-Za-z0-9_]{3,32}';}
    if (type === 'password') {input.maxLength = 128;input.autocomplete = mode === 'login' ? 'current-password' : 'new-password';}
    if(type==='password') {
      const group=document.createElement('span');group.className='password-control';
      const reveal=document.createElement('button');reveal.type='button';reveal.className='password-reveal';reveal.textContent='◉';
      reveal.setAttribute('aria-label','显示密码');reveal.setAttribute('aria-pressed','false');
      reveal.onclick=()=>{const visible=input.type==='password';input.type=visible?'text':'password';reveal.setAttribute('aria-label',visible?'隐藏密码':'显示密码');reveal.setAttribute('aria-pressed',String(visible));};
      group.append(input,reveal);item.append(group);
    } else item.append(input);
    form.append(item); return input;
  }
  function loginForm() {
    shell(mode === 'login' ? '登录，\n听见生活。' : '创建账号，\n记录声音。', 'auth');
    dialog.dataset.mode=mode;
    const brand=window.SoundTraceArt?.create('brand','auth-brand');const illustration=window.SoundTraceArt?.create('auth-speaker','auth-illustration');if(brand)dialog.prepend(brand);if(illustration)dialog.append(illustration);
    const form = document.createElement('form');
    field(form, 'username', '账号 · 字母、数字或下划线');
    const password = field(form, 'password', mode === 'login' ? '密码' : '密码 · 至少 10 位', 'password');
    if (mode === 'register') password.minLength = 10;
    const error = document.createElement('p'); error.className = 'st-account-error'; error.setAttribute('role', 'alert');
    const actions = document.createElement('div'); actions.className = 'st-account-actions';
    const submit = document.createElement('button'); submit.type = 'submit'; submit.className = 'st-account-primary'; submit.textContent = mode === 'login' ? '登录' : '注册并登录';
    const toggle = document.createElement('button'); toggle.type = 'button'; toggle.textContent = mode === 'login' ? '创建账号' : '已有账号';
    toggle.onclick = () => {mode = mode === 'login' ? 'register' : 'login'; loginForm();};
    actions.append(submit, toggle); form.append(error, actions); dialog.append(form);
    form.onsubmit = async event => {
      event.preventDefault(); submit.disabled = true; error.textContent = '';
      try {
        const response = await nativeFetch('/api/auth/' + mode, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
        const result = await response.json(); if (!response.ok) throw new Error(result.detail || '登录失败');
        await refresh(); resolveLogin?.(true); resolveLogin = null; dialog.close();
        window.dispatchEvent(new Event('soundtrace-login'));
      } catch (e) { error.textContent = e.message; } finally {submit.disabled = false;}
    };
  }
  function requireLogin() {
    if (pendingLogin) return pendingLogin;
    mode = 'login'; loginForm(); dialog.showModal();
    pendingLogin = new Promise(resolve => {resolveLogin = resolve;}).finally(() => {pendingLogin = null;});
    return pendingLogin;
  }
  dialog.addEventListener('close', () => {resolveLogin?.(false); resolveLogin = null;});
  window.fetch = async (input, options) => {
    const target = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, location.href);
    // Clone before sending so a saved recording can be retried after signing in.
    const request = new Request(input, options), retry = request.clone();
    const response = await nativeFetch(request);
    if (response.status !== 401 || target.origin !== location.origin || !target.pathname.startsWith('/api/') || target.pathname.startsWith('/api/auth/')) return response;
    if (await requireLogin()) return nativeFetch(retry);
    return response;
  };
  async function accountPanel() {
    shell('你的声音档案', 'management');
    const intro = document.createElement('p'); intro.className = 'st-account-intro'; intro.textContent = '管理个人资料，整理值得留下的声音。'; dialog.append(intro);
    const actions = document.createElement('div'); actions.className = 'st-account-actions';
    const profile = document.createElement('a'); profile.href = '/album?profile=1'; profile.textContent = '编辑个人资料';
    const logout = document.createElement('button'); logout.textContent = '退出登录';
    logout.onclick = async () => {await nativeFetch('/api/auth/logout', {method:'POST'});localStorage.removeItem('soundtrace_likes');location.reload();};
    const change = document.createElement('button'); change.textContent = '修改密码'; change.onclick = passwordForm;
    actions.append(profile, change, logout); dialog.append(actions);
    const section = document.createElement('h3'); section.className = 'st-account-section'; section.textContent = '我的声音'; dialog.append(section);
    const list = document.createElement('div'); list.className = 'st-account-list'; list.textContent = '正在读取记忆…'; dialog.append(list);
    const source = document.createElement('a');source.href='/source';source.textContent='开源源码与许可 ↗';source.className='st-account-source';dialog.append(source);
    if (!dialog.open) dialog.showModal();
    try {
      const result = await window.fetch('/api/memories').then(r => r.json()); list.replaceChildren();
      if (!result.memories?.length) list.textContent = '录下第一段声音，它会保存在这里。';
      for (const memory of result.memories || []) {
        const row = document.createElement('div'); row.className = 'st-account-row';
        const title = document.createElement('strong'); title.textContent = memory.title;
        const publish = document.createElement('button'); publish.textContent = '发布到社区';
        const remove = document.createElement('button'); remove.textContent = '删除'; remove.className = 'st-account-remove'; remove.setAttribute('aria-label', '删除记忆：' + memory.title);
        const status = document.createElement('p'); status.setAttribute('role', 'status');
        publish.onclick = async () => {
          publish.disabled = true;
          try {const r = await window.fetch(`/api/memories/${memory.id}/publish`, {method:'POST'});const value = await r.json();if(!r.ok)throw new Error(value.detail);status.textContent = '已发布到社区';}
          catch(e){status.textContent = e.message;}finally{publish.disabled = false;}
        };
        remove.onclick = async () => {
          if (!await confirmMemoryDeletion(memory.title)) return;
          remove.disabled = true;
          try {const r = await window.fetch(`/api/memories/${memory.id}`, {method:'DELETE'});if(!r.ok)throw new Error('删除失败');row.remove();window.dispatchEvent(new Event('soundtrace-content-change'));}
          catch(e){status.textContent = e.message;remove.disabled = false;}
        };
        const controls = document.createElement('div'); controls.className = 'st-account-row-actions'; controls.append(publish, remove);
        row.append(title, controls, status); list.append(row);
      }
    } catch { list.textContent = '暂时无法读取记忆，请重新打开。'; }
  }
  function passwordForm() {
    shell('修改密码', 'password'); mode = 'password';
    const illustration=window.SoundTraceArt?.create('password-art','password-illustration');if(illustration)dialog.append(illustration);
    const form = document.createElement('form');field(form, 'current_password', '当前密码', 'password').autocomplete = 'current-password';
    field(form, 'password', '新密码 · 至少 10 位', 'password').minLength = 10;
    const error = document.createElement('p');error.className = 'st-account-error';error.setAttribute('role', 'alert');
    const submit = document.createElement('button');submit.textContent = '保存新密码';submit.type = 'submit';submit.className='st-account-primary';form.append(error, submit);dialog.append(form);
    form.onsubmit = async e => {e.preventDefault();submit.disabled=true;try{const r=await window.fetch('/api/auth/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});const value=await r.json();if(!r.ok)throw new Error(value.detail);await refresh();dialog.close();}catch(e){error.textContent=e.message;}finally{submit.disabled=false;}};
  }
  function confirmMemoryDeletion(title, detail) {
    return new Promise(resolve=>{
      const confirmation=document.createElement('dialog');confirmation.className='st-account-dialog st-delete-dialog';
      const heading=document.createElement('h2');heading.textContent=detail?'删除这条动态？':'删除这段记忆？';
      const text=document.createElement('p');text.textContent=detail||('「'+title+'」及原声、音乐和已发布动态会一起删除。');
      const actions=document.createElement('div');actions.className='st-account-actions';
      const cancel=document.createElement('button');cancel.type='button';cancel.textContent='取消';
      const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent='确认删除';
      const finish=value=>{confirmation.close();confirmation.remove();resolve(value);};
      cancel.onclick=()=>finish(false);remove.onclick=()=>finish(true);
      confirmation.oncancel=e=>{e.preventDefault();finish(false);};
      actions.append(cancel,remove);const art=window.SoundTraceArt?.create('delete-art','delete-illustration');if(art)confirmation.append(art);confirmation.append(heading,text,actions);document.body.append(confirmation);confirmation.showModal();cancel.focus();
    });
  }
  window.soundtraceConfirmDeletion=confirmMemoryDeletion;
  button.onclick = () => window.soundtraceUser ? accountPanel() : requireLogin().then(ok => {if(ok)location.reload();});
  window.soundtraceAccountReady = refresh().catch(() => {button.hidden = true;return null;});
})();
