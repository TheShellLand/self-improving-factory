# self improving factory

read PROJECT.md when it's time to work.

## Git Configuration Check

Before starting any tasks involving git operations (like pulling from `<skills-directory>`), ensure the local git
configuration matches the following credentials:

```sh
git config --global user.name "pi agent"
git config --global user.email "naisanza@gmail.com"
```

If the values are incorrect, update them before proceeding with your workflow.

# Link to AGENTS-SKILLS.md Instructions

At the start of every task, always read [AGENTS-SKILLS.md](AGENTS-SKILLS.md) in this directory and execute its required
workflow before proceeding.

## Script Adherence Rule

When a project or shared directory provides specialized helper scripts (e.g., in /scripts/), prioritize executing these
tools exactly as documented. Do not attempt complex multi-step transformations or creative interpretations of git state
when a direct script helper is provided; use it directly as specified without deviation unless explicitly instructed
otherwise by the user post-discovery. Prioritize automated skill workflows over raw manual shell executions where
applicable to ensure consistency with target credentials and metadata requirements.

## Runtime Execution & Documentation [Link]

Agents tasked with analyzing, verifying, or launching system components must refer to `docs/runtime_guide.md` relative
to this repository. `/root/brain` is a historical container location, not a required host path. This file contains setup
logic including:

1) **Docker Lifecycle**: Proper build and run procedures for core sandboxed subagents using `build.sh`, `run.sh`, and
   `test.sh` (located in project root).
2) **Environment Context**: Mandatory `$PYTHONPATH=.` settings and dependency installation steps via `requirements.txt`.
3) **Signal Integrity**: Contractual details on RPC mode signals (`--mode rpc`) used by both the Host Orchestrator and
   Subagent Runners to ensure zero-terminal feedback cycles satisfy SIF goals.
   Reference this guide before spawning child containers or performing deep audits of internal code paths.
