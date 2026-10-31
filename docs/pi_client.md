# pi RPC client

Use `await client.run_structured(prompt)` when the prompt requests one JSON
object matching `ExecutionOutcome`: boolean `success`, nonempty `summary`, and
optional `observations`, `file_changes`, and `commit_message`. It returns the
validated model or raises `PiAgentError`. File proposals require success and a
nonempty commit message; unsafe, duplicate, and overlapping paths are rejected.
Prose, code fences, duplicate JSON keys, and non-finite numbers are rejected.
The gatekeeper still owns filesystem/symlink checks; this parser neither applies
changes nor establishes their correctness. `PiRunner` supplies the coordinator adapter.

`PiClient` implements one operation per fresh pi process using strict JSONL on
stdin/stdout. It supports `get_state`, `get_available_models`, and `prompt`.
`run_inference()` returns `{"text": ...}` only after a successful final assistant
message and `agent_settled`; a command acknowledgment or `agent_end` is not enough.
An optional synchronous `on_event` callback receives session events as they arrive.
Keep callbacks short; do not log sensitive model output indiscriminately.

The implementation follows the RPC, JSON events, and CLI documentation bundled
with installed `@earendil-works/pi-coding-agent` 1.4.0. Versions without
`agent_settled` are not supported and will hit the deadline rather than report
premature success.

`PiAgentConfig` reads `SIF_PI_EXECUTABLE` (default `pi`), `SIF_MODEL`,
`SIF_PROVIDER`, and `SIF_TIMEOUT` (default 120 seconds). Model/provider options
are passed as actual CLI flags. Provider credentials are inherited unchanged
from the environment; no invented `PI_MODEL` or `PI_PROVIDER` variables are used.
Pi may also use its own configured authentication. This client does not manage
pi's stored credentials.

`SIF_PI_CLEANUP_TIMEOUT` defaults to 5 seconds and `SIF_PI_MAX_RECORD_BYTES`
defaults to 1048576 bytes per stdout record. Explicit constructor options override
environment settings. Timeouts must be finite and positive; the record limit must
be a positive integer. Executable, model, and provider values must be nonblank
strings without NUL characters. Leave optional model/provider variables unset
to use pi defaults. Configuration does not load `.env` files automatically.
`tests/test_pi_config.py` verifies these settings and exact credential inheritance.

Tools, extensions, skills, prompt templates, and themes are disabled. Each
operation uses a temporary working directory and disables session persistence.
This is a text-only host client, not a security sandbox or Docker runner.
It does not execute model file proposals or verify `/goal` completion.

Operations are serialized per client, stdout records are size-limited, stderr is
drained without retention, and deadlines or cancellation trigger process cleanup.
Shutdown closes stdin, then kills the direct child if it exceeds the cleanup
timeout. Container/process-tree termination belongs to Phase 9.

With pi installed on PATH, check transport without making a model request:

```sh
PYTHONPATH=. python -m scripts.check_pi
```

Example inside an async application:

```python
from core.pi_client import PiClient

result = await PiClient().run_inference("Reply with hello.")
```

Verification: 58 regression tests passed, including malformed records,
disconnects, rejected commands, provider error messages, aborted runs, deadlines,
cancellation, and missing executables. A real pi 1.4.0 `get_state` operation
succeeded in 0.294 seconds including process startup. This is transport timing,
not live model event latency. A live model issue and coordinator integration
are tracked separately in PROJECT.md.

To connect an existing coordinator, supply `runner=PiRunner(PiClient(config))`,
importing `PiRunner` from `core.pi_runner` and using a `PiAgentConfig` instance.
The async callable accepts the claimed issue, session ID, and active strategy
dictionary. It requests the `ExecutionOutcome` JSON contract and returns the
client's validated result. Strategy values enter the prompt as typed JSON; they
do not override executable, credentials, provider, or model settings.

The host still supplies vault, reflection, and hotloader dependencies. Proposals
still require the coordinator's gatekeeper service. This adapter does not start
a worker or provide repository context, event persistence, or goal iteration.
Tests exercise mocked inference with real SQLite; no live model run is claimed.
