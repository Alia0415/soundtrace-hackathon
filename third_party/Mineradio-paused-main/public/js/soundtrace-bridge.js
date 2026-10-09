/*
 * SoundTrace integration layer for the unmodified Mineradio player and
 * particle runtime. The upstream modules and effects are not edited here.
 * Copyright (C) SoundTrace contributors.
 * SPDX-License-Identifier: GPL-3.0-only
 */
(function () {
  'use strict';
  var ready = false;
  var currentTracks = [];
  var queuedMessage = null;
  var parentOrigin = location.origin;
  var coverProxyInstalled = false;

  function report(type, detail) {
    if (window.parent !== window) window.parent.postMessage(Object.assign({ type:type }, detail || {}), parentOrigin);
  }
  function audioLevel(name) {
    if (typeof uniforms === 'undefined' || !uniforms[name]) return 0;
    var value = Number(uniforms[name].value);
    return isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  }
  function safeTrack(track, index) {
    if (!track || typeof track.audio !== 'string') return null;
    var localFile = /^\/outputs\/[\w./-]+$/.test(track.audio) && !track.audio.includes('..');
    // Demo edits live in IndexedDB; only accept blobs created by this same origin.
    var blobPrefix = 'blob:' + location.origin + '/';
    var localBlob = track.audio.startsWith(blobPrefix) && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(track.audio.slice(blobPrefix.length));
    if (!localFile && !localBlob) return null;
    var cover = typeof track.cover === 'string' && /^\/(assets|outputs)\/[\w./-]+$/.test(track.cover) && !track.cover.includes('..') ? track.cover : '';
    return {
      type:'local', source:'local', provider:'local',
      id:'soundtrace:' + String(track.id || index),
      name:String(track.title || '一段声音'),
      artist:String(track.artist || '声迹 · SoundTrace'),
      album:String(track.location || '声音记忆'),
      localKey:'soundtrace:' + String(track.id || index),
      localUrl:track.audio, localPath:track.audio,
      cover:cover ? location.origin + cover : '', duration:0
    };
  }
  function select(index, manual) {
    if (!ready || !currentTracks.length) return;
    index = Math.max(0, Math.min(currentTracks.length - 1, Number(index) || 0));
    try {
      if (currentIdx === index && audio) {
        if (audio.paused && typeof togglePlay === 'function') togglePlay();
        return;
      }
      playQueueAt(index, { manual:manual !== false, suppressPlayFailureNotice:true });
    } catch (error) {
      report('soundtrace-engine-error', { message:String(error && error.message || error) });
    }
  }
  function receive(message) {
    if (!message || typeof message.type !== 'string') return;
    if (!ready) { queuedMessage = message; return; }
    if (message.type === 'soundtrace-load') {
      currentTracks = (Array.isArray(message.tracks) ? message.tracks : []).map(safeTrack).filter(Boolean);
      playQueue = currentTracks.slice();
      currentIdx = -1;
      if (typeof renderQueuePanel === 'function') renderQueuePanel();
      if (currentTracks.length && message.autoplay !== false) select(message.index, true);
      else if (currentTracks.length) {
        var bottom = document.getElementById('bottom-bar');
        if (bottom) bottom.classList.add('visible');
      }
    } else if (message.type === 'soundtrace-select') select(message.index, true);
    else if (message.type === 'soundtrace-toggle' && typeof togglePlay === 'function') togglePlay();
    else if (message.type === 'soundtrace-pause' && audio) audio.pause();
  }
  window.addEventListener('message', function (event) {
    if (event.origin !== parentOrigin || event.source !== window.parent) return;
    receive(event.data);
  });
  function checkReady() {
    if (typeof playQueueAt !== 'function' || typeof dismissSplash !== 'function' || typeof coverProxySrc !== 'function') {
      setTimeout(checkReady, 120); return;
    }
    if (!coverProxyInstalled) {
      var upstreamCoverProxySrc = coverProxySrc;
      coverProxySrc = function (url, cacheBust) {
        if (typeof url === 'string' && (url.startsWith(location.origin + '/assets/') || url.startsWith(location.origin + '/outputs/'))) return url;
        return upstreamCoverProxySrc(url, cacheBust);
      };
      coverProxyInstalled = true;
    }
    try { dismissSplash({ instant:true }); } catch (_) { /* original runtime may still finish its intro */ }
    ready = true;
    if (audio) audio.addEventListener('error', function () {
      report('soundtrace-engine-error', { message:'音频暂时无法读取，请换一件藏品再试。' });
    });
    report('soundtrace-engine-ready');
    if (queuedMessage) { var message = queuedMessage; queuedMessage = null; receive(message); }
  }
  checkReady();
  setInterval(function () {
    if (!ready) return;
    var beatModal = document.getElementById('local-beat-modal');
    if (beatModal && beatModal.classList.contains('show') && typeof closeLocalBeatModal === 'function') closeLocalBeatModal();
    report('soundtrace-engine-state', {
      index:typeof currentIdx === 'number' ? currentIdx : -1,
      playing:!!(audio && !audio.paused),
      currentTime:audio ? audio.currentTime || 0 : 0,
      duration:audio && isFinite(audio.duration) ? audio.duration : 0,
      bass:audioLevel('uBass'),
      beat:audioLevel('uBeat'),
      energy:audioLevel('uEnergy')
    });
  }, 150);
}());
