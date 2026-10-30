"""Apply file proposals to an explicitly selected Git repository."""
import logging
import hashlib
import re
from pathlib import Path
import git
from core.config import GitConfig

logger = logging.getLogger(__name__)


class GitClient:
    """Commit validated file replacements in a clean, exclusively owned checkout.

    This is not a sandbox for executing untrusted code. Callers must serialize
    access to the repository while a proposal is being applied.
    """

    def __init__(self, repo_path=None, *, create=False, config=None):
        if config is not None and (repo_path is not None or create):
            raise ValueError("Pass Git options or config, not both")
        if config is None and repo_path is None:
            raise ValueError("A repository path is required")
        self.config = config if config is not None else GitConfig(repo_path, create)
        self.root = self.config.repo_path
        self.repo = (git.Repo.init(self.root, initial_branch="main") if self.config.create
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

    def proposal_snapshot(self, message, file_changes):
        """Capture recovery evidence without persisting proposed source contents."""
        return {
            "repository": str(self.root),
            "before_sha": self.get_last_commit(),
            "head_ref": None if self.repo.head.is_detached else self.repo.head.reference.path,
            "message": message,
            "files": {Path(item["filename"]).as_posix():
                      hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
                      for item in file_changes},
        }

    def verify_recovery(self, snapshot, commit_sha=None):
        """Read-only proof for an applied commit or an unchanged checkout.

        Requires exclusive checkout access and a stopped proposal owner. Never
        resets Git or rewrites files; ambiguous state requires manual inspection.
        """
        head_ref = None if self.repo.head.is_detached else self.repo.head.reference.path
        if snapshot["repository"] != str(self.root) or snapshot["head_ref"] != head_ref:
            raise ValueError("Recovery repository or branch does not match the proposal")
        if self.repo.is_dirty(untracked_files=True):
            raise ValueError("Recovery requires a clean checkout")
        before = snapshot["before_sha"]
        if commit_sha is None:
            if self.get_last_commit() != before:
                raise ValueError("Git changed; the proposal cannot be marked unapplied")
            return
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha) or self.get_last_commit() != commit_sha:
            raise ValueError("Supply the full current HEAD commit hash")
        commit = self.repo.head.commit
        if commit_sha != before:
            parents = [parent.hexsha for parent in commit.parents]
            if parents != ([before] if before else []):
                raise ValueError("Commit does not directly follow the saved revision")
            if commit.message.rstrip("\n") != snapshot["message"].rstrip("\n"):
                raise ValueError("Commit message differs from the proposal")
            if before:
                changed = {path for diff in self.repo.commit(before).diff(commit)
                           for path in (diff.a_path, diff.b_path) if path}
            else:
                changed = {entry.path for entry in commit.tree.traverse() if entry.type != "tree"}
            if not changed.issubset(snapshot["files"]):
                raise ValueError("Commit contains files outside the proposal")
        for filename, digest in snapshot["files"].items():
            try:
                blob = commit.tree / filename
            except KeyError as error:
                raise ValueError("A proposed file is missing from the commit") from error
            if blob.type != "blob" or blob.mode not in (0o100644, 0o100755):
                raise ValueError("Proposed file is not a regular Git blob")
            expected_mode = 0o100644
            if before:
                try:
                    expected_mode = (self.repo.commit(before).tree / filename).mode
                except KeyError:
                    pass
            if blob.mode != expected_mode:
                raise ValueError("Committed file mode differs from the proposal")
            if hashlib.sha256(blob.data_stream.read()).hexdigest() != digest:
                raise ValueError("Committed content differs from the proposal")


# Compatibility name for existing integrations.
GatekeeperVault = GitClient
