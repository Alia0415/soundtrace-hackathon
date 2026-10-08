import asyncio
import base64
import io
import json
import os
import tempfile
import unittest
import wave
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from soundtrace_art import generate_art, make_prompt
from soundtrace_public import create_app


def picture(color='#8dd9ff'):
    out = io.BytesIO()
    Image.new('RGB', (400, 300), color).save(out, format='JPEG')
    return out.getvalue()


def audio():
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b'\0\0'*8000)
    return out.getvalue()


class ArtServices(unittest.TestCase):
    def test_domestic_reference_protocol_private_image_and_single_result(self):
        calls = []
        def upstream(request):
            calls.append(request)
            self.assertEqual(str(request.url), 'https://ark.cn-beijing.volces.com/api/v3/images/generations')
            self.assertEqual(request.headers['Authorization'], 'Bearer mock-secret')
            body = json.loads(request.content)
            self.assertEqual(body['image'], 'data:image/jpeg;base64,'+base64.b64encode(picture()).decode())
            self.assertEqual(body['response_format'], 'b64_json')
            self.assertTrue(body['watermark']); self.assertFalse(body['stream'])
            self.assertNotIn('30.2', body['prompt']); self.assertNotIn('私人住址', body['prompt'])
            self.assertNotIn('sequential_image_generation', body)
            return httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(picture('#fff')).decode()}]})
        original = httpx.AsyncClient
        with patch.dict(os.environ, {'SOUNDTRACE_ARK_KEY':'mock-secret'}), patch('soundtrace_art.httpx.AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw)):
            result = asyncio.run(generate_art(picture(), {'notes':'湖边的风','lat':30.2,'location':'私人住址'}))
        self.assertEqual(result, picture('#fff')); self.assertEqual(len(calls), 1)

    def test_jobs_ownership_private_download_original_preserved_and_limits(self):
        async def provider(photo, memory):
            self.assertTrue(photo); self.assertEqual(memory['title'], '湖边')
            return picture('#fff')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOUNDTRACE_ARK_KEY':'mock-secret','SOUNDTRACE_IMAGE_DAILY_LIMIT':'1'}), patch('soundtrace_art.generate_art', provider):
            app = create_app(tmp); alice = TestClient(app); bob = TestClient(app); guest = TestClient(app)
            for client, username in ((alice,'alice'), (bob,'bob')):
                self.assertEqual(client.post('/api/auth/register',json={'username':username,'password':'Very-long-password-123'}).status_code,200)
            memory = alice.post('/api/memories',data={'title':'湖边','scene':'autumn-lake'}, files=[('audio',('a.wav',audio(),'audio/wav')),('images',('photo.jpg',picture(),'image/jpeg'))]).json()
            mid = memory['id']; raw = alice.get('/'+memory['images'][0]).content
            self.assertEqual(bob.post('/api/art/jobs',json={'memory_id':mid,'consent':True}).status_code,404)
            self.assertEqual(alice.post('/api/art/jobs',json={'memory_id':mid}).status_code,400)
            self.assertEqual(alice.post('/api/art/jobs',json={'memory_id':mid,'image_index':-1,'consent':True}).status_code,400)
            self.assertEqual(alice.post('/api/art/jobs',json={'memory_id':mid,'image_index':True,'consent':True}).status_code,400)
            created = alice.post('/api/art/jobs',json={'memory_id':mid,'consent':True})
            self.assertEqual(created.status_code,202,created.text)
            jid = created.json()['job_id']; job = alice.get('/api/art/jobs/'+jid).json()
            self.assertEqual(job['status'],'done',job); self.assertEqual(bob.get('/api/art/jobs/'+jid).status_code,404)
            updated = alice.get('/api/memories/'+mid).json()
            self.assertEqual(updated['images'],memory['images']); self.assertEqual(updated['audio'],memory['audio']); self.assertIsNone(updated['music_audio'])
            self.assertEqual(updated['art_status'],'stylized'); self.assertEqual(updated['scene_art_source'],memory['images'][0])
            self.assertEqual(alice.get('/'+memory['images'][0]).content,raw)
            for ref in job['results'].values():
                self.assertEqual(alice.get('/'+ref).status_code,200)
                self.assertEqual(bob.get('/'+ref).status_code,404); self.assertEqual(guest.get('/'+ref).status_code,404)
            self.assertEqual(alice.post('/api/art/jobs',json={'memory_id':mid,'consent':True}).status_code,429)
            self.assertEqual(bob.post('/api/memories/'+mid+'/background',json={'mode':'photo'}).status_code,404)
            self.assertEqual(alice.post('/api/memories/'+mid+'/background',json={'mode':'photo'}).json()['background_mode'],'photo')
            self.assertEqual(alice.post('/api/memories/'+mid+'/background',json={'mode':'stylized'}).json()['background_mode'],'stylized')
            remix = alice.post('/api/memories/'+mid+'/music',data={'title':'新的湖边日记'},files={'music_audio':('mix.wav',audio(),'audio/wav')})
            self.assertEqual(remix.status_code,200,remix.text)
            self.assertEqual(remix.json()['scene_art'],updated['scene_art']); self.assertEqual(remix.json()['art_status'],'stylized')
            alice.delete('/api/memories/'+mid)
            self.assertEqual(alice.get('/api/art/jobs/'+jid).status_code,404)
            self.assertEqual(alice.get('/'+updated['scene_art']).status_code,404)

    def test_service_failure_preserves_original_photo_and_does_not_leak_tokens(self):
        async def failure(*args):
            raise httpx.HTTPStatusError('Bearer mock-secret https://private-provider.test', request=httpx.Request('POST','https://private-provider.test'), response=httpx.Response(401))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOUNDTRACE_ARK_KEY':'mock-secret'}), patch('soundtrace_art.generate_art', failure):
            client = TestClient(create_app(tmp)); client.post('/api/auth/register',json={'username':'alice','password':'Very-long-password-123'})
            memory = client.post('/api/memories',files=[('audio',('a.wav',audio(),'audio/wav')),('images',('a.jpg',picture(),'image/jpeg'))]).json()
            jid = client.post('/api/art/jobs',json={'memory_id':memory['id'],'consent':True}).json()['job_id']
            job = client.get('/api/art/jobs/'+jid); self.assertEqual(job.json()['status'],'failed'); self.assertNotIn('mock-secret',job.text)
            updated = client.get('/api/memories/'+memory['id']).json()
            self.assertEqual(updated['cover_vinyl'],memory['cover_vinyl']); self.assertNotIn('scene_art',updated)
            self.assertEqual(client.get('/'+memory['images'][0]).status_code,200)
            with patch.dict(os.environ, {'SOUNDTRACE_ARK_KEY':''}):
                self.assertFalse(client.get('/api/art/config').json()['enabled'])
                self.assertEqual(client.post('/api/art/jobs',json={'memory_id':memory['id'],'consent':True}).status_code,503)

    def test_invalid_provider_output_is_rejected(self):
        original = httpx.AsyncClient
        with patch.dict(os.environ, {'SOUNDTRACE_ARK_KEY':'mock-secret'}), patch('soundtrace_art.httpx.AsyncClient', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200,json={'data':[{'url':'http://127.0.0.1/secret'}]})), **kw)):
            with self.assertRaises(RuntimeError):
                asyncio.run(generate_art(picture(), {}))


if __name__ == '__main__': unittest.main()
