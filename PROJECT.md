# Project Specification & Progress Log

## Overview
### Objective: Autonomous Self-Improving Agent System (ASIAS)
The primary goal of this project is to move beyond "looping" manual agent interactions in a terminal by creating an autonomous framework that improves itself as it operates live. The system must be able to reflect on its successes and failures, update internal knowledge bases about the environment/tools, and refine its own planning logic dynamically without human prompting between steps.

**No-Terminal Environment Philosophy**: Once deployed, all auditing, interaction via chat interface, and troubleshooting should occur within the web ui layer—effectively removing any need for CLI intervention unless performing core infrastructure upgrades.

## Distributed Sandboxed Architecture: 
To avoid nested containers while maintaining strict isolation, SASIAS uses **Distributed Orchestration**.
1. **Parent Container (Host Manager)**: Runs the main application engine (UI Bridge, Evolution Engine, Critic). It is equipped with host docker socket access to manage life cycles of subagent executions.
2. **Subagents (Task Runners)**: The system spawns task-specific agents into separate Docker containers as child processes.
3. **RPC Execution**: Communication between these distributed entities occurs via `python subprocess` calls invoking the agent executable in RPC mode (`pi --mode rpc`). This allows for decoupled execution where each sandbox can be treated as a remote service by the orchestrator while maintaining strict isolation from the parent.

## Perspective & Visual Observation Layer 
To enable "self-improving" reflection through observation rather than just log parsing, SASIAS captures visual context:
1. **User Context Injection**: Client browser viewport dimensions are captured at every user interaction and injected into signal logs within `history_vault.db`. These ensure bug reports match human perspective exactly.
2. **Standardized Subagent Viewports**: The Orchestrator enforces standardized screen resolutions (e.g., $1920 \times 1080$ default) on subagents to ensure consistent image analysis results across different tasks during vision processing.
3. **Signal Schema**: Every RPC pulse includes a mandatory optional `visual_state` field containing the base64 representation of the current UI view for auditing by both humans and agents.

## Task Governance & Resource Management
To respect hardware constraints ("One LLM resource" model), SASIAS implements an Issue Lifecycle:
-   **Bug Reporting System**: A permanent "Report Bug" button captures user state, viewport metadata, and navigation status into an internal issue queue stored in `history_vault.db`. 
-   **Priority Queue (Voting)**: Issues are stored in a dedicated table where users can vote on priority ($+$ / $-$). This provides human oversight over what tasks enter the autonomous loop first to avoid overloading system resources or causing unintended iterations.
-   **Human-in-the-loop Selection**: The orchestrator pulls high-priority issues from this board one at a time for deep analysis by the single available agent process when capacity allows.

## Secure Software Development Architecture
To prevent unsafe shell access while maintaining autonomy over code growth, we use a **Commit Gateway Pattern**.
1. **LLM Role (Content Decision)**: LLMs analyze results and generate proposed diffs and descriptive commit messages only as data objects (*not* command strings) passed through an RPC channel.
2. **Python Core Gatekeeper (Execution authority)**: A dedicated project library handles all Git operations via `GitPython`. This ensures that state transitions in version control are atomic, audited into standard logs, and protected against raw tool injection or unauthorized history manipulation from subagents.

**Tech Stack:** 
- Primary Language: Python
- Core Library: `pi-coding-agent-python-sdk`
- Web Framework: FastAPI / Flask + React for dashboard & bug reporting UI integration.
- Version Control Logic: `gitpython`, managed internally by ORCHESTRATOR logic blocks to ensure safety compliance.
- Communication Protocol: Host Docker Socket access with Subprocess/RPC communication core (`pi --mode rpc`).

## Planned Tasks (Roadmap)
*   **[x] Phase 0**: Project Initialization & Specification definition complete. Validated project structure and documentation requirements.
*   **Phase 1: Distributed System Architecture** - Finalize signaling schemas for RPC communication and define Gatekeeper, Observer, and Executor class structures. Map signal propagation from Chat Bridge $\rightarrow$ Signal Log $\rightarrow$ Child Sandbox execution results.
*   **Phase 2: Core Vault Foundation** - Initializing `history_vault.db`. Create migration scripts for the 'Signal Feed' ($w \times h$, base64 frames), Issues Queue (+voting logic), and Experience Memory blocks (critic values).
*   **Phase 3: Docker Orchestration Framework** - Build parent container setup with host socket mapping using Python-based lifecycle managers. Construct child sandbox templates/configs to enforce $1920 \times 1080$ viewport standardization at launch.
*   **Phase 4: Gatekeeper Commit Logic & Versioning System** - Fully integrate `GitPython` into core modules as a primary gateway. Implement commit message generation prompts that prevent raw shell injection while allowing complex diff application.
*   **Phase 5: UX Interface Layer (Chat Bridge)** - Develop FastAPI and React frontend featuring the state-aware "Report Bug" snapshot button, real-time Signal Audit logs, and priority voting dashboard for humans.
*   **Phase 6: Reflection Engine Development** - Build Critic module logic to interpret vault experience records. Finalize Hot Loading blocks for rules/weights injection without restart or re-builds of active containers.
*   **Phase 7: Full Autonomy Convergence** - Integrate full loop where prioritized issues from human queue trigger automatic sandbox execution $\rightarrow$ observation logging $\rightarrow$ critic reflection $\rightarrow$ model weight updates in dynamic cycle with zero manual terminal intervention.

## Implementation Details
### Core Components (Specifications)
*   **Executor**: Orchestrates subprocess spawning via Docker sockets; enforces $1920 \times 1080$ viewport rendering on subagents by default ($w,h$) and maintains an RPC connection pool to manage multiple distributed tasks concurrently while maintaining strict isolation.
*   **Observer**: Automatically parses child process logs/output streams using standard deviation logic; captures visual `base64` signals as they occur during task steps for ingestion into the experience memory layer.
*   **Critic / Reflector**: Analyzes specific execution telemetry against user-provided bug reports from `history_vault.db`; translates identified friction points into persistent vectorizable update rules or new behavior weights.
*   **Evolution Engine & Hot Loader**: Consumes critic updates to calculate prompt weightings OR operational strategy changes; uses hot loading blocks (runtime reload) of internal configuration modules without requiring container reboots or rebuilds.
*   **Chat Bridge & Audit UI**: Captures raw human input + browser context (viewport, path depth); populates common Signal\_log entries as first-order data objects; provides a voting dashboard for humans and an audit trail for every subagent signal fired across the distributed system.

## History / Logs
### Finalized Architecture Decision Log:
Distributed Orchestration model adopted to solve nested containers via Host Socket access (`/var/run/docker.sock`) combined with RPC Mode Subagents (`--mode rpc`). High-resolution viewport standardization ($1920 \times 1080$) locked in both frontend capture logic and backend sandbox generation logs. Issue management implemented through prioritized SQL queue (+voting) at host level, allowing human prior prioritization of LLM tasks on single machines. Version control strictly gated by Python's `GitPython` gateway pattern (No shell commits from agents). Project established as a "Zero Terminal" system for production operation!
