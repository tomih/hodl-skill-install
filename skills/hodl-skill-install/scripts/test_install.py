import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from argparse import Namespace
import install as i

class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / 'bundle'
        self.source = self.bundle / 'skills/ebonitete'
        self.source.mkdir(parents=True)
        (self.source / 'SKILL.md').write_text('---\nname: ebonitete\ndescription: Preflight\n---\nPreflight only')
        self.m = {'schemaVersion':1, 'bundleVersion':'0.2.0', 'customer':'demo', 'repository':'example/hodl-client-demo', 'supportedRuntimes':['codex','claude-code'], 'adapter':'project-standalone-skill', 'skills':[{'id':'ebonitete', 'version':'0.1.2', 'source':'skills/ebonitete', 'destinations':i.TARGETS}], 'files':{'skills/ebonitete/SKILL.md':hashlib.sha256((self.source/'SKILL.md').read_bytes()).hexdigest()}}
        self.save_manifest()
        self.key = self.root/'fixture.pub'
        self.key.write_text('ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+bytes(32)).decode())
        self.project = self.root/'project'
        (self.project/'.hodl').mkdir(parents=True)
        self.args = Namespace(bundle=str(self.bundle), public_key=str(self.key), project=str(self.project), customer='demo', repository=self.m['repository'], runtime='codex')
        self.set_runtime('codex')

    def save_manifest(self):
        (self.bundle/'manifest.json').write_text(json.dumps(self.m))

    def set_runtime(self, runtime):
        self.args.runtime = runtime
        (self.project/'.hodl/project.json').write_text(json.dumps({'customer':'demo', 'repository':self.m['repository'], 'runtime':runtime, 'project':str(self.project.resolve())}))

    def test_no_receipt_required_and_matching_retry_is_noop(self):
        result=i.install(self.args)
        self.assertEqual(result['status'], 'files-installed')
        self.assertEqual(result['registration'], 'unverified')
        self.assertEqual(i.install(self.args)['status'], 'files-already-matching')
        self.assertFalse((self.project/'.hodl/install-state.json').exists())

    def test_claude_native_path(self):
        self.set_runtime('claude-code')
        self.assertEqual(Path(i.install(self.args)['path']), self.project/'.claude/skills/ebonitete')
        self.assertFalse((self.project/'.agents').exists())

    def test_legacy_codex_bundle_without_receipt(self):
        self.m.pop('supportedRuntimes'); self.m['runtime']='codex'
        self.m['skills'][0].pop('destinations'); self.m['skills'][0]['destination']=i.TARGETS['codex']
        self.m['skills'][0]['version']='0.1.1'; self.save_manifest()
        i.install(self.args)

    def test_changed_target_preserved(self):
        target=Path(i.install(self.args)['path'])/'SKILL.md'
        target.write_text('user changed')
        with self.assertRaisesRegex(ValueError, 'preserved'): i.install(self.args)
        self.assertEqual(target.read_text(), 'user changed')

    def test_manifest_identity_destination_and_inventory_rejected(self):
        for field,value in [('customer','other'), ('repository','other/repo'), ('adapter','execute-shell')]:
            original=self.m[field]; self.m[field]=value; self.save_manifest()
            with self.assertRaises(ValueError): i.install(self.args)
            self.m[field]=original
        self.m['skills'][0]['destinations']={'codex':'../escape'}; self.save_manifest()
        with self.assertRaises(ValueError): i.install(self.args)
        self.m['skills'][0]['destinations']=i.TARGETS; self.save_manifest()
        (self.source/'unexpected').write_text('extra')
        with self.assertRaises(ValueError): i.install(self.args)
        self.assertFalse((self.project/'.agents').exists())

    def test_cross_runtime_install_and_symlink_rejected(self):
        self.args.runtime='claude-code'
        self.assertEqual(Path(i.install(self.args)['path']), self.project/'.claude/skills/ebonitete')
        self.args.runtime='codex'
        elsewhere=self.root/'elsewhere'; elsewhere.mkdir()
        (self.project/'.agents').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Symlink'): i.install(self.args)
        self.assertEqual(list(elsewhere.iterdir()), [])

if __name__ == '__main__': unittest.main()
