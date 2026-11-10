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
            self.assertEqual(b.prepare(a)['project']['project'], str(sub))
            root = sub
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
            with self.assertRaisesRegex(ValueError, 'Customer missing'):
                b.prepare(a)

    @patch.dict(b.os.environ, {}, clear=True)
    def test_cross_runtime_same_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Namespace(project=tmp, customer='demo', runtime='codex', repository='example/hodl-client-demo', write=True)
            b.prepare(a)
            before = (Path(tmp)/'.hodl/project.json').read_bytes()
            a.runtime = 'claude-code'
            self.assertEqual(b.prepare(a)['project']['runtime'], 'claude-code')
            self.assertEqual((Path(tmp)/'.hodl/project.json').read_bytes(), before)

    def test_runtime_conflict_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(b.os.environ, {'CLAUDECODE':'1'}, clear=True):
            result = b.preflight(Namespace(project=tmp, runtime='codex'))
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(result['observedRuntime'], 'claude-code')

    def test_copied_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / '.hodl').mkdir()
            (root / '.hodl/project.json').write_text(json.dumps({'project':'/another-project', 'customer':'demo', 'runtime':'codex', 'repository':'example/hodl-client-demo'}))
            a = Namespace(project=tmp, customer=None, runtime='codex', repository=None, write=True)
            with self.assertRaisesRegex(ValueError, 'Stored project path'):
                b.prepare(a)
            self.assertFalse((root / '.hodl/install-state.json').exists())

    def test_preflight_reports_missing_required_tools_without_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.shutil, 'which', return_value=None):
            result = b.preflight(Namespace(project=tmp, runtime='codex'))
            self.assertEqual(result['status'], 'blocked')
            self.assertTrue(result['projectWritable'])
            self.assertTrue(any('git' in message for message in result['blockers']))
            self.assertFalse((Path(tmp)/'.hodl').exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_preflight_broken_executable_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b.shutil, 'which', return_value='/fake/tool'), patch.object(b.subprocess, 'run', side_effect=OSError('not executable')):
            result = b.preflight(Namespace(project=tmp, runtime='claude-code'))
            self.assertEqual(result['status'], 'blocked')
            self.assertTrue(any('cannot run' in message for message in result['blockers']))

    def test_prepare_does_not_persist_unknown_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Namespace(project=tmp, customer='demo', runtime='codex', repository=None, write=True)
            with self.assertRaisesRegex(ValueError, 'repository required'): b.prepare(a)
            self.assertFalse((Path(tmp)/'.hodl').exists())

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
