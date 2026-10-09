/* SoundTrace local-only player adapter. SPDX-License-Identifier: GPL-3.0-only */
// Installed before the upstream startup bindings, only in soundtrace-engine.html.
// SoundTrace has its own accounts; upstream music-provider accounts are unavailable.
refreshLoginStatus = async function () { return false; };
refreshQQLoginStatus = async function () { return false; };
refreshKugouLoginStatus = async function () { return false; };
refreshQishuiLoginStatus = async function () { return false; };
startQQLoginStatusAutoRefresh = function () {};
startKugouLoginStatusAutoRefresh = function () {};
startQishuiLoginStatusAutoRefresh = function () {};
coverProxySrc = function (url) {
  if (typeof url !== 'string' || !url) return '';
  if (isInlineCoverSrc(url)) return url;
  try {
    var target = new URL(url, location.origin);
    if (target.origin === location.origin && /^\/(assets|outputs)\//.test(target.pathname)) return target.href;
  } catch (_) {}
  return '';
};
