"""Transactional issue, session, and telemetry operations."""
import json
import time
from uuid import uuid4

from core.database import DatabaseClient
from core.signals import SignalPulse


class Vault:
    def __init__(self, database_path):
        self.database = DatabaseClient(database_path)
        self.db_path = self.database.config.database_path

    @staticmethod
    def _record(connection, pulse):
        # Round-trip validation also checks in-place changes to mutable payloads.
        pulse = SignalPulse.model_validate_json(pulse.to_json())
        metadata = {**pulse.metadata, "viewport": pulse.viewport.model_dump(),
                    "visual_state": pulse.visual_state}
        connection.execute(
            "INSERT INTO trace_signals VALUES (?, ?, ?, ?, ?, ?)",
            (pulse.signal_id, pulse.timestamp, pulse.source_agent, pulse.action_type,
             json.dumps(pulse.payload, allow_nan=False), json.dumps(metadata, allow_nan=False)))

    def record(self, pulse):
        with self.database.connect() as connection:
            self._record(connection, pulse)

    def create_issue(self, report):
        issue_id = str(uuid4())
        pulse = SignalPulse(source_agent="bridge", payload={"issue_id": issue_id, **report},
                            viewport=report.get("client_viewport") or {})
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO issues VALUES (?, ?, ?, 'OPEN', ?, ?)",
                (issue_id, report["title"], json.dumps(report, allow_nan=False),
                 report.get("priority", 10.0), json.dumps(report.get("client_viewport", {}))))
            self._record(connection, pulse)
        return issue_id

    def list_issues(self):
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM issues ORDER BY priority_score DESC, issue_id LIMIT 100")]

    def vote(self, issue_id, delta):
        if delta not in (-1, 1):
            raise ValueError("Votes must be +1 or -1")
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE issues SET priority_score = priority_score + ? "
                "WHERE issue_id = ? AND status IN ('OPEN', 'WAITING')", (delta, issue_id))
            if not cursor.rowcount:
                raise ValueError("Issue is missing or no longer queued")
            self._record(connection, SignalPulse(source_agent="bridge", payload={
                "issue_id": issue_id, "vote": delta}))

    def claim_next(self):
        """Claim one issue across all workers; leave interrupted runs visible."""
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM agent_sessions WHERE status = 'RUNNING'").fetchone():
                return None
            if connection.execute("SELECT 1 FROM commit_proposals WHERE status = 'PREPARED'").fetchone():
                return None
            row = connection.execute(
                "SELECT * FROM issues WHERE status IN ('OPEN', 'WAITING') "
                "ORDER BY priority_score DESC, issue_id LIMIT 1").fetchone()
            if row is None:
                return None
            session_id = str(uuid4())
            connection.execute("UPDATE issues SET status = 'IN PROGRESS' WHERE issue_id = ?", (row["issue_id"],))
            connection.execute(
                "INSERT INTO agent_sessions (session_id, start_time, status) VALUES (?, ?, 'RUNNING')",
                (session_id, time.time()))
            connection.execute("INSERT INTO issue_runs VALUES (?, ?)", (session_id, row["issue_id"]))
            self._record(connection, SignalPulse(action_type="ACTION_START", payload={
                "issue_id": row["issue_id"], "session_id": session_id}))
            return dict(row), session_id

    def finish(self, session_id, success, summary):
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE agent_sessions SET status = ?, end_time = ?, success = ?, execution_summary = ? "
                "WHERE session_id = ? AND status = 'RUNNING'",
                ("COMPLETED" if success else "FAILED", time.time(), success, summary, session_id))
            if not cursor.rowcount:
                raise ValueError("Session is missing or already finished")
            connection.execute(
                "UPDATE issues SET status = ? WHERE issue_id = "
                "(SELECT issue_id FROM issue_runs WHERE session_id = ?)",
                ("CLOSED" if success else "FAILED", session_id))
            self._record(connection, SignalPulse(action_type="RESULT", payload={
                "session_id": session_id, "success": success, "summary": summary}))
