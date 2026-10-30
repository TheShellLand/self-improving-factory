"""Read issue and session evidence for reflection providers."""
import json
from core.database import DatabaseClient


class CriticModule:
    def __init__(self, database_path):
        self.database = DatabaseClient(database_path)
        self.db_path = self.database.config.database_path

    async def analyze_session_successes(self):
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM agent_sessions WHERE status IN ('COMPLETED', 'FAILED') "
                "ORDER BY start_time DESC LIMIT 50")]

    async def fetch_high_priority_issues(self):
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM issues WHERE status IN ('OPEN', 'WAITING') "
                "ORDER BY priority_score DESC")]

    def correlate_failures_to_signals(self, session_id):
        """Return observations and results with an exact payload session ID."""
        traces = []
        with self.database.connect() as connection:
            for row in connection.execute(
                "SELECT * FROM trace_signals WHERE action_type IN ('OBSERVATION', 'RESULT') "
                "ORDER BY timestamp"):
                try:
                    payload = json.loads(row["payload"])
                except (TypeError, ValueError):
                    continue
                if isinstance(payload, dict) and payload.get("session_id") == session_id:
                    traces.append(dict(row))
        return traces

    def identify_experience_drift(self):
        raise NotImplementedError("Experience drift requires an analysis provider")
