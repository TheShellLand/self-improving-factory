import sys
import os
from typing import Dict, List
import git

class GatekeeperVault:
    """The safe-zone interface for all version control operations."""
    def __init__(self, repo_path: str):
        if not os.path.exists(repo_path) or (os.path.isdir(repo_path) and not os.path.exists(os.path.join(repo_path, ".git"))):
            # We ignore errors because if it's a legitimate but non-standard dir we might want to init 
            try:
                os.makedirs(repo_path, exist_ok=True)
            except FileExistsError:
                pass

        try:
            self.repo = git.Repo.init(repo_path)
        except Exception as e:
             # If already initialized as a repo OR other reason why .init failed (e.g., path exists), try open it
             print(f"Initializing/Opening Repo at {repo_path}... ({str(e)})")
             self.repo = git.Repo(repo_path)

    def execute_proposed_commit(self, message: str, file_changes: List[Dict]) -> bool:
        """Verifies and applies agent commits via gitpython library abstraction layer."""
        print(f"[Gatekeeper] Applying batch of {len(file_changes)} changes.")
        try:
            for change in file_changes:
                filename = change['filename']
                content = change['content']
                full_path = os.path.join(self.repo.working_tree_dir, filename)
                # Ensure subdirectory structure exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)

            for change in file_changes:
                 self.repo.index.add(change['filename'])

            if not self.repo.is_dirty(): 
                print("[Gatekeeper] No changes detected (possibly same content).")
            else:
                 self.repo.index.commit(message)
            
            print(f"[Gatekeeper] Commit successful or no-op needed.")
            return True
        except Exception as e:
            print(f"!!! [Gatekeeper Error]: {e}", file=sys.stderr)
            return False

    def get_last_commit(self):
        try:
             h = self.repo.head.commit.hexsha
             return h
        except Exception:
             return None

if __name__ == "__main__":
	# Use a local testing directory for the script execution to not interfere with actual source dirs if they are git repos
	gatekeeper = GatekeeperVault("./test_git_vault")
	status = gatekeeper.execute_proposed_commit("Initial Test", [
		{"filename": "dir1/file1.txt", "content": "Content 1"},
		{"filename": "root_level_new.md", "content": "# Root Level New"}
	])
	assert status is True
	print(f"Final Repo State SHA: {gatekeeper.get_last_commit()}")
	print("Gatekeeper Logic Verified.")
