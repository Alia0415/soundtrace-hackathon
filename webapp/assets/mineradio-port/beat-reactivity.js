/*
 * SoundTrace audio response, adapted from Mineradio's
 * public/js/modules/01-scene/02-beat-camera-runtime.js (beatBandRms) and
 * public/js/modules/11-main-loop.js (band grouping, dynamic peaks, envelopes)
 * at d43de565acabfdc1a9c9820a27e81a98ccbebcef.
 * Copyright (C) Mineradio contributors and SoundTrace contributors.
 * SPDX-License-Identifier: GPL-3.0-only
 * Changes: isolated the Web Audio analysis, removed player / beat-map state,
 * and exposed a compact signal for SoundTrace's memory-themed canvas.
 */
(function () {
  'use strict';
  window.createSoundTraceBeatMeter = function () {
    var peak = { bass:.03, mid:.026, treble:.018, energy:.03 };
    var smooth = { bass:0, mid:0, treble:0, energy:0, beat:0 };
    var previousBass = 0;
    function bandRms(data, sampleRate, fftSize, lowHz, highHz) {
      var binHz = sampleRate / fftSize;
      var a = Math.max(1, Math.floor(lowHz / binHz));
      var b = Math.min(data.length - 1, Math.ceil(highHz / binHz));
      var sum = 0, count = 0;
      for (var i = a; i <= b; i++) {
        var value = data[i] / 255;
        sum += value * value;
        count++;
      }
      return count ? Math.sqrt(sum / count) : 0;
    }
    function envelope(before, target, attack, release) {
      return before + (target - before) * (target > before ? attack : release);
    }
    return {
      update: function (data, sampleRate, fftSize, playing) {
        if (!data || !playing) {
          Object.keys(smooth).forEach(function (key) { smooth[key] *= .90; });
          previousBass *= .90;
          return smooth;
        }
        var sub = bandRms(data, sampleRate, fftSize, 38, 74);
        var kick = bandRms(data, sampleRate, fftSize, 52, 165);
        var body = bandRms(data, sampleRate, fftSize, 165, 420);
        var bass = Math.min(1, kick * .86 + sub * .42 + body * .10);
        var mid = bandRms(data, sampleRate, fftSize, 2600, 6200);
        var treble = bandRms(data, sampleRate, fftSize, 6200, Math.min(16000, sampleRate / 2));
        var energy = 0;
        for (var i = 0; i < data.length; i++) energy += data[i] * data[i];
        energy = Math.sqrt(energy / data.length) / 255;
        peak.bass = Math.max(peak.bass * .994, bass, .03);
        peak.mid = Math.max(peak.mid * .993, mid, .026);
        peak.treble = Math.max(peak.treble * .992, treble, .018);
        peak.energy = Math.max(peak.energy * .995, energy, .03);
        var rb = Math.min(1, Math.pow(bass / Math.max(.038, peak.bass * .66), .78));
        var rm = Math.min(1, Math.pow(mid / Math.max(.025, peak.mid * .70), .86));
        var rt = Math.min(1, Math.pow(treble / Math.max(.020, peak.treble * .74), .92));
        var re = Math.min(1, Math.pow(energy / Math.max(.034, peak.energy * .68), .82));
        var onset = Math.max(0, rb - previousBass);
        previousBass = envelope(previousBass, rb, .24, .12);
        smooth.beat = Math.max(smooth.beat * .82, onset > .11 && re > .28 ? Math.min(1, onset * 2.2) : 0);
        smooth.bass = envelope(smooth.bass, Math.min(.82, rb * .78 + re * .025), .28, .075);
        smooth.mid = envelope(smooth.mid, Math.min(.68, rm * .64 + re * .025), .18, .060);
        smooth.treble = envelope(smooth.treble, Math.min(.56, rt * .54), .18, .055);
        smooth.energy = envelope(smooth.energy, Math.min(.72, re), .16, .055);
        return smooth;
      }
    };
  };
}());
