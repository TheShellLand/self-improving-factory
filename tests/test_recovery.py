import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from core.commit_service import CommitService
from core.database import connect, initialize_database
from core.gatekeeper import GatekeeperVault
from core.recovery import RecoveryService
from core.vault import Vault
from ui_backend.bridge import create_app


class SimulatedCrash(BaseException):
    pass


class TestRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "vault.db"
        initialize_database(self.db)
        self.vault = Vault(self.db)
        self.issue = self.vault.create_issue({"title": "Fix", "description": "Details"})
        _, self.session = self.vault.claim_next()
        self.gatekeeper = GatekeeperVault(Path(self.temp.name) / "repo", create=True)
        with self.gatekeeper.repo.config_writer() as config:
            config.set_value("user", "name", "Test")
            config.set_value("user", "email", "test@example.invalid")
        self.commits = CommitService(self.db, self.gatekeeper)
        self.recovery = RecoveryService(self.db, gatekeeper=self.gatekeeper,
                                        execution_stopped=lambda session: True)
        self.reason = {"actor": "operator", "reason": "Verified parent and child termination"}

    def interrupted_proposal(self, applied):
        execute = self.gatekeeper.execute_proposed_commit

        def interrupt(*args):
            if applied:
                self.assertTrue(execute(*args))
            raise SimulatedCrash()

        with patch.object(self.gatekeeper, "execute_proposed_commit", side_effect=interrupt):
            with self.assertRaises(SimulatedCrash):
                self.commits.apply(self.session, "Fix", [{"filename": "file.txt", "content": "fixed"}])
        return self.recovery.pending()["proposals"][0]["proposal_id"]

    def test_committed_crash_is_reconciled_without_reapplying_git(self):
        proposal = self.interrupted_proposal(applied=True)
        sha = self.gatekeeper.get_last_commit()
        with self.assertRaisesRegex(ValueError, "Resolve"):
            self.recovery.fail_session(self.session, **self.reason)
        self.recovery.resolve_proposal(proposal, commit_sha=sha, **self.reason)
        self.recovery.fail_session(self.session, **self.reason)
        self.assertEqual(self.gatekeeper.get_last_commit(), sha)
        with self.assertRaisesRegex(ValueError, "follow-up"):
            self.recovery.retry_issue(self.issue, **self.reason)
        with connect(self.db) as connection:
            row = connection.execute("SELECT * FROM commit_proposals").fetchone()
            self.assertEqual((row["status"], row["commit_sha"]), ("APPLIED", sha))
            logs = connection.execute("SELECT payload FROM trace_signals WHERE source_agent = 'recovery'").fetchall()
            self.assertEqual(len(logs), 2)
            self.assertEqual(json.loads(logs[0][0])["actor"], "operator")

    def test_unapplied_crash_can_be_requeued_with_new_session(self):
        proposal = self.interrupted_proposal(applied=False)
        self.recovery.resolve_proposal(proposal, **self.reason)
        self.recovery.fail_session(self.session, **self.reason)
        self.recovery.retry_issue(self.issue, **self.reason)
        issue, new_session = self.vault.claim_next()
        self.assertEqual(issue["issue_id"], self.issue)
        self.assertNotEqual(new_session, self.session)
        with connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT status FROM agent_sessions WHERE session_id = ?",
                                                (self.session,)).fetchone()[0], "FAILED")

    def test_unknown_or_active_execution_cannot_be_recovered(self):
        for probe in [None, lambda _: False, lambda _: "yes"]:
            recovery = RecoveryService(self.db, execution_stopped=probe)
            with self.assertRaisesRegex(RuntimeError, "not confirmed"):
                recovery.fail_session(self.session, **self.reason)
        self.assertEqual(self.vault.list_issues()[0]["status"], "IN PROGRESS")

    def test_proposal_recovery_requires_stopped_execution_too(self):
        proposal = self.interrupted_proposal(applied=False)
        recovery = RecoveryService(self.db, gatekeeper=self.gatekeeper)
        with self.assertRaises(RuntimeError):
            recovery.resolve_proposal(proposal, **self.reason)
        self.assertEqual(len(recovery.pending()["proposals"]), 1)

    def test_dirty_or_unrelated_git_state_stays_unresolved(self):
        proposal = self.interrupted_proposal(applied=False)
        (self.gatekeeper.root / "unrelated.txt").write_text("keep")
        with self.assertRaisesRegex(ValueError, "clean checkout"):
            self.recovery.resolve_proposal(proposal, **self.reason)
        self.gatekeeper.repo.index.add(["unrelated.txt"])
        unrelated = self.gatekeeper.repo.index.commit("Other work").hexsha
        with self.assertRaisesRegex(ValueError, "Git changed"):
            self.recovery.resolve_proposal(proposal, **self.reason)
        with self.assertRaises(ValueError):
            self.recovery.resolve_proposal(proposal, commit_sha=unrelated, **self.reason)
        self.assertEqual(len(self.recovery.pending()["proposals"]), 1)

    def test_matching_message_with_wrong_content_is_not_accepted(self):
        proposal = self.interrupted_proposal(applied=False)
        self.assertTrue(self.gatekeeper.execute_proposed_commit("Fix", [{"filename": "file.txt", "content": "wrong"}]))
        with self.assertRaisesRegex(ValueError, "content differs"):
            self.recovery.resolve_proposal(proposal, commit_sha=self.gatekeeper.get_last_commit(), **self.reason)

    def test_legacy_proposal_fails_closed_and_blocks_new_claims(self):
        with connect(self.db) as connection:
            connection.execute("INSERT INTO commit_proposals VALUES ('old', ?, 'PREPARED', NULL, NULL)", (self.session,))
        self.vault.finish(self.session, False, "interrupted")
        self.vault.create_issue({"title": "Another", "description": "queued"})
        self.assertIsNone(self.vault.claim_next())
        with self.assertRaisesRegex(ValueError, "no recovery evidence"):
            self.recovery.resolve_proposal("old", **self.reason)

    def test_recovery_audit_failure_rolls_back_session_transition(self):
        with patch.object(Vault, "_record", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                self.recovery.fail_session(self.session, **self.reason)
        self.assertEqual(self.vault.list_issues()[0]["status"], "IN PROGRESS")

    def test_repeated_recovery_does_not_duplicate_audit(self):
        self.recovery.fail_session(self.session, **self.reason)
        with self.assertRaises(ValueError):
            self.recovery.fail_session(self.session, **self.reason)
        self.recovery.retry_issue(self.issue, **self.reason)
        with self.assertRaises(ValueError):
            self.recovery.retry_issue(self.issue, **self.reason)

    def test_recovery_api_requires_configured_authorization(self):
        with TestClient(create_app(self.db)) as client:
            self.assertEqual(len(client.get("/api/recovery").json()["sessions"]), 1)
            response = client.post(f"/api/sessions/{self.session}/recover", json={"reason": "stopped"})
            self.assertEqual(response.status_code, 503)
        with TestClient(create_app(self.db, recovery_service=self.recovery,
                                   recovery_actor=lambda request: None)) as client:
            self.assertEqual(client.post(f"/api/sessions/{self.session}/recover", json={"reason": "stopped"}).status_code, 403)
        with TestClient(create_app(self.db, recovery_service=self.recovery,
                                   recovery_actor=lambda request: "operator")) as client:
            self.assertEqual(client.post(f"/api/sessions/{self.session}/recover", json={"reason": "stopped"}).status_code, 200)
            self.assertEqual(client.post(f"/api/issues/{self.issue}/retry", json={"reason": "safe to retry"}).status_code, 200)

    def test_version_one_migration_preserves_proposals(self):
        with connect(self.db) as connection:
            connection.execute("DROP TABLE proposal_evidence")
            connection.execute("PRAGMA user_version = 1")
            connection.execute("INSERT INTO commit_proposals VALUES ('old', ?, 'PREPARED', NULL, NULL)", (self.session,))
        initialize_database(self.db)
        self.assertEqual(self.recovery.pending()["proposals"][0]["proposal_id"], "old")
        with connect(self.db) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_noop_proposal_can_be_reconciled_at_original_head(self):
        self.gatekeeper.execute_proposed_commit("Initial", [{"filename": "file.txt", "content": "fixed"}])
        before = self.gatekeeper.get_last_commit()
        proposal = self.interrupted_proposal(applied=True)
        self.recovery.resolve_proposal(proposal, commit_sha=before, **self.reason)
        self.assertEqual(self.gatekeeper.get_last_commit(), before)
