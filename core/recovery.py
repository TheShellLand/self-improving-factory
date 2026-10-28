"""Explicit recovery for a quiescent worker and exclusively owned repository.

The host supplies execution_stopped(session_id), which must confirm that both
the parent task and any child execution are stopped. Missing or uncertain probes
fail closed. Operator identity must come from the host's authentication boundary.
"""
import json
import time

from core.database import connect
from core.signals import SignalPulse
from core.vault import Vault


class RecoveryService:
    def __init__(self, database_path, *, execution_stopped=None, gatekeeper=None):
        self.db_path = database_path
        self.execution_stopped = execution_stopped
        self.gatekeeper = gatekeeper

    def pending(self):
        with connect(self.db_path) as connection:
            return {
                "sessions": [dict(row) for row in connection.execute(
                    "SELECT * FROM agent_sessions WHERE status = 'RUNNING' ORDER BY start_time")],
                "proposals": [dict(row) for row in connection.execute(
                    "SELECT * FROM commit_proposals WHERE status = 'PREPARED' ORDER BY proposal_id")],
            }

    def _authorize_recovery(self, session_id, actor, reason):
        if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
            raise ValueError("Recovery requires an operator and a reason")
        if self.execution_stopped is None or self.execution_stopped(session_id) is not True:
            raise RuntimeError("Host has not confirmed that execution is stopped")

    @staticmethod
    def _audit(connection, session_id, actor, reason, operation, **details):
        Vault._record(connection, SignalPulse(source_agent="recovery", action_type="RESULT", payload={
            "session_id": session_id, "actor": actor, "reason": reason,
            "operation": operation, **details}))

    def resolve_proposal(self, proposal_id, *, actor, reason, commit_sha=None):
        """Resolve PREPARED only with saved evidence and a matching clean Git state."""
        if self.gatekeeper is None:
            raise RuntimeError("Recovery requires a configured gatekeeper")
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM commit_proposals WHERE proposal_id = ? AND status = 'PREPARED'",
                                     (proposal_id,)).fetchone()
            if row is None:
                raise ValueError("Proposal is missing or already resolved")
            self._authorize_recovery(row["session_id"], actor, reason)
            evidence = connection.execute("SELECT snapshot FROM proposal_evidence WHERE proposal_id = ?",
                                          (proposal_id,)).fetchone()
            if evidence is None:
                raise ValueError("Legacy proposal has no recovery evidence; manual investigation required")
            self.gatekeeper.verify_recovery(json.loads(evidence[0]), commit_sha)
            status = "APPLIED" if commit_sha else "FAILED"
            connection.execute("UPDATE commit_proposals SET status = ?, commit_sha = ?, error = ? WHERE proposal_id = ?",
                               (status, commit_sha, None if commit_sha else reason, proposal_id))
            self._audit(connection, row["session_id"], actor, reason, "resolve_proposal",
                        proposal_id=proposal_id, status=status, commit_sha=commit_sha)

    def fail_session(self, session_id, *, actor, reason):
        """Release a stopped session, keeping its issue FAILED until explicitly retried."""
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT s.status, r.issue_id FROM agent_sessions s JOIN issue_runs r USING(session_id) "
                "WHERE session_id = ?", (session_id,)).fetchone()
            if row is None or row["status"] != "RUNNING":
                raise ValueError("Session is missing or no longer running")
            self._authorize_recovery(session_id, actor, reason)
            if connection.execute("SELECT 1 FROM commit_proposals WHERE session_id = ? AND status = 'PREPARED'",
                                  (session_id,)).fetchone():
                raise ValueError("Resolve the session's Git proposals before releasing it")
            connection.execute("UPDATE agent_sessions SET status = 'FAILED', end_time = ?, success = 0, "
                               "execution_summary = ? WHERE session_id = ?", (time.time(), reason, session_id))
            connection.execute("UPDATE issues SET status = 'FAILED' WHERE issue_id = ?", (row["issue_id"],))
            self._audit(connection, session_id, actor, reason, "fail_session", issue_id=row["issue_id"])

    def retry_issue(self, issue_id, *, actor, reason):
        """Requeue a failed issue only when none of its attempts applied source changes."""
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            issue = connection.execute("SELECT status FROM issues WHERE issue_id = ?", (issue_id,)).fetchone()
            if issue is None or issue["status"] != "FAILED":
                raise ValueError("Only failed issues can be retried")
            attempts = connection.execute("SELECT s.* FROM agent_sessions s JOIN issue_runs r USING(session_id) "
                                          "WHERE r.issue_id = ?", (issue_id,)).fetchall()
            if not attempts:
                raise ValueError("Issue has no execution history to verify")
            for attempt in attempts:
                self._authorize_recovery(attempt["session_id"], actor, reason)
                if attempt["status"] == "RUNNING":
                    raise ValueError("An attempt is still running")
            if connection.execute(
                    "SELECT 1 FROM commit_proposals p JOIN issue_runs r USING(session_id) "
                    "WHERE r.issue_id = ? AND p.status IN ('PREPARED', 'APPLIED')", (issue_id,)).fetchone():
                raise ValueError("Issue has applied or unresolved Git changes; create a follow-up issue")
            connection.execute("UPDATE issues SET status = 'WAITING' WHERE issue_id = ?", (issue_id,))
            self._audit(connection, attempts[-1]["session_id"], actor, reason, "retry_issue", issue_id=issue_id)
