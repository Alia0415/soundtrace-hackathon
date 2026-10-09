"""Browser-to-backend regression with only the remote GPU inference mocked."""
import io, os, sys, tempfile, threading, time, wave
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app

out = io.BytesIO()
with wave.open(out, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b'\0\0' * 16000)
audio = out.getvalue()
calls = []
async def provider(content, kind, target, stage):
    assert content == audio
    calls.append((kind, target)); stage('处理测试素材')
    return {'tags': [{'en': 'Birdsong', 'zh': '鸟鸣'}]} if kind == 'analyze' else {'audio': audio}

with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': 'http://private.test', 'SOUNDTRACE_MUSIC_PROVIDER': 'none'}), patch('soundtrace_processing.process_audio', provider):
    server = uvicorn.Server(uvicorn.Config(create_app(folder), host='127.0.0.1', port=0, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    for _ in range(100):
        if server.started: break
        time.sleep(.05)
    assert server.started
    base = 'http://127.0.0.1:' + str(server.servers[0].sockets[0].getsockname()[1])
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True)
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            assert context.request.post(base+'/api/auth/register', data={'username': 'sound_test', 'password': 'Temporary-sound-pass-123'}).ok
            saved = context.request.post(base+'/api/memories', multipart={'audio': {'name': 'sound.wav', 'mimeType': 'audio/wav', 'buffer': audio}}).json()
            page = context.new_page(); errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base+'/studio?memory='+saved['id']+'#rec')
            for label in ['晴天', '平静', '散步', '选择音乐 →', '轻钢琴']:
                page.get_by_role('button', name=label, exact=True).click()
            page.locator('.timeline').wait_for()
            page.get_by_role('button', name='细调 ＋', exact=True).click()
            page.get_by_role('button', name='辨认录音中的声音', exact=True).click()
            page.locator('.tag-row').get_by_role('button', name='鸟鸣', exact=True).click()
            page.get_by_role('button', name='提取声音', exact=True).click()
            page.wait_for_function("document.querySelectorAll('.track-label').length===2")
            assert calls == [('analyze', ''), ('extract', 'Birdsong')], calls
            page.get_by_role('button', name='播放', exact=True).click()
            page.get_by_role('button', name='暂停', exact=True).click()
            page.get_by_role('button', name='收藏这段声音 ↗', exact=True).click()
            page.get_by_role('button', name='保存这段记忆 ↗', exact=True).click()
            page.get_by_role('heading', name='这一刻，已收藏', exact=True).wait_for()
            memory = context.request.get(base+'/api/memories/'+saved['id']).json()
            assert memory['music_audio']
            assert context.request.get(base+'/'+memory['audio']).body() == audio
            assert not errors, errors
            browser.close()
            print('PASS: browser analysis, tag selection, extraction track, playback and save; GPU inference mocked')
    finally:
        server.should_exit = True; thread.join(5)
