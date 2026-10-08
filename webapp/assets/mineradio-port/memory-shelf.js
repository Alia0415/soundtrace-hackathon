/*
 * SoundTrace fork of Mineradio's PSP shelf.
 * Source: public/js/modules/04-shelf/00-layout-hover.js,
 *         public/js/modules/04-shelf/01-manager-core.js,
 *         public/js/modules/04-shelf/05-card-interactions.js
 * Commit: d43de565acabfdc1a9c9820a27e81a98ccbebcef
 * Copyright (C) Mineradio contributors and SoundTrace contributors.
 * SPDX-License-Identifier: GPL-3.0-only
 * Changes: retained rendered-window management, PSP arc placement, summon
 * stagger, eased scrolling, hover lift and raycast interaction; replaced
 * card frames with frameless SoundTrace art, music-provider globals with
 * SoundTrace memories, and adapted coordinates to a right-side shelf.
 */
(function () {
  'use strict';

  window.createSoundTraceMineRadioShelf = function (host, onSelect) {
    if (!host || !window.THREE) return null;
    var THREE = window.THREE;
    var renderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true, powerPreference:'low-power' });
    } catch (_) { return null; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    renderer.domElement.className = 'stage-shelf-canvas';
    host.querySelector('.stage-shelf-viewport').appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(42, 1, .1, 30);
    camera.position.z = 5.9;
    var group = new THREE.Group();
    scene.add(group);
    var cards = [];
    var allItems = [], sourceItems = [];
    var renderedStart = -1;
    var SHELF_VISIBLE_RADIUS = 5;
    var SHELF_MAX_RENDER = SHELF_VISIBLE_RADIUS * 2 + 1;
    var centerTarget = 0, centerSmooth = 0, activeSourceIndex = 0;
    var selectedIdx = -1, shelfOpenAnimAt = -10, paneSwitchAt = -10, paneSwitchDir = 1;
    var lastCardRedrawAt = -10, lastCardPulseBucket = -1;
    var pointerParallax = { x:0, y:0, targetX:0, targetY:0 };
    var audio = { bass:0, beat:0 };
    var imageCache = Object.create(null);
    var raycaster = new THREE.Raycaster();
    var pointer = new THREE.Vector2();
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    var filter = 'all', running = false, frame = 0, previousTime = 0, drag = null, suppressClick = false;
    var counter = host.querySelector('[data-shelf-count]');
    var typeLabel = host.querySelector('[data-shelf-type]');
    var tabs = Array.from(host.querySelectorAll('[data-memory-filter]'));
    var previousButton = host.querySelector('[data-shelf-prev]');
    var nextButton = host.querySelector('[data-shelf-next]');

    function clampRange(value, min, max) { return Math.max(min, Math.min(max, value)); }
    function smoothstep(value) { return value * value * (3 - 2 * value); }
    function now() { return performance.now() * .001; }
    function accent() {
      return getComputedStyle(document.getElementById('listeningStage')).getPropertyValue('--stage-accent').trim() || '#8acfd6';
    }
    function makeRoundRect(ctx, x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
    }
    function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines) {
      var chars = String(text || '').split('');
      var line = '', lines = [];
      for (var i = 0; i < chars.length; i++) {
        var test = line + chars[i];
        if (ctx.measureText(test).width > maxWidth && line) {
          lines.push(line); line = chars[i];
          if (lines.length >= maxLines - 1) break;
        } else line = test;
      }
      if (line && lines.length < maxLines) lines.push(line);
      for (var j = 0; j < lines.length; j++) ctx.fillText(lines[j], x, y + j * lineHeight);
    }
    function coverRecord(url) {
      if (!url) return null;
      if (imageCache[url]) return imageCache[url];
      var record = { img:new Image(), loaded:false, failed:false };
      imageCache[url] = record;
      record.img.onload = function () {
        record.loaded = true;
        cards.forEach(function (card) { if (card.item.cover === url) { card.drawKey = ''; drawCard(card, card.item); } });
        render();
      };
      record.img.onerror = function () { record.failed = true; };
      record.img.src = url;
      return record;
    }
    function cardDrawSignature(card, item) {
      var rec = item.cover ? imageCache[item.cover] : null;
      var coverState = item.cover ? (rec && rec.loaded ? 'ready' : (rec && rec.failed ? 'fail' : 'wait')) : 'none';
      var pulseBucket = card.isCenter ? Math.round((audio.bass + audio.beat * .85) * 6) : 0;
      return [item.kind, item.title, item.sub, item.cover, coverState, card.isCenter ? 1 : 0,
        card.selected ? 1 : 0, card.dofBucket, pulseBucket, activeSourceIndex, accent()].join('|');
    }
    function drawCard(card, item) {
      item = item || card.item || {};
      var nextDrawKey = cardDrawSignature(card, item);
      if (card.drawKey === nextDrawKey) return;
      card.drawKey = nextDrawKey;
      var cv = card.canvas, ctx = card.ctx;
      var W = cv.width, H = cv.height;
      ctx.clearRect(0, 0, W, H);
      var isNow = item.sourceIndex === activeSourceIndex;
      var rec = coverRecord(item.cover);
      if (rec && rec.loaded && rec.img.naturalWidth) {
        ctx.save();
        ctx.shadowColor = accent();
        ctx.shadowBlur = card.isCenter ? 24 + audio.bass * 25 : 0;
        var ratio = Math.min((W - 38) / rec.img.naturalWidth, (H - 28) / rec.img.naturalHeight);
        var iw = rec.img.naturalWidth * ratio, ih = rec.img.naturalHeight * ratio;
        ctx.drawImage(rec.img, (W - iw) / 2, (H - ih) / 2, iw, ih);
        ctx.restore();
      } else {
        ctx.strokeStyle = 'rgba(194,235,223,0.55)';
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(W / 2, H / 2, 34, 0, Math.PI * 2); ctx.stroke();
      }
      if (card.isCenter) {
        ctx.strokeStyle = accent();
        ctx.lineWidth = 3 + audio.bass * 2;
        ctx.beginPath(); ctx.moveTo(W * .42, H - 9); ctx.lineTo(W * .58, H - 9); ctx.stroke();
      }
      if (card.dofBlur > .12) {
        ctx.fillStyle = 'rgba(0,0,0,' + Math.min(.28, card.dofBlur * .18).toFixed(3) + ')'; ctx.fillRect(0, 0, W, H);
      }
      card.texture.needsUpdate = true;
    }
    function buildOneCard(item, i) {
      var cv = document.createElement('canvas');
      cv.width = 720; cv.height = 360;
      var ctx = cv.getContext('2d');
      var tx = new THREE.CanvasTexture(cv);
      tx.minFilter = THREE.LinearFilter; tx.magFilter = THREE.LinearFilter;
      tx.generateMipmaps = false;
      var mat = new THREE.MeshBasicMaterial({ map:tx, transparent:true, opacity:.96, depthWrite:false, depthTest:false, side:THREE.DoubleSide });
      var geo = new THREE.PlaneGeometry(2.05, 1.025, 1, 1);
      var mesh = new THREE.Mesh(geo, mat);
      mesh.renderOrder = 50 + i;
      mesh.userData.index = i;
      group.add(mesh);
      var card = { canvas:cv, ctx:ctx, texture:tx, mesh:mesh, item:item, index:i,
        isCenter:false, selected:false, floatMix:0, fxPulse:0, dofBlur:0, dofBucket:-1, drawKey:'' };
      drawCard(card, item);
      return card;
    }
    function rebindShelfCard(card, item, index) {
      card.item = item; card.index = index; card.selected = index === selectedIdx;
      card.isCenter = Math.abs(index - centerSmooth) < .5;
      card.drawKey = ''; card.mesh.userData.index = index; card.mesh.renderOrder = 50 + index;
      drawCard(card, item);
      return card;
    }
    function disposeShelfCard(card) {
      if (card.mesh.parent) card.mesh.parent.remove(card.mesh);
      card.texture.dispose(); card.mesh.material.dispose(); card.mesh.geometry.dispose();
    }
    function disposeRenderedCards() {
      cards.forEach(disposeShelfCard); cards = []; renderedStart = -1;
    }
    function syncRenderedWindow(force) {
      var total = allItems.length;
      if (!total) { disposeRenderedCards(); return; }
      var center = Math.round(centerTarget);
      var start = Math.max(0, center - SHELF_VISIBLE_RADIUS);
      var end = Math.min(total - 1, start + SHELF_MAX_RENDER - 1);
      start = Math.max(0, end - SHELF_MAX_RENDER + 1);
      if (!force && start === renderedStart && cards.length === end - start + 1) return;
      renderedStart = start;
      var existingByIndex = Object.create(null);
      cards.forEach(function (card) { existingByIndex[card.index] = card; });
      var reusable = cards.filter(function (card) { return card.index < start || card.index > end; });
      var nextCards = [];
      for (var itemIdx = start; itemIdx <= end; itemIdx++) {
        var card = existingByIndex[itemIdx] || reusable.shift();
        if (!card) card = buildOneCard(allItems[itemIdx], itemIdx);
        else rebindShelfCard(card, allItems[itemIdx], itemIdx);
        nextCards.push(card);
      }
      reusable.forEach(disposeShelfCard);
      cards = nextCards;
    }
    function updateUi() {
      var item = allItems[Math.round(centerTarget)];
      if (counter) counter.textContent = item ? String(Math.round(centerTarget) + 1).padStart(2, '0') + ' / ' + String(allItems.length).padStart(2, '0') : '00 / 00';
      if (typeLabel) typeLabel.textContent = item ? (item.tag || '声音藏品') : '暂无声音藏品';
      if (previousButton) previousButton.disabled = centerTarget <= 0;
      if (nextButton) nextButton.disabled = centerTarget >= allItems.length - 1;
    }
    function applySelectedIndex(idx) {
      selectedIdx = idx == null || idx < 0 ? -1 : Math.round(idx);
      cards.forEach(function (card) {
        var next = card.index === selectedIdx;
        if (card.selected !== next) { card.selected = next; card.drawKey = ''; drawCard(card, card.item); }
      });
    }
    function step(direction) {
      if (!allItems.length) return;
      var previous = Math.round(centerTarget);
      centerTarget = clampRange(centerTarget + direction, 0, allItems.length - 1);
      var next = Math.round(centerTarget);
      syncRenderedWindow(false);
      applySelectedIndex(next);
      if (next !== previous) {
        var card = cards.find(function (candidate) { return candidate.index === next; });
        if (card) card.fxPulse = Math.max(card.fxPulse, .55);
      }
      updateUi();
      render();
    }
    function shelfLayoutProfile() {
      var compact = host.clientHeight < 500;
      return { sideX:.03, sideY:0, sideXStep:.20, sideYStep:compact ? .68 : .83,
        sideZ:.84, sideZStep:.12, sideEntryX:.82, sideScale:compact ? 1.10 : 1.25,
        sideRotY:.28, sideRotX:.042 };
    }
    // Port of MineRadio's placeCard: side shelf arc, staggered summon, depth,
    // pointer parallax, hover foreground lift, per-card pulse and DOF fading.
    function placeCard(card) {
      var delta = card.index - centerSmooth;
      var absD = Math.abs(delta);
      if (absD > SHELF_VISIBLE_RADIUS + .5) { card.mesh.visible = false; return; }
      card.mesh.visible = true;
      var layout = shelfLayoutProfile();
      var parX = pointerParallax.x, parY = pointerParallax.y;
      var parWeight = Math.max(0, 1 - absD * .16);
      var pulse = card.fxPulse || 0;
      var nextDof = clampRange((absD - .45) / 3.2, 0, 1);
      var nextDofBucket = Math.round(nextDof * 5);
      if (card.dofBucket !== nextDofBucket) {
        card.dofBucket = nextDofBucket; card.dofBlur = nextDof; card.drawKey = ''; drawCard(card, card.item);
      }
      var liftTarget = card.selected ? 1 : 0;
      var liftRate = liftTarget > card.floatMix ? .20 : .13;
      card.floatMix += (liftTarget - card.floatMix) * liftRate;
      if (!liftTarget && card.floatMix < .004) card.floatMix = 0;
      var lift = card.floatMix;
      var sideLayer = Math.max(0, SHELF_VISIBLE_RADIUS + 1 - Math.min(absD, SHELF_VISIBLE_RADIUS + 1));
      card.mesh.renderOrder = 60 + Math.round(sideLayer * 10) + Math.round(lift * 70);
      var elapsed = now();
      var breathPulse = .5 + .5 * Math.sin(elapsed * 1.22 + card.index * .74);
      var revealRaw = clampRange((elapsed - shelfOpenAnimAt - absD * .045) / .82, 0, 1);
      var reveal = reduced.matches ? 1 : smoothstep(revealRaw);
      var entry = (1 - reveal) * (.82 + absD * .075);
      var paneRaw = clampRange((elapsed - paneSwitchAt - absD * .030) / .72, 0, 1);
      var paneEase = reduced.matches ? 0 : 1 - smoothstep(paneRaw);
      var px = layout.sideX + absD * layout.sideXStep + entry * layout.sideEntryX;
      var py = layout.sideY - delta * layout.sideYStep + (1 - reveal) * (delta < 0 ? -.18 : .18);
      var pz = layout.sideZ - absD * layout.sideZStep - (1 - reveal) * .20;
      px += paneEase * paneSwitchDir * .60;
      py += paneEase * (delta < 0 ? -.16 : .16);
      pz -= paneEase * .22;
      px += parX * .060 * parWeight;
      py += parY * .046 * parWeight;
      pz += (parY * .026 - parX * .028) * parWeight;
      if (!reduced.matches) {
        py += Math.sin(elapsed * .92 + card.index * .64) * .035 * Math.max(.20, parWeight);
        pz += Math.cos(elapsed * .78 + card.index * .52) * .024 * parWeight;
      }
      px -= lift * .145; py += lift * .105; pz += lift * .220;
      var scale = (absD < .5 ? 1.12 : Math.max(.60, 1.04 - absD * .11))
        * (1 - (1 - reveal) * .12) * (1 + pulse * .056 + breathPulse * .014 + lift * .075) * layout.sideScale;
      card.mesh.position.set(px, py, pz);
      card.mesh.rotation.y = layout.sideRotY + (1 - reveal) * .16 + parX * .038 * parWeight;
      card.mesh.rotation.x = -delta * layout.sideRotX - parY * .024 * parWeight;
      card.mesh.scale.setScalar(scale);
      var opacity = absD < .5 ? 1 : Math.max(.29, 1 - absD * .24);
      card.mesh.material.opacity = Math.min(1, opacity * reveal * (1 - paneEase * .24) + pulse * .10 * reveal + breathPulse * .018);
      var isCenter = absD < .5;
      if (card.isCenter !== isCenter) { card.isCenter = isCenter; card.drawKey = ''; drawCard(card, card.item); }
      card.fxPulse *= .91;
    }
    function render() {
      if (!renderer) return;
      var startBalance = Math.max(0, 1 - centerSmooth) * .62;
      var endBalance = Math.max(0, centerSmooth - (allItems.length - 2)) * .62;
      group.position.y += (startBalance - endBalance - group.position.y) * (reduced.matches ? 1 : .08);
      group.rotation.y = pointerParallax.x * .018;
      group.rotation.x = -pointerParallax.y * .010;
      cards.forEach(placeCard);
      renderer.render(scene, camera);
    }
    function tick() {
      if (!running) return;
      var time = performance.now();
      var dt = Math.min(.05, (time - previousTime) / 1000 || .016);
      previousTime = time;
      var easing = reduced.matches ? 1 : 1 - Math.pow(1 - .16, dt * 60);
      centerSmooth += (centerTarget - centerSmooth) * easing;
      if (Math.abs(centerSmooth - centerTarget) < .001) centerSmooth = centerTarget;
      pointerParallax.x += (pointerParallax.targetX - pointerParallax.x) * .04;
      pointerParallax.y += (pointerParallax.targetY - pointerParallax.y) * .04;
      var pulseBucket = Math.round((audio.bass + audio.beat * .85) * 10);
      if (pulseBucket !== lastCardPulseBucket || time / 1000 - lastCardRedrawAt > 1.35) {
        lastCardPulseBucket = pulseBucket; lastCardRedrawAt = time / 1000;
        cards.forEach(function (card) { if (card.isCenter) drawCard(card, card.item); });
      }
      render();
      if (!reduced.matches) frame = requestAnimationFrame(tick);
    }
    function resize() {
      var viewport = host.querySelector('.stage-shelf-viewport');
      var width = Math.max(1, viewport.clientWidth), height = Math.max(1, viewport.clientHeight);
      camera.aspect = width / height; camera.updateProjectionMatrix();
      renderer.setSize(width, height, false); render();
    }
    function hitFromPointer(event) {
      var bounds = renderer.domElement.getBoundingClientRect();
      pointer.x = (event.clientX - bounds.left) / bounds.width * 2 - 1;
      pointer.y = -(event.clientY - bounds.top) / bounds.height * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      var hits = raycaster.intersectObjects(cards.filter(function (card) { return card.mesh.visible; }).map(function (card) { return card.mesh; }), false);
      if (!hits.length) return null;
      return cards.find(function (card) { return card.mesh === hits[0].object; }) || null;
    }
    function onPointerMove(event) {
      var bounds = renderer.domElement.getBoundingClientRect();
      pointerParallax.targetX = clampRange((event.clientX - bounds.left) / bounds.width * 2 - 1, -1, 1);
      pointerParallax.targetY = clampRange(1 - (event.clientY - bounds.top) / bounds.height * 2, -1, 1);
      if (drag && Math.abs(event.clientY - drag.y) > 12) {
        drag.moved = true; renderer.domElement.classList.add('is-dragging');
      }
      if (!drag || !drag.moved) {
        var hit = hitFromPointer(event);
        applySelectedIndex(hit ? hit.index : -1);
      }
      if (reduced.matches) render();
    }
    function onPointerDown(event) {
      drag = { x:event.clientX, y:event.clientY, moved:false };
      renderer.domElement.setPointerCapture(event.pointerId);
    }
    function onPointerUp(event) {
      if (!drag) return;
      var distance = event.clientY - drag.y;
      if (drag.moved) {
        suppressClick = true;
        step((distance > 0 ? -1 : 1) * Math.max(1, Math.min(3, Math.round(Math.abs(distance) / 95))));
      }
      drag = null;
      renderer.domElement.classList.remove('is-dragging');
    }
    function onClick(event) {
      if (suppressClick) { suppressClick = false; return; }
      var card = hitFromPointer(event);
      if (!card) return;
      if (Math.abs(card.index - centerSmooth) < .5) {
        card.fxPulse = 1;
        if (typeof onSelect === 'function') onSelect(card.item.sourceIndex);
      } else step(card.index - Math.round(centerTarget));
    }
    function onWheel(event) {
      if (!allItems.length) return;
      event.preventDefault();
      step(event.deltaY > 0 ? 1 : -1);
    }
    function onLeave() {
      pointerParallax.targetX = pointerParallax.targetY = 0;
      applySelectedIndex(-1);
      if (reduced.matches) render();
    }
    function setFilter(next) {
      if (next === filter) return;
      paneSwitchDir = next === 'all' ? -1 : 1;
      paneSwitchAt = now();
      filter = next;
      allItems = sourceItems.filter(function (item) { return filter === 'all' || item.kind === filter; });
      var selected = allItems.findIndex(function (item) { return item.sourceIndex === activeSourceIndex; });
      centerTarget = Math.max(0, selected);
      centerSmooth = centerTarget + (reduced.matches ? 0 : paneSwitchDir * 1.5);
      disposeRenderedCards(); syncRenderedWindow(true);
      tabs.forEach(function (tab) {
        var active = tab.dataset.memoryFilter === filter;
        tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active));
      });
      updateUi(); render();
    }
    function setItems(next) {
      sourceItems = (Array.isArray(next) ? next : []).map(function (item, index) {
        return Object.assign({}, item, { sourceIndex:index });
      });
      imageCache = Object.create(null);
      allItems = sourceItems.filter(function (item) { return filter === 'all' || item.kind === filter; });
      centerTarget = Math.max(0, allItems.findIndex(function (item) { return item.sourceIndex === activeSourceIndex; }));
      centerSmooth = centerTarget;
      disposeRenderedCards(); syncRenderedWindow(true);
      shelfOpenAnimAt = now(); updateUi(); render();
    }
    function setActive(sourceIndex) {
      activeSourceIndex = Math.max(0, Math.min(sourceItems.length - 1, sourceIndex));
      var next = allItems.findIndex(function (item) { return item.sourceIndex === activeSourceIndex; });
      if (next < 0) { setFilter('all'); next = activeSourceIndex; }
      centerTarget = Math.max(0, next);
      syncRenderedWindow(false);
      cards.forEach(function (card) { card.drawKey = ''; drawCard(card, card.item); });
      updateUi(); render();
    }
    function onReducedChange() { if (running) tick(); }
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('pointerup', onPointerUp);
    renderer.domElement.addEventListener('pointercancel', onPointerUp);
    renderer.domElement.addEventListener('pointerleave', onLeave);
    renderer.domElement.addEventListener('click', onClick);
    renderer.domElement.addEventListener('wheel', onWheel, { passive:false });
    if (previousButton) previousButton.addEventListener('click', function () { step(-1); });
    if (nextButton) nextButton.addEventListener('click', function () { step(1); });
    tabs.forEach(function (tab) { tab.addEventListener('click', function () { setFilter(tab.dataset.memoryFilter); }); });
    reduced.addEventListener('change', onReducedChange);
    var observer = new ResizeObserver(resize); observer.observe(host);
    resize(); updateUi();

    return {
      setItems:setItems,
      setActive:setActive,
      setAudioResponse:function (response) { audio.bass = response.bass || 0; audio.beat = response.beat || 0; },
      start:function () { if (running) return; running = true; previousTime = performance.now(); shelfOpenAnimAt = now(); tick(); },
      stop:function () { running = false; cancelAnimationFrame(frame); },
      destroy:function () {
        running = false; cancelAnimationFrame(frame); observer.disconnect(); reduced.removeEventListener('change', onReducedChange);
        renderer.domElement.removeEventListener('pointermove', onPointerMove);
        renderer.domElement.removeEventListener('pointerdown', onPointerDown);
        renderer.domElement.removeEventListener('pointerup', onPointerUp);
        renderer.domElement.removeEventListener('pointercancel', onPointerUp);
        renderer.domElement.removeEventListener('pointerleave', onLeave);
        renderer.domElement.removeEventListener('click', onClick);
        renderer.domElement.removeEventListener('wheel', onWheel);
        disposeRenderedCards(); renderer.dispose(); renderer.domElement.remove(); renderer = null;
      }
    };
  };
}());
