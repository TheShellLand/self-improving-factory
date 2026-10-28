import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from core.commit_service import CommitService
from core.coordinator import Coordinator
from core.database import connect, initialize_database
from core.evolution import EvolutionEngine
from core.gatekeeper import GatekeeperVault
from core.hotloader import HotLoaderModule
from core.vault import Vault


class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "vault.db"
        initialize_database(self.db)
        self.vault = Vault(self.db)
        self.vault.create_issue({"title": "Fix", "description": "Fix it"})
        self.gatekeeper = GatekeeperVault(Path(self.temp.name) / "repo", create=True)
        with self.gatekeeper.repo.config_writer() as writer:
            writer.set_value("user", "name", "Test")
            writer.set_value("user", "email", "test@example.invalid")
        self.service = CommitService(self.db, self.gatekeeper)
        self.provider = Mock(return_value={"logic_description": "Learned", "prompt_weights": {"retry": 2}})
        self.evolution = EvolutionEngine(self.db, self.provider)
        self.loader = HotLoaderModule(self.db)

    def coordinator(self, runner, service=True):
        return Coordinator(self.vault, runner, self.evolution, self.loader,
                           self.service if service else None)

    async def test_full_flow_persists_commit_reflection_and_terminal_status(self):
        async def runner(issue, session, config):
            return {"success": True, "summary": "Fixed", "observations": [{"step": "verified"}],
                    "commit_message": "Fix issue", "file_changes": [{"filename": "fix.txt", "content": "fixed"}]}
        coordinator = self.coordinator(runner)
        session = await coordinator.run_once()
        self.assertIsNone(await coordinator.run_once())
        self.assertEqual(self.vault.list_issues()[0]["status"], "CLOSED")
        self.assertEqual(self.loader.get_active_config(), {"retry": 2})
        self.assertEqual((self.gatekeeper.root / "fix.txt").read_text(), "fixed")
        with connect(self.db) as connection:
            proposal = connection.execute("SELECT * FROM commit_proposals").fetchone()
            self.assertEqual(proposal["commit_sha"], self.gatekeeper.get_last_commit())
            self.assertEqual(proposal["session_id"], session)
            self.assertEqual(proposal["status"], "APPLIED")
        self.evolution.reflect_session(self.vault.list_issues()[0], session)
        self.provider.assert_called_once()

    async def test_runner_error_finishes_failed_session(self):
        async def runner(*args):
            raise RuntimeError("Runner unavailable")
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            await self.coordinator(runner).run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "FAILED")
        self.assertIsNone(self.gatekeeper.get_last_commit())

    async def test_failed_execution_never_applies_proposals(self):
        async def runner(*args):
            return {"success": False, "summary": "Tests failed", "file_changes": [
                {"filename": "bad.txt", "content": "bad"}]}
        await self.coordinator(runner).run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "FAILED")
        self.assertFalse((self.gatekeeper.root / "bad.txt").exists())

    async def test_missing_gatekeeper_cannot_silently_discard_changes(self):
        async def runner(*args):
            return {"success": True, "summary": "Changed", "file_changes": [
                {"filename": "fix.txt", "content": "fix"}]}
        with self.assertRaisesRegex(RuntimeError, "gatekeeper"):
            await self.coordinator(runner, service=False).run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "FAILED")

    async def test_cancellation_keeps_claim_until_reconciliation(self):
        async def runner(*args):
            raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.coordinator(runner).run_once()
        self.assertIsNone(self.vault.claim_next())

    def test_pending_proposal_blocks_another_git_write(self):
        _, session = self.vault.claim_next()
        with connect(self.db) as connection:
            connection.execute("INSERT INTO commit_proposals VALUES ('pending', ?, 'PREPARED', NULL, NULL)", (session,))
        with self.assertRaisesRegex(RuntimeError, "reconciliation"):
            self.service.apply(session, "Change", [{"filename": "file.txt", "content": "data"}])
        self.assertIsNone(self.gatekeeper.get_last_commit())

    def test_rejected_proposal_has_a_failed_audit_record(self):
        _, session = self.vault.claim_next()
        with self.assertLogs("core.gatekeeper", level="ERROR"), self.assertRaises(ValueError):
            self.service.apply(session, "Invalid", [{"filename": "../escape", "content": "data"}])
        with connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT status FROM commit_proposals").fetchone()[0], "FAILED")
        self.assertFalse((self.gatekeeper.root.parent / "escape").exists())
