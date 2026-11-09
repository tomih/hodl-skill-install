#!/usr/bin/env python3
"""Verify curated pilot bundle and receipt; install standalone Codex project skills.
No SSH key creation, network, provisioning, user-wide fallback or updater.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys
from bootstrap import public_key

def validate(bundle, receipt, key, customer, repository):
    bundle = Path(bundle).resolve()
    m = json.loads((bundle / 'manifest.json').read_text())
    fingerprint = public_key(key)[1]
    repository_receipt = receipt is None
    if repository_receipt:
        digest = base64.b64decode(fingerprint.split(':', 1)[1] + '=').hex()
        receipt = bundle / 'provisioning/receipts' / (digest + '.json')
    receipt = Path(receipt)
    if receipt.is_symlink():
        raise ValueError('Symlinked provisioning receipt')
    r = json.loads(receipt.read_text())
    if repository_receipt or 'manifestSha256' in r:
        if r.get('manifestSha256') != hashlib.sha256((bundle / 'manifest.json').read_bytes()).hexdigest():
            raise ValueError('Provisioning receipt manifest digest mismatch')
    if type(r.get('keyId')) is not int or r['keyId'] <= 0:
        raise ValueError('Receipt requires positive GitHub keyId')
    expected = {'schemaVersion':1, 'type':'hodl.deploy-key.receipt', 'customer':customer,
                'repository':repository, 'fingerprint':fingerprint, 'scope':'read-only', 'approved':True}
    if any(r.get(k) != v for k,v in expected.items()):
        raise ValueError('Receipt mismatch; obtain matching authenticated Frost confirmation')
    if (m.get('schemaVersion'),m.get('customer'),m.get('repository'),m.get('runtime'),m.get('adapter')) != (1,customer,repository,'codex','project-standalone-skill'):
        raise ValueError('Manifest identity/adapter mismatch')
    # Pilot adapter deliberately supports one approved skill, not arbitrary manifest paths.
    if m.get('skills') != [{'id':'ebonitete','version':'0.1.1','source':'skills/ebonitete','destination':'.agents/skills/ebonitete'}]:
        raise ValueError('Unsupported pilot skill/version')
    if (bundle / 'skills').is_symlink() or (bundle / 'manifest.json').is_symlink():
        raise ValueError('Symlinked bundle metadata/root')
    source = bundle / 'skills/ebonitete'
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Invalid skill root')
    actual = {}
    for f in source.rglob('*'):
        if f.is_symlink(): raise ValueError('Symlink in bundle')
        if f.is_file(): actual[str(f.relative_to(bundle))] = hashlib.sha256(f.read_bytes()).hexdigest()
    if not actual or actual != m.get('files') or 'skills/ebonitete/SKILL.md' not in actual:
        raise ValueError('Bundle file inventory/checksum mismatch')
    return m

def install(args):
    m = validate(args.bundle,args.receipt,args.public_key,args.customer,args.repository)
    project = Path(args.project).resolve()
    identity = json.loads((project/'.hodl/project.json').read_text())
    if any(identity.get(k)!=v for k,v in {'customer':args.customer,'repository':args.repository,'runtime':'codex','project':str(project)}.items()):
        raise ValueError('Project identity mismatch')
    for rel in ('.hodl','.agents','.agents/skills','.agents/skills/ebonitete'):
        if (project/rel).is_symlink(): raise ValueError('Symlinked target/state rejected')
    target=project/'.agents/skills/ebonitete'
    if target.exists(): raise ValueError('Existing skill preserved; review manually, no overwrite')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(Path(args.bundle)/'skills/ebonitete',target)
    return {'status':'files-installed','bundleVersion':m['bundleVersion'],'path':str(target),
            'registration':'unverified','next':'New desktop chat: observe discovery and harmless invocation before recording acceptance'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','public-key','project','customer','repository'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--receipt', help='Legacy explicit receipt; default reads fingerprint-matched receipt from the authenticated customer clone')
    a=p.parse_args()
    try: print(json.dumps(install(a),indent=2))
    except (ValueError,OSError) as e: p.exit(1,str(e)+'\n')
if __name__=='__main__': main()
