# Self-improving factory

A Python foundation for recording agent activity, managing issues, applying Git proposals, and loading reflection updates.

## Setup

Use Python 3.12 or newer and Git. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHONPATH=. .venv/bin/python -m scripts.init_vault
PYTHONPATH=. .venv/bin/python -m scripts.main
```

The API listens on port 8000; interactive API documentation is at `/docs`.
Set `SASIAS_DB_PATH` to choose a database location. The default is
`history_vault.db` in the repository root. Initialization creates missing tables
and preserves records; it does not migrate incompatible schemas. Environment
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
docker run --rm -p 8000:8000 -e SASIAS_DB_PATH=/data/history_vault.db \
  -v sasias-data:/data sasias_runtime
```

`bash run.sh` starts an idle development container with the checkout mounted.
`bash test.sh` opens an interactive shell with the same mount. Both helpers work
from any directory, including checkout paths containing spaces. Set `SASIAS_IMAGE`
to override their image tag. See [the runtime guide](docs/runtime_guide.md).

## Components

- `core/database.py` owns database initialization and connection lifetimes.
- `ui_backend/bridge.py` exposes issue creation, priority listing, and audit reads.
- `core/gatekeeper.py` applies file replacements through GitPython. Opening a
  repository is the default; creating one requires `create=True`. It requires a
  clean checkout, rejects paths outside the repository and Git metadata, and
  restores files/index after ordinary write or commit failures. Callers must
  serialize access; this is not a security sandbox or a crash-safe transaction.
- `core/orchestrator_manager.py` executes Docker commands synchronously and keeps
  their status and output. Docker CLI access is required on the host running it.
- `core/critic.py` reads session evidence. `EvolutionEngine` requires an injected
  reflection provider; `HotLoaderModule` applies its persisted JSON configuration.

The autonomous scheduler, agent RPC integration, experience-drift analysis, and
frontend are unfinished. The image runs the API and includes Python dependencies
and Git; it does not include a `pi` agent or Docker CLI. Git commits are not yet
linked to SQLite task audit records. Historical completion claims in `PROJECT.md`
describe the intended roadmap and should not be treated as acceptance results.

## Verification and contributions

```sh
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=. .venv/bin/python -m scripts.test_vault_write
```

Tests use temporary databases/repositories and mock Docker subprocesses. Follow
`AGENTS.md`, add regression coverage for behavior changes, and keep generated
repositories and runtime data out of source control.
