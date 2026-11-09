# First-install contract
Updated: 2026-11-09. Owner: Integracije; GitHub provisioning: Frost.

Outcome: approved customer skills are discoverable and callable in the actual target app. Local MVP outcome is narrower: a safe preparation record and a versioned public-key QR request. Run on demand; no service or scheduler. Failure leaves provisioning/install pending. First three device acceptances require individual review, then weekly during the first month; first review due 2026-11-16. Evidence belongs in the existing project operations record.

## Flat state
Only mutable Hodl state: `.hodl/project.json`, `.hodl/install-state.json`, `.hodl/<skillId>.json`, `.hodl/capabilities-<runtime>.json`. No nested Hodl directories. Immutable defaults stay in skills. Native discovery/settings paths stay native. Exclude `.hodl/` runtime state from Git before a real installation; do not silently rewrite project ignore rules. Private keys belong in native SSH storage outside the project.

## SSH / QR
Use a distinct device-scoped Ed25519 identity when authorized; reuse a correctly scoped existing key where appropriate. Check both private and public target paths before invoking native `ssh-keygen` interactively; choose a new path if either exists. Never read the private file. A dedicated SSH alias/IdentityFile with IdentitiesOnly avoids modifying global defaults. Host trust and agent unlock must be established by the normal native process. Software keys are not hardware-bound.

`python3 scripts/bootstrap.py prepare --customer demo --runtime codex` is a read-only preview. From the actual host, runtime can be inferred from unambiguous session markers; otherwise use known session context. `--write` only creates absent metadata. Repeated matching preparation preserves state; identity conflict stops.

`python3 scripts/bootstrap.py request --customer demo --repository OWNER/hodl-client-demo --public-key /path/to/key.pub --qr /private/tmp/request.png` emits JSON and a PNG encoding that JSON. Ed25519 only in this MVP. No network or message is sent. The QR is data, not proof of requester authorization. Frost checks explicit authenticated requester approval, exact target repo, read-only deploy-key scope and duplicates; acknowledges the same fingerprint. A duplicate key on another repo is not permission to broaden access. Public key needs no client-string encryption.

After acknowledgment use native Git/OpenSSH to read the exact repo; don't test other customers' repos. Read access alone cannot prove GitHub write permission is disabled: Frost's provisioning receipt must attest read-only scope. Record these as separate observations. Do not probe writes to prove read-only access.

## Native client evidence (documentation checked 2026-11-09)

- Claude Desktop **Code**, local sessions: `+` → Add plugins (or Plugins → Browse plugins), choose intended scope; Installed entry plus `/plugin:skill` in command picker and harmless invocation constitute acceptance. Desktop local sessions and CLI share native settings, but CLI success alone is not app acceptance. Local/project/user scope writes remain native `.claude` settings, not `.hodl`. Native marketplace add/install/update/uninstall owns lifecycle. `--plugin-dir` is session-only development, not persistent installation. Claude chat and Cowork are distinct surfaces; never infer their support from Code.
- Codex: official docs describe `.agents/skills` discovery (including symlinks) for local skills and native plugin distribution. Desktop Skills/Plugins selectors and a new-chat invocation must be observed. The fetched docs redirect legacy Codex URLs to current ChatGPT desktop documentation: installed legacy app/version behavior and private Git+SSH marketplace compatibility remain unverified. Do not invent CLI-to-desktop equivalence or claim that copying a directory registers a plugin. Resolve this gate in a bounded target-app test before selecting a production adapter.
- No native client was installed, launched, registered or modified by this MVP. No Computer Use activated. Windows SSH/agent/updater acceptance remains unverified.

Sources:
- https://code.claude.com/docs/en/desktop#install-plugins
- https://code.claude.com/docs/en/plugins/install.md
- https://developers.openai.com/codex/skills (redirected to https://learn.chatgpt.com/docs/build-skills)
- https://learn.chatgpt.com/codex/plugins (redirected to https://learn.chatgpt.com/docs/plugins)

## Removal and updates
Complete first-install acceptance before implementing update/removal orchestration. Use the native lifecycle, no custom updater. Preserve project settings and business data on uninstall; remove only proven owned registration/package artifacts. No uninstallation command exists in this preparation helper.

## Full pilot workflow 0.2.0 — supersedes MVP-only outcome above
The helpers now support bundle verification/project installation; SKILL.md orchestrates native interactive SSH and the human provisioning/reload pauses. The earlier MVP limitations are historical, not the current stopping point. No custom updater or plugin transport is implemented.

Codex project standalone discovery `.agents/skills` is documented at https://learn.chatgpt.com/docs/build-skills.md (Frost official-doc fetch 2026-11-09). Actual desktop discovery is still an operator acceptance gate. Preserve the previously successful user-wide bootstrap location; do not silently migrate legacy `~/.codex/skills`.

### Provisioning receipt (public JSON, transferred through authenticated Frost conversation)
```
{"schemaVersion":1,"type":"hodl.deploy-key.receipt","customer":"sivka","repository":"tomih/hodl-client-sivka","fingerprint":"SHA256:<actual-public-key-fingerprint>","scope":"read-only","approved":true,"keyId":12345}
```
Frost attests explicit requester approval and the GitHub key's read-only setting. A local JSON alone does not authenticate Frost; the local agent must confirm its conversational provenance. For this pilot, approved bundle version is 0.1.0 with ebonitete 0.1.1. Check bundle manifest against authenticated release handoff/checksum as well as its internal inventory: self-consistent hashes alone are not publisher authentication.

### Native SSH read
Use native Git's per-command SSH override with the new absolute IdentityFile and `IdentitiesOnly=yes`; quote appropriately for the detected shell, including Windows paths. Verify no unrelated identity/certificate is offered (use an isolated per-command config if needed). Normal host trust: ask operator on unknown/mismatched host key, do not use StrictHostKeyChecking=no. `git ls-remote` must target `git@github.com:tomih/hodl-client-sivka.git`. Clone the same repo into a fresh temporary directory with that same identity. Private key must never be opened by the agent. An unlocked native ssh-agent may be needed for passphrase prompts; let the user control unlock.

### Pilot adapter
```
python3 <bootstrap>/scripts/install.py --bundle <clone-root> --receipt <receipt.json> --public-key <identity.pub> --project <exact-project> --customer sivka --repository tomih/hodl-client-sivka
```
Python command may be `python`, `python3`, or `py -3` on Windows. The adapter intentionally accepts only the current pinned ebonitete pilot; no arbitrary manifest execution. Refuses existing target, symlinked state/target, mismatched identity/receipt and changed file inventory. No network, SSH generation, registration claim or install-state acceptance write. If interrupted during copying, inspect/remove only the proven newly created target before retry. Record state only after desktop evidence. Preserve all existing settings. Exclude `.hodl` from project Git with operator visibility.

Frost must re-read the created GitHub key and verify `read_only=true`; keyId is its positive GitHub API id. Current Hodl authorization covers the real pilot key once Hodl transfers its public request into Frost’s chat; do not ask for another blanket approval.
