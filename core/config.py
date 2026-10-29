"""Paths shared by the API, command line tools, and runtime."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = Path(os.environ.get("SIF_DB_PATH", PROJECT_ROOT / "history_vault.db"))
SCHEMA_PATH = PROJECT_ROOT / "schema" / "history_vault_schema.sql"
