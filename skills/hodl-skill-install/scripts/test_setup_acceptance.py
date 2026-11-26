"""Attribution/stage tests only; synthetic evidence is not native host acceptance."""
import json
import unittest
from unittest.mock import patch
import acceptance
import install
import lifecycle
import test_install as fixtures


class SetupAcceptanceTests(unittest.TestCase):
    save_manifest = fixtures.InstallTests.save_manifest
    set_runtime = fixtures.InstallTests.set_runtime

    def setUp(self):
        fixtures.InstallTests.setUp(self)
        install.install(self.args)

    def event(self):
        record = json.loads((self.project / '.hodl/managed-codex.json').read_text())['skills']['ebonitete']
        return dict(skill='ebonitete', version=record['version'], filesDigest=lifecycle.digest(record['files']),
                    kind='observed', app='synthetic-host', appVersion='unknown',
                    invocation='synthetic native load', timestamp='2026-11-26T10:00:00Z')

    def begin(self):
        event = dict(self.event(), authorization='synthetic local task approval; this project only',
                     setupInvocation='python3 -B installed/scripts/setup_project.py --project-root EXACT')
        result = acceptance.resume(self.project, 'codex', setup_begin=event)
        self.assertEqual(result['pending'][0]['stage'], 'setup')
        return result['pending'][0]['setupAttempt']

    def result(self, attempt, status='succeeded'):
        event = dict(self.event(), attempt=attempt, status=status,
                     invocation='python3 -B installed/scripts/setup_project.py --project-root EXACT',
                     detail='synthetic observed ' + status)
        return acceptance.resume(self.project, 'codex', setup_result=event)

    def accept(self, attempt):
        return acceptance.resume(self.project, 'codex', evidence=dict(
            self.event(), localPreflight='read-only checks passed', setupAttempt=attempt, preflightStatus='passed'))

    def test_stage_sequence_and_noop_do_not_complete_early(self):
        attempt = self.begin()
        with self.assertRaisesRegex(ValueError, 'succeeded setup'):
            self.accept(attempt)
        install.install(self.args)
        self.assertEqual(acceptance.resume(self.project, 'codex')['pending'][0]['setupAttempt'], attempt)
        self.result(attempt)
        self.assertEqual(acceptance.resume(self.project, 'codex')['pending'][0]['stage'], 'native-preflight')
        self.assertEqual(self.accept(attempt)['status'], 'installed')
        self.assertEqual(install.install(self.args)['skills'][0]['acceptance'], 'complete')
        # A new cycle must recheck mutable setup, even with old unchanged acceptance.
        second = self.begin()
        self.assertNotEqual(second, attempt)
        self.assertEqual(install.install(self.args)['skills'][0]['acceptance'], 'pending')
        self.result(second)
        with self.assertRaises(ValueError):
            self.accept(attempt)
        self.assertEqual(self.accept(second)['status'], 'installed')

    def test_failed_or_interrupted_setup_resumes_without_bootstrap(self):
        attempt = self.begin()
        self.assertEqual(acceptance.resume(self.project, 'codex')['status'], 'acceptance-pending')
        self.result(attempt, 'failed')
        install.install(self.args)
        with self.assertRaises(ValueError):
            self.accept(attempt)
        second = self.begin()
        self.result(second)
        self.assertEqual(self.accept(second)['status'], 'installed')

    def test_missing_authorization_and_invalid_results_do_not_write(self):
        path = self.project / '.hodl/managed-codex.json'
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'authorization'):
            acceptance.resume(self.project, 'codex', setup_begin=self.event())
        self.assertEqual(path.read_bytes(), before)
        attempt = self.begin()
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.result('stale-attempt')
        bad = dict(self.event(), attempt=attempt, status='succeeded', invocation='unreviewed hook',
                   detail='fake')
        with self.assertRaises(ValueError):
            acceptance.resume(self.project, 'codex', setup_result=bad)
        self.assertEqual(path.read_bytes(), before)

    def test_changed_skill_and_interrupted_journal_reject_stage(self):
        event = dict(self.event(), authorization='local fixture approval', setupInvocation='documented fixture command')
        target = self.project / '.agents/skills/ebonitete/SKILL.md'
        target.write_text(target.read_text() + ' local modification')
        with self.assertRaisesRegex(ValueError, 'files changed'):
            acceptance.resume(self.project, 'codex', setup_begin=event)
        target.write_bytes((self.source / 'SKILL.md').read_bytes())
        journal = self.project / '.hodl/managed-codex-transaction.json'
        journal.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'transaction|installation'):
            acceptance.resume(self.project, 'codex', setup_begin=event)

    def test_setup_state_write_failure_rolls_back_and_old_stage_not_promoted(self):
        attempt = self.begin()
        managed = self.project / '.hodl/managed-codex.json'
        legacy = self.project / '.hodl/install-state.json'
        before = [p.read_bytes() for p in (managed, legacy)]
        original = lifecycle.atomic_json
        def fail(path, value):
            if path == legacy:
                raise OSError('fixture state failure')
            return original(path, value)
        with patch.object(lifecycle, 'atomic_json', side_effect=fail):
            with self.assertRaises(OSError):
                self.result(attempt)
        self.assertEqual([p.read_bytes() for p in (managed, legacy)], before)
        self.assertEqual(acceptance.resume(self.project, 'codex')['pending'][0]['stage'], 'setup')

    def test_setup_does_not_execute_any_recorded_command(self):
        marker = self.root / 'must-not-exist'
        event = dict(self.event(), authorization='fixture explicit task',
                     setupInvocation='touch ' + str(marker))
        acceptance.resume(self.project, 'codex', setup_begin=event)
        self.assertFalse(marker.exists())
        self.assertFalse((self.project / '.hodl/ebonitete.json').exists())
