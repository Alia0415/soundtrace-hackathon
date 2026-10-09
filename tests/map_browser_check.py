"""Tencent map browser regression. --live uses the ignored local map credentials."""
import io, os, sys, tempfile, threading, time, wave
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
import uvicorn
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app

live = '--live' in sys.argv
settings = {'SOUNDTRACE_TENCENT_MAP_KEY': 'private-test-map-key', 'SOUNDTRACE_TENCENT_MAP_SERVICE_KEY': ''}
if live:
    for line in (ROOT/'.env.production').read_text(encoding='utf-8').splitlines():
        name, sep, value = line.partition('=')
        if sep and name.startswith('SOUNDTRACE_TENCENT_MAP_'):
            settings[name] = value.strip()
    assert settings['SOUNDTRACE_TENCENT_MAP_KEY'] != 'private-test-map-key'

sdk = """window.sdkMarkers=[];window.sdkMaps=[];
window.TMap={
 LatLng:class{constructor(lat,lng){this.lat=lat;this.lng=lng;}},
 LatLngBounds:class{constructor(sw,ne){this.points=[sw];}extend(p){this.points.push(p);}},
 Map:class{constructor(id,options){this.host=document.getElementById(id);window.sdkMaps.push(options);}fitBounds(b,o){window.sdkFit=b.points;window.sdkFitOptions=o;}projectToContainer(p){return{x:150+p.lng,y:150+p.lat};}destroy(){this.host.replaceChildren();}},
 DOMOverlay:class{constructor(o){this.map=o.map;this.onInit(o);this.dom=this.createDOM();this.map.host.append(this.dom);this.updateDOM();window.sdkMarkers.push(o.position);}getMap(){return this.map;}}
};window.soundtraceTencentReady();"""
calls = []
def upstream(request):
    assert request.url.host == 'apis.map.qq.com'
    assert request.url.path == '/ws/coord/v1/translate'
    assert request.url.params['type'] == '1'
    points = [[float(n) for n in p.split(',')] for p in request.url.params['locations'].split(';')]
    calls.extend(points)
    return httpx.Response(200, json={'status': 0, 'locations': [{'lat': lat+.005, 'lng': lng+.005} for lat,lng in points]})

out=io.BytesIO()
with wave.open(out,'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*3200)
original_client=httpx.AsyncClient
from contextlib import nullcontext
with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,settings), (nullcontext() if live else patch('soundtrace_maps.httpx.AsyncClient',lambda **kw:original_client(transport=httpx.MockTransport(upstream),**kw))):
    server=uvicorn.Server(uvicorn.Config(create_app(folder),host='127.0.0.1',port=0,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    assert server.started
    base='http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000})
            context.request.post(base+'/api/auth/register',data={'username':'map_test','password':'Temporary-map-pass-123'})
            for title,lat,lng in [('北京的风',39.9,116.4),('上海的雨',31.2,121.4),('没有位置',None,None)]:
                fields={'title':title,'audio':{'name':'sound.wav','mimeType':'audio/wav','buffer':out.getvalue()}}
                if lat is not None:fields.update(lat=str(lat),lng=str(lng))
                assert context.request.post(base+'/api/memories',multipart=fields).ok
            config=context.request.get(base+'/api/map/config').json()
            assert config['provider']=='tencent' and 'key' not in config
            page=context.new_page();errors=[];urls=[];key_checks=[];network_errors=[];console_errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:urls.append(r.url))
            page.on('response',lambda r:key_checks.append(r) if '/_TMapService/checkKey' in r.url else None)
            from urllib.parse import urlsplit
            page.on('requestfailed',lambda r:network_errors.append((urlsplit(r.url).netloc,urlsplit(r.url).path,r.failure)))
            page.on('response',lambda r:network_errors.append((urlsplit(r.url).netloc,urlsplit(r.url).path,r.status)) if r.status>=400 else None)
            page.on('console',lambda m:console_errors.append(m.text.replace(settings['SOUNDTRACE_TENCENT_MAP_KEY'],'[redacted]')) if m.type=='error' else None)
            if not live:page.route('https://map.qq.com/api/gljs?**',lambda r:r.fulfill(body=sdk,content_type='application/javascript'))
            page.goto(base+'/map')
            try:page.wait_for_function("document.querySelectorAll('#geoMap .scene-orb').length===2",timeout=45000)
            except Exception:
                print('Map state:',page.locator('.map-service-state').inner_text() if page.locator('.map-service-state').count() else 'SDK did not render markers')
                raise
            assert page.locator('.unlocated-memory').count()==1
            assert page.locator('#list .work').count()==3
            if not live:
                assert sorted(calls)==[[31.2,121.4],[39.9,116.4]]
                assert len(page.evaluate('window.sdkFit'))==2
                assert page.evaluate('window.sdkFitOptions.maxZoom')==14
            else:
                page.wait_for_timeout(12000)
                page.screenshot(path=str(ROOT/'runtime/audit-20261009/tencent-map-desktop.png'),full_page=True)
            page.locator('#geoMap .scene-orb[aria-label="北京的风"]').click()
            page.get_by_role('heading',name='北京的风',exact=True).wait_for()
            assert page.locator('#mapMemory audio').count()==1
            page.get_by_role('button',name='关闭足迹详情',exact=True).click()
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name='查看足迹：上海的雨',exact=True).click()
            page.get_by_role('heading',name='上海的雨',exact=True).wait_for()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
            if live:
                page.wait_for_timeout(3000)
                assert key_checks,'Tencent key verification did not run'
                import re
                assert any(re.search(r'"error"\s*:\s*0',r.text()) for r in key_checks),'Tencent key verification failed'
                assert not [e for e in network_errors if e[1].startswith('/_TMapService')],network_errors
                shot=ROOT/'runtime/audit-20261009/tencent-map-mobile.png';shot.parent.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(shot),full_page=True)
                print('Live network failures:',sorted(set(network_errors)))
            else:
                page.route('**/api/map/coordinates',lambda r:r.fulfill(status=502,json={'detail':'位置转换暂时不可用，足迹仍保留在列表中'}))
                page.goto(base+'/map');page.locator('.map-service-state').wait_for()
                assert page.locator('#geoMap .scene-orb').count()==0
                page.get_by_role('button',name='查看足迹：北京的风',exact=True).click()
                page.get_by_role('heading',name='北京的风',exact=True).wait_for()
                page.route('**/api/map/config',lambda r:r.fulfill(json={'enabled':False,'provider':'tencent'}))
                page.goto(base+'/map');page.get_by_text('真实地图待启用：需要配置腾讯地图 Key',exact=True).wait_for()
                assert page.locator('#list .work').count()==3
                previous_sdk_requests=sum('map.qq.com/api/gljs' in url for url in urls)
                page.goto(base+'/demo/map');page.wait_for_function("document.querySelectorAll('.atlas-pin').length===6")
                assert sum('map.qq.com/api/gljs' in url for url in urls)==previous_sdk_requests
            assert not any(settings['SOUNDTRACE_TENCENT_MAP_KEY'] in url for url in urls),'Key leaked to browser URL'
            assert not any('amap.com' in url for url in urls),'Old map provider requested'
            assert not errors, [e.replace(settings['SOUNDTRACE_TENCENT_MAP_KEY'],'[redacted]') for e in errors]
            browser.close()
            print('PASS:', 'live Tencent SDK, key authentication and coordinate conversion' if live else 'mocked Tencent SDK and upstream', '; private key, markers, details, mobile layout and footprint list')
    finally:
        server.should_exit=True;thread.join(5)
