import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_bundle_check', ROOT / 'scripts/validate.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class BundleTests(unittest.TestCase):
    def copy_bundle(self, target):
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('.git', '.venv', '__pycache__', '*.pyc'))
        manifest = json.loads((target / 'deployment.json').read_text())
        manifest['bundle_sha256'] = validator.digest(target)
        (target / 'deployment.json').write_text(json.dumps(manifest))
        return manifest

    def test_pending_deployment_cannot_be_released(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / 'bundle'
            manifest = self.copy_bundle(root)
            manifest['status'] = 'pending'
            (root / 'deployment.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AssertionError, 'successful deployment'):
                validator.check(root, release=True)

    def test_rewriting_a_tagged_version_is_rejected_even_with_recomputed_digests(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / 'bundle'
            manifest = self.copy_bundle(root)
            def git(*args):
                subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)
            git('init', '-q')
            git('config', 'user.name', 'Bundle test')
            git('config', 'user.email', 'test@example.com')
            git('add', '.')
            git('commit', '-qm', 'released baseline')
            git('tag', 'v' + manifest['version'])
            with (root / 'README.md').open('a') as output:
                output.write('\nChanged published guidance\n')
            manifest['bundle_sha256'] = validator.digest(root)
            (root / 'deployment.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(AssertionError, 'Published version changed'):
                validator.check(root)
