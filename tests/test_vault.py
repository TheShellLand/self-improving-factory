import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError
from core.config import SCHEMA_PATH
from core.database import connect, initialize_database
from core.observer import ObserverModule
from core.signals import SignalPulse
from core.vault import Vault


class TestVault(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "vault.db"
        initialize_database(self.db)
        self.vault = Vault(self.db)

    def report(self):
        return self.vault.create_issue({"title": "Test", "description": "Details"})

    def test_signal_validation_and_persistence(self):
        for invalid in [{"signal_id": "bad"}, {"action_type": "UNKNOWN"},
                        {"timestamp": float("nan")}, {"viewport": {"width": -1}}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                SignalPulse(**invalid)
        pulse = SignalPulse(action_type="OBSERVATION", visual_state={"base64_data": "YQ=="})
        ObserverModule(self.vault).process_telemetry(pulse.model_dump())
        with connect(self.db) as connection:
            row = connection.execute("SELECT * FROM trace_signals WHERE signal_id = ?", (pulse.signal_id,)).fetchone()
        self.assertEqual(json.loads(row["metadata"])["viewport"]["width"], 1920)

    def test_issue_and_input_are_one_transaction(self):
        with self.assertRaises(ValueError):
            self.vault.create_issue({"title": "Bad", "context_blob": {"value": float("nan")}})
        self.assertEqual(self.vault.list_issues(), [])
        issue_id = self.report()
        with connect(self.db) as connection:
            signals = connection.execute("SELECT payload FROM trace_signals WHERE action_type = 'INPUT'").fetchall()
        self.assertEqual(json.loads(signals[0][0])["issue_id"], issue_id)

    def test_claim_is_exclusive_and_terminal_state_is_recorded(self):
        self.report()
        self.report()
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: self.vault.claim_next(), range(2)))
        claimed = [claim for claim in claims if claim is not None]
        self.assertEqual(len(claimed), 1)
        issue, session = claimed[0]
        self.vault.finish(session, True, "done")
        self.assertIsNotNone(self.vault.claim_next())
        statuses = {row["issue_id"]: row["status"] for row in self.vault.list_issues()}
        self.assertEqual(statuses[issue["issue_id"]], "CLOSED")
        with self.assertRaises(ValueError):
            self.vault.finish(session, True, "duplicate")

    def test_original_schema_upgrade_preserves_records(self):
        old_db = Path(self.temp.name) / "old.db"
        original = SCHEMA_PATH.read_text().replace(", 'CLOSED', 'FAILED'", "")
        with connect(old_db) as connection:
            connection.executescript(original)
            connection.execute("INSERT INTO issues (issue_id, title, status) VALUES ('old', 'Keep me', 'OPEN')")
        initialize_database(old_db)
        initialize_database(old_db)
        with connect(old_db) as connection:
            self.assertEqual(connection.execute("SELECT title FROM issues WHERE issue_id = 'old'").fetchone()[0], "Keep me")
            connection.execute("UPDATE issues SET status = 'CLOSED' WHERE issue_id = 'old'")
