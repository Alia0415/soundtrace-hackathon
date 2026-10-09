import os
import unittest
from unittest.mock import patch
import httpx
from soundtrace_network import provider_error, trust_environment


class NetworkServices(unittest.TestCase):
    def test_proxy_override_is_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(trust_environment())
        with patch.dict(os.environ, {'SOUNDTRACE_HTTP_TRUST_ENV': 'false'}):
            self.assertFalse(trust_environment())

    def test_errors_explain_recovery_without_leaking_provider_payload(self):
        for status, expected in [(401, 'Key'), (402, '余额'), (403, '权限'), (404, '模型'), (429, '额度')]:
            response = httpx.Response(status, request=httpx.Request('POST','https://provider.test/?key=secret'), text='secret')
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                message = provider_error(error, '音乐服务')
            self.assertIn(expected, message)
            self.assertNotIn('secret', message)
            self.assertNotIn('provider.test', message)
        self.assertIn('代理', provider_error(httpx.ConnectError('private network'), '音乐服务'))
