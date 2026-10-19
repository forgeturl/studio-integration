import importlib.util
import io
import json
from pathlib import Path
import unittest
from urllib.error import URLError

path = Path(__file__).resolve().parents[1] / 'examples/client.py'
spec = importlib.util.spec_from_file_location('studio_example_client', path)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ClientTests(unittest.TestCase):
    def test_purchase_preserves_institution_user_and_business_identity(self):
        calls = []
        def transport(request, timeout):
            calls.append(request)
            return io.BytesIO(b'{"id":"accepted"}')
        api = client.StudioClient('example-key', 'user-123', transport=transport)
        body = {'quote_id': 'a' * 32}
        self.assertEqual(api.request('POST', '/tasks', body, idempotency_key='business-1')['id'], 'accepted')
        headers = {k.lower(): v for k, v in calls[0].header_items()}
        self.assertEqual(headers['x-api-key'], 'example-key')
        self.assertEqual(headers['x-external-user-id'], 'user-123')
        self.assertEqual(headers['idempotency-key'], 'business-1')
        self.assertEqual(json.loads(calls[0].data), body)

    def test_timeout_does_not_retry_a_purchase(self):
        calls = []
        def timeout(request, **kwargs):
            calls.append(request)
            raise URLError('timeout')
        api = client.StudioClient('example-key', 'user-123', transport=timeout)
        with self.assertRaises(URLError):
            api.request('POST', '/tasks', {'quote_id': 'a' * 32}, idempotency_key='business-1')
        self.assertEqual(len(calls), 1)

    def test_download_and_cross_origin_urls_never_receive_institution_credentials(self):
        def forbidden(*args, **kwargs):
            self.fail('Invalid destination reached transport')
        api = client.StudioClient('example-key', 'user-123', transport=forbidden)
        for path in ['https://files.example.com/video.mp4', '//files.example.com/v', '/../assets/x', '/%2e%2e/assets/x', '/x\\y']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                api.request('GET', path)

    def test_api_redirects_do_not_forward_credentials(self):
        request = client.Request('https://avm.brightguo.com/api/partner/v1/wallet', headers={'X-API-Key': 'example-key'})
        self.assertIsNone(client.NoApiRedirects().redirect_request(request, None, 302, 'Found', {}, 'https://files.example.com/'))


if __name__ == '__main__':
    unittest.main()
