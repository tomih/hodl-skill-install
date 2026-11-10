# hodl-skill-install 0.2.4

Source: https://github.com/tomih/hodl-skill-install, tag v0.2.4, package skills/hodl-skill-install.

Customer skill IDs and exact versions come only from the verified exact-repository manifest, never bootstrap examples. Supports one or multiple approved skills with complete inventory/hashes, safe native project paths, matching frontmatter names and all-target conflict preflight. Existing modified customer targets remain untouched; this is not a customer-skill updater.

## Claude Code bootstrap replacement

Fetch tag v0.2.4 into a fresh temporary directory using existing authorized GitHub access. Verify SHA256SUMS. Preserve the existing ~/.claude/skills/hodl-skill-install with a backup outside skill discovery roots, then replace only that skill directory with skills/hodl-skill-install. Preserve other skills, project .hodl state and SSH keys. Start a new session only if skill discovery requires it; invoke /hodl-skill-install in the intended project. Customer slug and exact owner/repository must be confirmed before provisioning; skill names remain unknown until verified manifest retrieval.

25 offline tests and skill validation passed. Claude Code actual installation/invocation remains pending Hodl's guided test. No Mac or customer repository changes made. Previous tag v0.2.3 remains available for rollback.
