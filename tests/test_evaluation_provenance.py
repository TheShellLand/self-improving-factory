import unittest
from types import SimpleNamespace

from core.config import PiAgentConfig
from core.evaluation_provenance import EvaluationExecutionRecord, EvaluationProvenanceConfig


class TestEvaluationArguments(unittest.TestCase):
    def setUp(self):
        client = SimpleNamespace(config=PiAgentConfig(
            executable="/path with spaces/pi", provider="test", model="test-model"))
        self.record = EvaluationProvenanceConfig(
            source_revision="a" * 40, pi_version="test").capture(client)

    def test_supported_arguments_preserve_executable_and_selection(self):
        record = EvaluationExecutionRecord.model_validate(self.record)
        self.assertEqual(record.argv[0], "/path with spaces/pi")
        self.assertEqual(record.argv[-4:], ["--provider", "test", "--model", "test-model"])

    def test_changed_execution_contract_is_rejected(self):
        original = self.record["argv"]
        variants = [
            ["pi"], original[:-4], original[:-2], original + ["--tools", "bash"],
            [arg for arg in original if arg != "--no-tools"],
            ["print" if arg == "rpc" else arg for arg in original],
            original[:-1] + [" "],
            original[:-4] + ["--provider", "test", "--provider", "test-model"],
        ]
        for argv in variants:
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                EvaluationExecutionRecord.model_validate({**self.record, "argv": argv})
