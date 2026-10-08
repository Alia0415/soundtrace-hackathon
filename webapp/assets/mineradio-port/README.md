# Mineradio source port

Upstream: [XxHuberrr/Mineradio-paused](https://github.com/XxHuberrr/Mineradio-paused), commit `d43de565acabfdc1a9c9820a27e81a98ccbebcef`.

- `memory-shelf.js` is a modified GPL-3.0-only port of the PSP arc layout, Canvas card renderer, rendered-card window, summon animation, eased scrolling, pointer parallax, hover lift, and raycast interaction in upstream `public/js/modules/04-shelf/00-layout-hover.js`, `01-manager-core.js`, and `05-card-interactions.js`. Changes are recorded in its header and in `docs/MINERADIO_ADAPTATION.md`.
- `beat-reactivity.js` is a modified GPL-3.0-only port of frequency-band analysis from upstream `public/js/modules/01-scene/02-beat-camera-runtime.js` and envelope/peak logic from `public/js/modules/11-main-loop.js`.
- `three.r128.min.js` is copied byte for byte from upstream `public/vendor/three.r128.min.js`. Three.js is MIT-licensed; its license is in `LICENSE.three-MIT`.
- `LICENSE.GPL-3.0` and `NOTICE.upstream.md` preserve upstream terms and attributions. The complete upstream snapshot is in `third_party/Mineradio-paused-main/`.

The original Mineradio icon, name, skull point-cloud, and third-party music/account resources are not served by SoundTrace. The running shelf uses SoundTrace's existing photos, records, tapes, and location data.
