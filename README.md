# hodl-skill-install

Preview 0.1.0 — local onboarding preparation and public-key QR handoff.

This MVP detects a project/runtime, previews or creates flat `.hodl` metadata,
and creates a versioned public-key request for Hodl to forward to Frost.
It does not create SSH keys, contact Frost, provision customer repositories,
or install/update customer plugins. Python 3 is required; PNG generation also
requires `qrencode` (macOS: `brew install qrencode`). The QR integration test
is explicitly skipped when `qrencode` or `ssh-keygen` is unavailable; a skip is
not QR acceptance. Private keys must remain outside this repository.

## Verify without changing a customer project

```sh
python3 skills/hodl-skill-install/scripts/test_bootstrap.py
python3 skills/hodl-skill-install/scripts/bootstrap.py --help
```

## Codex local discovery test

Clone this repository, then in an explicitly selected disposable project create
`.agents/skills/hodl-skill-install` as a symlink to the absolute directory
`skills/hodl-skill-install` in the clone. Do not replace an existing entry.
Open that project in Codex, start a new chat, verify the skill selector and invoke
`$hodl-skill-install` requesting help/read-only preparation only. This is native
local skill discovery, not proof of plugin marketplace support.

## Claude Code / Desktop Code local test

In a local Code session add this clone as a local marketplace with
`/plugin marketplace add /absolute/path/to/clone`, then install
`hodl-skill-install@hodl-bootstrap` in the intended test scope using the native
plugin manager. Verify its Installed entry and invoke the skill from the command
picker in a new local Code session. CLI installation alone does not prove desktop
registration. Generic Claude chat and Cowork are not this test surface.

## Acceptance and cleanup

First invocation must be harmless: show capabilities or run helper help/preview;
do not generate keys or begin customer onboarding. Record actual app/version,
selector visibility and invocation separately from file placement and Git access.
Use native plugin uninstall for Claude, or remove only the test symlink for Codex.
Preserve `.hodl` settings and customer data. No custom updater is included.

See `skills/hodl-skill-install/references/installation.md` for the complete contract.
No license for third-party redistribution is granted by this preview.
