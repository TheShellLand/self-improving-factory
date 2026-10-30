"""Audit the intent and outcome of a gatekeeper operation.

Git and SQLite do not share a transaction. A PREPARED record left by a crash
must be reconciled against Git before retrying the operation.
"""
from uuid import uuid4
import json
from core.database import DatabaseClient
from core.signals import SignalPulse
from core.vault import Vault


class CommitService:
    def __init__(self, database_path, gatekeeper):
        self.database = DatabaseClient(database_path)
        self.db_path = self.database.config.database_path
        self.gatekeeper = gatekeeper

    def apply(self, session_id, message, file_changes):
        proposal_id = str(uuid4())
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute(
                    "SELECT 1 FROM agent_sessions WHERE session_id = ? AND status = 'RUNNING'",
                    (session_id,)).fetchone():
                raise ValueError("A running session is required for a code proposal")
            if connection.execute("SELECT 1 FROM commit_proposals WHERE status = 'PREPARED'").fetchone():
                raise RuntimeError("An unresolved Git proposal requires reconciliation")
            connection.execute("INSERT INTO commit_proposals VALUES (?, ?, 'PREPARED', NULL, NULL)",
                               (proposal_id, session_id))
            snapshot = self.gatekeeper.proposal_snapshot(message, file_changes)
            connection.execute("INSERT INTO proposal_evidence VALUES (?, ?)",
                               (proposal_id, json.dumps(snapshot, allow_nan=False)))
            Vault._record(connection, SignalPulse(source_agent="gatekeeper", action_type="ACTION_START",
                         payload={"proposal_id": proposal_id, "session_id": session_id,
                                  "message": message, "files": [item["filename"] for item in file_changes]}))
        try:
            applied = self.gatekeeper.execute_proposed_commit(message, file_changes)
        except Exception as error:
            # Recovery itself may have failed; preserve PREPARED for inspection.
            raise RuntimeError(f"Inspect unresolved proposal {proposal_id}") from error
        sha = self.gatekeeper.get_last_commit() if applied else None
        with self.database.connect() as connection:
            connection.execute("UPDATE commit_proposals SET status = ?, commit_sha = ?, error = ? "
                               "WHERE proposal_id = ?",
                               ("APPLIED" if applied else "FAILED", sha,
                                None if applied else "Gatekeeper rejected or rolled back the proposal", proposal_id))
            Vault._record(connection, SignalPulse(source_agent="gatekeeper", action_type="RESULT",
                         payload={"proposal_id": proposal_id, "session_id": session_id,
                                  "success": applied, "commit_sha": sha}))
        if not applied:
            raise ValueError("Gatekeeper rejected or rolled back the proposal")
        return sha
