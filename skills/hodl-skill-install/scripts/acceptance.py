#!/usr/bin/env python3
"""Resume and record attributed native acceptance; never execute business actions."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.dont_write_bytecode = True  # Keep immutable installed packages free of generated caches.
from install import TARGETS, inventory
from lifecycle import read_state, apply, digest, project_operation


def resume(project, runtime, evidence=None):
    with project_operation(Path(project).resolve() / ".hodl"):
        return _resume(project, runtime, evidence)


def _resume(project, runtime, evidence=None):
    project = Path(project).resolve()
    for path in (project / '.hodl', project / '.hodl/project.json', project / '.hodl/install-state.json'):
        if path.is_symlink():
            raise ValueError('Symlinked acceptance state')
    identity = read_state(project / '.hodl/project.json')
    path = project / '.hodl' / ('managed-' + runtime + '.json')
    if any((path.parent / (path.stem + '-transaction' + suffix)).exists() for suffix in ('.json', '.lock')):
        raise ValueError('Active/interrupted installation; resolve before acceptance')
    managed = read_state(path)
    if not managed or any(managed.get(k) != identity.get(k) for k in ('customer', 'repository')):
        raise ValueError('Missing/conflicting managed installation; run installer first')
    records = managed['skills']
    # Evidence JSON is caller-attributed observation, not executable manifest data.
    if evidence:
        sid = evidence.get('skill')
        record = records.get(sid)
        if not record or evidence.get('version') != record['version'] or evidence.get('filesDigest') != digest(record['files']):
            raise ValueError('Acceptance does not match current skill files/version')
        if evidence.get('kind') not in ('observed', 'user-reported') or any(not isinstance(evidence.get(k), str) or not evidence[k].strip() for k in ('app', 'appVersion', 'invocation', 'localPreflight', 'timestamp')):
            raise ValueError('Missing attributed harmless invocation/app/preflight evidence')
    pending = []
    for sid, record in records.items():
        target = project / TARGETS[runtime] / sid
        if str(target) != record['path'] or any(p.is_symlink() for p in (target, *target.parents)) or inventory(target, target) != record['files']:
            raise ValueError('Installed files changed; acceptance invalid: ' + sid)
        if evidence and evidence['skill'] == sid:
            record['acceptance'] = evidence
        if not record.get('acceptance'):
            pending.append({'id': sid, 'version': record['version'], 'filesDigest': digest(record['files']),
                            'next': 'Load the verified skill in this app; follow documented harmless local help/preflight only'})
    if evidence:
        legacy_path = project / '.hodl/install-state.json'
        state = read_state(legacy_path)
        runtimes = state.setdefault('runtimes', {})
        entry = runtimes.setdefault(runtime, {})
        entry.update(status='acceptance-pending' if pending else 'installed', skills=records,
                     manifestSha256=managed['manifestSha256'], commit=managed.get('commit'),
                     fingerprint=managed['fingerprint'], updated=datetime.now(timezone.utc).isoformat())
        apply([], path, managed, extra_states={legacy_path: state})
    return {'status': 'acceptance-pending' if pending else 'installed', 'pending': pending,
            'portalAcceptance': 'not-checked'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', required=True)
    p.add_argument('--runtime', choices=tuple(TARGETS), required=True)
    p.add_argument('--evidence', help='Local JSON containing attributed invocation evidence, never commands to execute')
    a = p.parse_args()
    try:
        print(json.dumps(resume(a.project, a.runtime, json.loads(Path(a.evidence).read_text()) if a.evidence else None), indent=2))
    except (ValueError, OSError) as e:
        p.exit(1, str(e) + '\n')

if __name__ == '__main__':
    main()
