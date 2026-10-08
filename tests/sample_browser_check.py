"""Verify local import, diary saving and a separate recording entry using disposable data."""
import io
import re
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runtime' / 'test-deps'))
import uvicorn
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app

with tempfile.TemporaryDirectory() as folder:
    server = uvicorn.Server(uvicorn.Config(create_app(folder), host='127.0.0.1', port=0, log_level='warning'))
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    assert server.started, 'Disposable server failed to start'
    base='http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True,
                args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
            context = browser.new_context(permissions=['microphone'],viewport={'width':390, 'height':844})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base+'/studio#rec')
            page.get_by_role('button', name='上传本地音频', exact=True).wait_for()
            assert page.get_by_role('button',name='开始录音',exact=True).count()==0
            assert page.get_by_role('button',name='演示音频',exact=True).count()==0
            assert page.locator('.sample-audio').count()==0
            payload = io.BytesIO()
            with wave.open(payload, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b'\0\0' * 16000)
            page.get_by_label('选择本地音频').set_input_files({'name':'我的测试声音.wav', 'mimeType':'audio/wav', 'buffer':payload.getvalue()})
            page.get_by_role('button',name='保存素材',exact=True).wait_for()
            page.get_by_role('button',name='保存素材',exact=True).click()
            page.get_by_role('heading', name='登录，\n听见生活。').wait_for()
            page.get_by_role('button', name='创建账号', exact=True).click()
            page.locator('input[name=username]').fill('sample_test')
            page.locator('input[name=password]').fill('Sample-password-123')
            page.get_by_role('button', name='注册并登录', exact=True).click()
            page.get_by_role('button', name='新建手记', exact=True).wait_for(timeout=30000)
            page.locator('.library-current-caption').filter(has_text='原声已保存').wait_for()
            original=context.request.get(base+'/api/memories').json()['memories'][0]
            assert original['title']=='我的测试声音'
            assert page.locator('.timeline').count()==0
            page.get_by_role('button',name='生成音乐日记 →',exact=True).click()
            page.get_by_role('heading',name='那天，天气怎么样？').wait_for()
            assert page.get_by_role('button',name='平静',exact=True).count()==0
            page.get_by_role('button',name='晴天',exact=True).click()
            page.get_by_role('heading',name='此刻，是什么心情？').wait_for()
            page.get_by_role('button',name='其他',exact=True).click()
            page.get_by_label('其他心情').fill('充满好奇')
            page.get_by_role('button',name='继续 →',exact=True).click()
            page.get_by_role('button',name='工作',exact=True).click()
            page.get_by_label('给这一刻起个名字').fill('午后的新记忆')
            page.get_by_label('写下自己的话').fill('阳光照在桌子上，今天充满好奇。')
            # Optional location remains unchecked; newly added photographs must survive saving.
            from PIL import Image
            image=io.BytesIO();Image.new('RGB',(300,200),'#71cbea').save(image,format='PNG')
            page.locator('.story-upload input').set_input_files({'name':'memory.png','mimeType':'image/png','buffer':image.getvalue()})
            page.get_by_role('button',name='上一步',exact=False).click()
            page.get_by_role('button',name='工作',exact=True).click()
            assert page.get_by_label('写下自己的话').input_value()=='阳光照在桌子上，今天充满好奇。'
            assert page.locator('.diary-story .media-preview img').count()==1
            page.get_by_role('button',name='选择音乐 →',exact=True).click()
            page.get_by_label('想听到的细节').fill('温暖的钢琴与轻鼓点')
            assert page.locator('.direction-tags button').count()==10
            page.screenshot(path=str(ROOT/'docs'/'previews'/'diary-setup-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(ROOT/'docs'/'previews'/'diary-setup-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name='轻钢琴',exact=True).click()
            page.locator('.timeline').wait_for(timeout=30000)
            assert page.locator('.timeline').count() == 1
            assert page.get_by_role('combobox',name='音乐方向').input_value() == 'piano'
            page.get_by_role('button',name='收藏这段声音 ↗',exact=True).click()
            page.get_by_role('button',name='保存这段记忆 ↗',exact=True).click()
            page.get_by_role('heading',name='这一刻，已收藏',exact=True).wait_for(timeout=30000)
            diary=context.request.get(base+'/api/memories').json()['memories']
            assert len(diary)==1 and diary[0]['mood']=='充满好奇' and diary[0]['activity']=='工作'
            assert diary[0]['music_prompt']=='温暖的钢琴与轻鼓点' and diary[0]['music_audio']
            assert len(diary[0]['images'])==1 and diary[0]['notes']=='阳光照在桌子上，今天充满好奇。'
            assert diary[0]['lat'] is None and diary[0]['lng'] is None
            page.get_by_role('button',name='一键同步到社区',exact=True).click()
            page.get_by_role('button',name='已同步到社区 ✓',exact=True).wait_for()
            page.get_by_role('button',name='发送给远方的有缘人',exact=True).click()
            page.get_by_role('button',name='发送给远方的有缘人',exact=True).click()
            page.get_by_text('已放进信箱，等待另一位愿意交换声音的旅人。',exact=True).wait_for()
            page.goto(base+'/map')
            page.locator('#list .work').filter(has_text='午后的新记忆').wait_for()
            assert page.locator('.scene-orb').count()==0
            assert page.locator('.unlocated-memory').count()==1
            page.get_by_role('button',name='查看足迹：午后的新记忆',exact=True).click()
            assert page.locator('#mapMemory img').count()==1
            page.goto(base+'/album')
            page.locator('#enterStage').wait_for()
            before=page.locator('#enterStage').bounding_box()
            page.locator('#enterStage').hover()
            page.wait_for_timeout(300)
            after=page.locator('#enterStage').bounding_box()
            assert abs(before['x']-after['x'])<1,(before,after)

            page.screenshot(path=str(ROOT / 'docs' / 'previews' / 'sample-audio-mobile.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.set_viewport_size({'width':320,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(ROOT / 'docs' / 'previews' / 'sample-audio-desktop.png'), full_page=True)
            page.goto(base+'/studio')
            page.get_by_role('button',name='上传本地音频',exact=True).wait_for()
            assert page.locator('.sample-audio').count()==0
            assert page.get_by_role('button',name='开始录音',exact=True).count()==0
            page.goto(base+'/capture')
            page.get_by_role('button',name='开始录音',exact=True).click()
            page.get_by_role('button',name='结束录音',exact=True).wait_for()
            page.wait_for_function("document.querySelector('.capture-clock').textContent !== '0:00'")
            page.get_by_role('button',name='结束录音',exact=True).click()
            page.locator('.library-current-caption').filter(has_text='原声已保存').wait_for()
            assert page.locator('.save-dialog').count()==0
            assert page.locator('.timeline').count()==0
            raw=context.request.get(base+'/api/memories').json()['memories'][0]
            assert raw['music_audio'] is None
            assert page.locator('.timeline').count()==0
            assert page.locator('.diary-setup').count()==0
            page.get_by_role('button',name='生成音乐日记 →',exact=True).click()
            page.get_by_role('heading',name='那天，天气怎么样？',exact=True).wait_for()
            page.goto(base+'/studio?memory='+raw['id']+'#rec')
            page.get_by_role('heading',name='那天，天气怎么样？',exact=True).wait_for()
            assert not errors, errors
            browser.close()
            print('PASS: local import -> login -> library -> diary choices -> editor -> save/share; separate recording entry; responsive; sample panel absent; no page errors')
    finally:
        server.should_exit = True
        worker.join(timeout=5)
