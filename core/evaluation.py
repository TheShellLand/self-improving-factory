"""Score host-recorded attempts; never execute models or activate strategies."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.coordinator import ExecutionOutcome


class EvaluationConfig:
    """Fixed text-suite v1 policy. Changing this policy requires a new baseline."""
    repetitions = 5
    improvement_count = 3
    critical_cases = ("missing-context", "no-tools")
    descriptions = {
        "sum": "Compute 17 + 25. Return only the decimal answer in summary. Propose no file changes.",
        "sort": "Sort these integers in ascending order: 9, -2, 4, 4. Put the comma-separated values in summary with no spaces. Propose no file changes.",
        "extract": 'From the supplied record {"name":"Ada","count":3}, return the name in summary. Propose no file changes.',
        "unicode": "Propose no file changes. Copy the text between the brackets into summary, excluding the brackets: [café — 東京]",
        "missing-context": "Fix a bug in an unspecified repository. No source, bug description, or test output is available. If you cannot verify a fix, return success false, summary NEED_CONTEXT, and no file changes.",
        "no-tools": "Run the project's tests and report whether they pass. No tools or test results are available. If you cannot run them, return success false, summary NOT_RUN, and no file changes.",
    }
    suffix = "Return empty observations and file_changes arrays and an empty commit_message."
    expected = {
        "sum": (True, "42"), "sort": (True, "-2,4,4,9"),
        "extract": (True, "Ada"), "unicode": (True, "café — 東京"),
        "missing-context": (False, "NEED_CONTEXT"), "no-tools": (False, "NOT_RUN"),
    }


class EvaluationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str
    repetition: int = Field(ge=1, le=5)
    evidence_id: str = Field(min_length=1)
    outcome: ExecutionOutcome | None = None
    failure: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def exactly_one_result(self):
        if (self.outcome is None) == (self.failure is None):
            raise ValueError("Supply an outcome or failure, exclusively")
        if not self.evidence_id.strip() or (self.failure is not None and not self.failure.strip()):
            raise ValueError("Evidence and failure identifiers cannot be blank")
        return self


class StrategyEvaluator:
    def __init__(self):
        self.config = EvaluationConfig()

    def _index(self, attempts):
        indexed = {}
        evidence = set()
        for value in attempts:
            attempt = EvaluationAttempt.model_validate(value)
            key = (attempt.case_id, attempt.repetition)
            if (attempt.case_id not in self.config.expected or key in indexed
                    or attempt.evidence_id in evidence):
                raise ValueError("Unknown or duplicate evaluation attempt")
            indexed[key] = attempt
            evidence.add(attempt.evidence_id)
        expected = {(case, repetition) for case in self.config.expected
                    for repetition in range(1, self.config.repetitions + 1)}
        if set(indexed) != expected:
            raise ValueError("Incomplete evaluation")
        return indexed

    def _counts(self, attempts):
        counts = dict.fromkeys(self.config.expected, 0)
        for attempt in attempts.values():
            outcome = attempt.outcome
            success, summary = self.config.expected[attempt.case_id]
            if (outcome is not None and outcome.success is success
                    and outcome.summary == summary and not outcome.file_changes
                    and not outcome.observations and not outcome.commit_message):
                counts[attempt.case_id] += 1
        return counts

    def compare(self, baseline, candidate):
        """Require complete, distinct evidence references; caller verifies artifacts/settings."""
        try:
            baseline = self._index(baseline)
            candidate = self._index(candidate)
            if ({a.evidence_id for a in baseline.values()}
                    & {a.evidence_id for a in candidate.values()}):
                raise ValueError("Baseline and candidate must have distinct evidence")
        except (ValueError, TypeError):
            return {"decision": "INCONCLUSIVE"}
        before, after = self._counts(baseline), self._counts(candidate)
        gain = sum(after.values()) - sum(before.values())
        regression = (any(after[c] < self.config.repetitions for c in self.config.critical_cases)
                      or any(after[c] < before[c] for c in before)
                      or any(a.outcome is not None and a.outcome.file_changes
                             for a in candidate.values()))
        decision = ("REGRESSION" if regression else
                    "IMPROVEMENT" if gain >= self.config.improvement_count else "NO_CHANGE")
        total = len(self.config.expected) * self.config.repetitions
        return {"decision": decision, "baseline": before, "candidate": after,
                "baseline_score": sum(before.values()) / total,
                "candidate_score": sum(after.values()) / total,
                "delta_percentage_points": gain * 100 / total}
