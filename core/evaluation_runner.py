"""Collect isolated text-suite attempts without reflection or code promotion."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from core.database import initialize_database
from core.evaluation import EvaluationConfig, StrategyEvaluator
from core.evaluation_provenance import EvaluationProvenanceConfig
from core.pi_client import PiClient, PiAgentError
from core.pi_runner import PiRunner
from core.strategy import StrategyProposal
from core.vault import Vault


class EvaluationRunner:
    def __init__(self, client=None, *, provenance=None):
        self.client = client if client is not None else PiClient()
        self.config = EvaluationConfig()
        self.provenance = (EvaluationProvenanceConfig.model_validate(provenance)
                           if provenance is not None else None)

    @staticmethod
    def _write(path, value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    async def run(self, output_directory, baseline, candidate):
        """Candidate is the complete merged strategy, not a patch. Never overwrite a run."""
        strategies = {name: StrategyProposal(logic_description="Evaluation snapshot", prompt_weights=value)
                      .model_dump()["prompt_weights"]
                      for name, value in (("baseline", baseline), ("candidate", candidate))}
        if self.provenance is None:
            raise ValueError("Evaluation provenance is required")
        execution = self.provenance.capture(self.client)
        root = Path(output_directory)
        root.mkdir(parents=True, exist_ok=False)
        manifest = {"suite": "text-v1", "status": "RUNNING", "strategies": strategies,
                    "execution": execution,
                    "strategy_hashes": {name: hashlib.sha256(json.dumps(value, sort_keys=True,
                        allow_nan=False).encode()).hexdigest() for name, value in strategies.items()},
                    "attempts": {"baseline": [], "candidate": []}}
        self._write(root / "manifest.json", manifest)
        try:
            for repetition in range(1, self.config.repetitions + 1):
                order = ("baseline", "candidate") if repetition % 2 else ("candidate", "baseline")
                for case, description in self.config.descriptions.items():
                    for name in order:
                        if self.provenance.capture(self.client) != execution:
                            raise ValueError("Evaluation execution settings changed")
                        identifier = f"{name}-{case}-{repetition}"
                        db = root / f"{identifier}.db"
                        initialize_database(db)
                        vault = Vault(db)
                        vault.create_issue({"title": case, "description": description + " " + self.config.suffix})
                        issue, session = vault.claim_next()
                        record = {"case_id": case, "repetition": repetition, "evidence_id": identifier}
                        evidence = {"session_id": session, "issue_id": issue["issue_id"],
                                    "database": db.name, "strategy_hash": manifest["strategy_hashes"][name],
                                    "started_at": time.time()}
                        started = time.monotonic()
                        try:
                            outcome = await PiRunner(self.client, vault=vault)(
                                issue, session, deepcopy(strategies[name]))
                            if self.provenance.capture(self.client) != execution:
                                raise ValueError("Evaluation execution settings changed")
                            record["outcome"] = outcome.model_dump()
                            vault.finish(session, outcome.success, outcome.summary)
                        except PiAgentError:
                            record["failure"] = "PiAgentError"
                            vault.finish(session, False, "Evaluation client failure")
                        except asyncio.CancelledError:
                            record["failure"] = "CancelledError"
                            raise
                        finally:
                            evidence.update(record)
                            evidence["ended_at"] = time.time()
                            evidence["duration_seconds"] = time.monotonic() - started
                            self._write(root / f"{identifier}.json", evidence)
                        manifest["attempts"][name].append(record)
                        self._write(root / "manifest.json", manifest)
                        if self.provenance.capture(self.client) != execution:
                            raise ValueError("Evaluation execution settings changed")
            manifest["report"] = StrategyEvaluator().compare(**manifest["attempts"])
            manifest["artifacts"] = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.iterdir() if path.suffix in (".db", ".json")
                and path.name != "manifest.json"}
            manifest["status"] = "COMPLETED"
        except BaseException:
            manifest["status"] = "INCOMPLETE"
            manifest["report"] = {"decision": "INCONCLUSIVE"}
            raise
        finally:
            self._write(root / "manifest.json", manifest)
        return manifest["report"]
