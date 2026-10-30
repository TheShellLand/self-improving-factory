import json
import unittest
from unittest.mock import AsyncMock

from core.pi_client import PiClient, PiAgentError
from core.pi_result import PiResultParser


class TestPiResult(unittest.IsolatedAsyncioTestCase):
    def test_valid_proposal_preserves_content(self):
        result = PiResultParser().parse(json.dumps({
            "success": True, "summary": "Updated", "commit_message": "fix example",
            "file_changes": [{"filename": "src/example.py", "content": "a\nb\n"}]}))
        self.assertEqual(result.file_changes[0].content, "a\nb\n")

    def test_invalid_json_and_result_shapes(self):
        for text in ('{}', '[]', '```json\n{}\n```',
                     '{"success":true,"success":false,"summary":"x"}',
                     '{"success":"true","summary":"x"}',
                     '{"success":true,"summary":" "}',
                     '{"success":true,"summary":"x","unexpected":1}',
                     '{"success":true,"summary":"x","observations":[{"x":NaN}]}',
                     '{"success":true,"summary":"x","observations":[{"x":1e999}]}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                PiResultParser().parse(text)

    def test_rejects_unsafe_and_conflicting_paths(self):
        for names in (["../x"], ["/tmp/x"], [".git/config"], ["a/.GIT/x"],
                      ["C:/x"], ["a\\b"], ["a//b"], ["./a"], ["x\x00"],
                      ["a", "a/b"], ["a", "A"], ["a", "a"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                PiResultParser().parse(json.dumps({
                    "success": True, "summary": "x", "commit_message": "change",
                    "file_changes": [{"filename": name, "content": ""} for name in names]}))

    def test_rejects_failure_proposals_and_missing_commit_message(self):
        for success, message in ((False, "change"), (True, "")):
            with self.assertRaises(ValueError):
                PiResultParser().parse(json.dumps({
                    "success": success, "summary": "x", "commit_message": message,
                    "file_changes": [{"filename": "a", "content": ""}]}))

    async def test_client_returns_validated_result_or_explicit_failure(self):
        client = PiClient()
        client.run_inference = AsyncMock(return_value={"text": '{"success":false,"summary":"Cannot finish"}'})
        self.assertFalse((await client.run_structured("task")).success)
        client.run_inference.return_value = {"text": "looks good"}
        with self.assertRaises(PiAgentError):
            await client.run_structured("task")
