"""Read-only consistency checks for completed evaluation artifacts."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from core.evaluation import StrategyEvaluator
from core.strategy import StrategyProposal


class EvaluationEvidenceClient:
    @staticmethod
    def _json(path):
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=StrategyProposal.unique_object)
        json.dumps(data, allow_nan=False)
        return data

    def verify(self, directory):
        try:
            return self._verify(Path(directory).resolve())
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            return {"decision": "INCONCLUSIVE"}

    def _verify(self, root):
        manifest = self._json(root / "manifest.json")
        if manifest["status"] != "COMPLETED" or manifest["suite"] != "text-v1":
            raise ValueError("Incomplete or unsupported evaluation")
        report = StrategyEvaluator().compare(**manifest["attempts"])
        if report["decision"] == "INCONCLUSIVE" or report != manifest["report"]:
            raise ValueError("Report mismatch")
        expected_files = set()
        sessions = set()
        for name in ("baseline", "candidate"):
            strategy_hash = hashlib.sha256(json.dumps(manifest["strategies"][name],
                sort_keys=True, allow_nan=False).encode()).hexdigest()
            if strategy_hash != manifest["strategy_hashes"][name]:
                raise ValueError("Strategy mismatch")
            for attempt in manifest["attempts"][name]:
                identifier = f"{name}-{attempt['case_id']}-{attempt['repetition']}"
                if attempt["evidence_id"] != identifier:
                    raise ValueError("Unexpected evidence path")
                for suffix in (".json", ".db"):
                    filename = identifier + suffix
                    expected_files.add(filename)
                    path = root / filename
                    if path.is_symlink() or not path.is_file():
                        raise ValueError("Missing or linked artifact")
                    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifacts"][filename]:
                        raise ValueError("Artifact hash mismatch")
                evidence = self._json(root / (identifier + ".json"))
                if any(evidence[key] != value for key, value in attempt.items()):
                    raise ValueError("Attempt mismatch")
                if evidence["strategy_hash"] != strategy_hash or evidence["database"] != identifier + ".db":
                    raise ValueError("Evidence linkage mismatch")
                session = evidence["session_id"]
                if session in sessions:
                    raise ValueError("Reused session")
                sessions.add(session)
                uri = (root / evidence["database"]).as_uri() + "?mode=ro"
                with closing(sqlite3.connect(uri, uri=True)) as connection:
                    row = connection.execute(
                        "SELECT r.issue_id, s.status, s.success, s.execution_summary "
                        "FROM issue_runs r JOIN agent_sessions s USING(session_id) WHERE r.session_id = ?",
                        (session,)).fetchone()
                    outcome = attempt.get("outcome")
                    success = outcome["success"] if outcome else False
                    summary = outcome["summary"] if outcome else "Evaluation client failure"
                    expected = (evidence["issue_id"], "COMPLETED" if success else "FAILED", int(success), summary)
                    if row != expected:
                        raise ValueError("Database result mismatch")
        if set(manifest["artifacts"]) != expected_files:
            raise ValueError("Unexpected artifact inventory")
        return report
