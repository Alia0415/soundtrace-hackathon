import asyncio
import io
import json
import os
import sqlite3
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from soundtrace_public import create_app
from soundtrace_processing import process_audio


def wav():
    out = io.BytesIO()
    with wave.open(out, 'wb') as file:
        file.setnchannels(1); file.setsampwidth(2); file.setframerate(16000)
        file.writeframes(b'\0\0' * 1600)
    return out.getvalue()


class ProcessingServices(unittest.TestCase):
    def test_private_worker_protocol_and_rejects_external_results(self):
        original = httpx.AsyncClient
        async def immediate(_): pass
        for ref in ('outputs/service_jobs/task/denoised.wav', 'https://other.test/steal.wav',
                    'outputs/service_jobs/other/denoised.wav', 'outputs/service_jobs/task/../../private.wav'):
            calls = []
            def upstream(request):
                calls.append(request)
                self.assertEqual(request.url.host, 'gpu.test')
                self.assertTrue(request.headers['Authorization'].startswith('Basic '))
                if request.url.path == '/api/upload':
                    return httpx.Response(200, json={'upload_id': 'sound.wav'})
                if request.url.path == '/api/jobs':
                    body = json.loads(request.content)
                    self.assertEqual(body, {'type': 'extract', 'upload_id': 'sound.wav', 'target_en': 'Birdsong', 'auto_register': False})
                    return httpx.Response(200, json={'job_id': 'task'})
                if request.url.path == '/api/jobs/task':
                    return httpx.Response(200, json={'status': 'done', 'results': {'denoised': ref}})
                return httpx.Response(200, content=wav())
            with self.subTest(ref=ref), patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': 'http://gpu.test', 'SOUNDTRACE_GPU_PASSWORD': 'private'}), patch('soundtrace_processing.httpx.AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw)), patch('soundtrace_processing.asyncio.sleep', immediate):
                if ref == 'outputs/service_jobs/task/denoised.wav':
                    self.assertEqual(asyncio.run(process_audio(wav(), 'extract', 'Birdsong', lambda _: None)), {'audio': wav()})
                    self.assertEqual(len(calls), 4)
                else:
                    with self.assertRaises(RuntimeError):
                        asyncio.run(process_audio(wav(), 'extract', 'Birdsong', lambda _: None))
                    self.assertEqual(len(calls), 3)

    def test_analysis_protocol_returns_only_bounded_labels(self):
        def upstream(request):
            if request.url.path == '/api/upload':
                return httpx.Response(200, json={'upload_id': 'sound.wav'})
            self.assertEqual(request.url.path, '/api/analyze/sound.wav')
            return httpx.Response(200, json={'tags': [{'en': 'Birdsong', 'zh': '鸟叫', 'internal': 'private'}] * 20})
        original = httpx.AsyncClient
        with patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': 'http://gpu.test'}), patch('soundtrace_processing.httpx.AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw)):
            result = asyncio.run(process_audio(wav(), 'analyze', '', lambda _: None))
        self.assertEqual(result, {'tags': [{'en': 'Birdsong', 'zh': '鸟叫'}] * 12})

    def test_ownership_download_quota_and_original_preserved(self):
        async def provider(content, kind, target, stage):
            self.assertEqual(content, wav()); stage('处理中')
            return {'audio': wav()}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': 'http://gpu.test', 'SOUNDTRACE_SOUND_DAILY_LIMIT': '1'}), patch('soundtrace_processing.process_audio', provider):
            app = create_app(tmp); alice = TestClient(app); bob = TestClient(app)
            for client, name in ((alice, 'alice'), (bob, 'bob')):
                self.assertEqual(client.post('/api/auth/register', json={'username': name, 'password': 'Very-long-password-123'}).status_code, 200)
            memory = alice.post('/api/memories', files={'audio': ('sound.wav', wav(), 'audio/wav')}).json()
            body = {'memory_id': memory['id'], 'type': 'extract', 'target': 'Birdsong'}
            self.assertEqual(bob.post('/api/sound/jobs', json=body).status_code, 404)
            created = alice.post('/api/sound/jobs', json=body)
            self.assertEqual(created.status_code, 202, created.text)
            endpoint = '/api/sound/jobs/' + created.json()['job_id']
            job = alice.get(endpoint).json(); self.assertEqual(job['status'], 'done', job)
            self.assertEqual(bob.get(endpoint).status_code, 404)
            self.assertEqual(bob.post(endpoint+'/cancel').status_code, 404)
            ref = job['results']['denoised']
            self.assertEqual(alice.get('/'+ref).content, wav())
            self.assertEqual(bob.get('/'+ref).status_code, 404)
            self.assertEqual(alice.get('/'+memory['audio']).content, wav())
            self.assertIsNone(alice.get('/api/memories/'+memory['id']).json()['music_audio'])
            self.assertEqual(alice.post('/api/sound/jobs', json=body).status_code, 429)

    def test_cancel_and_invalid_output_leave_no_media(self):
        for mode in ('cancel', 'invalid'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': 'http://gpu.test'}):
                app = create_app(tmp); client = TestClient(app)
                client.post('/api/auth/register', json={'username': 'alice', 'password': 'Very-long-password-123'})
                memory = client.post('/api/memories', files={'audio': ('sound.wav', wav(), 'audio/wav')}).json()
                async def provider(content, kind, target, stage):
                    if mode == 'cancel':
                        with sqlite3.connect(Path(tmp)/'soundtrace.sqlite3') as con:
                            con.execute('UPDATE sound_jobs SET cancel_requested=1')
                        con.close()
                    return {'audio': wav() if mode == 'cancel' else b'not-a-wave'}
                with patch('soundtrace_processing.process_audio', provider):
                    created = client.post('/api/sound/jobs', json={'memory_id': memory['id'], 'type': 'extract', 'target': 'Birdsong'})
                job = client.get('/api/sound/jobs/'+created.json()['job_id']).json()
                self.assertEqual(job['status'], 'cancelled' if mode == 'cancel' else 'failed', job)
                self.assertIsNone(job['results'])
                self.assertEqual(list(Path(tmp).rglob('extracted-*.wav')), [])
                self.assertEqual(client.get('/'+memory['audio']).content, wav())

    def test_unconfigured_and_invalid_requests(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': ''}):
            client = TestClient(create_app(tmp))
            self.assertEqual(client.post('/api/sound/jobs', json={}).status_code, 401)
            client.post('/api/auth/register', json={'username': 'alice', 'password': 'Very-long-password-123'})
            self.assertFalse(client.get('/api/health').json()['sound_analysis'])
            self.assertTrue(client.get('/api/health').json()['local_humming'])
            self.assertEqual(client.post('/api/sound/jobs', json={}).status_code, 503)
            with patch.dict(os.environ, {'SOUNDTRACE_GPU_URL': 'http://gpu.test'}):
                self.assertEqual(client.post('/api/sound/jobs', content='{').status_code, 400)
                self.assertEqual(client.post('/api/sound/jobs', json=[]).status_code, 400)
                self.assertEqual(client.post('/api/sound/jobs', json={'memory_id': 'x', 'type': 'extract', 'target': ''}).status_code, 400)


if __name__ == '__main__': unittest.main()
