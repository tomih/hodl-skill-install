"""Native workspace destinations; host dispatch remains attributed acceptance."""
TARGETS = {
    'codex': '.agents/skills',
    'claude-code': '.claude/skills',
    'openclaw': 'skills',
}
RUNTIMES = tuple(TARGETS)
