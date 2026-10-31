import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock

from core.coordinator import Coordinator
from core.database import initialize_database
from core.hotloader import HotLoaderModule
from core.pi_client import PiAgentError, PiClient
from core.pi_runner import PiRunner
from core.vault import Vault


class TestPiRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Path(temp.name) / "vault.db"
        initialize_database(db)
        self.vault = Vault(db)
        self.vault.create_issue({"title": "Explain", "description": "Explain café\nnext line"})
        self.client = PiClient()
        self.client.run_inference = AsyncMock()
        self.loader = HotLoaderModule(db)
        self.evolution = Mock()
        self.coordinator = Coordinator(self.vault, PiRunner(self.client),
                                       self.evolution, self.loader)

    async def test_coordinator_receives_validated_result_and_context(self):
        self.client.run_inference.return_value = {"text": json.dumps({
            "success": True, "summary": "Explained", "observations": [{"detail": "example"}]})}
        session = await self.coordinator.run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "CLOSED")
        prompt = self.client.run_inference.call_args.args[0]
        context = json.loads(prompt.split("\nContext:\n", 1)[1])
        self.assertEqual(context["session_id"], session)
        self.assertEqual(json.loads(context["issue"]["content"])["description"],
                         "Explain café\nnext line")
        self.assertEqual(context["strategy"], {})
        self.evolution.reflect_session.assert_called_once()

    async def test_strategy_preserves_types_without_changing_client_config(self):
        self.client.run_inference.return_value = {"text": '{"success":false,"summary":"Need context"}'}
        original = self.client.config
        strategy = {"retry": 2, "enabled": False, "nested": {"model": "untrusted"}}
        outcome = await PiRunner(self.client)({"title": "Task"}, "session", strategy)
        context = json.loads(self.client.run_inference.call_args.args[0].split("\nContext:\n", 1)[1])
        self.assertEqual(context["strategy"], strategy)
        self.assertIs(self.client.config, original)
        self.assertFalse(outcome.success)

    async def test_invalid_result_fails_issue(self):
        self.client.run_inference.return_value = {"text": "not JSON"}
        with self.assertRaises(PiAgentError):
            await self.coordinator.run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "FAILED")
        self.evolution.reflect_session.assert_not_called()

    async def test_provider_error_fails_issue(self):
        self.client.run_inference.side_effect = PiAgentError("Provider failed")
        with self.assertRaises(PiAgentError):
            await self.coordinator.run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "FAILED")

    async def test_cancellation_preserves_claim(self):
        self.client.run_inference.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.coordinator.run_once()
        self.assertIsNone(self.vault.claim_next())
        self.evolution.reflect_session.assert_not_called()

    async def test_proposals_still_require_gatekeeper(self):
        self.client.run_inference.return_value = {"text": json.dumps({
            "success": True, "summary": "Proposed", "commit_message": "Change",
            "file_changes": [{"filename": "file.txt", "content": "example"}]})}
        with self.assertRaisesRegex(RuntimeError, "gatekeeper"):
            await self.coordinator.run_once()
        self.assertEqual(self.vault.list_issues()[0]["status"], "FAILED")
