import asyncio
import io
import json
import os
import tempfile
import unittest
import wave
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from soundtrace_public import create_app
from soundtrace_music import generate_music


def wav(sample=100):
    out = io.BytesIO()
    with wave.open(out, 'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000)
        stream.writeframes(int(sample).to_bytes(2,'little',signed=True)*32000)
    return out.getvalue()


class MaterialFlowTests(unittest.TestCase):
    def test_import_separate_library_selected_audio_generation_and_restart(self):
        async def separate(content, stage):
            self.assertEqual(content,wav());return {'stems':[{'title':'鼓声','audio':wav(200)}, {'title':'其他声音','audio':wav(300)}]}
        async def generate(body, stage):
            self.assertEqual(body['_source_audio'],wav(200))
            self.assertEqual(body['notes'],'保留鼓点，清晨轻爵士')
            return wav(500)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'SOUNDTRACE_MUREKA_KEY':'test','SOUNDTRACE_MUSIC_PROVIDER':'mureka'}):
            app = create_app(folder);alice=TestClient(app);bob=TestClient(app)
            for client,name in [(alice,'alice'),(bob,'bob')]:client.post('/api/auth/register',json={'username':name,'password':'Materials-test-2026!'}).raise_for_status()
            with patch('soundtrace_media.convert',return_value=wav()):
                response=alice.post('/api/material-import',files={'file':('day.mp4',b'private-video','video/mp4')})
            self.assertEqual(response.status_code,201,response.text);memory=response.json()
            self.assertEqual(alice.get('/'+memory['original_file']).content,b'private-video')
            self.assertEqual(bob.get('/'+memory['original_file']).status_code,404)
            with patch('soundtrace_processing.separate_stems',separate):
                job=alice.post('/api/sound/jobs',json={'memory_id':memory['id'],'type':'separate'}).json()
            result=alice.get('/api/sound/jobs/'+job['job_id']).json()
            self.assertEqual(result['status'],'done',result)
            materials=alice.get('/api/material-library').json()['materials']
            self.assertEqual(len(materials),3)
            selected=next(item for item in materials if item['title']=='鼓声')
            self.assertEqual(bob.get('/api/material-library').json()['materials'],[])
            body={'memory_id':memory['id'],'source_ref':selected['audio'],'notes':'保留鼓点，清晨轻爵士'}
            self.assertEqual(bob.post('/api/music/jobs',json=body).status_code,404)
            with patch('soundtrace_music.generate_music',generate):
                job=alice.post('/api/music/jobs',json=body).json()
            music=alice.get('/api/music/jobs/'+job['job_id']).json()
            self.assertEqual(music['status'],'done',music)
            self.assertEqual(music['results']['generation_mode'],'audio-conditioned')
            self.assertEqual(music['results']['source_ref'],selected['audio'])
            saved=alice.post('/api/memories/'+memory['id']+'/music',files={'music_audio':('mix.wav',wav(500),'audio/wav')},data={'music_source_ref':selected['audio'],'title':'new music title'})
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(saved.json()['music_source_ref'],selected['audio'])
            self.assertEqual(saved.json()['music_duration'],2)
            originals=[m for m in alice.get('/api/material-library').json()['materials'] if m['material_kind']=='original']
            self.assertEqual(originals[0]['title'],'day')
            rejected=alice.post('/api/memories/'+memory['id']+'/music',files={'music_audio':('mix.wav',wav(500),'audio/wav')},data={'music_source_ref':'outputs/not-owned.wav'})
            self.assertEqual(rejected.status_code,400)
            reopened=TestClient(create_app(folder));reopened.post('/api/auth/login',json={'username':'alice','password':'Materials-test-2026!'}).raise_for_status()
            self.assertEqual(len(reopened.get('/api/material-library').json()['materials']),3)
            self.assertEqual(reopened.get('/'+selected['audio']).content,wav(200))

    def test_audio_and_prompt_are_sent_together_to_track_api(self):
        calls=[]
        def upstream(request):
            calls.append(request)
            if request.url.path=='/v1/files/upload':
                self.assertIn(b'encoded-source-audio',request.content)
                return httpx.Response(200,json={'id':'source-id'})
            if request.url.path=='/v1/track/generate':
                body=json.loads(request.content)
                self.assertEqual(body['upload_audio_id'],'source-id')
                self.assertEqual(body['generate_type'],'Instrumental')
                self.assertIn('morning',body['prompt'])
                return httpx.Response(200,json={'id':'track-id'})
            if request.url.path=='/v1/song/query/track-id':return httpx.Response(200,json={'status':'succeeded','choices':[{'wav_url':'https://cdn.test/output.wav'}]})
            self.assertNotIn('Authorization',request.headers)
            return httpx.Response(200,content=wav(500))
        original=httpx.AsyncClient
        async def immediate(_):pass
        with patch.dict(os.environ,{'SOUNDTRACE_MUSIC_PROVIDER':'mureka','SOUNDTRACE_MUREKA_KEY':'test'}), patch('soundtrace_media.convert',return_value=b'encoded-source-audio'),patch('soundtrace_music.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(upstream),**kw)),patch('soundtrace_music.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]),patch('soundtrace_music.asyncio.sleep',immediate):
            result=asyncio.run(generate_music({'_source_audio':wav(),'notes':'morning','style':'jazz'},lambda *args:None))
        self.assertEqual(result,wav(500));self.assertEqual(len(calls),4)
