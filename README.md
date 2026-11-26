# hodl-skill-install 0.2.10-rc.1

Local candidate only; not the public default or an approved customer bootstrap pin.

Give your agent this repository URL and ask it to install the skill in its current workspace:

https://github.com/tomih/hodl-skill-install

The agent performs the bootstrap below. The user does not need to upload an archive, copy skill files manually or run terminal commands. Merely opening this web page does not execute installation: the agent needs the user's installation request and filesystem/exec access.

## Agent bootstrap
1. Establish your actual runtime and exact configured workspace/project from host evidence. OpenClaw must use the intended agent's workspace, not the account home directory. If the host cannot write files or run commands, report that specific missing capability.
2. Fetch only this repository over HTTPS into fresh private scratch outside discovery. Record the retrieved full commit. Export its tracked files to a separate release directory: the complete release checksum inventory must not include Git's .git metadata.
3. Verify the complete SHA256SUMS inventory using the packaged self_update.py package validator; checksums detect corruption, and the user's approved source/commit establishes trust. Stop on missing/unexpected files or mismatched hashes.
4. Use the fetched release’s existing managed self_update.py to install the bootstrap at the native destination below. Do not manually copy around the lifecycle or overwrite local changes.
5. Check native discovery in the intended host and load hodl-skill-install. Run local bootstrap preflight before keys/network access to customer repositories. If discovery requires refresh, resume only hodl-skill-install in the same agent/workspace.

| Runtime | Bootstrap destination relative to established project/workspace |
| --- | --- |
| OpenClaw | skills/hodl-skill-install |
| Codex | .agents/skills/hodl-skill-install |
| Claude Code | .claude/skills/hodl-skill-install |

Example commands for an OpenClaw agent, after establishing its exact workspace. Set workspace from host evidence; do not infer it from a customer name.

```sh
set -eu
workspace=/absolute/configured/agent/workspace
scratch=$(mktemp -d)
chmod 700 "$scratch"
git clone --depth 1 https://github.com/tomih/hodl-skill-install.git "$scratch/repository"
git -C "$scratch/repository" rev-parse HEAD
mkdir "$scratch/release"
git -C "$scratch/repository" archive --format=tar --output="$scratch/release.tar" HEAD
tar -xf "$scratch/release.tar" -C "$scratch/release"
python3 -B "$scratch/release/skills/hodl-skill-install/scripts/self_update.py" --release "$scratch/release" --target "$workspace/skills/hodl-skill-install"
python3 -B "$workspace/skills/hodl-skill-install/scripts/bootstrap.py" preflight --project "$workspace" --runtime openclaw
```

self_update.py validates the complete release before staging/writing, preserves local modifications and stores its managed baseline/backups outside discovery. First install, repeat and explicit bootstrap replacement use this same helper. Keep retrieved commit and release hashes as evidence. Use a separately approved exact commit instead of default HEAD when a deployment is pinned.

In OpenClaw run skills list, skills info hodl-skill-install and skills check with --agent <actual-agent-id>. Verify the resolved path is this workspace; then load the exact skill using skills_read in that agent and follow its instructions. CLI discovery alone is not invocation.

## Customer onboarding and updates
After bootstrap, hodl-skill-install handles customer identity, isolated repository access, HODL1 public-key handoff, verified customer manifests, managed installation/update/restore and resumable attributed acceptance. Ask only for genuinely missing customer identity. Read-only deploy-key provisioning requires authenticated publisher approval; this public repository grants no customer access.
Mutable registers, history, local configuration and sent/uncertain notification ledgers belong outside immutable skill trees. Local modifications stop updates rather than being overwritten. Native invocation/local preflight and business acceptance remain separate. No schedules, email or business actions are activated by bootstrap.

## Verification status
Version 0.2.10-rc.1 adds OpenClaw alongside Codex and Claude Code. Local lifecycle tests passed with populated mutable state, including no-op, update, conflict and restore. Native acceptance on a particular customer device remains separate; no customer pins or installations are changed by this public release.

## Explicit setup stage
After managed first install/update/no-op/resume, load the exact verified skill. Only with applicable explicit setup authorization, record setup-begin before writes, run its documented idempotent local setup through ordinary tools, record its outcome, then run read-only preflight for that same attempt. Existing acceptance is not proof that mutable setup still exists. Skills without setup retain harmless acceptance. The evidence helper executes no commands/hooks; manifest data grants no setup authority. Read skills/hodl-skill-install/references/local-setup.md. This candidate is not publication, native/business acceptance or target-change approval.
