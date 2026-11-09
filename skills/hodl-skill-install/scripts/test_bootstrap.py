import base64
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace

spec = importlib.util.spec_from_file_location('bootstrap', Path(__file__).with_name('bootstrap.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class BootstrapTests(unittest.TestCase):
    def test_prepare_isolated_idempotent_and_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / '.git').mkdir()
            sub = root / 'src'
            sub.mkdir()
            a = Namespace(project=str(sub), customer='demo', runtime='codex', repository='example/hodl-client-demo', write=False)
            self.assertEqual(b.prepare(a)['project']['project'], str(root))
            self.assertFalse((root / '.hodl').exists())
            a.write = True
            b.prepare(a)
            state = root / '.hodl/install-state.json'
            state.write_text('{"sentinel":true}')
            b.prepare(a)
            self.assertEqual(json.loads(state.read_text()), {'sentinel': True})
            self.assertEqual(sorted(p.name for p in (root / '.hodl').iterdir()), ['install-state.json','project.json'])
            a.customer = 'other'
            with self.assertRaises(ValueError): b.prepare(a)

    def test_missing_identity_does_not_guess_from_folder(self):
        with tempfile.TemporaryDirectory(prefix='codex-test-sivka-') as tmp:
            a = Namespace(project=tmp, customer=None, runtime='codex', repository=None, write=False)
            with patch('builtins.input', return_value='demo') as prompt:
                result = b.prepare(a)
            prompt.assert_called_once()
            self.assertEqual(result['project']['customer'], 'demo')
            self.assertIsNone(result['project']['repository'])

    def test_copied_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / '.hodl').mkdir()
            (root / '.hodl/project.json').write_text(json.dumps({'project':'/another-project', 'customer':'demo', 'runtime':'codex', 'repository':'example/hodl-client-demo'}))
            a = Namespace(project=tmp, customer=None, runtime='codex', repository=None, write=True)
            with self.assertRaisesRegex(ValueError, 'Stored project path'):
                b.prepare(a)
            self.assertFalse((root / '.hodl/install-state.json').exists())

    def test_ambiguous_runtime_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(b.os.environ, {}, clear=True):
            a = Namespace(project=tmp, customer='demo', runtime=None, repository=None, write=True)
            with self.assertRaises(ValueError): b.prepare(a)
            self.assertFalse((Path(tmp) / '.hodl').exists())

    @unittest.skipUnless(shutil.which("qrencode") and shutil.which("ssh-keygen"),
                         "QR integration requires qrencode and ssh-keygen")
    def test_request_and_qr_with_synthetic_public_fixture(self):
        # A deterministic public blob, not a generated keypair; no private key exists.
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp) / 'fixture.pub'
            blob = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + bytes(range(32))
            public.write_text('ssh-ed25519 ' + base64.b64encode(blob).decode() + ' fixture')
            qr = Path(tmp) / 'request.png'
            a = Namespace(customer='demo', repository='example/hodl-client-demo', device='fixture', public_key=str(public), qr=str(qr))
            result = b.request(a)
            self.assertEqual(result['scope'], 'read-only')
            self.assertTrue(qr.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            native = subprocess.check_output(['ssh-keygen','-lf',str(public),'-E','sha256'], text=True).split()[1]
            self.assertEqual(result['fingerprint'], native)
            with self.assertRaises(FileExistsError): b.request(a)
            if shutil.which('zbarimg'):
                decoded = subprocess.check_output(['zbarimg','--quiet','--raw',str(qr)], text=True)
                self.assertEqual(json.loads(decoded), result)
            a.repository = 'example/hodl-client-other'
            with self.assertRaises(ValueError): b.request(a)
            public.write_text('-----BEGIN OPENSSH PRIVATE KEY-----')
            with self.assertRaises(ValueError): b.public_key(public)

    def test_symlink_state_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'elsewhere').mkdir()
            (root / '.hodl').symlink_to(root / 'elsewhere', target_is_directory=True)
            with self.assertRaises(ValueError): b.store(root, 'project.json', {})

if __name__ == '__main__': unittest.main()
