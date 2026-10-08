"""AMap configuration and fixed-upstream security-code proxy."""
import os
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import Response


def install_maps(app):
    @app.get('/api/map/config')
    def config():
        key = os.getenv('SOUNDTRACE_AMAP_KEY', '')
        return {'enabled': bool(key and os.getenv('SOUNDTRACE_AMAP_SECURITY_CODE')), 'provider': 'amap',
                'key': key, 'style': os.getenv('SOUNDTRACE_AMAP_STYLE', 'amap://styles/normal'),
                'service_host': '/_AMapService'}

    @app.get('/_AMapService/{path:path}')
    async def proxy(path: str, request: Request):
        key, code = os.getenv('SOUNDTRACE_AMAP_KEY', ''), os.getenv('SOUNDTRACE_AMAP_SECURITY_CODE', '')
        if not key or not code:
            raise HTTPException(503, '地图服务未配置')
        # Only routes used by JS SDK coordinate conversion and custom style; never an open proxy.
        upstreams = {'v3/assistant/coordinate/convert': 'restapi.amap.com',
                     'v4/map/styles': 'webapi.amap.com'}
        host = upstreams.get(path)
        if not host:
            raise HTTPException(404)
        params = list(request.query_params.multi_items())
        params = [(k, v) for k, v in params if k not in ('key', 'jscode')]
        params.extend([('key', key), ('jscode', code)])
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                result = await client.get('https://' + host + '/' + path, params=params)
            return Response(result.content, status_code=result.status_code,
                            media_type=result.headers.get('content-type', 'application/json'),
                            headers={'Cache-Control': 'private, max-age=60'})
        except httpx.HTTPError:
            raise HTTPException(502, '地图服务暂时无法连接')
