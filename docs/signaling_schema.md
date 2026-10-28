# Internal signal contract

`core.signals.SignalPulse` is the source of truth. This is an internal event
envelope, not a claim of compatibility with pi's RPC wire messages.

| Field | Contract |
| --- | --- |
| `signal_id` | UUID string, generated when omitted |
| `timestamp` | Finite nonnegative Unix seconds |
| `source_agent` | Nonempty component/agent name |
| `action_type` | INPUT, ACTION_START, OBSERVATION, RESULT, REFLECTION |
| `payload` | JSON object; session events include `session_id` |
| `metadata` | JSON object for additional context |
| `viewport` | Positive integer width/height; defaults to 1920/1080 |
| `visual_state` | Optional JSON object; no image analysis is implied |

Example execution result:

```json
{
  "signal_id": "cf974c42-d37f-469d-a185-af55b813fe32",
  "timestamp": 1790000000.0,
  "source_agent": "runner",
  "action_type": "RESULT",
  "payload": {"session_id": "session-1", "success": true, "summary": "Checks passed"},
  "metadata": {},
  "viewport": {"width": 1920, "height": 1080},
  "visual_state": null
}
```

The vault validates before insertion. Viewport and visual data are stored inside
the existing SQL metadata column. Duplicate signal IDs fail rather than silently
replacing evidence. Payloads must be JSON serializable without NaN/Infinity.
Legacy initialization rows predate the UUID contract and remain unchanged.

Runner, gatekeeper, and coordinator RESULT events have distinct `source_agent`
values: execution completion, Git outcome, and final pipeline outcome are separate.
No acknowledgment latency guarantee has yet been measured.
