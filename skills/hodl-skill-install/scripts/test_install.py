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
        self.m = {'schemaVersion':1, 'bundleVersion':'0.2.0', 'customer':'demo', 'repository':'example/hodl-client-demo', 'supportedRuntimes':list(i.TARGETS), 'adapter':'project-standalone-skill', 'skills':[{'id':'ebonitete', 'version':'0.1.2', 'source':'skills/ebonitete', 'destinations':{r:p+'/ebonitete' for r,p in i.TARGETS.items()}}], 'files':{'skills/ebonitete/SKILL.md':hashlib.sha256((self.source/'SKILL.md').read_bytes()).hexdigest()}}
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

    def test_install_and_matching_retry_is_noop(self):
        result=i.install(self.args)
        self.assertEqual(result['status'], 'files-installed')
        self.assertEqual(result['registration'], 'unverified')
        self.assertEqual(i.install(self.args)['status'], 'files-already-matching')
        self.assertEqual(json.loads((self.project/'.hodl/install-state.json').read_text())['runtimes']['codex']['status'], 'acceptance-pending')

    def test_claude_native_path(self):
        self.set_runtime('claude-code')
        self.assertEqual(Path(i.install(self.args)['path']), self.project/'.claude/skills/ebonitete')
        self.assertFalse((self.project/'.agents').exists())

    def test_legacy_single_runtime_manifest(self):
        self.m.pop('supportedRuntimes'); self.m['runtime']='codex'
        self.m['skills'][0].pop('destinations'); self.m['skills'][0]['destination']=i.TARGETS['codex']+'/ebonitete'
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
        self.m['skills'][0]['destinations']={r:p+'/ebonitete' for r,p in i.TARGETS.items()}; self.save_manifest()
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

    def add_skill(self, sid='company-research', version='4.5.6'):
        source=self.bundle/'skills'/sid
        source.mkdir()
        (source/'SKILL.md').write_text('---\nname: '+sid+'\ndescription: Local help\n---\nHelp')
        self.m['skills'].append({'id':sid, 'version':version, 'source':'skills/'+sid,
                                'destinations':{r:p+'/'+sid for r,p in i.TARGETS.items()}})
        self.m['files'].update(i.inventory(source, self.bundle))
        self.save_manifest()

    def test_non_pilot_skill_and_version(self):
        self.add_skill()
        self.m['skills']=self.m['skills'][1:]
        import shutil
        shutil.rmtree(self.source)
        self.m['files']=i.inventory(self.bundle/'skills', self.bundle)
        self.save_manifest()
        self.set_runtime('claude-code')
        result=i.install(self.args)
        self.assertEqual(result['skills'][0]['id'], 'company-research')
        self.assertEqual(result['skills'][0]['version'], '4.5.6')
        self.assertTrue((self.project/'.claude/skills/company-research/SKILL.md').is_file())
        self.assertFalse((self.project/'.claude/skills/ebonitete').exists())

    def test_multiple_and_second_target_conflict_before_any_write(self):
        self.add_skill()
        target=self.project/'.agents/skills/company-research'
        target.mkdir(parents=True)
        (target/'SKILL.md').write_text('local customization')
        with self.assertRaisesRegex(ValueError, 'preserved'): i.install(self.args)
        self.assertFalse((self.project/'.agents/skills/ebonitete').exists())
        self.assertEqual((target/'SKILL.md').read_text(), 'local customization')

    def test_multiple_install_and_retry_both_runtimes(self):
        self.add_skill()
        for runtime in i.TARGETS:
            self.set_runtime(runtime)
            result=i.install(self.args)
            self.assertEqual(len(result['skills']), 2)
            self.assertEqual(i.install(self.args)['status'], 'files-already-matching')
            for skill in result['skills']:
                self.assertTrue((Path(skill['path'])/'SKILL.md').is_file())

    def test_unsafe_duplicate_unpinned_skills(self):
        original=json.loads(json.dumps(self.m))
        for sid in ('../escape', '/absolute', 'a/b', 'UPPER', '.', 'a_b', 'a'*65, 'con', 'nul', 'com1'):
            self.m=json.loads(json.dumps(original)); self.m['skills'][0]['id']=sid
            self.save_manifest()
            with self.assertRaises(ValueError): i.install(self.args)
        for version in ('latest', '*', '>=1.0.0', '', None):
            self.m=json.loads(json.dumps(original)); self.m['skills'][0]['version']=version
            self.save_manifest()
            with self.assertRaises(ValueError): i.install(self.args)
        self.m=json.loads(json.dumps(original)); self.m['skills']*=2; self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'duplicate'): i.install(self.args)
        self.assertFalse((self.project/'.agents').exists())

    def test_hash_mismatch_and_unlisted_skill(self):
        (self.source/'SKILL.md').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'checksum'): i.install(self.args)
        (self.bundle/'skills/unlisted').mkdir()
        with self.assertRaisesRegex(ValueError, 'inventory'): i.install(self.args)

    def test_symlink_source_and_nested_content(self):
        outside=self.root/'outside'; outside.write_text('secret')
        (self.source/'linked').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlink'): i.install(self.args)
        self.assertFalse((self.project/'.agents').exists())

    def test_frontmatter_name_mismatch(self):
        (self.source/'SKILL.md').write_text('---\nname: wrong-name\ndescription: Help\n---\nHelp')
        self.m['files']=i.inventory(self.bundle/'skills', self.bundle); self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'frontmatter name'): i.install(self.args)
        self.assertFalse((self.project/'.agents').exists())

    def test_duplicate_json_keys_rejected(self):
        p=self.bundle/'manifest.json'
        p.write_text(p.read_text().replace('"schemaVersion": 1', '"schemaVersion": 1, "schemaVersion": 1'))
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'): i.install(self.args)

if __name__ == '__main__': unittest.main()
