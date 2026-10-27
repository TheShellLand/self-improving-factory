# SASIAS Runtime & Execution Guide

This document provides critical information on how to initialize, build, and execute components within the Autonomous Self-Improving Agent System (ASIAS). Agents must follow these instructions precisely when orchestrating subagent sandboxes or local execution loops.

## 1. Environment Prerequisites
Before any operations occur, ensure the host environment satisfies:
*   **Docker Engine**: Version >= 26.0 installed and active.
    *   The current user/docker service has access to `/var/run/docker.sock`.
*   **Python Dependencies**: The primary stack requires `fastapi`, `uvicorn`, `pydantic`, and `gitpython` in a path accessible by `.env`.
*   **Environment Pathing**: Ensure `$PYTHONPATH` includes the project root (`/root/brain`) so that modules in `./core/`, `./ui_backend/`, etc., are importable via relative paths.

## 2. Setup Lifecycle
To prepare the system for run-time:
1.  Navigate to `/root/brain`.
2.  Install python dependencies (Run locally or inside an initial setup container):
    ```bash
    pip install --break-system-packages -r requirements_txt
    ```
3.  Build the production runtime image used for sandboxed subagents:
    ```bash
    ./build.sh
    ```

## 3. Execution Models
The project provides three modes of execution depending on agent needs:

### A. Persistent Sandbox (`run.sh`)
Use this when you need a "waiting" sandbox that remains active while receiving RPC pulses from other system components ($w \times h$ viewports are pre-configured). It uses `tail -f /dev/null` to preserve container state without consuming high CPU cycles in its idle mode.

### B. Verification Shell (`test.sh`)
Use this for one-off diagnostic checks or manual inspection inside an ephemeral replica of the production environment. This mounts your current code directory into `/app`, allowing verification of internal core modules (e.g., `CriticModule`).

### C. Orchestrator Core
For running the main loop, use:
```bash
export PYTHONPATH=$PYTHONPATH:. && python3 ./scripts/main.py 
# Or a standard entry point defined by the UI Bridge logic.
```

## 4. Signal Propagation & RPC Interface
When an agent is prompted to "run" via SASIAS commands:
*   Subagents must initialize with `--mode rpc`.
*   Each pulse should log timestamps and operation states back to the `history_vault.db` in `/root/brain/history_vault.db`.
    - **Request Layer**: Entry added as Input signal ($type=INPUT$).
    - **Execution Loop**: Status updates logged into trace logs or session metadata (PENDING, RUNNING, COMPLETED).
    - **Reflection Closure**: Results are captured for Critique by injecting a terminal observation result ($type=RESULT$).

## 5. Version Control Security
Strictly use internal logic blocks that wrap around `gitpython` via `./core/gatekeeper.py`. Do not attempt raw shell executions using strings passed directly from non-validated agent headers to ensure data objects remain purely content and never execution commands until validated at the gateway level.
