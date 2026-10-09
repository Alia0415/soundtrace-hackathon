import asyncio
import io
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from soundtrace_public import create_app
from soundtrace_music import generate_music, make_prompt


def wav():
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*16000)
    return out.getvalue()


class GenerationServices(unittest.TestCase):
    def test_mureka_domestic_protocol_and_cdn_does_not_receive_key(self):
        calls=[]
        def upstream(request):
            calls.append(request)
            if request.url.path=='/v1/instrumental/generate':
                body=json.loads(request.content);self.assertEqual(body['n'],1);self.assertEqual(body['model'],'mureka-9.5')
                return httpx.Response(200,json={'id':'task-one','status':'queued'})
            if request.url.path=='/v1/instrumental/query/task-one':
                return httpx.Response(200,json={'status':'succeeded','choices':[{'wav_url':'https://audio.test/result.wav'}]})
            self.assertNotIn('Authorization',request.headers)
            return httpx.Response(200,content=wav())
        original=httpx.AsyncClient
        async def immediate(seconds):pass
        with patch.dict(os.environ,{'SOUNDTRACE_MUSIC_PROVIDER':'mureka','SOUNDTRACE_MUREKA_KEY':'private-key'}),patch('soundtrace_music.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(upstream),**kwargs)),patch('soundtrace_music.asyncio.sleep',immediate),patch('soundtrace_music.socket.getaddrinfo',return_value=[(2,1,6,'',('1.1.1.1',443))]):
            self.assertEqual(asyncio.run(generate_music({'style':'piano'},lambda *args:None)),wav())
        self.assertEqual(calls[0].url.host,'api.mureka.cn');self.assertEqual(len(calls),3)

    def test_acestep_official_protocol_and_no_external_file_redirect(self):
        calls=[]
        def upstream(request):
            calls.append(request)
            if request.url.path=='/release_task':
                payload=json.loads(request.content)
                self.assertEqual(payload['model'],'acestep-v15-turbo')
                self.assertFalse(payload['thinking']);self.assertEqual(payload['batch_size'],1)
                self.assertEqual(payload['inference_steps'],8)
                return httpx.Response(200,json={'code':200,'data':{'task_id':'t'}})
            if request.url.path=='/query_result':
                self.assertEqual(json.loads(request.content),{'task_id_list':['t']})
                return httpx.Response(200,json={'code':200,'data':[{'status':1,'result':json.dumps([{'file':'/v1/audio?path=test.wav'}])}]})
            return httpx.Response(200,content=wav())
        original=httpx.AsyncClient
        async def immediate(seconds):pass
        with patch.dict(os.environ,{'SOUNDTRACE_MUSIC_PROVIDER':'acestep','SOUNDTRACE_ACE_URL':'http://gpu.test','SOUNDTRACE_ACE_KEY':'test-secret'}),patch('soundtrace_music.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(upstream),**kwargs)),patch('soundtrace_music.asyncio.sleep',immediate):
            result=asyncio.run(generate_music({'title':'湖边','style':'piano'},lambda *args:None))
        self.assertEqual(result,wav());self.assertEqual(len(calls),3)
        self.assertTrue(all(c.headers['Authorization']=='Bearer test-secret' for c in calls))

    def test_music_jobs_ownership_persistence_download_and_quota(self):
        async def provider(body,stage):
            self.assertEqual(body['style'],'piano');stage('测试生成中','upstream');return wav()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SOUNDTRACE_MUSIC_PROVIDER':'acestep','SOUNDTRACE_ACE_URL':'http://gpu.test','SOUNDTRACE_MUSIC_DAILY_LIMIT':'1'}),patch('soundtrace_music.generate_music',provider):
            app=create_app(tmp);alice=TestClient(app);bob=TestClient(app)
            for client,user in ((alice,'alice'),(bob,'bob')):
                self.assertEqual(client.post('/api/auth/register',json={'username':user,'password':'Very-long-password-123'}).status_code,200)
            mid=alice.post('/api/memories',files={'audio':('sound.wav',wav(),'audio/wav')}).json()['id']
            self.assertEqual(bob.post('/api/music/jobs',json={'memory_id':mid}).status_code,404)
            created=alice.post('/api/music/jobs',json={'memory_id':mid,'style':'piano'})
            self.assertEqual(created.status_code,202,created.text);jid=created.json()['job_id']
            job=alice.get('/api/music/jobs/'+jid).json();self.assertEqual(job['status'],'done')
            self.assertEqual(bob.get('/api/music/jobs/'+jid).status_code,404)
            ref=job['results']['generated'];self.assertEqual(alice.get('/'+ref).content,wav())
            self.assertEqual(bob.get('/'+ref).status_code,404)
            self.assertEqual(alice.post('/api/music/jobs',json={'memory_id':mid}).status_code,429)
            with app.state.data_dir.joinpath('soundtrace.sqlite3').open('rb') as db:self.assertGreater(len(db.read()),0)
            self.assertIsNone(alice.get('/api/memories/'+mid).json()['music_audio'])

    def test_map_config_keeps_security_code_private_and_demo_entry_is_scoped(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SOUNDTRACE_AMAP_KEY':'public-key','SOUNDTRACE_AMAP_SECURITY_CODE':'private-security'}):
            client=TestClient(create_app(tmp))
            config=client.get('/api/map/config');self.assertTrue(config.json()['enabled']);self.assertNotIn('private-security',config.text)
            self.assertEqual(client.get('/_AMapService/arbitrary-path').status_code,404)
            self.assertIn('soundtrace-demo.js',client.get('/demo/album').text)
            self.assertNotIn('soundtrace-demo.js',client.get('/album').text)
            self.assertIn('href="/demo"',client.get('/').text)
            self.assertIn('studio-root',client.get('/capture').text)
            self.assertNotIn('fTitle',client.get('/capture').text)

    def test_prompt_uses_context_without_coordinates(self):
        prompt=make_prompt({'style':'jazz','notes':'风吹树叶','mood':'平静','lat':30.258,'lng':120.149})
        self.assertIn('jazz',prompt);self.assertIn('风吹树叶',prompt);self.assertNotIn('30.258',prompt)


if __name__=='__main__':unittest.main()
