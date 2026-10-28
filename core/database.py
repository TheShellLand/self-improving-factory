"""SQLite connections with explicit transaction and resource lifetimes."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from core.config import DATABASE_PATH, SCHEMA_PATH


@contextmanager
def connect(database_path=DATABASE_PATH):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path=DATABASE_PATH):
    """Create missing tables without deleting existing records."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
