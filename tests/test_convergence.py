import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from core.database import connect, initialize_database
from core.evolution import EvolutionEngine
from core.hotloader import HotLoaderModule


class TestReflection(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "vault.db"
        initialize_database(self.db)

    async def test_reflection_persists_and_loads_provider_output(self):
        with connect(self.db) as connection:
            connection.execute("INSERT INTO issues (issue_id, title, content, status) VALUES (?, ?, ?, ?)",
                               ("i1", "Failed", json.dumps({"context_blob": {"session_id": "s1"}}), "OPEN"))
            for session in ["s1", "s10"]:
                connection.execute(
                    "INSERT INTO trace_signals (signal_id, timestamp, source_agent, action_type, payload) "
                    "VALUES (?, 1, 'test', 'RESULT', ?)", (session, json.dumps({"session_id": session})))

        def provider(issue, traces):
            self.assertEqual(issue["issue_id"], "i1")
            self.assertEqual([row["signal_id"] for row in traces], ["s1"])
            return {"logic_description": "Retry more", "prompt_weights": {"retry": 2}}

        self.assertEqual(await EvolutionEngine(self.db, provider).run_reflection_cycle(), [1])
        loader = HotLoaderModule(self.db)
        self.assertEqual(loader.sync_once(), 1)
        self.assertEqual(loader.get_active_config(), {"retry": 2})
        self.assertEqual(loader.sync_once(), 0)

    async def test_provider_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "reflection provider"):
            await EvolutionEngine(self.db).run_reflection_cycle()

    def test_same_timestamp_does_not_skip_later_updates(self):
        engine = EvolutionEngine(self.db)
        engine._commit_knowledge_update("First", {"a": 1})
        with connect(self.db) as connection:
            connection.execute("UPDATE knowledge_updates SET applied_at = 1")
        loader = HotLoaderModule(self.db)
        loader.sync_once()
        engine._commit_knowledge_update("Second", {"b": 2})
        with connect(self.db) as connection:
            connection.execute("UPDATE knowledge_updates SET applied_at = 1")
        self.assertEqual(loader.sync_once(), 1)
        self.assertEqual(loader.get_active_config(), {"a": 1, "b": 2})
