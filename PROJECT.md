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

`[x]` means implemented and verified at the scope described; `[ ]` means work or
verification remains. Check off tasks only when tool results support completion.
Tasks in earlier phases that point to later phases track the same remaining work;
update both when that work is verified. Passing injected-provider tests does not
establish live agent performance. All phases follow the automonisaur reuse,
config/client, and environment-credential rules above.

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

## Phase tasks

### Phase 0 — Project setup and specification

- [x] Add dependency manifests and a runnable API entry point.
- [x] Build the API Docker image and verify its HTTP endpoint.
- [x] Make shell helpers and host paths portable across checkout locations.
- [x] Document local setup and verification commands in `README.md`.
- [x] Refactor settings into config classes and connections into client classes,
  reuse automonisaur's environment helper, and document reuse decisions.

Evidence: `tests/test_configuration.py`, successful `bash build.sh`, and the
container API smoke check. Keep setup instructions aligned with later changes.

### Phase 1 — Signals and component boundaries

- [x] Validate signal UUIDs, Unix timestamps, action types, JSON payloads,
  positive viewport dimensions, and optional visual state.
- [x] Validate and persist observer telemetry.
- [x] Delegate executor calls to real execution logic instead of fabricated IDs.
- [ ] Map actual pi RPC events to session-linked signals (Phase 8).
- [ ] Measure live event latency (Phase 8); the former sub-50 ms claim is unverified.

Evidence: `tests/test_signaling_contract.py`, `tests/test_vault.py`, and
`tests/test_executor.py`.

### Phase 2 — Vault and issue lifecycle

- [x] Close connections explicitly and initialize tables without resetting data.
- [x] Upgrade the original issue-status constraint through a versioned migration.
- [x] Record issue creation and its INPUT signal in one transaction.
- [x] Implement priority votes, exclusive issue claims, and terminal session/issue states.
- [x] Block new claims while a RUNNING session or PREPARED proposal remains unresolved.
- [x] Preserve interrupted attempts and require explicit recovery and retry.
- [x] Reject retries when an attempt has applied or unresolved Git work.
- [ ] Connect a production execution-stop verifier (Phase 14).
- [ ] Implement and exercise backup/restore procedures (Phase 14).

Evidence: `tests/test_vault.py` and `tests/test_recovery.py`, including migration,
rollback, concurrent claims, recovery audit, and evidence-storage upgrades.
Migration supports the repository's original schema, not arbitrary external
variants. The checked-in DB changes only when initialization is explicitly run
or the API starts against it.

### Phase 3 — Docker orchestration

- [x] Construct explicit argv with viewport settings.
- [x] Capture output and exit codes, enforce execution timeouts, and retry cleanup.
- [x] Expose synchronous execution to async callers through a worker thread.
- [x] Verify the built API runtime separately from mocked Docker tests.
- [ ] Package pi and its dependencies in an agent image (Phase 9).
- [ ] Connect bidirectional RPC and bounded streaming output (Phase 9).
- [ ] Confirm child termination on cancellation (Phase 9).

Evidence: `tests/test_orchestration.py`, `tests/test_executor.py`, and Docker/API
smoke checks. The current image contains Python, Git, Bash, and the API, but no
pi or Docker CLI.

### Phase 4 — Gatekeeper and code audit

- [x] Require explicit `create=True` when creating a Git repository.
- [x] Require a clean checkout and validate proposed paths, including symlink checks.
- [x] Restore files and index state after ordinary write or commit failures.
- [x] Record PREPARED intent before Git writes and APPLIED/FAILED outcomes with
  commit hashes and session IDs.
- [x] Block further proposals until interrupted PREPARED intent is reconciled.
- [x] Retain repository, branch, base revision, message, and content-hash evidence.
- [x] Verify applied commits or unchanged checkouts during read-only recovery;
  leave dirty, unrelated, ambiguous, or evidence-free proposals unresolved.
- [x] Preserve successful commits if subsequent reflection fails.
- [ ] Verify proposed code in isolation before promotion (Phase 10).
- [ ] Protect application and recovery against concurrent filesystem writers.
- [ ] Connect production operator authorization and execution-stop adapters (Phase 14).

Evidence: `tests/test_gatekeeper.py`, `tests/test_coordinator.py`, and
`tests/test_recovery.py`, including crash injection, content mismatch, and no-op
reconciliation. Git and SQLite are not one atomic transaction. The gatekeeper
is not an OS sandbox; callers must provide exclusive checkout access.

### Phase 5 — Human interface and audit API

- [x] Validate and persist bug reports, viewport data, and priority votes.
- [x] Expose issues, including terminal states, sessions, and audit records.
- [x] Expose pending recovery inspection and proposal/session recovery and retry routes.
- [x] Disable recovery mutations with 503 until host recovery and authorization
  callbacks are supplied; do not trust a user-supplied actor.
- [x] Expose interactive API documentation at `/docs`.
- [ ] Build the browser dashboard, chat/report form, and task selection controls (Phase 13).
- [ ] Build browser recovery controls (Phase 13).
- [ ] Implement production authentication and deployment policy (Phase 14).

Evidence: `tests/test_ui_bridge.py` and recovery API tests in
`tests/test_recovery.py`. Empty frontend files do not count as a completed UI.

### Phase 6 — Reflection and configuration loading

- [x] Provide an injectable reflection interface using issue and exact-session evidence.
- [x] Deduplicate session-scoped updates and version them transactionally with
  a REFLECTION signal.
- [x] Load configuration by insertion ID so equal timestamps do not skip updates.
- [ ] Connect a real analysis client (Phase 12).
- [ ] Evaluate drift and measure strategy quality (Phase 12).
- [ ] Handle invalid legacy updates without silently losing later records (Phase 12).

Evidence: `tests/test_convergence.py` and `tests/test_coordinator.py`.
An invalid update currently blocks the loader until corrected. The legacy batch
API leaves deduplication to its caller; the coordinator uses session-scoped reflection.

### Phase 7 — Convergence and autonomy

- [x] Implement `Coordinator.run_once()`: claim an issue, load configuration,
  invoke an injected runner, record evidence, apply successful proposals through
  the gatekeeper, reflect, reload, and finish the session/issue.
- [x] Prevent failed executions from applying code proposals.
- [x] Mark ordinary exceptions FAILED and retain RUNNING claims on cancellation.
- [x] Test the flow using a deterministic runner, real temporary SQLite, and real
  temporary Git, including failure and missing-gatekeeper behavior.
- [ ] Connect the live runner and model configuration (Phase 8).
- [ ] Add durable scheduling and production recovery (Phases 11 and 14).
- [ ] Connect human controls and demonstrate a live browser-operated workflow (Phase 13).

Evidence: `tests/test_coordinator.py`. The coordinator is a library, not an
automatically started daemon; local tests do not establish live autonomy.

### Phase 8 — Live agent client

- [x] Inspect automonisaur for reusable agent/protocol functionality and record the choice.
- [ ] Add a config class for the pi executable, model/provider selection, timeouts,
  and environment-based credentials.
- [x] Build a client for the actual `pi --mode rpc` protocol.
- [ ] Connect the client to the coordinator's runner interface.
- [ ] Map protocol events to session-linked signals.
- [ ] Validate structured results and file proposals before returning them to the coordinator.
- [x] Test malformed output, disconnects, and agent failure without inventing success.
- [ ] Process one issue with a live agent and retain its events and final result.
- [ ] Ensure agent loops continuously until `/goal` state requirements are met before declaring a multi-step goal completed.
- [ ] Measure and record live event latency.

Container execution follows in Phase 9; verified code promotion requires Phase 10.

Client evidence: `tests/test_pi_client.py` and a successful real pi 1.4.0
`get_state` check through `scripts/check_pi.py`. See `docs/pi_client.md` for the
supported operations and remaining integration limits.

### Phase 9 — Agent container and execution lifecycle

Depends on Phase 8.

- [ ] Build an agent image containing pi and its runtime dependencies.
- [ ] Connect bidirectional RPC through the Docker client.
- [ ] Pass only required credentials from environment variables.
- [ ] Keep the Docker socket and parent checkout write access out of child containers.
- [ ] Bound captured and streamed output and enforce execution timeouts.
- [ ] Confirm child termination on cancellation.
- [ ] Test success, failure, timeout, cancellation, and failed cleanup; block work
  for recovery when termination is uncertain.
- [ ] Run one submitted issue in a real container with session-linked events and
  a final result, without code promotion.

### Phase 10 — Verify proposed code before applying it

Depends on Phases 8–9.

- [ ] Apply proposals to isolated checkouts of their recorded base revisions.
- [ ] Run host-selected checks in a sandbox.
- [ ] Store content hashes, base revision, check results, and session linkage.
- [ ] Allow only the exact verified proposal through the gatekeeper; reverify
  when the base revision or proposal changes.
- [ ] Demonstrate a passing proposal producing a commit with linked evidence.
- [ ] Verify that failing checks, timeouts, and stale or altered proposals leave
  the parent checkout unchanged.
- [ ] Verify that check execution cannot write to the parent checkout or bypass
  the gatekeeper.

An agent's success flag alone does not establish that its source changes work.

### Phase 11 — Continuous task processing

Depends on Phases 8–10 and Phase 14's execution-stop/recovery support.

- [ ] Add a durable scheduler around the coordinator.
- [ ] Process queued issues sequentially and prevent competing schedulers from
  overlapping model execution.
- [ ] Support pause/resume and orderly shutdown.
- [ ] Preserve attempts across restarts and block unresolved sessions/proposals.
- [ ] Route explicit retries through existing recovery rules.
- [ ] Test restart during execution and Git proposal handling without silently
  duplicating work.
- [ ] Verify pause, shutdown, reconciliation, and retry with retained audit history.

### Phase 12 — Reflection with measurable results

Depends on Phases 8–10.

- [ ] Connect a real analysis client using exact-session evidence.
- [ ] Validate strategy proposals and version configuration updates.
- [ ] Handle invalid updates without silently losing later records.
- [ ] Define an evaluation task set, baseline, success metric, and regression
  threshold before automatically adopting changes.
- [ ] Evaluate strategy quality and drift using recorded outcomes.
- [ ] Restore the previous configuration when a change fails evaluation.
- [ ] Demonstrate a live, traceable analysis update and repeatable comparison
  reporting improvement, regression, or no change.
- [ ] Test rejection and rollback of harmful or invalid updates.

Persisting a configuration update alone does not establish improvement.

### Phase 13 — Web interface and human controls

Uses Phases 11–12 and Phase 14's authentication support.

- [ ] Build task submission, chat/report forms, priority, and explicit task selection.
- [ ] Display live progress, audit history, and reasons work is blocked.
- [ ] Display proposed changes, verification results, and resulting commits.
- [ ] Connect pause/resume, recovery, and retry controls to the backend.
- [ ] Display strategy updates and their evaluation results.
- [ ] Enforce backend authorization for browser actions and direct API requests.
- [ ] Demonstrate an authorized user submitting/selecting a task, observing a live
  run, inspecting its result, and recovering an interrupted attempt through the
  browser without terminal commands after setup.

### Phase 14 — Authentication, recovery, and backup/restore

Build required pieces alongside Phases 9–13, before unattended deployment.

- [ ] Implement production operator authentication and authorization.
- [ ] Implement a host verifier confirming both parent execution and child
  containers have stopped.
- [ ] Connect the verifier and authorization to the existing recovery service.
- [ ] Reject unauthorized mutations and prevent recovery when worker state is uncertain.
- [ ] Demonstrate authorized reconciliation of an interrupted attempt with an audit trail.
- [x] Document current API deployment configuration and startup blockers in
  `docs/deployment.md`.
- [ ] Resolve the documented API startup blocker and verify deployment from a fresh image.
- [ ] Implement backup/restore for SQLite and Git revisions referenced by audit records.
- [ ] Restore into a separate environment and verify issues, sessions, strategy
  versions, and referenced commits.

## Verification and next work

Run the complete regression suite with the configured interpreter:

```sh
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python -m scripts.test_vault_write
bash build.sh
```

Tests use temporary state and mock Docker execution. Build and HTTP smoke checks
are separate. No result in this document establishes live model performance.

Start with Phase 8's live agent client, then Phase 9's container milestone and
Phase 10's verified proposals. Build Phase 14's recovery and authentication
support before enabling unattended scheduling or browser operations that need
it. Continue with scheduling, evaluated reflection, and the web interface.
Preserve the gatekeeper boundary throughout. Detailed contracts and setup live in
`docs/signaling_schema.md`, `docs/signaling_flow_map.md`, and `docs/runtime_guide.md`.
See `docs/recovery.md` for the recovery service contract and API workflow.
