"""Tencent JSAPI GL configuration, key delegation and GPS coordinate conversion."""
import json
import math
import os
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response


def map_key():
    return os.getenv('SOUNDTRACE_TENCENT_MAP_KEY', '').strip()


def install_maps(app, account):
    @app.get('/api/map/config')
    def config():
        return {'enabled': bool(map_key()), 'provider': 'tencent',
                'style': os.getenv('SOUNDTRACE_TENCENT_MAP_STYLE', '').strip(),
                'service_host': '/_TMapService'}

    # Exact SDK key-delegation endpoints, never a general WebService proxy.
    @app.get('/_TMapService')
    @app.get('/_TMapService/{path:path}')
    async def proxy(request: Request, path: str = ''):
        upstreams = {'': 'https://pr.map.qq.com/pingd',
                     'checkKey': 'https://apikey.map.qq.com/mkey/index.php/mkey/check',
                     'oversea': 'https://overseactrl.map.qq.com/v4'}
        if path not in upstreams:
            raise HTTPException(404)
        key = map_key()
        if not key:
            raise HTTPException(503, '腾讯地图服务未配置')
        if len(request.url.query) > 12000:
            raise HTTPException(413, '地图请求参数过长')
        params = [(k, v) for k, v in request.query_params.multi_items()
                  if k.lower() not in ('key', 'key2', 'subkey', 'apikey', 'appid')]
        params.append(('apikey' if path == 'oversea' else 'key', key))
        if not path:
            params.append(('appid', 'jsapi_v3'))
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                result = await client.get(upstreams[path], params=params,
                                          headers={'Referer': str(request.base_url)})
                result.raise_for_status()
            return Response(result.content, media_type=result.headers.get('content-type', 'application/javascript'),
                            headers={'Cache-Control': 'no-store'})
        except httpx.HTTPError:
            raise HTTPException(502, '腾讯地图暂时无法连接，请稍后重试')

    @app.post('/api/map/coordinates')
    async def coordinates(request: Request):
        account(request)
        key = os.getenv('SOUNDTRACE_TENCENT_MAP_SERVICE_KEY', '').strip() or map_key()
        if not key:
            raise HTTPException(503, '腾讯地图服务未配置')
        raw = await request.body()
        if len(raw) > 6000:
            raise HTTPException(413, '位置数据过多')
        body = json.loads(raw)
        points = body.get('locations') if isinstance(body, dict) else None
        if not isinstance(points, list) or not 1 <= len(points) <= 40:
            raise HTTPException(400, '每次支持转换 1 到 40 个位置')
        for p in points:
            if (not isinstance(p, list) or len(p) != 2 or
                any(type(n) not in (int, float) or not math.isfinite(n) for n in p) or
                not -90 <= p[0] <= 90 or not -180 <= p[1] <= 180):
                raise HTTPException(400, '位置坐标无效')
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get('https://apis.map.qq.com/ws/coord/v1/translate',
                    params={'key': key, 'type': 1, 'locations': ';'.join(f'{lat},{lng}' for lat, lng in points)},
                    headers={'Referer': str(request.base_url)})
                response.raise_for_status()
            payload = response.json()
            if payload.get('status') != 0:
                raise HTTPException(502, '腾讯坐标转换失败，请检查 WebService 权限与访问限制')
            result = payload.get('locations')
            if not isinstance(result, list) or len(result) != len(points):
                raise ValueError()
            for p in result:
                if (not isinstance(p, dict) or
                    any(type(p.get(k)) not in (int, float) or not math.isfinite(p[k]) for k in ('lat', 'lng')) or
                    not -90 <= p['lat'] <= 90 or not -180 <= p['lng'] <= 180):
                    raise ValueError()
            return {'locations': [{'lat': p['lat'], 'lng': p['lng']} for p in result]}
        except (httpx.HTTPError, ValueError, AttributeError):
            raise HTTPException(502, '位置转换暂时不可用，足迹仍保留在列表中')
