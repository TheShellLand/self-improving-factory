"""Verify knowledge persistence using a disposable database."""
from pathlib import Path
from tempfile import TemporaryDirectory
from core.database import initialize_database
from core.evolution import EvolutionEngine
from core.hotloader import HotLoaderModule


def log_kernel_update():
    with TemporaryDirectory() as directory:
        database = Path(directory) / "vault.db"
        initialize_database(database)
        EvolutionEngine(database)._commit_knowledge_update("Integrity check", {"gatekeeper_auth": 1.0})
        loader = HotLoaderModule(database)
        assert loader.sync_once() == 1
        assert loader.get_active_config() == {"gatekeeper_auth": 1.0}
    print("Knowledge persistence verified in a temporary database.")


if __name__ == "__main__":
    log_kernel_update()
