"""Persist pi wire events without interpreting them as task success."""
from uuid import UUID

from core.signals import SignalPulse


class PiEventRecorder:
    def __init__(self, vault, session_id, issue_id):
        self.vault = vault
        self.session_id = str(UUID(session_id))
        self.issue_id = str(UUID(issue_id))
        self.sequence = 0

    def __call__(self, event):
        if not isinstance(event, dict) or not isinstance(event.get("type"), str) or not event["type"]:
            raise ValueError("Expected a typed pi event")
        if event["type"] == "response":
            raise ValueError("RPC responses are not session events")
        sequence = self.sequence + 1
        self.vault.record(SignalPulse(
            source_agent="pi", action_type="OBSERVATION",
            payload={"session_id": self.session_id, "issue_id": self.issue_id,
                     "sequence": sequence, "event": event},
            metadata={"protocol": "pi-rpc"}))
        self.sequence = sequence
