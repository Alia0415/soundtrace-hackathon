"""Verify upload-only studio and demo-only audio action on the local site."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/test-deps'))
from playwright.sync_api import sync_playwright
shots=ROOT/'docs/previews/audio-import-v2'
shots.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
    context=browser.new_context()
    page=context.new_page();errors=[];sample_requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:sample_requests.append(r.url) if '/api/studio/sample' in r.url else None)
    for mode in ['formal','demo']:
        route='/demo/studio' if mode=='demo' else '/studio'
        for w,h,label in [(1440,1000,'desktop'),(390,844,'mobile'),(320,740,'small'),(431,630,'short')]:
            page.set_viewport_size({'width':w,'height':h})
            page.goto('http://127.0.0.1:8093'+route+'#rec',wait_until='networkidle')
            page.get_by_role('heading',name='导入已有音频',exact=True).wait_for()
            assert page.get_by_role('button',name='上传本地音频',exact=True).count()==1
            assert page.get_by_role('button',name='演示音频',exact=True).count()==(1 if mode=='demo' else 0)
            assert page.locator('.capture-scene,.sample-audio').count()==0
            assert page.get_by_role('button',name='开始录音',exact=True).count()==0
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(mode,w)
            if label=='short':
                upload=page.get_by_role('button',name='上传本地音频',exact=True).bounding_box()
                assert upload['y']+upload['height'] < h-70,upload
            page.screenshot(path=str(shots/(mode+'-'+label+'.png')),full_page=True)
    page.get_by_role('button',name='演示音频',exact=True).click()
    page.get_by_role('button',name='生成音乐日记 →',exact=True).wait_for()
    page.get_by_role('heading',name='溪边 · 演示音频',exact=True).wait_for()
    assert not page.locator('.error').count(),page.locator('.error').all_text_contents()
    assert not sample_requests,sample_requests
    assert not errors,errors
    context.close();browser.close()
print('PASS: formal upload only; demo extra audio button loads source; no sample widget or recording; 1440/390/320 responsive; no page errors')
