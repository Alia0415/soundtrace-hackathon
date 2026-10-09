"""Real Basic Pitch inference in the browser; no mocked transcription service."""
import io, math, os, struct, sys, tempfile, threading, time, wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import uvicorn
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app

def melody():
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050)
        samples=[]
        for midi in (60,64,67):
            hz=440*2**((midi-69)/12)
            for i in range(11025):
                t=i/22050
                envelope=min(1,i/400,(11024-i)/700)
                value=envelope*(.4*math.sin(2*math.pi*hz*t)+.15*math.sin(4*math.pi*hz*t))
                samples.append(struct.pack('<h',int(value*32767)))
            samples.extend([b'\0\0']*2205)
        w.writeframes(b''.join(samples))
    return out.getvalue()

with tempfile.TemporaryDirectory() as folder:
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
            context=browser.new_context(viewport={'width':390,'height':844})
            assert context.request.post(base+'/api/auth/register',data={'username':'hum_test','password':'Temporary-hum-pass-123'}).ok
            original=melody()
            saved=context.request.post(base+'/api/memories',multipart={'title':'Hum regression','audio':{'name':'melody.wav','mimeType':'audio/wav','buffer':original}}).json()
            page=context.new_page();errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append((r.url,r.method)))
            page.goto(base+'/studio?memory='+saved['id']+'#rec')
            for label in ['晴天','平静','散步','选择音乐 →','轻钢琴']:
                page.get_by_role('button',name=label,exact=True).click()
            page.locator('.timeline').wait_for()
            page.get_by_role('button',name='细调 ＋',exact=True).click()
            button=page.get_by_role('button',name='这是我的哼唱',exact=True)
            assert button.is_enabled()
            requests.clear()
            button.click();page.get_by_role('button',name='停止等待',exact=True).click()
            button.wait_for();page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='这是我的哼唱').disabled")
            started=time.monotonic();button.click()
            try:page.locator('.track-label[data-track-kind=hum]').wait_for(timeout=180000)
            except Exception:
                print('Diagnosis:',errors,page.locator('.error').all_text_contents(),flush=True);raise
            print('Real model completed in',round(time.monotonic()-started,2),'seconds',flush=True)
            # Inspect only inference: the later album page may load font stylesheets.
            assert not [url for url,method in requests if url.startswith(('http:','https:')) and not url.startswith(base+'/')],requests
            assert not [url for url,method in requests if method=='POST'],requests
            page.get_by_role('button',name='播放',exact=True).click();page.get_by_role('button',name='暂停',exact=True).click()
            page.get_by_role('button',name='收藏这段声音 ↗',exact=True).click()
            page.get_by_role('button',name='保存这段记忆 ↗',exact=True).click()
            page.get_by_role('heading',name='这一刻，已收藏',exact=True).wait_for(timeout=30000)
            memory=context.request.get(base+'/api/memories/'+saved['id']).json()
            assert memory['music_audio']
            assert context.request.get(base+'/'+memory['audio']).body()==original
            mixed=context.request.get(base+'/'+memory['music_audio']).body()
            assert len(mixed)>44 and mixed!=original
            assert not errors,errors
            browser.close()
            print('PASS: real Basic Pitch, cancellation/retry, local-only processing, playback, saved mix, original preserved')
    finally:
        server.should_exit=True;thread.join(5)
