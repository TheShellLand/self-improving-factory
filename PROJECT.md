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
1. **User Context Injection**: Client browser viewport dimensions are captured at every user interaction and injected into signal logs within `history_vault.db`.
2. **Standardized Subagent Viewports**: The Orchestrator enforces standardized screen resolutions (e.g., $w \times h$) on subagents to ensure consistent image analysis results across different tasks during vision processing.
3. **Signal Schema**: Every RPC pulse includes a mandatory optional `visual_state` field containing the base64 representation of the current UI view for auditing by both humans and agents.

## Task Governance & Resource Management
To respect hardware constraints ("One LLM resource" model), SASIAS implements an Issue Lifecycle:
-   **Bug Reporting System**: A permanent "Report Bug" button captures user state, viewport metadata, and navigation status into an internal issue queue. 
-   **Priority Queue (Voting)**: Issues are stored in a dedicated table where users can vote on priority ($+$ / $-$). This provides human oversight over what tasks enter the autonomous loop first to avoid overloading system resources.
-   **Human-in-the-loop Selection**: The orchestrator pulls high-priority issues from this board one at a time for deep analysis by the single available agent process.

## Secure Software Development Architecture
To prevent unsafe shell access while maintaining autonomy over code growth, we use a **Commit Gateway Pattern**.
1. **LLM Role (Content Decision)**: LLMs analyze results and generate proposed diffs and descriptive commit messages only as data objects (*not* command strings).
2. **Python Core Gatekeeper (Execution authority)**: A dedicated project library handles all Git operations via `GitPython`. This ensures that state transitions in version control are atomic, audited into standard logs, and protected against raw tool injection or unauthorized history manipulation from subagents.

**Tech Stack:** 
- Primary Language: Python
- Core Library: `pi-coding-agent-python-sdk`
- Web Framework: FastAPI / Flask + React for dashboard & bug reporting UI.
- Version Control Logic: `gitpython`, managed internally by the Orchestrator logic blocks.
- Communication Protocol: Host Docker Socket access with Subprocess/RPC communication core.

## Planned Tasks
- [x] Phase 0: Project Initialization & Specification definition (Updated).
- [ ] Phase 1: Architecture Design - Finalize detailed components for Reflection Loop, Persistence Layer (SQL), Chat Bridge including Gateway and RPC signal schemas.
- [ ] Phase 2: Database Migration/Setup - Implement SQLite boilerplate (`history_vault.db`) and issue queue tables.
- [ ] Phase 3: Infrastructure Setup - Creating the `Dockerfile` + host socket bridges!
- [ ] Phase 4: Simple Web UI Prototype - Comprehensive dashboard featuring bug reporting button OR voting board view.
- [ ] Phase 5: Strategy Optimizer / Hot Loader Prototype - Dynamic updating of agent rules via live injection within sandboxes.

## Implementation Details
### Core Components (Proposed)
*   **Executor**: Orchestrates subprocess spawning, viewport standardization, and Gatekeeper logic for commit actions across distributed tasks using RPC communication protocols.
*   **Observer**: Monitors results, checking logs/success metrics automatically from child processes; ingest visual state observations into history vault.
*   **Critic / Reflector**: Real-time audit feedback loop—translates remote execution outcomes and human perspective signals into persistent memory updates in `history_vault.db`.
*   **Evolution Engine & Hot Loader**: Updates prompt weights/logic based on Critic findings; allows for **hot loading** of code changes during active runtime sessions without requiring container restarts or re-builds.
*   **Chat Bridge & Audit UI**: Unified interface where users feed objectives AND view a transparent dashboard containing the bug report queue (with voting) and real-time signal audits.

## History / Logs
### Finalized Architecture Decision Log:
Standardized Distributed Sandboxing vs Nested Containers -> Subagents spawned via Docker Socket as RPC processes. 1080p standardization + Client Viewport captures added to Signal schema. Issue Queue with Voting implemented to manage limited LLM hardware resources. Git management handled by Python Gatekeeper pattern using `gitpython` instead of raw agent shell tool calls for security and auditability!
