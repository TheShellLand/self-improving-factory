# API deployment configuration

This guide covers the API service. It does not start a model worker, scheduler,
or browser dashboard. See [runtime verification](runtime_guide.md) and
[recovery operations](recovery.md) for component contracts.

## Current startup blocker

At this documentation review, `scripts/main.py` imports `ApiConfig`, but
`core/config.py` does not define it. A fresh image of this checkout therefore
cannot start its default API command. Restore and verify that configuration
contract before using the deployment procedure below. An older image starting
successfully is not verification of the current checkout.

## Configuration

The application does not automatically load `.env` files. Export variables for
host execution or pass them explicitly with Docker `-e`. `.env-example` is a
reference, not a file that is loaded automatically.

| Setting | Purpose | Default or requirement |
| --- | --- | --- |
| `SIF_DB_PATH` | SQLite file location | Repository-root `history_vault.db`; use `/data/history_vault.db` with the volume below |
| `SIF_IMAGE` | Image tag used by build/run helpers | `sif_runtime`; does not select the image in a literal `docker run` command |
| `SIF_API_HOST` | Intended API listen address | `.env-example` specifies `0.0.0.0`; requires restoring `ApiConfig` |
| `SIF_API_PORT` | Intended API listen port | `.env-example` specifies `8000`; requires restoring `ApiConfig` |
| `SIF_TASK_TIMEOUT` | Docker execution timeout, seconds | `600`; finite and positive |
| `SIF_CLEANUP_TIMEOUT` | Docker cleanup timeout, seconds | `10`; finite and positive |
| `SIF_POLL_INTERVAL` | Configuration loader interval, seconds | `5`; finite and positive |
| `DOCKER_HOST` | Docker client endpoint | Inherited environment unless an explicit socket is supplied |

The execution and polling settings do not start workers. The API container needs
neither the Docker socket nor a writable mount of this repository. Model-client
configuration is under development and is not part of this API procedure.

## Deployment procedure after the startup blocker is fixed

Run from the repository root with Docker running. Use the documented build helper:

```sh
bash build.sh
docker run -d --name sif-api --restart unless-stopped -p 127.0.0.1:8000:8000 -e SIF_DB_PATH=/data/history_vault.db -e SIF_API_HOST=0.0.0.0 -e SIF_API_PORT=8000 -v sif-data:/data sif_runtime
```

The API binds inside the container; the published port binds only to the host's
loopback interface. The current API does not provide production authentication
for ordinary issue mutations. Keep access local until authentication and a
deployment access policy are implemented. Recovery mutations remain disabled
unless the host supplies both recovery and operator-authorization callbacks;
setting an environment variable alone does not enable them.

On startup, the API initializes missing tables and supported schema upgrades.
The named volume retains the database when the container is replaced. Reuse the
existing volume name for an existing deployment; a different name creates a
different database. A persistent volume is not a backup.

Check startup and API access:

```sh
docker logs --tail 100 sif-api
curl --fail http://127.0.0.1:8000/api/issues
curl --fail http://127.0.0.1:8000/openapi.json
```

The issues endpoint should return a JSON list. These checks establish API
availability, not live agent operation or recovery readiness.

## Stop and replace

```sh
docker stop sif-api
docker rm sif-api
```

Rebuild and repeat the run command with the same data volume. Do not remove the
volume to update the application. Backup/restore and schema rollback procedures
remain unfinished; preserve data before introducing schema-changing versions.

The dependency manifest follows automonisaur's default branch. Rebuilding may
fetch different upstream code; record the source commit and resulting image ID
for each verified deployment. Reverting an image does not revert its database.
