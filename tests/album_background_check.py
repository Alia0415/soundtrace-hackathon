"""Visual regression for all six crops, plus genuine private-media backgrounds."""
import io
import os
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'runtime/test-deps'))
import uvicorn
from PIL import Image
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app

SHOTS=ROOT/'docs/previews/album-background-v2'; SHOTS.mkdir(parents=True,exist_ok=True)
SCENES=['sea-window','rainy-city','autumn-lake','snow-mountain','spring-meadow','desert-dusk']

def picture(color):
    output=io.BytesIO(); Image.new('RGB',(400,500),color).save(output,format='JPEG'); return output.getvalue()

def sound():
    output=io.BytesIO()
    with wave.open(output,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b'\0\0'*8000)
    return output.getvalue()

async def mock_art(photo,memory):
    return picture('#ffd76d')

with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'SOUNDTRACE_ARK_KEY':'mock-only-not-a-real-key'}), patch('soundtrace_art.generate_art',mock_art):
    server=uvicorn.Server(uvicorn.Config(create_app(folder),host='127.0.0.1',port=0,log_level='warning'))
    worker=threading.Thread(target=server.run,daemon=True); worker.start()
    for _ in range(100):
        if server.started: break
        time.sleep(.05)
    assert server.started, 'Disposable server failed to start'
    port=server.servers[0].sockets[0].getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1080}); page=context.new_page(); errors=[]; leaked=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:leaked.append(r.url) if '/api/' in r.url else None)
            for width,height,label in [(1440,1080,'desktop'),(390,844,'mobile'),(320,740,'small')]:
                page.set_viewport_size({'width':width,'height':height})
                for scene in SCENES:
                    page.goto(base+'/demo/album?scene='+scene,wait_until='networkidle')
                    page.wait_for_timeout(100)
                    active=page.locator('.scene-slide.is-active'); assert active.get_attribute('data-scene')==scene
                    crop=active.locator('.scene-window .scene-crop'); assert crop.count()==1
                    geometry=crop.evaluate('(el)=>({box:el.getBoundingClientRect().toJSON(),ratio:parseFloat(getComputedStyle(el.parentElement).getPropertyValue("--scene-crop-ratio")),background:getComputedStyle(el).backgroundPosition})')
                    assert abs(geometry['box']['width']/geometry['box']['height']-geometry['ratio'])<.01
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(width,scene)
                    assert active.locator('.demo-photo-landscape .scene-crop').count()==1
                    if label!='small': page.screenshot(path=str(SHOTS/(scene+'-'+label+'.png')),full_page=True)
            assert not leaked,leaked
            # A separate real account on this disposable server; no personal data touched.
            page.goto(base+'/album',wait_until='networkidle')
            request=context.request
            assert request.post(base+'/api/auth/register',data={'username':'backgroundtest','password':'Very-long-password-123'}).ok
            memory=request.post(base+'/api/memories',multipart={'title':'我的真实照片','scene':'autumn-lake','audio':{'name':'a.wav','mimeType':'audio/wav','buffer':sound()},'images':{'name':'real.jpg','mimeType':'image/jpeg','buffer':picture('#8dd9ff')}}).json()
            page.set_viewport_size({'width':1440,'height':1080})
            page.goto(base+'/album?scene=autumn-lake',wait_until='networkidle')
            photo=page.locator('.scene-slide.is-active .memory-background'); photo.wait_for()
            assert photo.get_attribute('src')=='/'+memory['images'][0]
            assert photo.evaluate('(el)=>getComputedStyle(el).objectFit')=='cover'
            assert page.locator('#backgroundTools').is_visible()
            page.locator('#backgroundTools').get_by_role('button',name='生成手绘',exact=True).click()
            page.locator('#backgroundTools').get_by_text('AI 手绘 · 原照片已保留',exact=True).wait_for(timeout=15000)
            assert 'art-' in photo.get_attribute('src')
            page.locator('#backgroundTools').get_by_role('button',name='照片',exact=True).click()
            page.wait_for_function('(source)=>document.querySelector(".scene-slide.is-active .memory-background").getAttribute("src")===source',arg='/'+memory['images'][0])
            page.reload(wait_until='networkidle'); assert photo.get_attribute('src')=='/'+memory['images'][0]
            page.locator('#backgroundTools').get_by_role('button',name='手绘',exact=True).click()
            page.wait_for_function('document.querySelector(".scene-slide.is-active .memory-background").src.includes("art-")')
            page.set_viewport_size({'width':390,'height':844}); page.wait_for_timeout(500)
            if not page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'):
                print('OVERFLOW',page.evaluate('({width:innerWidth,doc:document.documentElement.scrollWidth,elements:[...document.querySelectorAll("body *")].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&!e.closest(".scene-track")).map(e=>({name:e.tagName,id:e.id,cls:e.className,box:e.getBoundingClientRect().toJSON()})).slice(0,12)})'))
                page.screenshot(path=str(SHOTS/'formal-mobile-debug.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert photo.evaluate('(el)=>getComputedStyle(el).objectFit')=='cover'
            # The actual diary wizard must carry the choice through save, not only the album buttons.
            page.set_viewport_size({'width':1440,'height':1080})
            page.goto(base+'/studio?memory='+memory['id']+'#rec',wait_until='networkidle')
            page.get_by_role('button',name='晴天',exact=True).click()
            page.get_by_role('button',name='平静',exact=True).click()
            page.get_by_role('button',name='散步',exact=True).click()
            page.get_by_label('写下自己的话').fill('验证保存时使用照片生成手绘，原声保留。')
            page.get_by_label('生成手绘',exact=True).check()
            page.get_by_role('button',name='选择音乐 →',exact=True).click()
            page.get_by_role('button',name='轻钢琴',exact=True).click()
            page.locator('.timeline').wait_for()
            page.get_by_role('button',name='收藏这段声音 ↗',exact=True).click()
            page.get_by_role('button',name='保存这段记忆 ↗',exact=True).click()
            page.wait_for_url('**/album**',timeout=30000)
            page.get_by_role('heading',name='这一刻，已收藏',exact=True).wait_for()
            page.get_by_role('button',name='看看我的收藏',exact=True).click()
            page.locator('#backgroundTools').get_by_text('AI 手绘 · 原照片已保留',exact=True).wait_for(timeout=15000)
            final=request.get(base+'/api/memories/'+memory['id']).json()
            assert final['background_mode']=='stylized' and final['art_status']=='stylized'
            assert final['images']==memory['images'] and final['audio']==memory['audio']
            assert not errors,errors
            browser.close()
            print('PASS: 6 scene crops at 1440/390/320; zero demo API leaks; private photo, mocked style job, original switch, persistence, mobile fit; wizard selection survives save.')
    finally:
        server.should_exit=True; worker.join(5)
