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
