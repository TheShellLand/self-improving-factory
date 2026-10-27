import sqlite3
import json
from typing import List, Dict, Any

class CriticModule:
    """Analyzes SASIAS experience memory records to identify friction points and strategy drift."""
    def __init__(self, database_path: str):
        self.db_path = database_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        # Row factory makes retrieval easier for mapping columns to dicts
        conn.row_factory = sqlite3.Row
        return conn

    async def analyze_session_successes(self) -> List[Dict]:
        """Fetches recent sessions from agent_sessions table for correlation analysis."""
        # Currently returns all finished/failed session metadata 
        query = """SELECT * FROM agent_sessions WHERE status IN ('COMPLETED', 'FAILED') ORDER BY start_time DESC LIMIT 50;"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    async def fetch_high_priority_issues(self) -> List[Dict]:
        """Retrieves issues with high priority scores to focus reflection on critical blocking points."""
        # Note: Status can be OPEN, WAITING (for human selection), or already processing etc... we want the backlog of prioritized problems.
        query = "SELECT * FROM issues WHERE status IN ('OPEN', 'WAITING') ORDER BY priority_score DESC"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def correlate_failures_to_signals(self, session_id: str) -> Dict[str, Any]:
        """Digs into trace_signals associated with a specific session ID and identifies anomalous signal flows."""
        # Logic looks specifically at inputs/observations that led to FAILED sessions or low-success results logged by agents.
        # For now, it returns the raw log of signals related to this session's id (correlation logic pending completion).
        with self._get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM trace_signals WHERE action_type IN ('OBSERVATION', 'RESULT') AND payload LIKE ?" # Simplified check for demo
            # Real implementation would parse JSON from database before matching IDs appropriately if they aren't shared exactly 1:1 in all actions.

    def identify_experience_drift(self) -> List[Dict]:
        """Aggregates recent knowledge updates with high negative scores or repeated issue patterns."""
        pass


if __name__ == "__main__":
    critic = CriticModule("/root/brain/history_vault.db")
    print("Critic Module Initialized.")
