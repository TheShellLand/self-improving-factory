# Self Improving Factory Harness (SIFH)

An agent orchestration harness for managing tasks, agents, and isolated subagents,
retaining execution evidence, and controlling proposed code and strategy changes.

SIFH provides the execution lifecycle around agents: task claims, protocol events,
verification boundaries, Git promotion, reflection, and recovery. It processes one
model task at a time. The planned browser interface is an operator console for
the harness. The coordinator and host pi adapter work today; containerized agent
execution, continuous scheduling, verified promotion, and browser controls remain
in progress. See [PROJECT.md](PROJECT.md) for verified milestones.

## Setup

Use Python 3.12 or newer and Git. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHONPATH=. .venv/bin/python -m scripts.init_vault
PYTHONPATH=. .venv/bin/python -m scripts.main
```

The API listens on port 8000; interactive API documentation is at `/docs`.
Set `SIFH_DB_PATH` to choose a database location. The default is
`history_vault.db` in the repository root. Initialization creates missing tables
and upgrades the original issue-status constraint while preserving records.
Other incompatible schemas require an explicit migration. Environment
variables must be exported by your shell; `.env-example` is a reference only.

```sh
curl http://localhost:8000/api/issues
curl -X POST http://localhost:8000/api/report-bug \
  -H 'Content-Type: application/json' \
  -d '{"title":"Task failed","description":"Observed failure","client_viewport":{"width":1920,"height":1080}}'
```

## Docker

```sh
bash build.sh
docker run --rm -p 8000:8000 -e SIFH_DB_PATH=/data/history_vault.db \
  -v sifh-data:/data sifh_runtime
```

`bash run.sh` starts an idle development container with the checkout mounted.
`bash test.sh` opens an interactive shell with the same mount. Both helpers work
from any directory, including checkout paths containing spaces. Set `SIFH_IMAGE`
to override their image tag. See [the runtime guide](docs/runtime_guide.md).

All project environment variables now use `SIFH_` instead of `SIF_`; old names
are no longer read as configuration. Rename exported settings and deployment
configuration, preserving their values, especially the database path. Provider
credentials and standard variables such as `DOCKER_HOST` and `PYTHONPATH` retain
their existing names.

When upgrading an existing deployment, update exported variables to `SIFH_DB_PATH`
and `SIFH_IMAGE`, and rebuild the image as `sifh_runtime`. Reuse the existing Docker
data volume to retain your database; `sifh-data` above is the name for a new setup.

## Components

- Follow the [automonisaur reuse and Config/Client conventions](docs/automonisaur.md)
  when adding code. Automonisaur is a runtime dependency from its default branch; its standard
  installation includes a large collection of integration dependencies.
- `core/database.py` owns schema upgrades and connection lifetimes; `core/vault.py`
  owns transactional signals, issue claims, votes, and session outcomes.
- `ui_backend/bridge.py` exposes issue creation/listing, votes, sessions, and audit reads.
- `core/gatekeeper.py` applies file replacements through GitPython. Opening a
  repository is the default; creating one requires `create=True`. It requires a
  clean checkout, rejects paths outside the repository and Git metadata, and
  restores files/index after ordinary write or commit failures. Callers must
  serialize access; this is not a security sandbox or a crash-safe transaction.
- `core/orchestrator_manager.py` executes Docker commands synchronously and keeps
  their status and output, enforces timeouts, and retries failed cleanup. Docker
  CLI access is required on the host running it; `ExecutorCore` provides async access.
- `core/critic.py` reads session evidence. `EvolutionEngine` requires an injected
  reflection provider; `HotLoaderModule` applies its persisted JSON configuration.

- `core/commit_service.py` links Git proposals and commit hashes to SQLite sessions.
  Interrupted PREPARED records retain recovery evidence and block new work.
- `core/recovery.py` reconciles Git evidence, fails stopped sessions, and explicitly
  requeues eligible issues. See [recovery operations](docs/recovery.md).
- `core/coordinator.py` processes one issue through an injected runner, optional
  gatekeeper proposal, session-scoped reflection, and configuration reload.

The continuous scheduler, pi RPC adapter, production recovery adapters,
experience-drift analysis, and frontend
are unfinished. The image runs the API and includes Python dependencies and Git;
it does not include a `pi` agent or Docker CLI. `PROJECT.md` distinguishes verified
phase refactors from features that still need to be built or tested.

## Verification and contributions

```sh
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=. .venv/bin/python -m scripts.test_vault_write
```

Tests use temporary databases/repositories and mock Docker subprocesses. Follow
`AGENTS.md`, add regression coverage for behavior changes, and keep generated
repositories and runtime data out of source control.
