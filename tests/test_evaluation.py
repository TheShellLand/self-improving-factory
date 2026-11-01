import unittest

from core.evaluation import EvaluationConfig, StrategyEvaluator


class TestStrategyEvaluator(unittest.TestCase):
    def attempts(self, prefix):
        return [{"case_id": case, "repetition": repetition,
                 "evidence_id": f"{prefix}/{case}/{repetition}",
                 "outcome": {"success": success, "summary": summary}}
                for case, (success, summary) in EvaluationConfig.expected.items()
                for repetition in range(1, 6)]

    def test_improvement_requires_three_additional_passes(self):
        baseline, candidate = self.attempts("base"), self.attempts("candidate")
        for attempt in baseline[:2]:
            attempt["outcome"]["summary"] = "wrong"
        evaluator = StrategyEvaluator()
        self.assertEqual(evaluator.compare(baseline, candidate)["decision"], "NO_CHANGE")
        baseline[2]["outcome"]["summary"] = "wrong"
        result = evaluator.compare(baseline, candidate)
        self.assertEqual(result["decision"], "IMPROVEMENT")
        self.assertEqual(result["delta_percentage_points"], 10)

    def test_per_case_regression_overrides_total_gain(self):
        baseline, candidate = self.attempts("base"), self.attempts("candidate")
        for attempt in baseline[:5]:
            attempt["outcome"]["summary"] = "wrong"
        candidate[5]["outcome"]["summary"] = "wrong"
        self.assertEqual(StrategyEvaluator().compare(baseline, candidate)["decision"], "REGRESSION")

    def test_critical_failure_even_when_baseline_also_fails(self):
        baseline, candidate = self.attempts("base"), self.attempts("candidate")
        for attempts in (baseline, candidate):
            attempts[-1].pop("outcome")
            attempts[-1]["failure"] = "timeout"
        self.assertEqual(StrategyEvaluator().compare(baseline, candidate)["decision"], "REGRESSION")

    def test_missing_duplicate_or_invalid_evidence_is_inconclusive(self):
        baseline = self.attempts("base")
        for candidate in (self.attempts("c")[:-1], self.attempts("c") + self.attempts("c")[:1],
                          self.attempts("base")):
            self.assertEqual(StrategyEvaluator().compare(baseline, candidate)["decision"], "INCONCLUSIVE")
        candidate = self.attempts("c")
        candidate[0]["outcome"]["success"] = "true"
        self.assertEqual(StrategyEvaluator().compare(baseline, candidate)["decision"], "INCONCLUSIVE")

    def test_exact_match_and_false_success_cases(self):
        baseline, candidate = self.attempts("base"), self.attempts("candidate")
        result = StrategyEvaluator().compare(baseline, candidate)
        self.assertEqual(result["candidate_score"], 1)
        self.assertEqual(result["decision"], "NO_CHANGE")
        candidate[0]["outcome"]["summary"] += " "
        self.assertEqual(StrategyEvaluator().compare(baseline, candidate)["candidate"]["sum"], 4)
