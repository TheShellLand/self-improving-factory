"""Persist reflection proposals supplied by an explicit analysis provider."""
import json
import time
from core.critic import CriticModule
from core.database import connect
from core.signals import SignalPulse
from core.vault import Vault


class EvolutionEngine:
    def __init__(self, database_path, reflection_provider=None):
        self.db_path = database_path
        self.reflection_provider = reflection_provider

    async def run_reflection_cycle(self):
        """Pass each prioritized issue and its evidence to the provider.

        The caller owns issue scheduling and deduplication across cycles.
        A provider accepts (issue, traces) and returns logic_description and
        prompt_weights, or None when no update is appropriate.
        """
        if self.reflection_provider is None:
            raise RuntimeError("Configure a reflection provider before running a cycle")
        critic = CriticModule(self.db_path)
        versions = []
        for issue in await critic.fetch_high_priority_issues():
            try:
                content = json.loads(issue["content"] or "{}")
            except (TypeError, ValueError):
                content = {}
            context = content.get("context_blob", {}) if isinstance(content, dict) else {}
            session_id = context.get("session_id") if isinstance(context, dict) else None
            traces = critic.correlate_failures_to_signals(session_id) if session_id else []
            update = self.reflection_provider(issue, traces)
            if update is not None:
                versions.append(self._commit_knowledge_update(
                    update["logic_description"], update["prompt_weights"]))
        return versions

    def reflect_session(self, issue, session_id):
        """Persist at most one provider update for a completed execution attempt."""
        if self.reflection_provider is None:
            raise RuntimeError("Configure a reflection provider before running a cycle")
        with connect(self.db_path) as connection:
            existing = connection.execute(
                "SELECT version_number FROM reflection_sources WHERE source_id = ?", (session_id,)).fetchone()
        if existing:
            return existing[0]
        traces = CriticModule(self.db_path).correlate_failures_to_signals(session_id)
        update = self.reflection_provider(issue, traces)
        if update is None:
            return None
        return self._commit_knowledge_update(
            update["logic_description"], update["prompt_weights"], source_id=session_id)

    def _commit_knowledge_update(self, desc, weights, *, source_id=None):
        weights = json.loads(weights) if isinstance(weights, str) else weights
        if not isinstance(weights, dict):
            raise ValueError("Prompt weights must be a JSON object")
        encoded = json.dumps(weights, allow_nan=False)
        with connect(self.db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if source_id is not None:
                existing = connection.execute(
                    "SELECT version_number FROM reflection_sources WHERE source_id = ?", (source_id,)).fetchone()
                if existing:
                    return existing[0]
            version = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM knowledge_updates"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO knowledge_updates "
                "(applied_at, version_number, logic_description, prompt_weights) VALUES (?, ?, ?, ?)",
                (time.time(), version, desc, encoded))
            if source_id is not None:
                connection.execute("INSERT INTO reflection_sources VALUES (?, ?)", (source_id, version))
                Vault._record(connection, SignalPulse(source_agent="evolution", action_type="REFLECTION",
                             payload={"session_id": source_id, "version_number": version}))
        return version
