# Automonisaur reuse and code conventions

SIF uses [automonisaur](https://github.com/TheShellLand/automonisaur) as its first
source of reusable integrations and as the reference for object-oriented code.
The runtime requirement follows upstream's default branch. The revision inspected
and tested for this refactor was `1a300fd962f0dd9a81ac04f2f02b530e6cdc10bb`;
future installations may fetch newer code.

## Reuse decisions

For the pi client, the inspected automonisaur revision has no pi RPC transport.
Its `subprocessWrapper.Run` uses blocking `communicate()` without bidirectional
JSONL dispatch or a deadline. `PiClient` therefore uses asyncio subprocess pipes
while reusing the existing config/environment convention.

| Need | Upstream reviewed | Current choice |
| --- | --- | --- |
| Environment settings | `automon.helpers.osWrapper.environ` | Import directly in config classes |
| Config/client separation | Integration `config.py` and `client.py` classes | Apply to SQLite, Git, Docker, and application setup |
| SQLite transactions and migrations | No SQLite client in the inspected revision | `DatabaseClient` retains SIF's transaction and migration rules |
| Docker lifecycle | No Docker client; `subprocessWrapper.Run` has no communicate timeout | `DockerClient` retains argv execution, timeout cleanup, and status tracking |
| Git proposals and recovery evidence | No Git client in the inspected revision | `GitClient` retains validation, rollback, and recovery checks |
| Model and HTTP integrations | Existing clients include Ollama and Requests | Revisit when implementing a real provider; no unused clients added |
| Signal identifiers | `uuidWrapper.Uuid.hex` generates UUID1 | Retain random UUID4 identifiers |
| Signal serialization | `jsonWrapper.Json.dumps_dict` converts values to strings | Retain typed JSON with non-finite numbers rejected |
| Audit timestamps | `Dates` returns local datetime/date values | Retain Unix timestamps |
| Proposal content evidence | `cryptography.hashing.Hashlib` provides MD5 | Retain SHA-256 content hashes |

Before creating code, inspect the installed upstream revision for a matching
function or class. Reuse suitable implementations directly and add an entry here
when a needed behavior prevents reuse. Do not wrap an unrelated class simply to
increase the number of upstream imports.

## Configuration and clients

Use a `*Config` class for settings and a `*Client` class for connections.
Explicit non-secret options override environment defaults. Read environment
defaults when constructing config objects, so applications and tests can create
independent configurations. Retain compatibility wrappers only for existing
callers; new code should use the classes.

```python
from core.config import DatabaseConfig, DockerConfig
from core.database import DatabaseClient
from core.orchestrator_manager import DockerClient

database = DatabaseClient(config=DatabaseConfig(database_path="/tmp/sif-example.db"))
database.initialize()
docker = DockerClient(config=DockerConfig(timeout=120, cleanup_timeout=10))
```

Tokens, keys, secrets, and passwords must be read from environment variables
inside the relevant config class. Do not put secrets in source defaults, example
files, repr output, or logs. Use `os.getenv` for exact credential strings:
automonisaur's `environ` helper strips quotes/whitespace and converts boolean
strings, which is useful for settings but can alter a credential. Current SIF
clients connect to local Git/SQLite or inherit Docker's environment; there is no
model API credential consumer yet.

## Dependency behavior

Install with `python -m pip install -r requirements-dev.txt` using the configured
interpreter. Runtime installations use `requirements.txt`; Git is needed to fetch
the upstream source. The normal upstream package installs many integration
dependencies, even when SIF only imports a helper. Its package initialization
also configures Python logging. These are upstream behaviors, not a claim that
SIF uses every integration. The Docker build installs the same dependency.

## Verification

`tests/test_configuration.py` covers environment changes after import, explicit
overrides, invalid timing settings, API server settings, database rollback and
connection closure, and the Git/Docker config paths. Existing lifecycle,
recovery, API, and coordinator tests cover preserved behavior.
