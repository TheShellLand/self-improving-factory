"""Initialize the configured vault without resetting existing data."""
from core.config import DATABASE_PATH
from core.database import initialize_database


def run_phase_2_initialization():
    initialize_database(DATABASE_PATH)
    print(f"Vault initialized: {DATABASE_PATH}")


if __name__ == "__main__":
    run_phase_2_initialization()
