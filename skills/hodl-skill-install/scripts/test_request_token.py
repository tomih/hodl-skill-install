import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
import bootstrap
import request_token as t


class RequestTokenTests(unittest.TestCase):
    def request(self, slug='alpine-studio', device='Računalnik 🐝 東京'):
        blob = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + bytes(range(32))
        import hashlib
        return dict(schemaVersion=1, type='hodl.deploy-key.request', customer=slug,
                    repository='tomih/hodl-client-' + slug, device=device, scope='read-only',
                    publicKey='ssh-ed25519 ' + base64.b64encode(blob).decode(),
                    fingerprint='SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('='))

    def raw_token(self, value, slug):
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return t.PREFIX + base64.urlsafe_b64encode(t.xor(raw, slug)).decode().rstrip('=')

    def test_unicode_compact_utf8_contract_and_roundtrip(self):
        for slug in ('alpine-studio', 'river-lab'):
            value = self.request(slug)
            token = t.encode(value, slug)
            self.assertEqual(token, self.raw_token(value, slug))
            self.assertEqual(t.decode(token, slug), value)
            self.assertEqual(t.encode(value, slug), token)
            self.assertNotIn('publicKey', token)
            with self.assertRaises(ValueError):
                t.decode(token, 'wrong-customer')

    def test_malformed_token_and_schema(self):
        for token in ('', 'HODL2.abc', 'HODL1.', 'HODL1.!!!', 'HODL1.a', 'HODL1.abc=', 'HODL1.abc\n'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                t.decode(token, 'alpine-studio')
        for value in ([], None, {}, dict(self.request(), schemaVersion=True),
                      dict(self.request(), instructions='execute something'),
                      dict(self.request(), customer='other'), dict(self.request(), repository='other/repo'),
                      dict(self.request(), scope='write'), dict(self.request(), device=''),
                      dict(self.request(), device='bad\nlabel'), dict(self.request(), publicKey='private'),
                      dict(self.request(), publicKey='ssh-ed25519 !'),
                      dict(self.request(), fingerprint='SHA256:wrong')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                t.decode(self.raw_token(value, 'alpine-studio'), 'alpine-studio')
        with self.assertRaises(ValueError): t.decode(t.encode(self.request(), 'alpine-studio'), '')

    def test_changed_customers_projects_both_adapters_and_cli_token_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            for slug, runtime in (('alpine-studio', 'codex'), ('river-lab', 'claude-code')):
                project = Path(tmp) / ('projekt-č-' + slug); project.mkdir()
                bootstrap.prepare(Namespace(project=str(project), customer=slug, repository=None, runtime=runtime, write=True))
                value = self.request(slug)
                public = project / 'fixture.pub'; public.write_text(value['publicKey'])
                script = str(Path(bootstrap.__file__).resolve())
                result = subprocess.check_output([sys.executable, script, 'request', '--customer', slug,
                                                 '--repository', value['repository'], '--public-key', str(public),
                                                 '--device', value['device']], text=True)
                self.assertEqual(result, t.encode(value, slug) + '\n')
                helper = str(Path(t.__file__).resolve())
                decoded = subprocess.check_output([sys.executable, helper, 'decode', '--customer', slug, '--token', result.strip()], text=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
                self.assertEqual(json.loads(decoded), value)
                request = project / 'request.json'; request.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
                encoded = subprocess.check_output([sys.executable, helper, 'encode', '--customer', slug, '--request', str(request)], text=True)
                self.assertEqual(encoded, result)

    def test_qr_encoder_receives_exact_token_not_json(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            value = self.request()
            public = Path(tmp)/'public.pub'; public.write_text(value['publicKey'])
            args = Namespace(customer=value['customer'], repository=value['repository'], device=value['device'],
                             public_key=str(public), qr=str(Path(tmp)/'handoff.png'))
            with patch.object(bootstrap.shutil,'which',return_value='/usr/bin/qrencode'), patch.object(bootstrap.subprocess,'run') as run:
                token = bootstrap.request(args)
            self.assertEqual(run.call_args.kwargs['input'], token.encode('ascii'))
            self.assertEqual(t.decode(token, value['customer']), value)

    def test_duplicate_fields_rejected(self):
        raw = '{"schemaVersion":1,"schemaVersion":1}'
        token = t.PREFIX + base64.urlsafe_b64encode(t.xor(raw.encode(), 'demo')).decode().rstrip('=')
        with self.assertRaises(ValueError): t.decode(token, 'demo')


if __name__ == '__main__': unittest.main()
