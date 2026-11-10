# hodl-skill-install 0.2.8

Install, update and resume local acceptance of approved customer skills. Publisher configuration supplies repository naming; supply the customer slug. Bare invocation resumes pending acceptance or checks the exact customer repository. Bootstrap replacement is an explicit request using separate authorized source access.

Provisioning requests are HODL1 tokens. The QR contains exactly the token; verify token and QR round-trip before display. Token encoding/decoding uses Python stdlib only. It obscures public request data but provides no authentication or integrity. Publisher approval through an authenticated channel is still required. The decoder is `skills/hodl-skill-install/scripts/request_token.py decode --customer <slug> --token <token>`; decoded data never supplies executable instructions.

Verify the full SHA256SUMS inventory from an authorized fetched release. Follow `skills/hodl-skill-install/SKILL.md` and `references/installation.md` for commands, native runtime adapters, managed updates, backups and interrupted-operation recovery. Preserve keys, project configuration, other skills and local changes. Native discovery/local preflight and portal acceptance are distinct. There is no background service or automatic provisioning.
