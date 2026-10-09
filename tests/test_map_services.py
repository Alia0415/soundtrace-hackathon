import json
import os
import tempfile
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from soundtrace_public import create_app


class MapServices(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {'SOUNDTRACE_TENCENT_MAP_KEY': 'private-map-key',
            'SOUNDTRACE_TENCENT_MAP_SERVICE_KEY': 'private-service-key', 'SOUNDTRACE_TENCENT_MAP_STYLE': ''})
        self.env.start(); self.addCleanup(self.env.stop)
        self.client = TestClient(create_app(self.folder.name))
        self.client.post('/api/auth/register', json={'username': 'map_user', 'password': 'Temporary-map-pass-123'})

    def upstream(self, handler):
        original = httpx.AsyncClient
        return patch('soundtrace_maps.httpx.AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))

    def test_config_hides_credentials_and_old_provider_is_removed(self):
        config = self.client.get('/api/map/config')
        self.assertEqual(config.json(), {'enabled': True, 'provider': 'tencent', 'style': '', 'service_host': '/_TMapService'})
        self.assertNotIn('private-', config.text)
        self.assertEqual(self.client.get('/_AMapService/v4/map/styles').status_code, 404)
        self.assertEqual(self.client.get('/_TMapService/service/geocoder').status_code, 404)
        with patch.dict(os.environ, {'SOUNDTRACE_TENCENT_MAP_KEY': ''}):
            self.assertFalse(self.client.get('/api/map/config').json()['enabled'])
            self.assertEqual(self.client.get('/_TMapService/checkKey').status_code, 503)

    def test_key_delegation_fixed_hosts_and_overridden_credentials(self):
        expected = {'': ('pr.map.qq.com', '/pingd', 'key'),
                    '/checkKey': ('apikey.map.qq.com', '/mkey/index.php/mkey/check', 'key'),
                    '/oversea': ('overseactrl.map.qq.com', '/v4', 'apikey')}
        for path, (host, route, key_param) in expected.items():
            def handle(request):
                self.assertEqual(request.url.host, host); self.assertEqual(request.url.path, route)
                self.assertEqual(request.url.params.get_list(key_param), ['private-map-key'])
                self.assertNotIn('attacker', str(request.url))
                self.assertNotIn('cookie', request.headers)
                self.assertEqual(request.headers['referer'], 'http://testserver/')
                return httpx.Response(200, content=b'callback({"info":{"error":0}})', headers={'Content-Type': 'application/javascript'})
            with self.subTest(path=path), self.upstream(handle):
                response = self.client.get('/_TMapService'+path+'?callback=callback&key=attacker&key=attacker&key2=attacker&apikey=attacker&subkey=attacker&appid=attacker')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertNotIn('private-map-key', response.text)

    def test_coordinates_auth_validation_gps_order_and_service_key(self):
        guest = TestClient(self.client.app)
        self.assertEqual(guest.post('/api/map/coordinates', json={'locations': [[39.9,116.4]]}).status_code, 401)
        for points in ([], [[1,2]]*41, [[91,0]], [[0,181]], [['39.9',116.4]], [[True,0]], [{'lat': 1, 'lng': 2}]):
            self.assertEqual(self.client.post('/api/map/coordinates', json={'locations': points}).status_code, 400)
        def handle(request):
            self.assertEqual(request.url.host, 'apis.map.qq.com')
            self.assertEqual(request.url.path, '/ws/coord/v1/translate')
            self.assertEqual(request.url.params['key'], 'private-service-key')
            self.assertEqual(request.url.params['type'], '1')
            self.assertEqual(request.url.params['locations'], '39.9,116.4;31.2,121.4')
            return httpx.Response(200, json={'status': 0, 'locations': [{'lat':39.905,'lng':116.405},{'lat':31.205,'lng':121.405}]})
        with self.upstream(handle):
            response = self.client.post('/api/map/coordinates', json={'locations': [[39.9,116.4],[31.2,121.4]]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['locations'][0], {'lat':39.905,'lng':116.405})

    def test_upstream_errors_redirects_and_invalid_coordinates(self):
        payloads = [{'status': 110, 'message': 'private-service-key'},
                    {'status': 0, 'locations': []},
                    {'status': 0, 'locations': [{'lat': 100, 'lng': 120}]},
                    {'status': 0, 'locations': [{'lat': None, 'lng': 120}]}, []]
        for payload in payloads:
            with self.subTest(payload=payload), self.upstream(lambda r: httpx.Response(200,json=payload)):
                response = self.client.post('/api/map/coordinates', json={'locations': [[39.9,116.4]]})
                self.assertEqual(response.status_code, 502)
                self.assertNotIn('private-service-key', response.text)
        calls = []
        def redirect(request):
            calls.append(request.url.host)
            return httpx.Response(302, headers={'Location':'https://untrusted.test/'})
        with self.upstream(redirect):
            self.assertEqual(self.client.get('/_TMapService/checkKey').status_code, 502)
        self.assertEqual(calls, ['apikey.map.qq.com'])


if __name__ == '__main__': unittest.main()
