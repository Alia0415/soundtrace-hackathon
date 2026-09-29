import http.client
import json
import tempfile
import threading
import time
import wave
import io
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import soundtrace_api as api
import soundtrace_mvp as pipeline


class APITests(unittest.TestCase):
    def setUp(self):
        # Malformed requests must never run the real worker or overwrite demo outputs.
        submit_patch = patch.object(api.WORKER, 'submit')
        submit_patch.start()
        self.addCleanup(submit_patch.stop)

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_health_and_missing_job(self):
        self.assertEqual(self.request('GET', '/health')[0], 200)
        self.assertEqual(self.request('GET', '/v1/jobs/missing')[0], 404)

    def test_non_object_json_is_rejected_without_disconnecting(self):
        for body in ('[]', 'null', '42', '"hello"'):
            with self.subTest(body=body):
                self.assertEqual(self.request('POST', '/v1/demo-jobs', body)[0], 400)

    def test_invalid_duration(self):
        for duration in (0, 61, None, 'invalid'):
            with self.subTest(duration=duration):
                body = json.dumps({'duration': duration})
                self.assertEqual(self.request('POST', '/v1/demo-jobs', body)[0], 400)

    def test_invalid_body_length_is_rejected_before_read(self):
        for length in ('-1', '1000000'):
            with self.subTest(length=length):
                self.assertIn(self.request('POST', '/v1/demo-jobs', headers={'Content-Length': length})[0], (400, 413))

    def test_create_and_poll_job(self):
        with patch.object(api.WORKER, 'submit') as submit:
            status, _, raw = self.request('POST', '/v1/demo-jobs', '{"duration":30}')
            self.assertEqual(status, 202)
            job = json.loads(raw)
            submit.assert_called_once()
            status, _, raw = self.request('GET', '/v1/jobs/' + job['id'])
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)['status'], 'queued')

    def test_job_audio_is_downloadable_but_other_files_are_not(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(api, 'JOB_OUTPUTS', Path(folder)):
            job = api.STORE.create('birds', 30)
            output = Path(folder) / job.id / 'mix.wav'
            output.parent.mkdir()
            output.write_bytes(b'RIFF-test-audio')
            relative = f'outputs/jobs/{job.id}/mix.wav'
            job.result = {'outputs': {'mix': relative}}
            job.status = 'succeeded'
            status, headers, data = self.request('GET', '/' + relative)
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'audio/wav')
            self.assertEqual(data, output.read_bytes())
            self.assertEqual(self.request('GET', f'/outputs/jobs/{job.id}/../../soundtrace_api.py')[0], 404)
            self.assertEqual(self.request('GET', f'/outputs/jobs/{job.id}/unlisted.wav')[0], 404)

    def test_real_worker_renders_and_serves_a_30_second_stereo_wav(self):
        # Isolate the real pipeline so an audit never rewrites checked-in demo files.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = api.JobStore()
            worker = api.DemoWorker(store)
            with patch.object(api, 'STORE', store), patch.object(api, 'ROOT', root), \
                 patch.object(api, 'JOB_OUTPUTS', root / 'outputs' / 'jobs'), \
                 patch.object(pipeline, 'ROOT', root), patch.object(pipeline, 'OUT', root / 'outputs'):
                job = store.create('birds', 30)
                worker.submit(job)
                deadline = time.monotonic() + 45
                while job.status not in ('succeeded', 'failed') and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertEqual(job.status, 'succeeded', job.error)
                self.assertTrue(job.result['target_backend'].startswith('dsp_'))
                status, _, data = self.request('GET', '/' + job.result['outputs']['mix'])
                self.assertEqual(status, 200)
                with wave.open(io.BytesIO(data)) as audio:
                    self.assertEqual(audio.getnchannels(), 2)
                    self.assertEqual(audio.getnframes(), audio.getframerate() * 30)


if __name__ == '__main__':
    unittest.main()
