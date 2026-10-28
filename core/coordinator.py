"""One-at-a-time issue processing with explicit execution and reflection adapters.

This module does not select a model, run a daemon, or interpret pi RPC events.
The host supplies an async runner returning ExecutionOutcome.
"""
from pydantic import BaseModel, ConfigDict, Field

from core.observer import ObserverModule
from core.signals import SignalPulse


class FileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1)
    content: str


class ExecutionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool = Field(strict=True)
    summary: str
    observations: list[dict] = Field(default_factory=list)
    file_changes: list[FileChange] = Field(default_factory=list)
    commit_message: str = ""


class Coordinator:
    def __init__(self, vault, runner, evolution, hotloader, commit_service=None):
        self.vault = vault
        self.runner = runner
        self.evolution = evolution
        self.hotloader = hotloader
        self.commit_service = commit_service

    async def run_once(self):
        """Process at most one issue. Failed attempts remain visible, not requeued.

        Cancellation leaves the session RUNNING so another worker cannot overlap
        an execution that may still be alive. Recovery must reconcile it first.
        """
        claim = self.vault.claim_next()
        if claim is None:
            return None
        issue, session_id = claim
        try:
            self.hotloader.sync_once()
            outcome = ExecutionOutcome.model_validate(await self.runner(
                issue, session_id, self.hotloader.get_active_config()))
            observer = ObserverModule(self.vault)
            for payload in outcome.observations:
                observer.process_telemetry(SignalPulse(
                    source_agent="runner", action_type="OBSERVATION",
                    payload={**payload, "session_id": session_id}).model_dump())
            self.vault.record(SignalPulse(source_agent="runner", action_type="RESULT", payload={
                "session_id": session_id, "success": outcome.success, "summary": outcome.summary}))
            if outcome.success and outcome.file_changes:
                if self.commit_service is None:
                    raise RuntimeError("Code changes require the configured gatekeeper")
                self.commit_service.apply(session_id, outcome.commit_message,
                                          [change.model_dump() for change in outcome.file_changes])
            self.evolution.reflect_session(issue, session_id)
            self.hotloader.sync_once()
            self.vault.finish(session_id, outcome.success, outcome.summary)
        except Exception as error:
            self.vault.finish(session_id, False, str(error))
            raise
        return session_id
