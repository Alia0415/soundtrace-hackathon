"""Exercise demo storage/navigation and real-site isolation on a disposable server."""
import io
import json
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime/test-deps'))
import uvicorn
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app

shots=ROOT/'docs/previews/demo-v1';shots.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    server=uvicorn.Server(uvicorn.Config(create_app(folder),host='127.0.0.1',port=8095,log_level='warning'))
    worker=threading.Thread(target=server.run,daemon=True);worker.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];api_requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:api_requests.append(r.url) if '/api/' in r.url else None)
            page.goto('http://127.0.0.1:8095/demo/map',wait_until='networkidle')
            page.get_by_role('heading',name='西湖边的晚风',exact=True).wait_for()
            assert page.locator('.atlas-pin').count()==6
            assert page.locator('#list .work').count()==6
            for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
                page.set_viewport_size({'width':width,'height':height})
                for route in ['','map','community','album','studio']:
                    page.goto('http://127.0.0.1:8095/demo'+('/'+route if route else ''),wait_until='networkidle')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),(width,route)
                    if route=='community':assert page.locator('.community-post').count()==3
                    if route=='album':
                        assert page.locator('.memory-object.tape').count()==1
                        assert page.locator('.memory-object.vinyl').count()==1
                        assert page.locator('.memory-object.photo').count()==1
                        button=page.locator('#enterStage');before=button.bounding_box();button.hover();page.wait_for_timeout(250);after=button.bounding_box();assert abs(before['x']-after['x'])<1
                    page.screenshot(path=str(shots/((route or 'home')+'-'+label+'.png')),full_page=True)
            page.goto('http://127.0.0.1:8095/demo/studio',wait_until='networkidle')
            payload=io.BytesIO()
            with wave.open(payload,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*32000)
            page.get_by_label('选择本地音频').set_input_files({'name':'演示新原声.wav','mimeType':'audio/wav','buffer':payload.getvalue()})
            page.get_by_role('button',name='生成音乐日记 →',exact=True).wait_for()
            page.get_by_role('button',name='生成音乐日记 →',exact=True).click()
            page.get_by_role('button',name='晴天',exact=True).click();page.get_by_role('button',name='平静',exact=True).click();page.get_by_role('button',name='散步',exact=True).click()
            page.get_by_label('给这一刻起个名字').fill('演示专属的新记忆');page.get_by_label('写下自己的话').fill('这条记忆只存在演示空间里。')
            page.get_by_role('button',name='选择音乐 →',exact=True).click();page.get_by_role('button',name='轻钢琴',exact=True).click()
            page.locator('.timeline').wait_for();page.get_by_role('button',name='收藏这段声音 ↗',exact=True).click();page.get_by_role('button',name='保存这段记忆 ↗',exact=True).click()
            try:page.wait_for_function("location.pathname === '/demo/album'",timeout=30000)
            except Exception:
                print('SAVE DIAGNOSTICS:',page.url,page.locator('.error').all_text_contents(),errors)
                page.screenshot(path=str(shots/'save-error.png'),full_page=True)
                raise
            page.get_by_role('heading',name='这一刻，已收藏',exact=True).wait_for()
            page.get_by_role('button',name='一键同步到社区',exact=True).click();page.get_by_role('button',name='已同步到社区 ✓',exact=True).wait_for()
            page.get_by_role('button',name='发送给远方的有缘人',exact=True).click();page.get_by_role('button',name='发送给远方的有缘人',exact=True).click()
            page.goto('http://127.0.0.1:8095/demo/community',wait_until='networkidle');assert page.locator('.community-post').count()==4
            page.get_by_role('heading',name='演示专属的新记忆',exact=True).wait_for()
            like=page.locator('.community-post').first.get_by_role('button',name='喜欢',exact=False);like.click();page.wait_for_function("document.querySelector('.community-post .community-like').getAttribute('aria-pressed') === 'true'")
            page.locator('.community-post').first.get_by_role('button',name='回应',exact=False).click();page.get_by_label('回应内容').fill('演示回应');page.get_by_role('button',name='发送回应',exact=True).click();page.get_by_text('演示回应',exact=False).wait_for()
            page.goto('http://127.0.0.1:8095/demo/map',wait_until='networkidle');assert page.locator('#list .work').count()==7;assert page.locator('.unlocated-memory').count()==1
            assert not api_requests,api_requests
            assert context.request.get('http://127.0.0.1:8095/api/memories').json()['memories']==[]
            assert context.request.get('http://127.0.0.1:8095/api/feed').json()['posts']==[]
            page.goto('http://127.0.0.1:8095/map',wait_until='networkidle');assert page.locator('.atlas-pin').count()==0
            assert page.locator('.map-service-state').count()==1
            # Production Tencent SDK and coordinate behavior is covered separately in map_browser_check.py.
            assert not errors,errors
            browser.close();print('PASS: demo layouts, six scenes, wizard, editor, saved collection, feed/reply/send, map, reload and production data isolation')
    finally:server.should_exit=True;worker.join(timeout=5)
