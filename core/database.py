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
        if connection.execute("PRAGMA user_version").fetchone()[0] > 1:
            raise ValueError("Database schema is newer than this application")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("BEGIN IMMEDIATE")
        # Upgrade the original issue status constraint while retaining every row.
        definition = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'issues'").fetchone()[0]
        if "'CLOSED'" not in definition:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(issues)")}
            expected = {"issue_id", "title", "content", "status", "priority_score", "viewport_snapshot"}
            if columns != expected:
                raise ValueError("Unsupported issues schema; explicit migration required")
            connection.execute("CREATE TABLE issues_v2 (issue_id TEXT PRIMARY KEY, title TEXT, "
                               "content TEXT, status TEXT CHECK(status IN ('OPEN', 'WAITING', "
                               "'IN PROGRESS', 'REJECTED', 'CLOSED', 'FAILED')), "
                               "priority_score REAL DEFAULT 0.5, viewport_snapshot TEXT)")
            connection.execute("INSERT INTO issues_v2 SELECT issue_id, title, content, status, "
                               "priority_score, viewport_snapshot FROM issues")
            connection.execute("DROP TABLE issues")
            connection.execute("ALTER TABLE issues_v2 RENAME TO issues")
        connection.execute("CREATE TABLE IF NOT EXISTS issue_runs ("
                           "session_id TEXT PRIMARY KEY REFERENCES agent_sessions(session_id), "
                           "issue_id TEXT NOT NULL REFERENCES issues(issue_id))")
        connection.execute("CREATE TABLE IF NOT EXISTS commit_proposals ("
                           "proposal_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, "
                           "status TEXT NOT NULL, commit_sha TEXT, error TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS reflection_sources ("
                           "source_id TEXT PRIMARY KEY, version_number INTEGER NOT NULL)")
        connection.execute("PRAGMA user_version = 1")
