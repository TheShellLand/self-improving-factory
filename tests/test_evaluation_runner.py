import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock

from core.coordinator import ExecutionOutcome
from core.evaluation import EvaluationConfig
from core.evaluation_runner import EvaluationRunner
from core.pi_client import PiAgentError
from core.config import PiAgentConfig
from core.evaluation_evidence import EvaluationEvidenceClient


class TestEvaluationRunner(unittest.IsolatedAsyncioTestCase):
    def runner(self, client):
        client.config = PiAgentConfig(provider="test", model="test")
        return EvaluationRunner(client, provenance={"source_revision": "a" * 40, "pi_version": "test"})

    async def test_collects_sixty_isolated_attempts_and_scores(self):
        client = AsyncMock()

        async def result(prompt, on_event):
            context = json.loads(prompt.split("\nContext:\n")[1])
            success, summary = EvaluationConfig.expected[context["issue"]["title"]]
            on_event({"type": "agent_settled", "aborted": False})
            return ExecutionOutcome(success=success, summary=summary)

        client.run_structured.side_effect = result
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            report = await self.runner(client).run(root, {}, {"style": "brief"})
            self.assertEqual(report["decision"], "NO_CHANGE")
            self.assertEqual(report["candidate_score"], 1)
            self.assertEqual(len(list(root.glob("*.db"))), 60)
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "COMPLETED")
            self.assertEqual(manifest["execution"]["max_events"], client.config.max_events)
            self.assertEqual(len(manifest["attempts"]["baseline"]), 30)
            verifier = EvaluationEvidenceClient()
            self.assertEqual(verifier.verify(root), report)
            manifest_path = root / "manifest.json"
            original_manifest = manifest_path.read_text()
            for field in ("strategies", "strategy_hashes"):
                for invalid in (None, [], {}, {"baseline": {}, "candidate": {}, "extra": {}}):
                    with self.subTest(field=field, invalid=invalid):
                        altered = json.loads(original_manifest)
                        altered[field] = invalid
                        manifest_path.write_text(json.dumps(altered))
                        self.assertEqual(verifier.verify(root)["decision"], "INCONCLUSIVE")
            for invalid in ([], None, "{}", 42, True):
                with self.subTest(strategy=invalid):
                    altered = json.loads(original_manifest)
                    altered["strategies"]["baseline"] = invalid
                    manifest_path.write_text(json.dumps(altered))
                    self.assertEqual(verifier.verify(root)["decision"], "INCONCLUSIVE")
            for field, value in (("max_events", 0), ("timeout", -1),
                                 ("runner_source_sha256", "invalid"),
                                 ("declared", {}), ("argv", [])):
                with self.subTest(field=field):
                    altered = json.loads(original_manifest)
                    altered["execution"][field] = value
                    manifest_path.write_text(json.dumps(altered))
                    self.assertEqual(verifier.verify(root)["decision"], "INCONCLUSIVE")
            altered = json.loads(original_manifest)
            del altered["execution"]
            manifest_path.write_text(json.dumps(altered))
            self.assertEqual(verifier.verify(root)["decision"], "INCONCLUSIVE")
            manifest_path.write_text(original_manifest)
            self.assertEqual(verifier.verify(root), report)
            artifact = root / "baseline-sum-1.json"
            original = artifact.read_bytes()
            artifact.write_text("{}")
            self.assertEqual(verifier.verify(root)["decision"], "INCONCLUSIVE")
            artifact.write_bytes(original)
            self.assertEqual(verifier.verify(root), report)
            (root / "baseline-sum-1.db").unlink()
            self.assertEqual(verifier.verify(root)["decision"], "INCONCLUSIVE")
            with self.assertRaises(FileExistsError):
                await self.runner(client).run(root, {}, {})

    async def test_client_failures_are_retained_without_selective_retries(self):
        client = AsyncMock()
        client.run_structured.side_effect = PiAgentError("private provider details")
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            report = await self.runner(client).run(root, {}, {})
            self.assertEqual(report["decision"], "REGRESSION")
            self.assertEqual(client.run_structured.await_count, 60)
            self.assertNotIn("private provider details", (root / "manifest.json").read_text())

    async def test_cancelled_run_is_inconclusive_and_preserves_evidence(self):
        client = AsyncMock()
        client.run_structured.side_effect = asyncio.CancelledError()
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            with self.assertRaises(asyncio.CancelledError):
                await self.runner(client).run(root, {}, {})
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["report"]["decision"], "INCONCLUSIVE")
            self.assertEqual(len(list(root.glob("*.db"))), 1)
            self.assertEqual(json.loads((root / "baseline-sum-1.json").read_text())["failure"], "CancelledError")

    async def test_changed_settings_abort_comparison(self):
        client = AsyncMock()
        runner = self.runner(client)

        async def changed(*args, **kwargs):
            client.config.model = "changed"
            return ExecutionOutcome(success=True, summary="42")

        client.run_structured.side_effect = changed
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            with self.assertRaisesRegex(ValueError, "settings changed"):
                await runner.run(root, {}, {})
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["report"]["decision"], "INCONCLUSIVE")
            self.assertEqual(client.run_structured.await_count, 1)

    async def test_missing_provenance_creates_no_artifacts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            with self.assertRaisesRegex(ValueError, "provenance"):
                await EvaluationRunner(AsyncMock()).run(root, {}, {})
            self.assertFalse(root.exists())

    async def test_invalid_execution_settings_create_no_artifacts(self):
        for setting, value in (("max_events", 0), ("max_record_bytes", True),
                               ("timeout", float("inf")), ("cleanup_timeout", -1),
                               ("executable", ""), ("model", " ")):
            with self.subTest(setting=setting):
                client = AsyncMock()
                runner = self.runner(client)
                setattr(client.config, setting, value)
                with TemporaryDirectory() as directory:
                    root = Path(directory) / "run"
                    with self.assertRaises(ValueError):
                        await runner.run(root, {}, {})
                    self.assertFalse(root.exists())
                    client.run_structured.assert_not_awaited()

    async def test_final_provider_failure_cannot_hide_settings_drift(self):
        client = AsyncMock()
        runner = self.runner(client)
        calls = 0

        async def failing(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 60:
                client.config.max_events += 1
            raise PiAgentError("provider failure")

        client.run_structured.side_effect = failing
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            with self.assertRaisesRegex(ValueError, "settings changed"):
                await runner.run(root, {}, {})
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(calls, 60)
            self.assertEqual(manifest["status"], "INCOMPLETE")
            self.assertEqual(manifest["report"], {"decision": "INCONCLUSIVE"})
            self.assertEqual(len(manifest["attempts"]["candidate"]), 30)
            final = json.loads((root / "candidate-no-tools-5.json").read_text())
            self.assertEqual(final["failure"], "PiAgentError")
            self.assertTrue((root / final["database"]).exists())

    async def test_changed_event_budget_aborts_comparison(self):
        client = AsyncMock()
        runner = self.runner(client)
        client.config.max_events = 12

        async def changed(*args, **kwargs):
            client.config.max_events = 13
            return ExecutionOutcome(success=True, summary="42")

        client.run_structured.side_effect = changed
        with TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            with self.assertRaisesRegex(ValueError, "settings changed"):
                await runner.run(root, {}, {})
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["execution"]["max_events"], 12)
            self.assertEqual(manifest["status"], "INCOMPLETE")
            self.assertEqual(manifest["report"]["decision"], "INCONCLUSIVE")
            self.assertEqual(client.run_structured.await_count, 1)
            self.assertTrue((root / "baseline-sum-1.db").exists())
