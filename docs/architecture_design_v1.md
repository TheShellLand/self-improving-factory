# SASIAS Architecture Design v1 - [Distributed Sandboxing]

## 1. Orhcestrator Model (Parent Container)
The main agent engine operates as a high-level manager with access to host resources but no direct external execution exposure except through defined "gates."

### Communication Protocol: Distributed RPC Subagents
Instead of nesting containers (which is unsupported/unsafe), we treat every subagent task as an out-of-band process.
*   **Subagent Spawning**: Parent container uses the Docker Host Socket (`/var/run/docker.sock`) via Python's `subprocess` and `gitpython`.
*   **State Sync**: Each sandbox executes in `--mode rpc`, establishing bi-directional communication channels for logs, status pulses, and final results.

## 2. Persistence & Logic Layers
A single SQLite database (`history_vault.db`) maintains three synchronized layers:
1.  The **Signal Feed**: A high-volume log of all raw inputs (from users) and outputs (from subagents), enriched with client viewport dimensions at point of entry.
2.  The **Experience Layer**: High-level reflections from "Critic" modules to update agent prompt weights dynamically.
3.  The **Prioritized Issue Queue**: All bug reports and user requested goals are pooled into an `issues` table where they receive a persistent priority score based on human voting $(+/-)$.

## 3. Execution Gates & Safety Rails
### Secure Software Revisioning (Gatekeeper Pattern)
Agents do *not* have direct access to shell commands like `git commit`. Instead:
1. Agents deliver content + metadata via RPC message signals.
2. The Orchestrator passes these objects through the **Source Control Gate**.
3. Internal project logic uses `GitPython` to atomically apply changes, log successes/failures in history_vault.db, and move onto next tasks or feedback loops.

### Vision Standardization Layer
To resolve ambiguity across distributed sandboxes, all visual outputs are normalized:
-   **Client Persistence**: Users' viewport data is saved on input for reproduction accuracy ("See exactly what I saw").
-   **Sandbox Standard**: All subagents use standardized high-resolution viewports (e.g., 1920x1080) unless a specific human objective overrides this standard via the UI Bridge context.
