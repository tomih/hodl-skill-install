#!/usr/bin/env python3
"""Verify an exact-repository bundle and install its approved native project skills.
The caller proves exact-repository SSH retrieval; this offline helper cannot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from bootstrap import public_key

TARGETS = {'codex': '.agents/skills', 'claude-code': '.claude/skills'}
SKILL_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
RESERVED_IDS = {'con', 'prn', 'aux', 'nul', *(f'{prefix}{n}' for prefix in ('com', 'lpt') for n in range(1, 10))}
VERSION = re.compile(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?')


def inventory(root, relative_to):
    actual = {}
    for f in root.rglob('*'):
        if f.is_symlink():
            raise ValueError('Symlink in skill tree')
        if f.is_file():
            actual[f.relative_to(relative_to).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
        elif not f.is_dir():
            raise ValueError('Non-regular entry in skill tree')
    return actual


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def validate(bundle, customer, repository, runtime):
    bundle = Path(bundle).resolve()
    for rel in ('manifest.json', 'skills'):
        if (bundle / rel).is_symlink():
            raise ValueError('Symlinked bundle metadata/root')
    m = json.loads((bundle / 'manifest.json').read_text(), object_pairs_hook=unique_object)
    if not isinstance(m, dict) or (m.get('schemaVersion'), m.get('customer'), m.get('repository'), m.get('adapter')) != (1, customer, repository, 'project-standalone-skill'):
        raise ValueError('Manifest identity/adapter mismatch')
    if not isinstance(m.get('bundleVersion'), str) or not VERSION.fullmatch(m['bundleVersion']):
        raise ValueError('Missing exact bundle version')
    runtimes = m.get('supportedRuntimes', [m.get('runtime')])
    if not isinstance(runtimes, list) or runtime not in TARGETS or runtime not in runtimes:
        raise ValueError('Unsupported target runtime')
    skills = m.get('skills')
    if not isinstance(skills, list) or not skills:
        raise ValueError('Missing approved skill list')
    ids = set()
    for skill in skills:
        if not isinstance(skill, dict):
            raise ValueError('Invalid skill entry')
        sid, version = skill.get('id'), skill.get('version')
        if not isinstance(sid, str) or len(sid) > 64 or not SKILL_ID.fullmatch(sid) or sid in ids or sid in RESERVED_IDS:
            raise ValueError('Unsafe or duplicate skill id')
        ids.add(sid)
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise ValueError('Missing exact skill version')
        if skill.get('source') != 'skills/' + sid:
            raise ValueError('Unsupported skill source')
        destinations = skill.get('destinations', {})
        if not isinstance(destinations, dict):
            raise ValueError('Invalid skill destinations')
        for app, path in destinations.items():
            if app not in TARGETS or path != TARGETS[app] + '/' + sid:
                raise ValueError('Unsupported skill destination')
        destination = destinations.get(runtime, skill.get('destination'))
        if destination != TARGETS[runtime] + '/' + sid:
            raise ValueError('Unsupported skill destination')
        source = bundle / 'skills' / sid
        if source.is_symlink() or not source.is_dir():
            raise ValueError('Symlinked or missing skill source')
    root = bundle / 'skills'
    if {p.name for p in root.iterdir()} != ids:
        raise ValueError('Unlisted or missing skill inventory')
    actual = inventory(root, bundle)
    if not actual or actual != m.get('files') or any('skills/' + sid + '/SKILL.md' not in actual for sid in ids):
        raise ValueError('Bundle file inventory/checksum mismatch')
    for sid in ids:
        text = (root / sid / 'SKILL.md').read_text(encoding='utf-8')
        lines = text.splitlines()
        if not lines or lines[0] != '---' or '---' not in lines[1:]:
            raise ValueError('Missing skill frontmatter')
        header = lines[1:lines[1:].index('---') + 1]
        names = [line.partition(':')[2].strip() for line in header if line.startswith('name:')]
        # Native skill packages use a literal frontmatter name, not YAML aliases/tags.
        if len(names) != 1 or names[0] not in (sid, "'" + sid + "'", '"' + sid + '"'):
            raise ValueError('Skill frontmatter name does not match manifest id')
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
    planned = []
    # Validate EVERY destination before writing any skill, including a later conflict.
    for skill in m['skills']:
        sid = skill['id']
        rel = Path(TARGETS[runtime]) / sid
        for ancestor in (*reversed(rel.parents), rel):
            path = project / ancestor
            if path.is_symlink():
                raise ValueError('Symlinked target rejected')
            if path.exists() and not path.is_dir():
                raise ValueError('Non-directory target/ancestor; preserved')
        target = project / rel
        if target.exists():
            expected_files = {Path(p).relative_to('skills/' + sid).as_posix(): h
                              for p, h in m['files'].items() if p.startswith('skills/' + sid + '/')}
            if inventory(target, target) != expected_files:
                raise ValueError('Different version or local changes installed; preserved, updates not supported')
        planned.append((skill, target, target.exists()))
    results = []
    for skill, target, matching in planned:
        if not matching:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(Path(args.bundle) / skill['source'], target)
        results.append({'id': skill['id'], 'version': skill['version'], 'path': str(target),
                        'status': 'files-already-matching' if matching else 'files-installed'})
    result = {'status': 'files-already-matching' if all(x[2] for x in planned) else 'files-installed',
              'bundleVersion': m['bundleVersion'], 'skills': results, 'fingerprint': fingerprint,
              'registration': 'unverified',
              'next': 'Invoke each verified skill harmlessly in the actual app; reload only if discovery needs it'}
    if len(results) == 1:
        result['path'] = results[0]['path']
    return result


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
