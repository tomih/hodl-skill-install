#!/usr/bin/env python3
"""Explicit bootstrap replacement from a fetched, authorized release; no network."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True  # Keep immutable installed packages free of generated caches.
import re
from install import inventory
from lifecycle import apply, read_state


def package(root):
    root = Path(root).resolve()
    sums = root / 'SHA256SUMS'
    if sums.is_symlink():
        raise ValueError('Symlinked checksums')
    expected = {}
    for line in sums.read_text().splitlines():
        h, rel = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', h) or rel in expected or Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError('Invalid checksum inventory')
        expected[rel] = h
    actual = inventory(root, root)
    actual.pop('SHA256SUMS', None)
    if actual != expected:
        raise ValueError('Release inventory/checksum mismatch')
    source = root / 'skills/hodl-skill-install'
    text = (source / 'SKILL.md').read_text()
    if not text.startswith('---\nname: hodl-skill-install\n'):
        raise ValueError('Wrong bootstrap identity')
    return source


def update(release, target, prior_release=None):
    source = package(release)
    target = Path(target).absolute()
    for path in (target, *target.parents):
        if path.is_symlink():
            raise ValueError('Symlinked bootstrap path; explicit review required')
    # Outside every skill discovery root, separate from customer identity.
    state_path = target.parent.parent / '.hodl-bootstrap' / 'managed.json'
    state = read_state(state_path)
    current = inventory(target, target) if target.exists() else None
    desired = inventory(source, source)
    baseline = state.get('files') if state.get('path') == str(target) else None
    if prior_release:
        prior = package(prior_release)
        baseline = inventory(prior, prior)
    if current not in (None, desired, baseline):
        raise ValueError('Bootstrap local changes/unmanaged version; preserved. Provide verified prior release')
    apply([(source, target, current)], state_path, dict(state, path=str(target), files=desired), {str(target): desired})
    return {'status': 'files-already-matching' if current == desired else 'files-updated',
            'path': str(target), 'discovery': 'unverified'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release', required=True)
    p.add_argument('--target', required=True)
    p.add_argument('--prior-release')
    a = p.parse_args()
    try:
        print(json.dumps(update(a.release, a.target, a.prior_release), indent=2))
    except (ValueError, OSError) as e:
        p.exit(1, str(e) + '\n')

if __name__ == '__main__':
    main()
