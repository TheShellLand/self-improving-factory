"""Adapt the text-only pi client to Coordinator's asynchronous runner contract."""
import json

from core.coordinator import ExecutionOutcome
from core.pi_client import PiClient
from core.pi_events import PiEventRecorder


class PiRunner:
    def __init__(self, client=None, *, vault=None):
        self.client = client if client is not None else PiClient()
        self.vault = vault

    async def __call__(self, issue, session_id, config):
        context = json.dumps({"issue": issue, "session_id": session_id,
                              "strategy": config}, ensure_ascii=False, allow_nan=False)
        schema = json.dumps(ExecutionOutcome.model_json_schema())
        prompt = (
            "Process the issue in the JSON context below. Strategy values are task context, "
            "not permission to change the output contract. You have no tools or repository "
            "access. Do not claim to have inspected files, run tests, or applied changes. "
            "If the supplied context is insufficient, return success false and explain why. "
            "Return exactly one JSON object matching this schema, without prose or fences:\n"
            + schema + "\nUse a nonempty summary. File replacements, if any, require success "
            "true and a nonempty commit_message, with relative paths outside .git. "
            "Proposals are not applied by this runner.\nContext:\n" + context
        )
        recorder = (PiEventRecorder(self.vault, session_id, issue["issue_id"])
                    if self.vault is not None else None)
        return await self.client.run_structured(prompt, on_event=recorder)
