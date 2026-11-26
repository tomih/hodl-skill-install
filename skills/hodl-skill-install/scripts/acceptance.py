#!/usr/bin/env python3
"""Record attributed native load, explicit local setup and read-only preflight; execute no hooks."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid
sys.dont_write_bytecode = True
from install import TARGETS, inventory
from lifecycle import read_state, apply, digest, project_operation, acceptance_complete


def strings(value, fields):
    if any(not isinstance(value.get(k), str) or not value[k].strip() for k in fields):
        raise ValueError('Missing attributed stage fields: ' + ', '.join(fields))


def resume(project, runtime, evidence=None, setup_begin=None, setup_result=None):
    if sum(x is not None for x in (evidence, setup_begin, setup_result)) > 1:
        raise ValueError('Only one stage event per call')
    with project_operation(Path(project).resolve() / ".hodl"):
        return _resume(project, runtime, evidence, setup_begin, setup_result)


def _resume(project, runtime, evidence=None, setup_begin=None, setup_result=None):
    project = Path(project).resolve()
    for state_path in (project / '.hodl', project / '.hodl/project.json', project / '.hodl/install-state.json'):
        if state_path.is_symlink():
            raise ValueError('Symlinked acceptance state')
    identity = read_state(project / '.hodl/project.json')
    path = project / '.hodl' / ('managed-' + runtime + '.json')
    if any((path.parent / (path.stem + '-transaction' + suffix)).exists() for suffix in ('.json', '.lock')):
        raise ValueError('Active/interrupted installation; resolve before acceptance')
    managed = read_state(path)
    if not managed or any(managed.get(k) != identity.get(k) for k in ('customer', 'repository')):
        raise ValueError('Missing/conflicting managed installation; run installer first')
    records = managed['skills']
    # Validate every managed tree before persisting any stage. All events are data,
    # caller-attributed observations, never commands or independently verified authority.
    for sid, record in records.items():
        target = project / TARGETS[runtime] / sid
        if str(target) != record['path'] or any(p.is_symlink() for p in (target, *target.parents)) or inventory(target, target) != record['files']:
            raise ValueError('Installed files changed; acceptance invalid: ' + sid)
    event = next((x for x in (evidence, setup_begin, setup_result) if x is not None), None)
    if event is not None:
        if not isinstance(event, dict):
            raise ValueError('Stage evidence must be a JSON object')
        record = records.get(event.get('skill'))
        if not record or event.get('version') != record['version'] or event.get('filesDigest') != digest(record['files']):
            raise ValueError('Acceptance does not match current skill files/version')
        if setup_begin is not None:
            strings(event, ('authorization', 'setupInvocation', 'app', 'appVersion', 'invocation', 'timestamp'))
            if event.get('kind') not in ('observed', 'user-reported'):
                raise ValueError('Missing attributed native-load kind')
            record['localSetup'] = dict(event, status='pending', attempt=uuid.uuid4().hex)
        elif setup_result is not None:
            setup = record.get('localSetup', {})
            strings(event, ('attempt', 'invocation', 'timestamp', 'detail'))
            if event.get('status') not in ('succeeded', 'failed'):
                raise ValueError('Setup result must be succeeded or failed')
            if (setup.get('attempt') != event['attempt'] or setup.get('status') != 'pending'
                    or event['invocation'] != setup.get('setupInvocation')):
                raise ValueError('Setup result does not match a pending documented attempt')
            setup.update(status=event['status'], result=event)
        else:
            if event.get('kind') not in ('observed', 'user-reported'):
                raise ValueError('Missing attributed harmless invocation/app/preflight evidence')
            strings(event, ('app', 'appVersion', 'invocation', 'localPreflight', 'timestamp'))
            setup = record.get('localSetup')
            if setup and (setup.get('status') != 'succeeded' or
                          event.get('setupAttempt') != setup['attempt'] or
                          event.get('preflightStatus') != 'passed'):
                raise ValueError('Preflight requires succeeded setup and the same setupAttempt with preflightStatus=passed')
            record['acceptance'] = event
    pending = []
    for sid, record in records.items():
        if not acceptance_complete(record):
            setup = record.get('localSetup')
            stage = 'setup' if setup and setup.get('status') != 'succeeded' else 'native-preflight'
            pending.append({'id': sid, 'version': record['version'], 'filesDigest': digest(record['files']),
                            'stage': stage,
                            'setupAttempt': setup.get('attempt') if setup else None,
                            'next': ('Resume explicitly authorized documented setup, then read-only preflight'
                                     if setup else 'Load the verified skill in this app; follow documented harmless local help/preflight only')})
    if event is not None:
        legacy_path = project / '.hodl/install-state.json'
        state = read_state(legacy_path)
        entry = state.setdefault('runtimes', {}).setdefault(runtime, {})
        entry.update(status='acceptance-pending' if pending else 'installed', skills=records,
                     manifestSha256=managed['manifestSha256'], commit=managed.get('commit'),
                     fingerprint=managed['fingerprint'], updated=datetime.now(timezone.utc).isoformat())
        apply([], path, managed, extra_states={legacy_path: state})
    return {'status': 'acceptance-pending' if pending else 'installed', 'pending': pending,
            'portalAcceptance': 'not-checked'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--runtime', choices=tuple(TARGETS), required=True)
    events = parser.add_mutually_exclusive_group()
    events.add_argument('--evidence', help='Private JSON: successful attributed read-only native preflight')
    events.add_argument('--setup-begin', help='Private JSON: verified native load and explicit setup authorization reference')
    events.add_argument('--setup-result', help='Private JSON: observed outcome of that documented setup attempt')
    args = parser.parse_args()
    try:
        load = lambda p: json.loads(Path(p).read_text()) if p else None
        print(json.dumps(resume(args.project, args.runtime, load(args.evidence),
                                load(args.setup_begin), load(args.setup_result)), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
