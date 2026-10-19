"""Validate the published integration bundle without contacting Studio."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from jsonschema import Draft202012Validator
from openapi_spec_validator import validate


ROOT = Path(__file__).resolve().parents[1]


def digest(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if (not path.is_file() or any(p in ('.git', '__pycache__', '.venv') for p in path.relative_to(root).parts)
                or path.name in ('deployment.json', '.env') or path.suffix == '.pyc'):
            continue
        files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def check(root=ROOT, *, release=False):
    spec = json.loads((root / 'openapi.json').read_text())
    version = json.loads((root / 'version.json').read_text())
    deployment = json.loads((root / 'deployment.json').read_text())
    assert re.fullmatch(r'\d+\.\d+\.\d+', version['version']), 'Invalid release version'
    assert spec['info']['version'] == version['version'] == deployment['version'], 'Version mismatch'
    assert spec['servers'] == [{'url': 'https://avm.brightguo.com'}], 'Unexpected production origin'
    assert deployment['bundle_sha256'] == digest(root), 'Bundle digest mismatch'
    assert deployment['contract_sha256'] == hashlib.sha256((root / 'openapi.json').read_bytes()).hexdigest(), 'Contract digest mismatch'
    assert re.fullmatch('[0-9a-f]{40}', deployment['source_commit']), 'Missing source commit'
    assert f"## [{version['version']}]" in (root / 'CHANGELOG.md').read_text(), 'Missing version changelog'
    previous = subprocess.run(['git', 'show', 'v' + version['version'] + ':deployment.json'],
                              cwd=root, capture_output=True, text=True)
    if previous.returncode == 0:
        assert json.loads(previous.stdout)['bundle_sha256'] == deployment['bundle_sha256'], 'Published version changed; increase the version'
    validate(spec)
    for path, operations in spec['paths'].items():
        assert path.startswith(('/api/partner/v1/', '/api/integrations/')), path
        assert '/sso/session' not in path, 'Browser session handoff is not a partner API'
        for method, operation in operations.items():
            if method not in ('get', 'post', 'put', 'patch', 'delete'):
                continue
            if path.startswith('/api/partner/v1/'):
                assert operation.get('security') == [{'InstitutionKey': []}], path
                assert operation['responses']['200']['content']['application/json']['schema'], path
    for path in root.rglob('*.md'):
        text = path.read_text()
        assert text.count('```') % 2 == 0, f'Unbalanced fence: {path}'
        for href in re.findall(r'\]\(([^)\s]+)\)', text):
            if href.startswith(('https://', 'http://', '#', 'mailto:')):
                continue
            assert (path.parent / href.split('#')[0]).exists(), f'Broken link: {path}: {href}'
        for block in re.findall(r'```json\n(.*?)\n```', text, re.S):
            json.loads(block)
        for block in re.findall(r'```bash\n(.*?)\n```', text, re.S):
            subprocess.run(['bash', '-n'], input=block, text=True, check=True)
        assert not re.search(r'avm_org_[A-Za-z0-9_-]{20,}', text), 'A real credential may be present'
    request_schema = spec['paths']['/api/partner/v1/scripts/estimate']['post']['requestBody']['content']['application/json']['schema']
    Draft202012Validator(dict(request_schema, components=spec['components'])).validate(
        {'input': json.loads((root / 'examples/input.json').read_text())})
    if release:
        assert deployment['status'] == 'success', 'Release requires successful deployment'
        assert re.fullmatch(r'https://github.com/forgeturl/avm-website/actions/runs/\d+', deployment['run_url']), 'Missing deployment run'
    print(f"Integration bundle {version['version']} validated (release={release})")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', action='store_true')
    args = parser.parse_args()
    check(release=args.release)
