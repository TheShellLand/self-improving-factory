"""HTTP access to the audit trail and issue queue."""
from contextlib import asynccontextmanager
from typing import Literal
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from core.config import DATABASE_PATH
from core.database import connect, initialize_database
from core.signals import Viewport
from core.vault import Vault
from core.recovery import RecoveryService


class BugReport(BaseModel):
    title: str = Field(min_length=1)
    description: str
    path_depth: int = Field(default=0, ge=0)
    client_viewport: Viewport = Field(default_factory=Viewport)
    context_blob: dict = Field(default_factory=dict)
    priority: float = Field(default=10.0, allow_inf_nan=False)


class Vote(BaseModel):
    delta: Literal[-1, 1]


class RecoveryRequest(BaseModel):
    reason: str = Field(min_length=1)


class ProposalRecovery(RecoveryRequest):
    commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


def create_app(database_path=DATABASE_PATH, *, recovery_service=None, recovery_actor=None):
    vault = Vault(database_path)
    recovery = recovery_service or RecoveryService(database_path)
    if Path(recovery.db_path).resolve() != Path(database_path).resolve():
        raise ValueError("Recovery service must use the application's database")

    def operator(request: Request):
        if recovery_actor is None or recovery_service is None:
            raise HTTPException(status_code=503, detail="Recovery mutations are not configured")
        actor = recovery_actor(request)
        if not isinstance(actor, str) or not actor.strip():
            raise HTTPException(status_code=403, detail="Recovery operator authorization required")
        return actor

    def recover(operation, *args, **kwargs):
        try:
            operation(*args, **kwargs)
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"status": "recorded"}
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

    @application.get("/api/recovery")
    def pending_recovery():
        return recovery.pending()

    @application.post("/api/sessions/{session_id}/recover")
    def recover_session(session_id: str, data: RecoveryRequest, actor: str = Depends(operator)):
        return recover(recovery.fail_session, session_id, actor=actor, reason=data.reason)

    @application.post("/api/issues/{issue_id}/retry")
    def retry_issue(issue_id: str, data: RecoveryRequest, actor: str = Depends(operator)):
        return recover(recovery.retry_issue, issue_id, actor=actor, reason=data.reason)

    @application.post("/api/proposals/{proposal_id}/recover")
    def recover_proposal(proposal_id: str, data: ProposalRecovery, actor: str = Depends(operator)):
        return recover(recovery.resolve_proposal, proposal_id, actor=actor,
                       reason=data.reason, commit_sha=data.commit_sha)

    return application


app = create_app()
