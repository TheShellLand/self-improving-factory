# Runtime and verification guide

## Environment

Use the project root as the working directory and `PYTHONPATH=.` for local module
execution. Python 3.12+ and Git are required. Install runtime dependencies with
your configured interpreter's `-m pip install -r requirements_txt`; use
`requirements-dev.txt` for tests. Activate a virtual environment first. Agents
using PyCharm must follow the python-tools skill to select its configured SDK.

`SASIAS_DB_PATH` selects the SQLite database; the default is the project-root
`history_vault.db`. The application does not automatically load `.env` files.
`python -m scripts.init_vault` creates missing tables without resetting records.
Existing incompatible schemas require an explicit migration.

## Docker lifecycle

With Docker Engine 26+ running:

1. Run `bash build.sh` to build `sasias_runtime`.
2. Run `bash run.sh` for an idle development container, or `bash test.sh` for an
   interactive verification shell. Both mount this checkout at `/app` and set
   `SASIAS_VIEWPORT=1920x1080`. The image sets `PYTHONPATH=/app`.
3. Stop an idle container using `docker rm -f <container-name>` when done.

For the API with persistent storage:

```sh
docker run --rm -p 8000:8000 -e SASIAS_DB_PATH=/data/history_vault.db \
  -v sasias-data:/data sasias_runtime
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

Tests use disposable state and mock Docker execution. They do not prove the
autonomous loop is operational. The reflection provider, issue scheduler, and
agent execution integration must be configured/implemented before that claim.

## Planned signal contract

Future agent runners must use `pi --mode rpc`. Inputs and observations should
carry session identity and viewport metadata; outcomes should be recorded as
RESULT signals. Current telemetry and executor classes remain prototypes.

## Git proposals

Use `GatekeeperVault` to apply file proposals. Open existing repositories by
default; pass `create=True` explicitly for new repositories. Use temporary
directories for tests. A clean checkout and exclusive caller access are required.
Validation and rollback cover ordinary exceptions, not concurrent writers,
process termination, or filesystem failure during recovery.
