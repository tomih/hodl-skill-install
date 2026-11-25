"""Offline adapter contract. Synthetic evidence is NOT native OpenClaw acceptance."""
import json
from argparse import Namespace
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import bootstrap
import install
import acceptance
import lifecycle
import self_update
import test_lifecycle as fixtures


class OpenClawPreflightTests(unittest.TestCase):
    @patch.dict(bootstrap.os.environ, {}, clear=True)
    def test_explicit_openclaw_prepare_and_cli_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(project=tmp, runtime='openclaw', customer='demo',
                             repository=None, write=True)
            def run(argv, **kwargs):
                output = 'OpenClaw 2026.11.4 (d843d6a)\n' if argv[-1] == '--version' and 'openclaw' in argv[0] else 'tool version\n'
                return subprocess.CompletedProcess(argv, 0, output, '')
            with patch.object(bootstrap.shutil, 'which', side_effect=lambda n: '/bin/' + n), patch.object(bootstrap.subprocess, 'run', side_effect=run):
                result = bootstrap.preflight(args)
            self.assertEqual(result['status'], 'ready')
            self.assertEqual(result['appVersion'], 'OpenClaw 2026.11.4 (d843d6a)')
            self.assertIsNone(result['observedRuntime'])
            self.assertEqual(result['runtimeEvidence'], 'explicit caller context')
            self.assertFalse((Path(tmp)/'.hodl').exists())
            bootstrap.prepare(args)
            before = install.inventory(Path(tmp)/'.hodl', Path(tmp))
            bootstrap.prepare(args)
            self.assertEqual(install.inventory(Path(tmp)/'.hodl', Path(tmp)), before)

    @patch.dict(bootstrap.os.environ, {}, clear=True)
    def test_missing_or_invalid_cli_blocks_and_does_not_infer_active_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(project=tmp, runtime='openclaw')
            with patch.object(bootstrap.shutil, 'which', return_value=None):
                self.assertEqual(bootstrap.preflight(args)['status'], 'blocked')
            with patch.object(bootstrap.shutil, 'which', return_value='/bin/fake'), patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'not OpenClaw', '')):
                self.assertEqual(bootstrap.preflight(args)['status'], 'blocked')
                self.assertIsNone(bootstrap.detect_runtime())
            self.assertFalse((Path(tmp)/'.hodl').exists())


class PopulatedStateTests(unittest.TestCase):
    setUp = fixtures.LifecycleTests.setUp
    set_runtime = fixtures.LifecycleTests.set_runtime
    save_manifest = fixtures.LifecycleTests.save_manifest
    add_skill = fixtures.LifecycleTests.add_skill
    change_bundle = fixtures.LifecycleTests.change_bundle

    def populate(self, runtime):
        self.set_runtime(runtime)
        # Nonempty opaque application data deliberately lives outside immutable skills.
        values = {
            '.hodl/local-settings.json': b'{"timezone":"Europe/Ljubljana","enabled":false}',
            '.hodl/lead-register.json': b'{"leads":[{"id":"synthetic-1","status":"qualified"}]}',
            '.hodl/history.jsonl': b'{"id":"synthetic-1","event":"reviewed"}\n',
            '.hodl/notifications/sent.jsonl': b'{"id":"notice-1","receipt":"synthetic-receipt"}\n',
            '.hodl/notifications/uncertain.jsonl': b'{"id":"notice-2","status":"uncertain"}\n',
            'operations/local-settings.json': b'{"mail":false,"schedules":false}',
            '.hodl/managed-unrelated.json': b'{"keep":"other runtime opaque state"}',
            '.hodl/project.json': (self.project/'.hodl/project.json').read_bytes(),
            install.TARGETS[runtime] + '/unrelated/SKILL.md': b'local unrelated skill',
        }
        for name, value in values.items():
            path = self.project/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        database = self.project/'data/register.sqlite'
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE leads (id TEXT PRIMARY KEY, status TEXT)')
            connection.execute('INSERT INTO leads VALUES (?, ?)', ('synthetic-1', 'qualified'))
        values['data/register.sqlite'] = database.read_bytes()
        legacy = {'custom':'preserve', 'runtimes':{'unrelated':{'status':'installed','receipt':'keep'}}}
        (self.project/'.hodl/install-state.json').write_text(json.dumps(legacy))
        return values

    def assert_preserved(self, values):
        for name, value in values.items():
            self.assertEqual((self.project/name).read_bytes(), value, name)
        legacy = json.loads((self.project/'.hodl/install-state.json').read_text())
        self.assertEqual(legacy['custom'], 'preserve')
        self.assertEqual(legacy['runtimes']['unrelated'], {'status':'installed','receipt':'keep'})

    def test_install_noop_accept_update_conflict_failure_restore_populated_all_adapters(self):
        for runtime in install.TARGETS:
            with self.subTest(runtime=runtime):
                # Fresh fixture for each runtime, including populated mutable data before first install.
                if runtime != next(iter(install.TARGETS)):
                    self.setUp()
                self.add_skill()
                values = self.populate(runtime)
                key_before = self.key.read_bytes()
                self.assertEqual(install.install(self.args)['status'], 'files-installed')
                self.assert_preserved(values)
                prior = self.root/'verified-prior'; shutil.copytree(self.bundle, prior)
                pending = acceptance.resume(self.project, runtime)['pending']
                for item in pending:
                    evidence = dict(skill=item['id'], version=item['version'], filesDigest=item['filesDigest'],
                                    kind='user-reported', app='synthetic test host', appVersion='fixture',
                                    invocation='synthetic harmless load', localPreflight='fixture help only',
                                    timestamp='2026-11-25T13:00:00Z')
                    acceptance.resume(self.project, runtime, evidence)
                before = install.inventory(self.project, self.project)
                self.assertEqual(install.install(self.args)['status'], 'files-already-matching')
                self.assertEqual(install.inventory(self.project, self.project), before)
                self.assertEqual(acceptance.resume(self.project, runtime)['pending'], [])
                self.change_bundle()
                self.assertEqual(install.install(self.args)['status'], 'files-updated')
                self.assertEqual([p['id'] for p in acceptance.resume(self.project, runtime)['pending']], ['ebonitete'])
                self.assert_preserved(values)
                # Conflict in later skill prevents the earlier change and preserves ALL state.
                target = self.project/install.TARGETS[runtime]/'company-research/SKILL.md'
                old = target.read_bytes()
                target.write_bytes(old + b' local edit')
                self.change_bundle('0.1.4')
                before = install.inventory(self.project, self.project)
                with self.assertRaisesRegex(ValueError, 'preserved'):
                    install.install(self.args)
                self.assertEqual(install.inventory(self.project, self.project), before)
                target.write_bytes(old)
                # Fail after replacements, during state commit: exact byte rollback.
                before = install.inventory(self.project, self.project)
                original = lifecycle.atomic_json
                def fail(path, value):
                    if Path(path).name == 'install-state.json':
                        raise OSError('injected post-replacement state failure')
                    return original(path, value)
                with patch.object(lifecycle, 'atomic_json', side_effect=fail):
                    with self.assertRaisesRegex(OSError, 'injected'):
                        install.install(self.args)
                # Backups are append-only evidence; compare all preexisting content.
                for name, checksum in before.items():
                    self.assertEqual(install.inventory(self.project, self.project)[name], checksum, name)
                self.assert_preserved(values)
                # Restore a verified earlier bundle using the SAME managed installer.
                self.args.bundle = str(prior)
                self.assertEqual(install.install(self.args)['status'], 'files-updated')
                self.assertEqual(install.install(self.args)['status'], 'files-already-matching')
                self.assert_preserved(values)
                self.assertEqual(self.key.read_bytes(), key_before)
                journal = self.project/('.hodl/managed-' + runtime + '-transaction.json')
                journal.write_text('{}')
                before = install.inventory(self.project, self.project)
                with self.assertRaisesRegex(ValueError, 'Interrupted'):
                    install.install(self.args)
                with self.assertRaisesRegex(ValueError, 'interrupted'):
                    acceptance.resume(self.project, runtime)
                self.assertEqual(install.inventory(self.project, self.project), before)

    def test_mutable_files_inside_skill_are_preserved_as_conflict(self):
        self.populate('openclaw')
        install.install(self.args)
        path = self.project/'skills/ebonitete/registry.json'
        path.write_text('{"populated":["synthetic"]}')
        self.change_bundle()
        before = install.inventory(self.project, self.project)
        with self.assertRaisesRegex(ValueError, 'preserved'):
            install.install(self.args)
        self.assertEqual(install.inventory(self.project, self.project), before)

    def test_openclaw_rejects_manifest_without_explicit_runtime_approval(self):
        values = self.populate('openclaw')
        self.m['supportedRuntimes'].remove('openclaw')
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            install.install(self.args)
        self.assert_preserved(values)


class OpenClawBootstrapUpdateTests(unittest.TestCase):
    def test_managed_bootstrap_first_noop_update_failure_restore_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases = []
            for version in ('0.2.8', '0.2.9-rc.1'):
                release = root/version
                skill = release/'skills/hodl-skill-install'
                skill.mkdir(parents=True)
                (skill/'SKILL.md').write_text('---\nname: hodl-skill-install\ndescription: Install\n---\nVersion ' + version)
                (release/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(install.inventory(release, release).items())))
                releases.append(release)
            workspace = root/'workspace'
            target = workspace/'skills/hodl-skill-install'
            mutable = workspace/'.hodl/notifications/uncertain.jsonl'
            mutable.parent.mkdir(parents=True)
            mutable.write_bytes(b'{"id":"synthetic","status":"uncertain"}\n')
            target.parent.mkdir(parents=True)
            self_update.update(releases[0], target)
            self.assertEqual(self_update.update(releases[0], target)['status'], 'files-already-matching')
            before = install.inventory(workspace, workspace)
            original = lifecycle.atomic_json
            def fail(path, value):
                if Path(path).name == 'managed.json':
                    raise OSError('injected bootstrap commit failure')
                return original(path, value)
            with patch.object(lifecycle, 'atomic_json', side_effect=fail):
                with self.assertRaisesRegex(OSError, 'injected'):
                    self_update.update(releases[1], target)
            after = install.inventory(workspace, workspace)
            for name, checksum in before.items():
                self.assertEqual(after[name], checksum)
            self_update.update(releases[1], target)
            self_update.update(releases[0], target)
            self.assertEqual(mutable.read_bytes(), b'{"id":"synthetic","status":"uncertain"}\n')
            (target/'custom.json').write_text('{"local":true}')
            before = install.inventory(workspace, workspace)
            with self.assertRaisesRegex(ValueError, 'preserved'):
                self_update.update(releases[1], target)
            self.assertEqual(install.inventory(workspace, workspace), before)


if __name__ == '__main__':
    unittest.main()
