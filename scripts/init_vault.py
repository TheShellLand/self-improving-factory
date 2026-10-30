"""Initialize the configured vault without resetting existing data."""
from core.database import DatabaseClient


class VaultInitializer:
    def __init__(self, client=None):
        self.client = client if client is not None else DatabaseClient()

    def run(self):
        self.client.initialize()
        print(f"Vault initialized: {self.client.config.database_path}")


def run_phase_2_initialization():
    VaultInitializer().run()


if __name__ == "__main__":
    run_phase_2_initialization()
