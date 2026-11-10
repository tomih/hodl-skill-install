"""Local on-demand transactions. No network, discovery or provisioning authority."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from contextlib import contextmanager


@contextmanager
def project_operation(folder):
    """Serialize identity/managed/acceptance reads through writes across runtimes."""
    folder = Path(folder)
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise ValueError("Symlinked lifecycle directory")
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / "install-acceptance.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError("Active/interrupted project operation lock; review before recovery: " + str(lock))
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink()


def tree(root):
    from install import inventory
    return inventory(root, root) if root.exists() else None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_state(path):
    if path.is_symlink():
        raise ValueError('Symlinked lifecycle state')
    return json.loads(path.read_text()) if path.exists() else {}


def atomic_json(path, value):
    fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2)
            f.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _apply(plans, state_path, state, expected_files=None, extra_states=None):
    """plans: (source, target, observed inventory). Stage all before first write.
    Backups are content addressed and outside discovery. Keep history; never prune it.
    A crash leaves a journal for explicit recovery; a caught failure rolls back.
    """
    state_path = Path(state_path)
    folder = state_path.parent
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise ValueError('Symlinked lifecycle directory')
    folder.mkdir(parents=True, exist_ok=True)
    journal = folder / (state_path.stem + '-transaction.json')
    if journal.exists() or journal.is_symlink():
        raise ValueError('Interrupted transaction; review/recover journal: ' + str(journal))
    for source, target, old in plans:
        expected = (expected_files or {}).get(str(target), tree(Path(source)))
        if tree(Path(source)) != expected:
            raise ValueError('Staged source checksum mismatch')
        if Path(target).is_symlink() or tree(Path(target)) != old:
            raise ValueError('Target changed before staging; preserved')
    changes = [(Path(s), Path(t), old) for s, t, old in plans
               if (expected_files or {}).get(str(t), tree(Path(s))) != old]
    extra_states = extra_states or {}
    if not changes and read_state(state_path) == state and all(read_state(p) == v for p, v in extra_states.items()):
        return
    backup_root = folder / 'backups'
    if backup_root.is_symlink():
        raise ValueError('Symlinked backup directory')
    with tempfile.TemporaryDirectory(prefix='.stage-', dir=folder) as tmp:
        staged, backups = [], []
        for n, (source, target, old) in enumerate(changes):
            candidate = Path(tmp) / str(n)
            expected = (expected_files or {}).get(str(target), tree(source))
            shutil.copytree(source, candidate)
            if tree(candidate) != expected:
                raise ValueError('Staged candidate checksum mismatch')
            if tree(target) != old:
                raise ValueError('Target changed during staging; preserved')
            backup = None
            if old is not None:
                backup = backup_root / digest({'target': str(target), 'files': old})
                if backup.is_symlink():
                    raise ValueError('Symlinked backup')
                if not backup.exists():
                    backup_root.mkdir(exist_ok=True)
                    shutil.copytree(target, backup)
                if tree(backup) != old:
                    raise ValueError('Backup checksum mismatch')
            staged.append(candidate)
            backups.append(backup)
        before = state_path.read_bytes() if state_path.exists() else None
        other_before = {p: p.read_bytes() if p.exists() else None for p in extra_states}
        atomic_json(journal, {'statePath': str(state_path), 'previousState': before.decode() if before else None,
                             'extraStates': {str(p): b.decode() if b else None for p, b in other_before.items()},
                             'targets': [{'target': str(t), 'backup': str(b) if b else None,
                                          'previousFiles': old} for (_, t, old), b in zip(changes, backups)]})
        touched = []
        try:
            for (source, target, old), candidate, backup in zip(changes, staged, backups):
                if target.is_symlink() or tree(target) != old:
                    raise ValueError('Target changed before replacement; preserved')
                touched.append((target, backup))
                if target.exists():
                    shutil.rmtree(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(candidate, target)
            atomic_json(state_path, state)
            for path, value in extra_states.items():
                atomic_json(path, value)
        except Exception:
            # On rollback failure leave journal/backups intact for intervention.
            for target, backup in reversed(touched):
                if target.exists():
                    shutil.rmtree(target)
                if backup:
                    shutil.copytree(backup, target)
            if before is None:
                state_path.unlink(missing_ok=True)
            else:
                state_path.write_bytes(before)
            for path, raw in other_before.items():
                if raw is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(raw)
            journal.unlink()
            raise
        journal.unlink()


def apply(plans, state_path, state, expected_files=None, extra_states=None):
    state_path = Path(state_path)
    folder = state_path.parent
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise ValueError('Symlinked lifecycle directory')
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder / (state_path.stem + '-transaction.lock')
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError('Active/interrupted transaction lock; review before recovery: ' + str(lock))
    os.close(fd)
    try:
        return _apply(plans, state_path, state, expected_files, extra_states)
    finally:
        lock.unlink()
