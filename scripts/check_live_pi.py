"""Run one harmless live model issue and retain an isolated audit vault."""
import argparse
import asyncio
import json
from pathlib import Path
import time

from core.coordinator import Coordinator
from core.database import initialize_database
from core.evolution import EvolutionEngine
from core.hotloader import HotLoaderModule
from core.pi_client import PiClient
from core.pi_runner import PiRunner
from core.vault import Vault


class LivePiCheckConfig:
    def __init__(self, directory):
        self.directory = Path(directory)


class LivePiCheck:
    def __init__(self, config):
        self.config = config

    async def run(self):
        root = self.config.directory
        root.mkdir(parents=True, exist_ok=False)
        database = root / "vault.db"
        initialize_database(database)
        vault = Vault(database)
        vault.create_issue({"title": "Live arithmetic check", "description":
            "Compute 17 + 25. Return success true and summary exactly 42. "
            "Return empty observations and file_changes arrays and an empty commit_message."})
        client = PiClient()
        coordinator = Coordinator(vault, PiRunner(client, vault=vault),
                                  EvolutionEngine(database, lambda *_: None),
                                  HotLoaderModule(database))
        started = time.monotonic()
        try:
            await coordinator.run_once()
        finally:
            with vault.database.connect() as connection:
                signals = [dict(row) for row in connection.execute("SELECT * FROM trace_signals ORDER BY rowid")]
                sessions = [dict(row) for row in connection.execute("SELECT * FROM agent_sessions")]
            for signal in signals:
                signal["payload"] = json.loads(signal["payload"])
                signal["metadata"] = json.loads(signal["metadata"])
            evidence = {"duration_seconds": time.monotonic() - started,
                        "issues": vault.list_issues(), "sessions": sessions, "signals": signals}
            (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        session = sessions[0]
        events = [s for s in signals if s["source_agent"] == "pi"]
        if (session["status"] != "COMPLETED" or session["execution_summary"] != "42"
                or not events or not any(s["payload"]["event"].get("type") == "agent_settled"
                                        for s in events)):
            raise RuntimeError("Live issue did not meet verification criteria; inspect retained evidence")
        print(json.dumps({"session_id": session["session_id"], "events": len(events),
                          "summary": session["execution_summary"], "directory": str(root),
                          "duration_seconds": evidence["duration_seconds"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="New directory for retained evidence")
    asyncio.run(LivePiCheck(LivePiCheckConfig(parser.parse_args().directory)).run())
