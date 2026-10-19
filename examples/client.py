"""Standard-library partner client. Importing this module makes no requests."""
import argparse
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoApiRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def open_api(request, timeout):
    return build_opener(NoApiRedirects()).open(request, timeout=timeout)


class StudioClient:
    def __init__(self, api_key, external_user_id, base_url='https://avm.brightguo.com/api/partner/v1', *, transport=open_api):
        parsed = urlsplit(base_url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path.rstrip('/') != '/api/partner/v1'):
            raise ValueError('Use the agreed HTTPS partner API base URL')
        if not api_key or not external_user_id or external_user_id != external_user_id.strip():
            raise ValueError('Set the institution API key and stable external user ID')
        self.base_url, self.key, self.user, self.transport = base_url.rstrip('/'), api_key, external_user_id, transport

    @classmethod
    def from_env(cls):
        return cls(os.environ['STUDIO_API_KEY'], os.environ['STUDIO_EXTERNAL_USER_ID'],
                   os.getenv('STUDIO_API_BASE_URL', 'https://avm.brightguo.com/api/partner/v1'))

    def request(self, method, path, body=None, *, idempotency_key=None):
        parsed = urlsplit(path)
        if (not path.startswith('/') or path.startswith('//') or parsed.scheme or parsed.netloc
                or parsed.fragment or any(part in ('.', '..') for part in parsed.path.split('/'))
                or '%' in parsed.path or '\\' in path):
            raise ValueError('Only relative partner API paths are accepted; download URLs use a separate client')
        headers = {'X-API-Key': self.key, 'X-External-User-ID': self.user, 'Accept': 'application/json'}
        if idempotency_key is not None:
            headers['Idempotency-Key'] = idempotency_key
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(self.base_url + path, data=data, headers=headers, method=method.upper())
        # HTTP errors and timeouts are returned to the caller; purchases are never retried here.
        with self.transport(request, timeout=30) as response:
            return json.load(response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Read-only connectivity example')
    parser.add_argument('operation', choices=['catalog', 'wallet'])
    args = parser.parse_args()
    print(json.dumps(StudioClient.from_env().request('GET', '/' + args.operation), ensure_ascii=False, indent=2))
