import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from core.config import PiAgentConfig
from core.pi_client import PiClient, PiAgentError


class RpcProcess:
    def __init__(self, mode):
        self.mode = mode
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.stdin = self
        self.returncode = None
        self.closed = False

    def write(self, data):
        request = json.loads(data)
        if self.mode == "timeout":
            return
        if self.mode == "malformed":
            self.stdout.feed_data(b"not json\n")
            return
        if self.mode == "disconnect":
            self.stdout.feed_eof()
            return
        records = [{"type": "response", "id": request["id"],
                    "command": request["type"], "success": self.mode != "reject"}]
        records += [{"type": "message_end", "message": {
            "role": "assistant", "stopReason": "error" if self.mode == "error" else "stop",
            "content": [{"type": "text", "text": "hello\u2028world"}]}},
            {"type": "agent_end", "willRetry": False}]
        if self.mode != "no_settlement":
            records.append({"type": "agent_settled", "aborted": self.mode == "aborted"})
        for record in records:
            self.stdout.feed_data(json.dumps(record, ensure_ascii=False).encode() + b"\n")

    async def drain(self):
        pass

    def close(self):
        self.closed = True
        self.returncode = 0
        self.stderr.feed_eof()

    async def wait(self):
        return self.returncode


class TestPiClient(unittest.IsolatedAsyncioTestCase):
    async def test_success_waits_for_settlement_and_preserves_unicode(self):
        process = RpcProcess("success")
        events = []
        with patch("core.pi_client.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            result = await PiClient().run_inference("hello", on_event=events.append)
        self.assertEqual(result, {"text": "hello\u2028world"})
        self.assertEqual(events[-1]["type"], "agent_settled")
        self.assertTrue(process.closed)

    async def test_failures_never_return_success_and_close_process(self):
        for mode in ("malformed", "disconnect", "reject", "error", "aborted", "timeout", "no_settlement"):
            with self.subTest(mode=mode):
                process = RpcProcess(mode)
                with patch("core.pi_client.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
                    with self.assertRaises(PiAgentError):
                        await PiClient(PiAgentConfig(timeout=0.02)).run_inference("hello")
                self.assertTrue(process.closed)

    async def test_cancellation_closes_process(self):
        process = RpcProcess("timeout")
        with patch("core.pi_client.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            task = asyncio.create_task(PiClient().run_inference("hello"))
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(process.closed)

    async def test_missing_executable(self):
        with self.assertRaises(PiAgentError):
            await PiClient(PiAgentConfig(executable="/nonexistent/sif-pi")).run_inference("hello")

    def test_configuration_reads_environment_and_preserves_credentials(self):
        with patch.dict(os.environ, {"SIF_MODEL": "test", "SIF_PROVIDER": "example",
                                     "SIF_TIMEOUT": "7", "OPENAI_API_KEY": " exact value "}):
            config = PiAgentConfig()
            self.assertEqual(config.timeout, 7)
            self.assertIn("test", config.argv())
            self.assertIn("example", config.argv())
            self.assertEqual(config.environment()["OPENAI_API_KEY"], " exact value ")
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                PiAgentConfig(timeout=timeout)
