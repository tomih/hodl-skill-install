#!/usr/bin/env python3
"""Preparation and canonical QR request helpers; full orchestration is in SKILL.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
RUNTIMES = ('codex', 'claude-code')

def checked_slug(value):
    if not SLUG.fullmatch(value):
        raise ValueError('Expected a lowercase kebab-case customer slug')
    return value

def detect_project(start):
    start = Path(start).resolve()
    for p in (start, *start.parents):
        if (p / '.hodl/project.json').is_file() or (p / '.git').exists():
            return p
    return start

def detect_runtime():
    # Executable presence is not evidence of the active host.
    if os.environ.get('CODEX_THREAD_ID') and not os.environ.get('CLAUDECODE'):
        return 'codex'
    if os.environ.get('CLAUDECODE') and not os.environ.get('CODEX_THREAD_ID'):
        return 'claude-code'
    return None

def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}

def store(project, name, value):
    folder = project / '.hodl'
    if folder.is_symlink():
        raise ValueError('Refusing symlinked .hodl directory')
    folder.mkdir(exist_ok=True)
    target = folder / name
    # Exclusive create: never clobber user settings, including on a repeated run.
    with target.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')

def public_key(path):
    raw = Path(path).read_text().strip()
    parts = raw.split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519':
        raise ValueError('MVP accepts only an OpenSSH Ed25519 public key, never a private key')
    blob = base64.b64decode(parts[1], validate=True)
    prefix = b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'
    if len(blob) != 51 or not blob.startswith(prefix):
        raise ValueError('Invalid Ed25519 public key structure')
    fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')
    return ' '.join(parts[:2]), fingerprint

def prepare(args):
    project = detect_project(args.project)
    old = read_json(project / '.hodl/project.json')
    if old and old.get('project') != str(project):
        raise ValueError('Stored project path does not match active project; review identity before reuse')
    customer = checked_slug(args.customer or old.get('customer') or input('Customer slug: ').strip())
    runtime = args.runtime or old.get('runtime') or detect_runtime()
    if runtime not in RUNTIMES:
        raise ValueError('Active runtime ambiguous; specify --runtime codex or claude-code (not generic Claude chat/Cowork)')
    repo = old.get('repository')
    if args.repository:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/hodl-client-' + re.escape(customer), args.repository):
            raise ValueError('Repository must be an explicit owner/hodl-client-<customer>')
        if repo and repo != args.repository:
            raise ValueError('Repository conflicts with existing project identity')
        repo = args.repository
    result = {'schemaVersion': 1, 'customer': customer, 'repository': repo,
              'runtime': runtime, 'project': str(project)}
    if old and any(old.get(k) != result[k] for k in ('customer','runtime','repository')):
        raise ValueError('Project identity conflict; review existing configuration first')
    if args.write:
        if not old:
            store(project, 'project.json', result)
        if not (project / '.hodl/install-state.json').exists():
            store(project, 'install-state.json', {'schemaVersion': 1, 'status': 'prepared',
                  'installed': [], 'registration': 'unverified', 'access': 'unverified'})
    return {'project': result, 'tools': {t: shutil.which(t) for t in ('git','ssh','ssh-keygen','qrencode')},
            'next': 'Confirm repository with Frost; reuse a proven scoped identity or create a dedicated no-passphrase read-only deploy key. No installation performed.'}

def request(args):
    customer = checked_slug(args.customer)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/hodl-client-' + re.escape(customer), args.repository):
        raise ValueError('Exact owner/customer repository required')
    key, fingerprint = public_key(args.public_key)
    result = {'schemaVersion': 1, 'type': 'hodl.deploy-key.request',
              'customer': customer, 'repository': args.repository,
              'device': args.device or socket.gethostname(), 'scope': 'read-only',
              'publicKey': key, 'fingerprint': fingerprint,
              'approval': 'Frost must verify explicit requester approval in the authenticated conversation'}
    payload = json.dumps(result, ensure_ascii=True, separators=(',', ':'))
    if args.qr:
        # No shell interpolation; exclusive reservation prevents overwrite.
        output = Path(args.qr)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as f:
                if shutil.which('qrencode'):
                    subprocess.run(['qrencode', '-t', 'PNG', '-l', 'M', '-s', '8', '-o', '-'],
                                   input=payload.encode(), stdout=f, check=True)
                else:
                    try:
                        import qrcode
                    except ImportError:
                        raise ValueError('No local QR backend. Omit --qr, serialize request compactly, and let the local agent choose an available offline encoder; guide user if installation is needed.')
                    qrcode.make(payload).save(f, format='PNG')
        except Exception:
            output.unlink(missing_ok=True)
            raise
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare', help='Detect project and runtime; default is read-only')
    prep.add_argument('--project', default='.')
    prep.add_argument('--customer')
    prep.add_argument('--runtime', choices=RUNTIMES)
    prep.add_argument('--repository')
    prep.add_argument('--write', action='store_true', help='Create flat .hodl metadata, never install')
    req = commands.add_parser('request', help='Build public-key QR handoff, never send')
    req.add_argument('--customer', required=True)
    req.add_argument('--repository', required=True)
    req.add_argument('--device')
    req.add_argument('--public-key', required=True)
    req.add_argument('--qr', help='New PNG output path; use a private temporary delivery directory')
    args = p.parse_args()
    try:
        print(json.dumps(prepare(args) if args.command == 'prepare' else request(args), indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        p.exit(1, str(exc) + '\n')

if __name__ == '__main__':
    main()
