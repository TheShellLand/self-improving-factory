import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.database import initialize_database
from core.pi_client import PiClient, PiAgentError
from core.pi_events import PiEventRecorder
from core.pi_runner import PiRunner
from core.vault import Vault
from test_pi_client import RpcProcess


class TestPiEvents(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "vault.db"
        initialize_database(path)
        self.vault = Vault(path)
        self.vault.create_issue({"title": "Task"})
        self.issue, self.session = self.vault.claim_next()
        self.recorder = PiEventRecorder(self.vault, self.session, self.issue["issue_id"])

    def records(self):
        with self.vault.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM trace_signals WHERE source_agent = 'pi' ORDER BY rowid")]

    async def test_wire_events_persist_even_when_final_result_is_invalid(self):
        process = RpcProcess("success")
        with patch("core.pi_client.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with self.assertRaises(PiAgentError):
                await PiRunner(PiClient(), vault=self.vault)(self.issue, self.session, {})
        rows = self.records()
        payloads = [json.loads(row["payload"]) for row in rows]
        self.assertEqual([p["event"]["type"] for p in payloads],
                         ["message_end", "agent_end", "agent_settled"])
        self.assertEqual([p["sequence"] for p in payloads], [1, 2, 3])
        self.assertTrue(all(p["session_id"] == self.session for p in payloads))
        self.assertTrue(all(row["action_type"] == "OBSERVATION" for row in rows))
        self.assertTrue(process.closed)

    def test_remote_fields_cannot_override_host_identity(self):
        event = {"type": "future_event", "session_id": "forged", "sequence": 999,
                 "source_agent": "host", "value": {"flag": False, "count": 2}}
        self.recorder(event)
        event["value"]["count"] = 3
        row = self.records()[0]
        payload = json.loads(row["payload"])
        self.assertEqual(payload["session_id"], self.session)
        self.assertEqual(payload["issue_id"], self.issue["issue_id"])
        self.assertEqual(payload["sequence"], 1)
        self.assertEqual(payload["event"]["value"], {"flag": False, "count": 2})
        self.assertEqual(row["source_agent"], "pi")

    def test_invalid_events_are_not_persisted(self):
        for event in ({}, {"type": ""}, {"type": 1}, {"type": "response"},
                      {"type": "update", "value": float("nan")}):
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.recorder(event)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.recorder.sequence, 0)

    def test_receipt_timing_uses_monotonic_clock(self):
        with patch("core.pi_events.monotonic", side_effect=[100, 100.25, 101]):
            recorder = PiEventRecorder(self.vault, self.session, self.issue["issue_id"])
            recorder({"type": "start", "elapsed_seconds": 999})
            recorder({"type": "agent_settled"})
        timing = [json.loads(row["metadata"])["receipt_timing"]
                  for row in self.records()]
        self.assertEqual(timing, [
            {"elapsed_seconds": 0.25, "inter_event_seconds": None},
            {"elapsed_seconds": 1, "inter_event_seconds": 0.75},
        ])

    def test_failed_write_does_not_advance_timing(self):
        vault = Mock()
        vault.record.side_effect = [None, RuntimeError("write failed"), None]
        with patch("core.pi_events.monotonic", side_effect=[100, 101, 102, 104]):
            recorder = PiEventRecorder(vault, self.session, self.issue["issue_id"])
            recorder({"type": "start"})
            with self.assertRaises(RuntimeError):
                recorder({"type": "update"})
            recorder({"type": "end"})
        signal = vault.record.call_args.args[0]
        self.assertEqual(signal.payload["sequence"], 2)
        self.assertEqual(signal.metadata["receipt_timing"]["inter_event_seconds"], 3)

    async def test_storage_failure_propagates_and_closes_process(self):
        process = RpcProcess("success")
        vault = Mock()
        vault.record.side_effect = RuntimeError("Storage unavailable")
        with patch("core.pi_client.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with self.assertRaisesRegex(RuntimeError, "Storage unavailable"):
                await PiRunner(PiClient(), vault=vault)(self.issue, self.session, {})
        self.assertTrue(process.closed)
