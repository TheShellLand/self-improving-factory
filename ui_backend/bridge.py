"""HTTP access to the audit trail and issue queue."""
from contextlib import asynccontextmanager
import json
import uuid
from fastapi import FastAPI
from pydantic import BaseModel, Field
from core.config import DATABASE_PATH
from core.database import connect, initialize_database


class BugReport(BaseModel):
    title: str = Field(min_length=1)
    description: str
    path_depth: int = Field(default=0, ge=0)
    client_viewport: dict[str, int] = Field(default_factory=dict)
    context_blob: dict = Field(default_factory=dict)
    priority: float = Field(default=10.0, allow_inf_nan=False)


def create_app(database_path=DATABASE_PATH):
    @asynccontextmanager
    async def lifespan(app):
        initialize_database(database_path)
        yield

    application = FastAPI(lifespan=lifespan)

    @application.get("/api/audit-trail")
    def get_audit_trail():
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM trace_signals ORDER BY timestamp DESC LIMIT 100")]

    @application.post("/api/report-bug")
    def report_bug(data: BugReport):
        issue_id = str(uuid.uuid4())
        with connect(database_path) as connection:
            connection.execute(
                "INSERT INTO issues (issue_id, title, content, status, priority_score, "
                "viewport_snapshot) VALUES (?, ?, ?, 'OPEN', ?, ?)",
                (issue_id, data.title, data.model_dump_json(), data.priority,
                 json.dumps(data.client_viewport)),
            )
        return {"status": "recorded", "issue_id": issue_id}

    @application.get("/api/issues")
    def list_priority_issues():
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM issues WHERE status IN ('OPEN', 'WAITING') "
                "ORDER BY priority_score DESC LIMIT 20")]

    return application


app = create_app()
