"""HTTP access to the audit trail and issue queue."""
from contextlib import asynccontextmanager
from typing import Literal
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from core.database import DatabaseClient
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


class ApiApplication:
    """Own the API's clients, lifecycle, and route handlers."""

    def __init__(self, database_path=None, *, recovery_service=None, recovery_actor=None):
        self.database = DatabaseClient(database_path)
        database_path = self.database.config.database_path
        self.vault = Vault(database_path)
        self.recovery = recovery_service or RecoveryService(database_path)
        self.recovery_actor = recovery_actor
        self.recovery_enabled = recovery_service is not None and recovery_actor is not None
        if Path(self.recovery.db_path).resolve() != database_path.resolve():
            raise ValueError("Recovery service must use the application's database")
        self.app = FastAPI(lifespan=self.lifespan)
        self._register_routes()

    @asynccontextmanager
    async def lifespan(self, app):
        self.database.initialize()
        yield

    def operator(self, request: Request):
        if not self.recovery_enabled:
            raise HTTPException(status_code=503, detail="Recovery mutations are not configured")
        actor = self.recovery_actor(request)
        if not isinstance(actor, str) or not actor.strip():
            raise HTTPException(status_code=403, detail="Recovery operator authorization required")
        return actor

    @staticmethod
    def recover(operation, *args, **kwargs):
        try:
            operation(*args, **kwargs)
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"status": "recorded"}

    def get_audit_trail(self):
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM trace_signals ORDER BY timestamp DESC LIMIT 100")]

    def report_bug(self, data: BugReport):
        issue_id = self.vault.create_issue(data.model_dump())
        return {"status": "recorded", "issue_id": issue_id}

    def list_priority_issues(self):
        return self.vault.list_issues()

    def vote(self, issue_id: str, data: Vote):
        try:
            self.vault.vote(issue_id, data.delta)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"status": "recorded"}

    def sessions(self):
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM agent_sessions ORDER BY start_time DESC LIMIT 100")]

    def pending_recovery(self):
        return self.recovery.pending()

    def _register_routes(self):
        self.app.add_api_route("/api/audit-trail", self.get_audit_trail, methods=["GET"])
        self.app.add_api_route("/api/report-bug", self.report_bug, methods=["POST"])
        self.app.add_api_route("/api/issues", self.list_priority_issues, methods=["GET"])
        self.app.add_api_route("/api/issues/{issue_id}/vote", self.vote, methods=["POST"])
        self.app.add_api_route("/api/sessions", self.sessions, methods=["GET"])
        self.app.add_api_route("/api/recovery", self.pending_recovery, methods=["GET"])

        # FastAPI dependencies bind to this application's authorization callback.
        @self.app.post("/api/sessions/{session_id}/recover")
        def recover_session(session_id: str, data: RecoveryRequest, actor: str = Depends(self.operator)):
            return self.recover(self.recovery.fail_session, session_id, actor=actor, reason=data.reason)

        @self.app.post("/api/issues/{issue_id}/retry")
        def retry_issue(issue_id: str, data: RecoveryRequest, actor: str = Depends(self.operator)):
            return self.recover(self.recovery.retry_issue, issue_id, actor=actor, reason=data.reason)

        @self.app.post("/api/proposals/{proposal_id}/recover")
        def recover_proposal(proposal_id: str, data: ProposalRecovery, actor: str = Depends(self.operator)):
            return self.recover(self.recovery.resolve_proposal, proposal_id, actor=actor,
                                reason=data.reason, commit_sha=data.commit_sha)


def create_app(database_path=None, *, recovery_service=None, recovery_actor=None):
    """Compatibility factory for ASGI hosts and tests."""
    return ApiApplication(database_path, recovery_service=recovery_service,
                          recovery_actor=recovery_actor).app


app = create_app()
