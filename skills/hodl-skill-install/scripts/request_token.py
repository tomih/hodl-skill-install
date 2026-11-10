#!/usr/bin/env python3
"""Encode/decode public deploy-key requests. Obfuscation is not authentication."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True

PREFIX = 'HODL1.'
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
FIELDS = {'schemaVersion', 'type', 'customer', 'repository', 'device', 'scope', 'publicKey', 'fingerprint'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate request field')
        result[key] = value
    return result


def validate_request(request, customer):
    if not isinstance(customer, str) or not SLUG.fullmatch(customer):
        raise ValueError('Expected a lowercase kebab-case customer slug')
    if not isinstance(request, dict) or set(request) != FIELDS:
        raise ValueError('Invalid request schema')
    publisher = json.loads((Path(__file__).resolve().parent.parent / 'publisher.json').read_text(encoding='utf-8'))
    if (type(request['schemaVersion']) is not int or request['schemaVersion'] != 1 or
            request['type'] != 'hodl.deploy-key.request' or request['customer'] != customer or
            request['repository'] != publisher['owner'] + '/' + publisher['customerRepositoryPrefix'] + customer or
            request['scope'] != 'read-only'):
        raise ValueError('Request identity/schema/scope mismatch')
    if not isinstance(request['device'], str) or not request['device'].strip() or len(request['device']) > 255 or any(ord(c) < 32 for c in request['device']):
        raise ValueError('Invalid device label')
    key = request['publicKey']
    if not isinstance(key, str) or len(key.split()) != 2 or key.split()[0] != 'ssh-ed25519':
        raise ValueError('Invalid Ed25519 public key')
    try:
        blob = base64.b64decode(key.split()[1], validate=True)
    except ValueError as exc:
        raise ValueError('Invalid public key encoding') from exc
    if len(blob) != 51 or not blob.startswith(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'):
        raise ValueError('Invalid Ed25519 public key structure')
    fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode('ascii').rstrip('=')
    if request['fingerprint'] != fingerprint:
        raise ValueError('Public key fingerprint mismatch')
    return request


def xor(data, customer):
    key = customer.encode('utf-8')
    if not key:
        raise ValueError('Customer slug required')
    return bytes(value ^ key[n % len(key)] for n, value in enumerate(data))


def encode(request, customer):
    validate_request(request, customer)
    raw = json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return PREFIX + base64.urlsafe_b64encode(xor(raw, customer)).decode('ascii').rstrip('=')


def decode(token, customer):
    if not isinstance(customer, str) or not SLUG.fullmatch(customer):
        raise ValueError('Expected a lowercase kebab-case customer slug')
    if not isinstance(token, str) or not token.startswith(PREFIX) or len(token) > 16384:
        raise ValueError('Invalid HODL1 token')
    body = token[len(PREFIX):]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', body):
        raise ValueError('Invalid Base64URL token')
    try:
        data = base64.b64decode(body + '=' * (-len(body) % 4), altchars=b'-_', validate=True)
        if base64.urlsafe_b64encode(data).decode('ascii').rstrip('=') != body:
            raise ValueError('Noncanonical Base64URL token')
        request = json.loads(xor(data, customer).decode('utf-8'), object_pairs_hook=unique_object)
        return validate_request(request, customer)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError('Invalid request token or customer slug: ' + str(exc)) from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    enc = commands.add_parser('encode')
    enc.add_argument('--request', required=True, help='UTF-8 JSON file containing the public request')
    enc.add_argument('--customer', required=True)
    dec = commands.add_parser('decode')
    dec.add_argument('--token', required=True)
    dec.add_argument('--customer', required=True)
    args = p.parse_args()
    try:
        if args.command == 'encode':
            print(encode(json.loads(Path(args.request).read_text(encoding='utf-8'), object_pairs_hook=unique_object), args.customer))
        else:
            print(json.dumps(decode(args.token, args.customer), ensure_ascii=True, indent=2))
    except (ValueError, OSError, TypeError) as exc:
        p.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
