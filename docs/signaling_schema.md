# SASIAS RPC & Signaling Contract - v1.0

## Purpose
To provide a strictly typed communication protocol for all distributed subagents interacting with the Parent Orchestrator via `--mode rpc`. This ensures that every 'pulse' or observation is consistent enough for automated reflection loops (Critic/Evolution Engine).

## Base Message Structure (`Signal`)
Every signal must be serializable into JSON and include these mandatory keys:

- `signal_id`: UUIDv4 string.
- `timestamp`: ISO8601 UTC float/string.
- `source_agent`: Name of the sandbox agent ID.
- `action_type`: Enum [INPUT | ACTION_START | OBSERVATION | RESULT | REFLECTION].
- `payload`: Dictionary containing specifics to the action type.
- `metadata`: 
    - `subagent_context`: { "shell": "bash", "executor": "docker" }
    - `viewport_standard`: { "w": 1920, "h": 1080 }

## Specific Payloads

### Input (User Pulse)
Captured via Chat Bridge:
```json
{
  "user_id": "string",
  "command": "raw text input from user",
  "client_perspective": {
    "width": integer,
    "height": integer,
    "session_depth": integer
  }
}
```

### Observation (Visual/Pulse)
Sent by Subagents during execution:
```json
{
  "step_index": integer,
  "status": ["success", "failure", "pending"],
  "visual_state": {
    "base64_data": "...",
    "viewport": {"w": 1920, "h": 1080},
    "description": "string describing current UI focus"
  },
  "stdout_chunk": "bytes or string snippet"
}
```

### Result (Signal Closure)
Final signal emitted at sandbox termination:
```json
{
  "exit_code": integer,
  "summary": "brief summary of subtask success/fail",
  "artifacts\": [\"list of modified files and their diff hashes\"] }
```

## Quality Constraints
-   **Latency**: Signal pulses must be acknowledged by Parent within <50ms.
-   **Auditability**: Every `signal_id` from a Subagent MUST appear in the 'trace_signals' table before it can modify any project state via an Executor call.
