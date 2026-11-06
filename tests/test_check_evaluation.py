from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from scripts.check_evaluation import EvaluationCheck, main


class TestEvaluationCheck(unittest.TestCase):
    def test_verified_decisions_are_not_adoption_exit_codes(self):
        for decision in ("IMPROVEMENT", "NO_CHANGE", "REGRESSION", "INCONCLUSIVE"):
            with self.subTest(decision=decision):
                client = Mock()
                client.verify.return_value = {"decision": decision}
                output = StringIO()
                with redirect_stdout(output):
                    code = EvaluationCheck(client).run("saved run")
                self.assertEqual(code, 1 if decision == "INCONCLUSIVE" else 0)
                self.assertEqual(json.loads(output.getvalue()), {"decision": decision})
                client.verify.assert_called_once_with("saved run")

    def test_malformed_evidence_is_inconclusive_and_unchanged(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text("invalid json")
            before = path.read_bytes()
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([directory]), 1)
            self.assertEqual(json.loads(output.getvalue()), {"decision": "INCONCLUSIVE"})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_missing_directory_is_not_created(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "missing"
            with redirect_stdout(StringIO()):
                self.assertEqual(main([str(path)]), 1)
            self.assertFalse(path.exists())
