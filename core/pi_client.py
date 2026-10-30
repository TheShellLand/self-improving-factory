"""One-operation pi JSONL RPC client; no shell or agent tools are enabled."""
import asyncio
import json
import tempfile
from uuid import uuid4

from core.config import PiAgentConfig


class PiAgentError(RuntimeError):
    """Launch, protocol, provider, or deadline failure."""


class PiClient:
    def __init__(self, config=None):
        self.config = config if config is not None else PiAgentConfig()
        self._lock = asyncio.Lock()

    async def _drain_stderr(self, stream):
        # Drain continuously without retaining potentially sensitive diagnostics.
        while await stream.read(8192):
            pass

    async def _read(self, process):
        try:
            line = await process.stdout.readline()
            if not line:
                raise PiAgentError("pi disconnected before completing the operation")
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get("type"), str):
                raise ValueError("Expected a typed JSON object")
            return record
        except (ValueError, UnicodeError) as error:
            raise PiAgentError("Invalid or oversized pi RPC record") from error

    async def _exchange(self, process, command, params, on_event):
        request_id = uuid4().hex
        process.stdin.write(json.dumps(
            {"id": request_id, "type": command, **params}, allow_nan=False
        ).encode("utf-8") + b"\n")
        await process.stdin.drain()
        acknowledged = False
        settled = False
        message = None
        while True:
            record = await self._read(process)
            if record["type"] == "response":
                if record.get("id") != request_id or record.get("command") != command:
                    raise PiAgentError("Unexpected pi RPC response")
                if record.get("success") is not True:
                    raise PiAgentError("pi rejected the RPC command")
                if command != "prompt":
                    return record.get("data")
                disposition = (record.get("data") or {}).get("disposition")
                if disposition not in (None, "started"):
                    raise PiAgentError("Prompt did not start a new agent run")
                acknowledged = True
            else:
                if on_event is not None:
                    on_event(record)
                if record["type"] == "message_end":
                    candidate = record.get("message")
                    if isinstance(candidate, dict) and candidate.get("role") == "assistant":
                        message = candidate
                if record["type"] == "agent_settled":
                    if record.get("aborted") is not False:
                        raise PiAgentError("pi run was aborted or settlement is invalid")
                    settled = True
            if acknowledged and settled:
                if not message or message.get("stopReason") != "stop":
                    raise PiAgentError("pi did not produce a successful final assistant message")
                content = message.get("content")
                if not isinstance(content, list):
                    raise PiAgentError("Invalid assistant content")
                text = "".join(block["text"] for block in content
                               if isinstance(block, dict) and block.get("type") == "text"
                               and isinstance(block.get("text"), str))
                if not text:
                    raise PiAgentError("pi returned no text")
                return {"text": text}

    async def _stop(self, process):
        if process.stdin:
            process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), self.config.cleanup_timeout)
        except TimeoutError:
            if process.returncode is None:
                process.kill()
            await asyncio.wait_for(process.wait(), self.config.cleanup_timeout)

    async def perform_action(self, action, params=None, *, on_event=None):
        """Run a supported operation in a fresh process with bounded lifetime."""
        if action not in {"get_state", "get_available_models", "prompt"}:
            raise ValueError("Unsupported RPC action")
        params = dict(params or {})
        if {"id", "type"} & params.keys():
            raise ValueError("RPC identity fields cannot be overridden")
        if action == "prompt" and (set(params) != {"message"} or
                                  not isinstance(params["message"], str) or
                                  not params["message"].strip()):
            raise ValueError("A nonempty prompt message is required")
        if action != "prompt" and params:
            raise ValueError("This operation accepts no parameters")
        async with self._lock:
            process = None
            stderr_task = None
            with tempfile.TemporaryDirectory(prefix="sif-pi-") as directory:
                try:
                    async with asyncio.timeout(self.config.timeout):
                        process = await asyncio.create_subprocess_exec(
                            *self.config.argv(), cwd=directory,
                            env=self.config.environment(),
                            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE, limit=self.config.max_record_bytes)
                        stderr_task = asyncio.create_task(self._drain_stderr(process.stderr))
                        return await self._exchange(process, action, params, on_event)
                except TimeoutError as error:
                    raise PiAgentError("pi RPC deadline exceeded") from error
                except OSError as error:
                    raise PiAgentError("Could not start or communicate with pi") from error
                finally:
                    try:
                        if process is not None:
                            await self._stop(process)
                    finally:
                        if stderr_task is not None:
                            stderr_task.cancel()
                            await asyncio.gather(stderr_task, return_exceptions=True)

    async def run_inference(self, prompt, *, on_event=None):
        """Return final text only after pi settles; never treat acknowledgment as success."""
        return await self.perform_action("prompt", {"message": prompt}, on_event=on_event)
