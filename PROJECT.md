# Self-improving factory (SIF): specification and phase progress

## Objective

Build an autonomous agent system that learns from execution outcomes, updates
its strategies, and proposes improvements to its own source code. Human input,
issue prioritization, and observation should ultimately happen through a web UI.
The system should process one model task at a time and preserve evidence for
every change. Terminal commands remain appropriate for development and setup.

## Architectural decisions

- **Reuse automonisaur first:** inspect its existing functions and classes before
  adding an implementation. Import suitable functionality directly. When an
  existing helper cannot preserve SIF's behavior, document the reason for a local
  implementation. Prefer objects, separate configuration into `*Config` classes,
  and put connections to external systems in `*Client` classes.
- **Environment credentials:** tokens, keys, secrets, and passwords must come
  from environment variables, never source-code defaults. Config classes own
  retrieval. Preserve secret values exactly; use `os.getenv` for credentials
  rather than helpers that trim strings or coerce booleans. No credential-backed
  model client is implemented yet.
- **Distributed sandboxes:** a parent host manages sibling Docker containers.
  Only the parent needs Docker daemon access; child runners do not receive its
  socket or write access to the parent checkout.
- **Agent protocol:** the planned agent adapter uses `pi --mode rpc`. The internal
  signal model is separate from that wire protocol. Live pi integration is pending.
- **Git gatekeeper:** agents submit structured file replacements and commit
  messages. The parent applies them through `GatekeeperVault` and GitPython.
  This role is required for autonomous source changes; it is not an optional
  logging utility. No agent-supplied shell command performs parent Git operations.
- **SQLite vault:** stores issues, sessions, signals, commit outcomes, and strategy
  updates. Git stores code history; SQLite links changes to execution context.
- **Perspective:** preserve browser viewport data; default sandbox viewport is
  1920 × 1080. Visual observations are optional and do not imply image analysis.
- **Learning:** current updates are JSON configuration/prompt values. They do not
  train or modify model parameters.

## How to read progress

Each phase lists what works and what still needs to be built or tested.
Passing local tests does not mean that a phase works with a live agent.
Tests using injected providers check local behavior, not live model performance.

## Automonisaur refactor

The first refactor introduces `DatabaseConfig`, `DockerConfig`, `GitConfig`,
`ApiConfig`, and `HotLoaderConfig`, alongside the existing `SandboxConfig`.
`DatabaseClient` owns SQLite connections and migrations; all database services
use it. `DockerClient` owns container execution and cleanup. `GitClient` owns
the existing gatekeeper behavior. `ApiApplication`, `ApiServer`, and
`VaultInitializer` own application setup and lifecycle.

Environment defaults reuse automonisaur's `environ` helper. The dependency follows
upstream's default branch. The inspected and tested revision was
`1a300fd962f0dd9a81ac04f2f02b530e6cdc10bb`. That revision has no
SQLite, Docker, or Git client. Its subprocess `Run` helper calls `communicate()`
without a timeout, so the Docker client retains bounded subprocess handling.
See `docs/automonisaur.md` for the reuse decisions and development rules.

Existing names `GatekeeperVault` and `DockerOrchestrationEngine`, plus database
and application factory functions, remain compatibility entry points.
This refactor does not implement the unfinished live-agent features below.

### Phase 0 — Project setup and specification

**Refactor verified.** Dependency manifests, runnable API entry point, Docker
image, portable shell helpers, and setup instructions exist. Host paths are
resolved relative to this checkout instead of assuming `/root/brain`.

Verification: build the image with `bash build.sh`; follow `README.md` for local
setup and test commands. Keep this phase checklist aligned with verified behavior.

### Phase 1 — Signals and component boundaries

**Internal contract implemented.** `core/signals.py` defines validated UUIDs,
Unix timestamps, action types, JSON payloads, positive viewport dimensions, and
optional visual state. The observer validates telemetry and can persist it.
`core/executor.py` delegates execution instead of returning a fabricated ID.

Verification: `tests/test_signaling_contract.py`, `tests/test_vault.py`, and
`tests/test_executor.py`.

Still needed: map actual pi RPC events to this contract and measure latency.
The previous sub-50 ms acknowledgment claim was never established by these tests.

### Phase 2 — Vault and issue lifecycle

**Foundation implemented.** Connections close explicitly; initialization preserves
data. A versioned upgrade extends the original issue-status constraint. The
vault records issue creation and its INPUT signal in one transaction. Priority
voting, exclusive issue claims, session outcomes, and terminal issue states exist.

Only one RUNNING session may be claimed through the vault at a time. A crash or
cancellation leaves that claim visible; it is not automatically retried.
Unresolved PREPARED Git proposals also block new claims. Recovery can fail a
stopped session and explicitly requeue a failed issue while retaining every
attempt. It refuses retries when any attempt has applied or unresolved Git work.

Verification: `tests/test_vault.py` covers original-schema upgrades, retained
records, transactional rollback, concurrent claims, and terminal transitions.

Recovery verification: `tests/test_recovery.py` covers stopped-worker checks,
audit rollback, explicit retries, and schema-v1 upgrades to evidence storage.

Still needed: operational backup/restore and a production execution-stop
verifier. The migration supports the repository's original schema, not arbitrary
external schema variants. Initialization does not change the checked-in DB until
explicitly invoked or the API is started against it.

### Phase 3 — Docker orchestration

**Lifecycle refactored.** Explicit argument lists, viewport settings, timeout
handling, captured output, exit codes, and cleanup retries share one execution
path. Async callers use a worker thread around bounded synchronous execution.

Verification: `tests/test_orchestration.py` covers success, failure, missing Docker,
and timeout cleanup; `tests/test_executor.py` checks dispatch and argument handling.
Docker image/API smoke tests exercise the built runtime separately.

Still needed: agent image containing pi, bidirectional RPC, streaming output
with bounds, and cancellation that confirms child termination. The current image
contains the API runtime, Python, Git, and Bash; it has no pi or Docker CLI.

### Phase 4 — Gatekeeper and code audit

**Gatekeeper retained and integrated.** New repositories require `create=True`.
Proposals require a clean checkout and validated paths. Ordinary failures restore
files and index state. `CommitService` records PREPARED intent before Git writes,
then APPLIED/FAILED with the resulting commit hash and session ID.

Git and SQLite do not share an atomic transaction. An interrupted PREPARED entry
blocks another proposal until an operator reconciles Git and the audit record.
Successful commits are not undone merely because later reflection fails.
New proposals retain their repository, branch, original revision, message, and
content hashes. `RecoveryService` uses this evidence to verify an applied commit
or unchanged checkout without changing Git. Dirty, unrelated, or ambiguous state
remains unresolved; older proposals without evidence require manual investigation.

Verification: `tests/test_gatekeeper.py` and `tests/test_coordinator.py`, including
rejected proposals, rollback, symlink/path checks, pending-intent blocking, and
commit-to-session linkage.

Verification also includes crash injection before and after Git writes,
content mismatch rejection, and no-op reconciliation in `tests/test_recovery.py`.

Still needed: production operator authentication/execution-stop adapters and
isolation against concurrent filesystem writers. The gatekeeper is not an OS
security sandbox. Recovery requires exclusive access to the checkout.

### Phase 5 — Human interface and audit API

**Backend refactored.** Validated bug reports, viewport capture, issue listing,
priority votes, session listing, and audit reads use the shared vault service.
Issue listing includes terminal states so outcomes remain visible.
The API exposes pending recovery inspection and explicit proposal/session recovery
and issue retry routes. Mutations return 503 until the host supplies a recovery
service and an operator authorization callback; no user-supplied actor is trusted.

Verification: `tests/test_ui_bridge.py` covers persistence, validation, ordering,
votes, and recorded input signals. FastAPI exposes the interface at `/docs`.

Still needed: the browser dashboard/chat/report form, authentication and
deployment policy, explicit human selection controls, and a recovery UI.
The empty frontend files are not a completed UI.

### Phase 6 — Reflection and configuration loading

**Provider boundary implemented.** A caller-supplied reflection provider receives
the issue and exact-session evidence. Session-scoped updates are deduplicated
and versioned transactionally with a REFLECTION signal. The loader consumes
updates by insertion ID, so equal timestamps do not skip records.

Verification: `tests/test_convergence.py` and `tests/test_coordinator.py` cover
persistence, deduplication, exact session matching, and configuration loading.

Still needed: a real analysis provider, drift evaluation, strategy quality
measurement, and handling invalid legacy updates. An invalid update stops the
loader at that record until corrected. The legacy batch reflection API leaves
deduplication to its caller; the coordinator uses session-scoped reflection.

### Phase 7 — Convergence and autonomy

**Coordinator implemented; live autonomy still unfinished.** `Coordinator.run_once()`
claims one issue, loads configuration, invokes an injected async runner, records
observations/results, applies successful code proposals through the gatekeeper,
reflects, reloads configuration, and closes the session/issue. Failed executions
never apply code proposals. Exceptions mark the attempt FAILED; cancellation
retains the RUNNING claim for reconciliation.

Verification: `tests/test_coordinator.py` exercises the entire flow with a
deterministic runner, a real temporary SQLite database, and a real temporary Git
repository. It also tests failure, cancellation, and missing-gatekeeper behavior.

Still needed: production runner/model configuration, pi RPC adapter, durable
scheduling, production recovery adapters, human controls, and a live zero-terminal end-to-end run.
The coordinator is a library boundary, not an automatically started daemon.

## Verification and next work

Run the complete regression suite with the configured interpreter:

```sh
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python -m scripts.test_vault_write
bash build.sh
```

Tests use temporary state and mock Docker execution. Build and HTTP smoke checks
are separate. No result in this document establishes live model performance.

Next work should implement the pi adapter against its real protocol, wire the
execution-stop verifier and operator authentication, then connect human controls
and durable scheduling. Preserve
the gatekeeper boundary throughout. Detailed contracts and setup live in
`docs/signaling_schema.md`, `docs/signaling_flow_map.md`, and `docs/runtime_guide.md`.
See `docs/recovery.md` for the recovery service contract and API workflow.
