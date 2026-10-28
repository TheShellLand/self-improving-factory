from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import git
from core.gatekeeper import GatekeeperVault


class TestGatekeeper(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.vault = GatekeeperVault(self.root, create=True)
        with self.vault.repo.config_writer() as config:
            config.set_value("user", "name", "Test Agent")
            config.set_value("user", "email", "test@example.invalid")

    def commit(self, filename="nested/file.txt", content="hello"):
        return self.vault.execute_proposed_commit("Test change", [{"filename": filename, "content": content}])

    def test_create_is_explicit(self):
        missing = self.root.parent / "missing"
        with self.assertRaises(git.exc.NoSuchPathError):
            GatekeeperVault(missing)
        self.assertFalse(missing.exists())

    def test_commit_and_noop(self):
        self.assertTrue(self.commit())
        sha = self.vault.get_last_commit()
        self.assertEqual(self.vault.repo.active_branch.name, "main")
        self.assertTrue(self.commit())
        self.assertEqual(self.vault.get_last_commit(), sha)

    def test_invalid_batch_does_not_write_any_files(self):
        with self.assertLogs("core.gatekeeper", level="ERROR"):
            self.assertFalse(self.vault.execute_proposed_commit("Invalid", [
                {"filename": "valid.txt", "content": "hello"},
                {"filename": "../escape.txt", "content": "bad"}]))
        self.assertFalse((self.root / "valid.txt").exists())
        self.assertFalse((self.root.parent / "escape.txt").exists())

    def test_rejects_metadata_and_absolute_paths(self):
        for path in [".git/config", str(self.root.parent / "outside"), "."]:
            with self.subTest(path=path), self.assertLogs("core.gatekeeper", level="ERROR"):
                self.assertFalse(self.commit(path))

    def test_rejects_dirty_checkout(self):
        self.assertTrue(self.commit())
        (self.root / "unrelated.txt").write_text("user work")
        self.vault.repo.index.add(["unrelated.txt"])
        with self.assertLogs("core.gatekeeper", level="ERROR"):
            self.assertFalse(self.commit(content="changed"))
        self.assertEqual((self.root / "nested/file.txt").read_text(), "hello")
        self.assertTrue(self.vault.repo.is_dirty())

    def test_commit_failure_restores_files_and_index(self):
        self.assertTrue(self.commit())
        sha = self.vault.get_last_commit()
        with patch("git.index.base.IndexFile.commit", side_effect=RuntimeError("failure")):
            with self.assertLogs("core.gatekeeper", level="ERROR"):
                self.assertFalse(self.commit("new/deep/file.txt"))
        self.assertFalse((self.root / "new").exists())
        self.assertFalse(self.vault.repo.is_dirty(untracked_files=True))
        self.assertEqual(self.vault.get_last_commit(), sha)

    def test_parent_file_is_rejected_without_touching_existing_content(self):
        self.assertTrue(self.commit("parent", "keep"))
        with self.assertLogs("core.gatekeeper", level="ERROR"):
            self.assertFalse(self.commit("parent/child"))
        self.assertEqual((self.root / "parent").read_text(), "keep")
        self.assertFalse(self.vault.repo.is_dirty())

    def test_tracked_symlink_cannot_modify_external_file(self):
        outside = self.root.parent / "outside"
        outside.write_text("keep")
        (self.root / "link").symlink_to(outside)
        self.vault.repo.index.add(["link"])
        self.vault.repo.index.commit("Track symlink")
        with self.assertLogs("core.gatekeeper", level="ERROR"):
            self.assertFalse(self.commit("link", "overwrite"))
        self.assertEqual(outside.read_text(), "keep")
