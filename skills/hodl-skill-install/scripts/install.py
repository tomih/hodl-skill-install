#!/usr/bin/env python3
"""Verify a publisher-retrieved pilot bundle and install native project skills.
The caller proves exact-repository SSH retrieval; this offline helper cannot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from bootstrap import public_key

TARGETS = {'codex': '.agents/skills/ebonitete', 'claude-code': '.claude/skills/ebonitete'}


def inventory(root, relative_to):
    actual = {}
    for f in root.rglob('*'):
        if f.is_symlink():
            raise ValueError('Symlink in skill tree')
        if f.is_file():
            actual[f.relative_to(relative_to).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return actual


def validate(bundle, customer, repository, runtime):
    bundle = Path(bundle).resolve()
    for rel in ('manifest.json', 'skills', 'skills/ebonitete'):
        if (bundle / rel).is_symlink():
            raise ValueError('Symlinked bundle metadata/root')
    m = json.loads((bundle / 'manifest.json').read_text())
    if (m.get('schemaVersion'), m.get('customer'), m.get('repository'), m.get('adapter')) != (1, customer, repository, 'project-standalone-skill'):
        raise ValueError('Manifest identity/adapter mismatch')
    runtimes = m.get('supportedRuntimes', [m.get('runtime')])
    if runtime not in TARGETS or runtime not in runtimes:
        raise ValueError('Unsupported target runtime')
    skills = m.get('skills')
    if not isinstance(skills, list) or len(skills) != 1:
        raise ValueError('Unsupported pilot skill list')
    skill = skills[0]
    if skill.get('id') != 'ebonitete' or skill.get('version') not in ('0.1.1', '0.1.2') or skill.get('source') != 'skills/ebonitete':
        raise ValueError('Unsupported pilot skill/version/source')
    destination = skill.get('destinations', {}).get(runtime, skill.get('destination'))
    if destination != TARGETS[runtime]:
        raise ValueError('Unsupported skill destination')
    source = bundle / 'skills/ebonitete'
    if not source.is_dir():
        raise ValueError('Missing skill source')
    actual = inventory(source, bundle)
    if not actual or actual != m.get('files') or 'skills/ebonitete/SKILL.md' not in actual:
        raise ValueError('Bundle file inventory/checksum mismatch')
    return m


def install(args):
    project = Path(args.project).resolve()
    for rel in ('.hodl', '.hodl/project.json'):
        if (project / rel).is_symlink():
            raise ValueError('Symlinked project identity')
    identity = json.loads((project / '.hodl/project.json').read_text())
    runtime = getattr(args, 'runtime', None)
    if runtime not in TARGETS:
        raise ValueError('Explicit actual --runtime required')
    expected = {'customer': args.customer, 'repository': args.repository, 'project': str(project)}
    if any(identity.get(k) != v for k, v in expected.items()):
        raise ValueError('Project identity mismatch')
    m = validate(args.bundle, args.customer, args.repository, runtime)
    fingerprint = public_key(args.public_key)[1]
    rel = Path(TARGETS[runtime])
    for ancestor in (*reversed(rel.parents), rel):
        if (project / ancestor).is_symlink():
            raise ValueError('Symlinked target rejected')
    target = project / rel
    if target.exists():
        expected_files = {Path(p).relative_to('skills/ebonitete').as_posix(): h for p, h in m['files'].items()}
        if not target.is_dir() or inventory(target, target) != expected_files:
            raise ValueError('Different version or local changes installed; preserved, updates not supported')
        status = 'files-already-matching'
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(Path(args.bundle) / 'skills/ebonitete', target)
        status = 'files-installed'
    return {'status': status, 'bundleVersion': m['bundleVersion'], 'path': str(target),
            'fingerprint': fingerprint, 'registration': 'unverified',
            'next': 'Invoke the skill in the actual target app; reload only if discovery needs it'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'public-key', 'project', 'customer', 'repository'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--runtime', choices=tuple(TARGETS), required=True)
    a = p.parse_args()
    try:
        print(json.dumps(install(a), indent=2))
    except (ValueError, OSError) as e:
        p.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
