# Runtime and verification guide

## Environment

Use the project root as the working directory and `PYTHONPATH=.` for local module
execution. Python 3.12+ and Git are required. Install runtime dependencies with
your configured interpreter's `-m pip install -r requirements.txt`; use
`requirements-dev.txt` for tests. Activate a virtual environment first. Agents
using PyCharm must follow the python-tools skill to select its configured SDK.

`SIF_DB_PATH` selects the SQLite database; the default is the project-root
`history_vault.db`. The application does not automatically load `.env` files.
Configuration classes read defaults at construction. `SIF_API_HOST` and
`SIF_API_PORT` configure the server; `SIF_TASK_TIMEOUT`, `SIF_CLEANUP_TIMEOUT`,
and `SIF_POLL_INTERVAL` configure execution, cleanup, and configuration polling
in seconds. See `.env-example` and [reuse conventions](automonisaur.md).
`python -m scripts.init_vault` creates missing tables without resetting records.
Initialization upgrades the original issue-status constraint and adds audit/link
tables without removing existing records. Other incompatible schemas require an
explicit migration.

## Docker lifecycle

See [deployment configuration](deployment.md) for persistence, environment
settings, replacement procedures, and the current API startup blocker.

With Docker Engine 26+ running:

1. Run `bash build.sh` to build `sif_runtime`.
2. Run `bash run.sh` for an idle development container, or `bash test.sh` for an
   interactive verification shell. Both mount this checkout at `/app` and set
   `SIF_VIEWPORT=1920x1080`. The image sets `PYTHONPATH=/app`.
3. Stop an idle container using `docker rm -f <container-name>` when done.

For the API with persistent storage:

```sh
docker run --rm -p 8000:8000 -e SIF_DB_PATH=/data/history_vault.db \
  -v sif-data:/data sif_runtime
```

The image includes Python, Git, Bash, and the application dependencies. Its
default command starts the API. A host orchestrator needs Docker CLI access and
access to the Docker daemon; child containers do not receive the Docker socket.
The `pi` executable and RPC integration are not bundled or implemented yet.

## Verification

Using the configured Python interpreter:

```sh
PYTHONPATH=. python -m unittest discover -s tests -v
PYTHONPATH=. python -m scripts.test_vault_write
```

Tests use disposable state and mock Docker execution. The coordinator integration
test uses a deterministic runner, real temporary Git, and real temporary SQLite.
It does not prove the live autonomous loop is operational. Production runner and
reflection adapters, continuous scheduling, and production recovery are unfinished.

## Planned signal contract

Future pi adapters must use `pi --mode rpc`. The internal `SignalPulse` envelope
validates identity, timestamps, action types, and viewport metadata. The executor
requires host-selected argv; it does not map the pi wire protocol itself. Runner
and pipeline outcomes are recorded as distinct RESULT signals.

## Git proposals

Use `GatekeeperVault` to apply file proposals. Open existing repositories by
default; pass `create=True` explicitly for new repositories. Use temporary
directories for tests. A clean checkout and exclusive caller access are required.
Validation and rollback cover ordinary exceptions, not concurrent writers,
process termination, or filesystem failure during recovery.

CommitService records PREPARED before applying a proposal and APPLIED/FAILED
afterward. A remaining PREPARED record must be reconciled against Git; do not
retry it blindly. Cancellation leaves a RUNNING session to prevent overlapping
work. The recovery service requires a host verifier that confirms both the parent
task and child execution have stopped. Mutating recovery routes additionally
require a host operator authorization callback; they are disabled in the default
API. No automatic recovery daemon or recovery UI is implemented yet.
See [recovery operations](recovery.md) for evidence checks and the recovery order.
