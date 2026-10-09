// Local SoundTrace server: static app + durable studio saves, optional AI proxy.
// Run with: node tools/preview-server.cjs
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const studioApi = require('./studio-service.cjs').createStudioApi(root);
const routes = {
  '/': 'webapp/home.html',
  '/studio': 'webapp/index.html',
  '/capture': 'webapp/index.html',
  '/library': 'webapp/index.html',
  '/album': 'webapp/album-room.html',
  '/map': 'webapp/map.html',
  '/community': 'webapp/community.html',
  '/me': 'webapp/me.html',
};
const data = {
  '/api/works': ['works.json', 'works', false],
  '/api/photos': ['photos.json', 'photos', true],
  '/api/materials': ['materials.json', 'materials', true],
  '/api/inbox': ['exchanges.json', 'items', true, 'in'],
  '/api/exchange': ['exchanges.json', 'items', false],
  '/api/feed': ['feed.json', 'posts', true],
  '/api/user': ['user.json', null, false],
};
const mime = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp', '.gif':'image/gif', '.svg':'image/svg+xml', '.woff2':'font/woff2', '.wav':'audio/wav', '.mp3':'audio/mpeg', '.m4a':'audio/mp4', '.ogg':'audio/ogg', '.mp4':'video/mp4', '.webm':'video/webm', '.mov':'video/quicktime' };
http.createServer(async (req, res) => {
  if (await studioApi(req, res)) return;
  const requestedPath = new URL(req.url, 'http://localhost').pathname;
  const demo = /^\/demo(?:\/|$)/.test(requestedPath);
  const pathname = demo ? requestedPath.replace(/^\/demo/, '') || '/' : requestedPath;
  if (pathname === '/me') {
    res.writeHead(302, { Location:(demo ? '/demo' : '') + '/album?profile=1' });
    return res.end();
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(503, {'Content-Type':'application/json; charset=utf-8'});
    return res.end(JSON.stringify({ detail:'只读视觉预览；请使用 FastAPI 服务进行创作或提交。' }));
  }
  if (demo && routes[pathname]) {
    let html = fs.readFileSync(path.join(root, routes[pathname]), 'utf8');
    html = html.replace('<head>', '<head><script src="/assets/soundtrace-demo.js?v=6"></script><script src="/assets/soundtrace-account.js?v=5" defer></script>');
    res.writeHead(200, {'Content-Type':'text/html; charset=utf-8', 'Cache-Control':'no-store'});
    return res.end(req.method === 'HEAD' ? undefined : html);
  }
  if (data[pathname]) {
    const [file, key, reverse, direction] = data[pathname];
    let value;
    try { value = JSON.parse(fs.readFileSync(path.join(root, 'outputs', file), 'utf8')); }
    catch { value = key ? [] : {}; }
    if (direction) value = value.filter(item => item.dir === direction);
    if (reverse) value = value.slice().reverse();
    const payload = JSON.stringify(key ? { [key]:value } : value);
    res.writeHead(200, {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store'});
    return res.end(payload);
  }
  const relative = routes[pathname] || (pathname.startsWith('/assets/') ? `webapp${pathname}` : pathname.startsWith('/mineradio/') ? `third_party/Mineradio-paused-main/public${pathname.slice(10)}` : pathname.startsWith('/outputs/') ? pathname.slice(1) : null);
  if (!relative) { res.writeHead(404); return res.end(); }
  const target = path.resolve(root, relative);
  if (!target.startsWith(root + path.sep) || !fs.existsSync(target) || !fs.statSync(target).isFile()) { res.writeHead(404); return res.end(); }
  const size = fs.statSync(target).size;
  const type = mime[path.extname(target).toLowerCase()] || 'application/octet-stream';
  const headers = { 'Content-Type':type + (type.startsWith('text/') || type === 'application/json' ? '; charset=utf-8' : ''), 'Accept-Ranges':'bytes' };
  const range = req.headers.range && /^bytes=(\d*)-(\d*)$/.exec(req.headers.range);
  if (range) {
    const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]));
    const end = range[2] && range[1] ? Math.min(size - 1, Number(range[2])) : size - 1;
    if (start > end || start >= size) { res.writeHead(416, { 'Content-Range':`bytes */${size}` }); return res.end(); }
    res.writeHead(206, { ...headers, 'Content-Length':end - start + 1, 'Content-Range':`bytes ${start}-${end}/${size}` });
    return fs.createReadStream(target, { start, end }).pipe(res);
  }
  res.writeHead(200, { ...headers, 'Content-Length':size });
  fs.createReadStream(target).pipe(res);
}).listen(Number(process.env.PORT || 8090), '127.0.0.1', () => console.log(`SoundTrace: http://127.0.0.1:${process.env.PORT || 8090}`));
