import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import test_install as fixtures
import install as i
import lifecycle as life
import acceptance
import self_update


class LifecycleTests(unittest.TestCase):
    setUp = fixtures.InstallTests.setUp
    save_manifest = fixtures.InstallTests.save_manifest
    set_runtime = fixtures.InstallTests.set_runtime
    add_skill = fixtures.InstallTests.add_skill
    def change_bundle(self, version='0.1.3'):
        (self.source/'SKILL.md').write_text('---\nname: ebonitete\ndescription: Preflight\n---\nUpdated local help')
        self.m['skills'][0]['version']=version
        self.m['bundleVersion']='0.3.0'
        self.m['files']=i.inventory(self.bundle/'skills', self.bundle)
        self.save_manifest()

    def test_update_both_roots_and_multiple_skills_noop(self):
        self.add_skill()
        for runtime in i.TARGETS:
            self.set_runtime(runtime)
            i.install(self.args)
        self.change_bundle()
        for runtime in i.TARGETS:
            self.set_runtime(runtime)
            result=i.install(self.args)
            self.assertEqual(result['status'], 'files-updated')
            self.assertEqual([s['status'] for s in result['skills']], ['files-updated','files-already-matching'])
            backups=list((self.project/'.hodl/backups').iterdir())
            self.assertEqual(i.install(self.args)['status'], 'files-already-matching')
            self.assertEqual(list((self.project/'.hodl/backups').iterdir()), backups)
        self.assertTrue((self.project/'.claude/skills/ebonitete/SKILL.md').read_text().endswith('Updated local help'))

    def test_synthetic_customer_project_and_skill_lifecycle_both_adapters(self):
        import tempfile
        from argparse import Namespace
        for customer in ('alpine-studio', 'river-lab'):
            for runtime in i.TARGETS:
                with self.subTest(customer=customer, runtime=runtime), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    project = root / ('projekt-č-' + customer)
                    (project / '.hodl').mkdir(parents=True)
                    repository = 'tomih/hodl-client-' + customer
                    (project / '.hodl/project.json').write_text(json.dumps(dict(customer=customer, repository=repository, project=str(project))))
                    bundle = root / 'bundle'
                    source = bundle / 'skills/document-summary'
                    source.mkdir(parents=True)
                    entry = source / 'SKILL.md'
                    entry.write_text('---\nname: document-summary\ndescription: Summarize documents\n---\nLocal help')
                    manifest = dict(schemaVersion=1, bundleVersion='1.0.0', customer=customer, repository=repository,
                                    supportedRuntimes=list(i.TARGETS), adapter='project-standalone-skill',
                                    skills=[dict(id='document-summary', version='1.0.0', source='skills/document-summary',
                                                 destinations={r: p + '/document-summary' for r,p in i.TARGETS.items()})])
                    def save():
                        manifest['files'] = i.inventory(bundle/'skills',bundle)
                        (bundle/'manifest.json').write_text(json.dumps(manifest))
                    save()
                    args = Namespace(bundle=str(bundle),project=str(project),customer=customer,repository=repository,
                                     runtime=runtime,public_key=str(self.key))
                    self.assertEqual(i.install(args)['status'], 'files-installed')
                    self.assertEqual(i.install(args)['status'], 'files-already-matching')
                    entry.write_text(entry.read_text() + ' updated')
                    manifest['skills'][0]['version'] = '1.0.1'; save()
                    self.assertEqual(i.install(args)['status'], 'files-updated')
                    target = project / i.TARGETS[runtime] / 'document-summary/SKILL.md'
                    target.write_text('user customization')
                    with self.assertRaisesRegex(ValueError,'preserved'): i.install(args)
                    self.assertEqual(target.read_text(),'user customization')

    def test_later_local_conflict_prevents_earlier_update(self):
        self.add_skill(); i.install(self.args)
        first=self.project/'.agents/skills/ebonitete/SKILL.md'
        before=first.read_bytes()
        other=self.project/'.agents/skills/company-research/SKILL.md'
        other.write_text('local edit')
        self.change_bundle()
        with self.assertRaisesRegex(ValueError, 'preserved'): i.install(self.args)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(other.read_text(), 'local edit')

    def test_second_replace_failure_rolls_back_files_and_state(self):
        self.add_skill(); i.install(self.args)
        state=self.project/'.hodl/managed-codex.json'
        before=state.read_bytes()
        first=self.project/'.agents/skills/ebonitete/SKILL.md'; old=first.read_bytes()
        self.change_bundle()
        other=self.bundle/'skills/company-research/SKILL.md'; other.write_text(other.read_text()+' new')
        self.m['files']=i.inventory(self.bundle/'skills', self.bundle); self.save_manifest()
        original=life.os.replace
        def fail(source, target):
            if Path(target).name == 'company-research': raise OSError('injected replacement failure')
            return original(source,target)
        with patch.object(life.os,'replace',side_effect=fail):
            with self.assertRaisesRegex(OSError,'injected'): i.install(self.args)
        self.assertEqual(first.read_bytes(), old)
        self.assertEqual(state.read_bytes(), before)
        self.assertFalse((self.project/'.hodl/managed-codex-transaction.json').exists())

    def test_staging_failure_writes_no_targets(self):
        self.add_skill()
        original=life.shutil.copytree
        def fail(source,target,*a,**kw):
            if Path(source).name == 'company-research': raise OSError('injected staging failure')
            return original(source,target,*a,**kw)
        with patch.object(life.shutil,'copytree',side_effect=fail):
            with self.assertRaises(OSError): i.install(self.args)
        self.assertFalse((self.project/'.agents').exists())

    def test_legacy_prior_bundle_adoption_and_modified_rejection(self):
        i.install(self.args)
        prior=self.root/'prior'; shutil.copytree(self.bundle,prior)
        (self.project/'.hodl/managed-codex.json').unlink()
        self.change_bundle()
        with self.assertRaisesRegex(ValueError,'Unmanaged'): i.install(self.args)
        self.args.prior_bundle=str(prior)
        self.assertEqual(i.install(self.args)['status'],'files-updated')
        target=self.project/'.agents/skills/ebonitete/SKILL.md'; target.write_text('local')
        with self.assertRaisesRegex(ValueError,'preserved'): i.install(self.args)
        self.assertEqual(target.read_text(),'local')

    def test_acceptance_resume_skip_invalidate_and_preserve(self):
        i.install(self.args)
        state=self.project/'.hodl/install-state.json'
        state.write_text(json.dumps({'sentinel':True,'runtimes':{'claude-code':{'status':'kept'}}}))
        pending=acceptance.resume(self.project,'codex')['pending'][0]
        evidence=dict(skill=pending['id'], version=pending['version'], filesDigest=pending['filesDigest'],
                      kind='observed', app='Codex',appVersion='unknown',invocation='$ebonitete',
                      localPreflight='Documented local help loaded; no portal',timestamp='2026-11-10T11:00:00Z')
        self.assertEqual(acceptance.resume(self.project,'codex',evidence)['status'],'installed')
        i.install(self.args)
        self.assertEqual(acceptance.resume(self.project,'codex')['pending'],[])
        self.assertTrue(json.loads(state.read_text())['sentinel'])
        self.assertEqual(json.loads(state.read_text())['runtimes']['claude-code']['status'],'kept')
        self.change_bundle(); i.install(self.args)
        self.assertEqual(len(acceptance.resume(self.project,'codex')['pending']),1)
        with self.assertRaises(ValueError): acceptance.resume(self.project,'codex',evidence)

    def test_prior_bundle_retry_preserves_newer_managed_acceptance(self):
        i.install(self.args)
        prior=self.root/'prior';shutil.copytree(self.bundle,prior)
        self.change_bundle();i.install(self.args)
        pending=acceptance.resume(self.project,'codex')['pending'][0]
        evidence=dict(skill=pending['id'],version=pending['version'],filesDigest=pending['filesDigest'],kind='observed',
                      app='Codex',appVersion='unknown',invocation='$ebonitete',localPreflight='Help loaded',timestamp='2026-11-10T11:00:00Z')
        acceptance.resume(self.project,'codex',evidence)
        self.args.prior_bundle=str(prior)
        self.assertEqual(i.install(self.args)['status'],'files-already-matching')
        self.assertEqual(acceptance.resume(self.project,'codex')['pending'],[])

    def test_interrupted_journal_blocks(self):
        i.install(self.args)
        self.change_bundle()
        (self.project/'.hodl/managed-codex-transaction.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Interrupted'): i.install(self.args)

    def test_acceptance_blocks_interleaved_update_before_stale_evidence_write(self):
        i.install(self.args)
        pending=acceptance.resume(self.project,'codex')['pending'][0]
        evidence=dict(skill=pending['id'],version=pending['version'],filesDigest=pending['filesDigest'],
                      kind='observed',app='Codex',appVersion='unknown',invocation='$ebonitete',
                      localPreflight='Local help loaded',timestamp='2026-11-10T11:00:00Z')
        self.change_bundle()
        original=acceptance.apply
        def interleave(*args,**kwargs):
            with self.assertRaisesRegex(ValueError,'project operation lock'): i.install(self.args)
            return original(*args,**kwargs)
        with patch.object(acceptance,'apply',side_effect=interleave):
            self.assertEqual(acceptance.resume(self.project,'codex',evidence)['status'],'installed')
        i.install(self.args)
        self.assertEqual(len(acceptance.resume(self.project,'codex')['pending']),1)

    def test_cross_runtime_operations_serialize_and_preserve_both_records(self):
        from argparse import Namespace
        other=Namespace(**vars(self.args));other.runtime='claude-code'
        original=i.apply
        def interleave(*args,**kwargs):
            with self.assertRaisesRegex(ValueError,'project operation lock'): i.install(other)
            return original(*args,**kwargs)
        with patch.object(i,'apply',side_effect=interleave): i.install(self.args)
        i.install(other)
        state=json.loads((self.project/'.hodl/install-state.json').read_text())
        self.assertEqual(set(state['runtimes']),{'codex', 'claude-code'})
        for runtime in ('codex', 'claude-code'):
            self.assertEqual(len(acceptance.resume(self.project,runtime)['pending']),1)

    def test_candidate_tamper_between_validation_and_stage(self):
        original=i.validate
        def tamper(*args):
            result=original(*args)
            (self.source/'SKILL.md').write_text('tamper after validation')
            return result
        with patch.object(i,'validate',side_effect=tamper):
            with self.assertRaisesRegex(ValueError,'Staged'): i.install(self.args)
        self.assertFalse((self.project/'.agents').exists())

    def test_legacy_state_write_failure_rolls_back_everything(self):
        i.install(self.args)
        managed=self.project/'.hodl/managed-codex.json'
        legacy=self.project/'.hodl/install-state.json'
        target=self.project/'.agents/skills/ebonitete/SKILL.md'
        before=[p.read_bytes() for p in (managed,legacy,target)]
        self.change_bundle()
        original=life.atomic_json
        def fail(path,value):
            if path == legacy: raise OSError('injected state failure')
            return original(path,value)
        with patch.object(life,'atomic_json',side_effect=fail):
            with self.assertRaises(OSError): i.install(self.args)
        self.assertEqual([p.read_bytes() for p in (managed,legacy,target)],before)

    def test_lock_blocks_and_preserves_config_other_skill_and_key(self):
        config=self.project/'.hodl/ebonitete.json'; config.write_text('{"custom":true}')
        other=self.project/'.agents/skills/unrelated/SKILL.md'; other.parent.mkdir(parents=True); other.write_text('keep')
        key_before=self.key.read_bytes()
        lock=self.project/'.hodl/managed-codex-transaction.lock'; lock.write_text('active')
        with self.assertRaisesRegex(ValueError,'lock'): i.install(self.args)
        lock.unlink(); i.install(self.args); self.change_bundle(); i.install(self.args)
        self.assertEqual(config.read_text(),'{"custom":true}')
        self.assertEqual(other.read_text(),'keep')
        self.assertEqual(self.key.read_bytes(),key_before)

    def test_unsafe_state_and_backup_symlinks_rejected(self):
        outside=self.root/'outside'; outside.mkdir()
        managed=self.project/'.hodl/managed-codex.json'; managed.symlink_to(outside/'missing')
        with self.assertRaisesRegex(ValueError,'Symlink'): i.install(self.args)
        managed.unlink(); i.install(self.args); self.change_bundle()
        backups=self.project/'.hodl/backups'; backups.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Symlink'): i.install(self.args)
        self.assertEqual(list(outside.iterdir()),[])



class BootstrapUpdateTests(unittest.TestCase):
    def test_legacy_self_update_noop_conflict_and_sums(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=root/'old'; new=root/'new'
            for release, version in ((old,'0.2.4'),(new,'0.2.5')):
                skill=release/'skills/hodl-skill-install'; skill.mkdir(parents=True)
                (skill/'SKILL.md').write_text('---\nname: hodl-skill-install\ndescription: Install\n---\nVersion '+version)
                (release/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in i.inventory(release,release).items()))
            target=root/'.claude/skills/hodl-skill-install'; target.parent.mkdir(parents=True)
            shutil.copytree(old/'skills/hodl-skill-install',target)
            with self.assertRaises(ValueError): self_update.update(new,target)
            self.assertEqual(self_update.update(new,target,old)['status'],'files-updated')
            self.assertEqual(self_update.update(new,target)['status'],'files-already-matching')
            (target/'custom').write_text('keep')
            with self.assertRaisesRegex(ValueError,'preserved'): self_update.update(new,target)
            (new/'skills/hodl-skill-install/extra').write_text('tamper')
            with self.assertRaisesRegex(ValueError,'checksum'): self_update.update(new,target)

    def test_normal_helper_invocations_do_not_mutate_package(self):
        import tempfile, os, subprocess, sys
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(__file__).resolve().parent.parent
            target=Path(tmp)/'skill'
            shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            before=i.inventory(target,target)
            env=dict(os.environ);env.pop('PYTHONDONTWRITEBYTECODE',None)
            for name in ('install','self_update','acceptance','bootstrap','request_token'):
                subprocess.run([sys.executable,str(target/'scripts'/(name+'.py')),'--help'],env=env,check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(i.inventory(target,target),before)

if __name__ == '__main__': unittest.main()
