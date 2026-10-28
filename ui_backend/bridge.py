"""HTTP access to the audit trail and issue queue."""
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from core.config import DATABASE_PATH
from core.database import connect, initialize_database
from core.signals import Viewport
from core.vault import Vault


class BugReport(BaseModel):
    title: str = Field(min_length=1)
    description: str
    path_depth: int = Field(default=0, ge=0)
    client_viewport: Viewport = Field(default_factory=Viewport)
    context_blob: dict = Field(default_factory=dict)
    priority: float = Field(default=10.0, allow_inf_nan=False)


class Vote(BaseModel):
    delta: Literal[-1, 1]


def create_app(database_path=DATABASE_PATH):
    vault = Vault(database_path)
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
        issue_id = vault.create_issue(data.model_dump())
        return {"status": "recorded", "issue_id": issue_id}

    @application.get("/api/issues")
    def list_priority_issues():
        return vault.list_issues()

    @application.post("/api/issues/{issue_id}/vote")
    def vote(issue_id: str, data: Vote):
        try:
            vault.vote(issue_id, data.delta)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"status": "recorded"}

    @application.get("/api/sessions")
    def sessions():
        with connect(database_path) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM agent_sessions ORDER BY start_time DESC LIMIT 100")]

    return application


app = create_app()
