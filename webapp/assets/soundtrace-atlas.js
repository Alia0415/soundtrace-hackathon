(() => {
  'use strict';
  const scenes = [
    { id:'sea-window', name:'海港午后', color:'#52b5d3' },
    { id:'rainy-city', name:'雨夜城市', color:'#ae82d1' },
    { id:'autumn-lake', name:'秋日湖畔', color:'#d8a269' },
    { id:'snow-mountain', name:'雪山清晨', color:'#a7cce1' },
    { id:'spring-meadow', name:'春日花野', color:'#9aca9e' },
    { id:'desert-dusk', name:'沙漠黄昏', color:'#e2a083' },
  ];
  const atlas = document.getElementById('soundscapeAtlas');
  const signals = document.getElementById('atlasSignals');
  if (!atlas || !signals) return;
  const buttons = [];
  let selected = 0, rotation = 0, drag = null, suppressClickUntil = 0;

  function setScene(index) {
    selected = (index + scenes.length) % scenes.length;
    const scene = scenes[selected];
    atlas.style.setProperty('--atlas-accent', scene.color);
    document.getElementById('atlasImage').style.backgroundImage = `url('/assets/scenes-v1/${scene.id}.png')`;
    document.getElementById('atlasName').textContent = scene.name;
    document.getElementById('atlasNumber').textContent = `${String(selected + 1).padStart(2, '0')} / 06`;
    document.getElementById('atlasEnter').href = `/album?scene=${scene.id}`;
    buttons.forEach((button, i) => {
      button.classList.toggle('is-active', i === selected);
      button.setAttribute('aria-pressed', String(i === selected));
    });
  }
  function positionSignals() {
    const bounds = atlas.getBoundingClientRect();
    const radius = Math.min(bounds.width * (bounds.width < 760 ? .38 : .31), bounds.height * .38, 300);
    buttons.forEach((button, index) => {
      const angle = -Math.PI / 2 + index * 2 * Math.PI / scenes.length + rotation;
      button.style.left = `${bounds.width / 2 + Math.cos(angle) * radius}px`;
      button.style.top = `${bounds.height / 2 + Math.sin(angle) * radius}px`;
    });
  }
  function selectNearestTop() {
    let best = 0, distance = Infinity;
    for (let index = 0; index < scenes.length; index++) {
      const angle = -Math.PI / 2 + index * 2 * Math.PI / scenes.length + rotation;
      const delta = Math.atan2(Math.sin(angle + Math.PI / 2), Math.cos(angle + Math.PI / 2));
      if (Math.abs(delta) < distance) { best = index; distance = Math.abs(delta); }
    }
    setScene(best);
  }
  function setMode(mode) {
    const footprints = mode === 'footprint';
    document.body.classList.toggle('mode-atlas', !footprints);
    document.body.classList.toggle('mode-footprint', footprints);
    document.getElementById('atlasMode').setAttribute('aria-pressed', String(!footprints));
    document.getElementById('footprintMode').setAttribute('aria-pressed', String(footprints));
    document.getElementById('cnt').textContent = footprints ? `${typeof works !== 'undefined' ? works.length : 0} 个声音记忆` : '06 个声景频率';
    if (footprints && typeof geoMap !== 'undefined' && geoMap) requestAnimationFrame(() => geoMap.invalidateSize());
    if (!footprints && typeof stopAll === 'function') stopAll();
    if (!footprints) positionSignals();
  }
  scenes.forEach((scene, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'atlas-signal';
    button.setAttribute('aria-label', `选择${scene.name}`);
    const image = document.createElement('img');
    image.src = `/assets/scenes-v1/${scene.id}.png`;
    image.alt = '';
    image.loading = 'eager';
    const label = document.createElement('span'); label.textContent = scene.name;
    button.append(image, label);
    button.addEventListener('click', () => { if (performance.now() > suppressClickUntil) setScene(index); });
    signals.appendChild(button);
    buttons.push(button);
  });
  atlas.addEventListener('pointerdown', event => {
    if (event.target.closest('button,a')) return;
    drag = { id:event.pointerId, x:event.clientX, start:rotation, moved:false };
    atlas.setPointerCapture(event.pointerId);
  });
  atlas.addEventListener('pointermove', event => {
    if (!drag || drag.id !== event.pointerId) return;
    const shift = event.clientX - drag.x;
    if (Math.abs(shift) > 4) drag.moved = true;
    if (!drag.moved) return;
    rotation = drag.start + shift / Math.max(260, atlas.clientWidth) * Math.PI * 1.5;
    atlas.classList.add('is-dragging');
    positionSignals();
  });
  function finishDrag() {
    if (!drag) return;
    if (drag.moved) { suppressClickUntil = performance.now() + 250; selectNearestTop(); }
    drag = null;
    atlas.classList.remove('is-dragging');
  }
  atlas.addEventListener('pointerup', finishDrag);
  atlas.addEventListener('pointercancel', finishDrag);
  atlas.addEventListener('keydown', event => {
    if (event.target !== atlas || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    setScene(selected + (event.key === 'ArrowRight' ? 1 : -1));
  });
  document.getElementById('atlasMode').addEventListener('click', () => setMode('atlas'));
  document.getElementById('footprintMode').addEventListener('click', () => setMode('footprint'));
  window.addEventListener('resize', positionSignals);
  try {
    const stored = localStorage.getItem('soundtrace-room-scene');
    const index = scenes.findIndex(scene => scene.id === stored);
    if (index >= 0) selected = index;
  } catch (_) { /* storage may be unavailable */ }
  setScene(selected);
  setMode('atlas');
})();
