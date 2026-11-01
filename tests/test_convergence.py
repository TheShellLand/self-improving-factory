import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from core.database import connect, initialize_database
from core.evolution import EvolutionEngine
from core.hotloader import HotLoaderModule
from core.vault import Vault


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

    def test_invalid_proposals_leave_versions_and_audit_unchanged(self):
        vault = Vault(self.db)
        vault.create_issue({"title": "Task"})
        issue, session = vault.claim_next()
        invalid = [
            {"logic_description": " ", "prompt_weights": {}},
            {"logic_description": 1, "prompt_weights": {}},
            {"logic_description": "Why", "prompt_weights": {}, "unknown": True},
            {"logic_description": "Why", "prompt_weights": {"a": float("inf")}},
            {"logic_description": "Why", "prompt_weights": {1: "bad key"}},
            {"logic_description": "Why", "prompt_weights": {"a": (1, 2)}},
            {"logic_description": "Why", "prompt_weights": '{"a":1,"a":2}'},
            {"logic_description": "Why", "prompt_weights": "[]"},
        ]
        for proposal in invalid:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                EvolutionEngine(self.db, lambda *_: proposal).reflect_session(issue, session)
        with connect(self.db) as connection:
            for table in ("knowledge_updates", "reflection_sources"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM trace_signals WHERE action_type = 'REFLECTION'").fetchone()[0], 0)
        engine = EvolutionEngine(self.db, lambda *_: {
            "logic_description": "Keep exact types", "prompt_weights": {"nested": [True, None, 2]}})
        self.assertEqual(engine.reflect_session(issue, session), 1)
        self.assertEqual(engine.reflect_session(issue, session), 1)
        self.assertEqual(engine._commit_knowledge_update("Next", '{"retry":3}'), 2)
        loader = HotLoaderModule(self.db)
        self.assertEqual(loader.sync_once(), 2)
        self.assertEqual(loader.get_active_config(), {"nested": [True, None, 2], "retry": 3})

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

    def test_invalid_updates_are_audited_and_later_rows_load_after_restart(self):
        invalid = ["broken", "[]", "null", '{"a":NaN}', '{"a":1e999}',
                   '{"nested":{"a":1,"a":2}}']
        with connect(self.db) as connection:
            for value in ['{"before":1}', *invalid, '{"after":2}']:
                connection.execute(
                    "INSERT INTO knowledge_updates (applied_at, version_number, logic_description, prompt_weights) "
                    "VALUES (1, 1, 'legacy', ?)", (value,))
        for loader in (HotLoaderModule(self.db), HotLoaderModule(self.db)):
            with self.assertLogs("core.hotloader", level="WARNING"):
                self.assertEqual(loader.sync_once(), 2)
            self.assertEqual(loader.get_active_config(), {"before": 1, "after": 2})
            self.assertEqual(loader.sync_once(), 0)
        with connect(self.db) as connection:
            rejected = [json.loads(row[0]) for row in connection.execute(
                "SELECT payload FROM trace_signals WHERE source_agent = 'hotloader'")]
            self.assertEqual(len(rejected), 12)
            self.assertEqual({row["update_id"] for row in rejected}, set(range(2, 8)))
            self.assertTrue(all(row["status"] == "REJECTED" for row in rejected))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM knowledge_updates").fetchone()[0], 8)

    def test_failed_rejection_audit_does_not_advance_cursor(self):
        with connect(self.db) as connection:
            for value in ('bad', '{"later":true}'):
                connection.execute(
                    "INSERT INTO knowledge_updates (applied_at, version_number, logic_description, prompt_weights) "
                    "VALUES (1, 1, 'legacy', ?)", (value,))
        loader = HotLoaderModule(self.db)
        with patch("core.hotloader.Vault.record", side_effect=RuntimeError("Storage failed")):
            with self.assertRaisesRegex(RuntimeError, "Storage failed"):
                loader.sync_once()
        self.assertEqual(loader.get_active_config(), {})
        with self.assertLogs("core.hotloader", level="WARNING"):
            self.assertEqual(loader.sync_once(), 1)
        self.assertEqual(loader.get_active_config(), {"later": True})
