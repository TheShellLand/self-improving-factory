"""Apply file proposals to an explicitly selected Git repository."""
import logging
from pathlib import Path
import git

logger = logging.getLogger(__name__)


class GatekeeperVault:
    """Commit validated file replacements in a clean, exclusively owned checkout.

    This is not a sandbox for executing untrusted code. Callers must serialize
    access to the repository while a proposal is being applied.
    """

    def __init__(self, repo_path: str, *, create: bool = False):
        self.root = Path(repo_path).resolve()
        self.repo = (git.Repo.init(self.root, initial_branch="main") if create
                     else git.Repo(self.root, search_parent_directories=False))
        if self.repo.bare:
            raise ValueError("A working tree is required")

    def _validate(self, message, file_changes):
        if not isinstance(message, str) or not message.strip():
            raise ValueError("A nonempty commit message is required")
        if self.repo.is_dirty(untracked_files=True):
            raise ValueError("The repository must be clean before applying a proposal")
        changes = {}
        for change in file_changes:
            name, content = change["filename"], change["content"]
            if not isinstance(name, str) or not isinstance(content, str):
                raise ValueError("Filenames and contents must be strings")
            relative = Path(name)
            if (not name or relative.is_absolute() or ".." in relative.parts
                    or any(part.lower() == ".git" for part in relative.parts)):
                raise ValueError(f"Invalid repository path: {name}")
            target = self.root / relative
            if target == self.root or not target.resolve().is_relative_to(self.root):
                raise ValueError(f"Path escapes the repository: {name}")
            for path in (target, *target.parents):
                if path == self.root:
                    break
                if path.is_symlink():
                    raise ValueError(f"Symlink paths are not supported: {name}")
                if path != target and path.exists() and not path.is_dir():
                    raise ValueError(f"Parent is not a directory: {name}")
                if path.is_dir() and (path / ".git").exists():
                    raise ValueError(f"Nested repositories are not supported: {name}")
            if target.exists() and not target.is_file():
                raise ValueError(f"Target is not a file: {name}")
            if target in changes:
                raise ValueError(f"Duplicate target: {name}")
            changes[target] = content
        if any(parent in changes for path in changes for parent in path.parents):
            raise ValueError("A file cannot also be a parent directory")
        return changes

    def execute_proposed_commit(self, message: str, file_changes: list[dict]) -> bool:
        """Apply a batch, restoring files and index if writing or committing fails."""
        originals = {}
        created_dirs = set()
        index_path = Path(self.repo.index.path)
        index_bytes = None
        started = False
        try:
            changes = self._validate(message, file_changes)
            originals = {path: path.read_bytes() if path.exists() else None for path in changes}
            index_bytes = index_path.read_bytes() if index_path.exists() else None
            started = True
            for path, content in changes.items():
                parent = path.parent
                while not parent.exists():
                    created_dirs.add(parent)
                    parent = parent.parent
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            if changes:
                self.repo.index.add([str(path.relative_to(self.root)) for path in changes])
                if self.repo.is_dirty():
                    self.repo.index.commit(message)
            return True
        except Exception:
            logger.exception("Proposal failed")
            if started:
                for path, original in originals.items():
                    if original is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(original)
                for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
                    directory.rmdir()
                if index_bytes is None:
                    index_path.unlink(missing_ok=True)
                else:
                    index_path.write_bytes(index_bytes)
            return False

    def get_last_commit(self):
        return self.repo.head.commit.hexsha if self.repo.head.is_valid() else None
