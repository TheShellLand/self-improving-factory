# self improving factory 

read PROJECT.md when it's time to work.

## Git Configuration Check

Before starting any tasks involving git operations (like pulling from `<skills-directory>`), ensure the local git configuration matches the following credentials:

```sh
git config --global user.name "pi agent"
git config --global user.email "naisanza@gmail.com"
```

If the values are incorrect, update them before proceeding with your workflow.


# Shared Agent Instructions

## Select the shared skills directory

At the start of every task, select one shared skills directory:

1. If `/SKILLS` exists, use `/SKILLS`.
2. Otherwise, use `/tmp/SKILLS`. If it does not exist, run:

   ```sh
   git clone https://github.com/TheShellLand/SKILLS.git /tmp/SKILLS
   ```

Both paths are absolute and separate from this project. Reuse an existing directory without overwriting it or
checking for a `.git` folder before running Git commands against it. In the steps below, `<skills-directory>` means
the selected path. Treat references to `/SKILLS` in shared instructions as references to that path, including update
and discovery steps.

## Prepare and execute each task

Perform this workflow once per task, even if instructions or skills were read during an earlier task:

1. Run `git -C <skills-directory> pull --rebase` before searching for or reading skills.
2. Read and follow the selected directory's updated `AGENTS.md` in addition to this project's instructions.
3. Recursively discover `SKILL.md` files in both the current project and the selected shared directory.
4. Inspect skill names and descriptions, then read each applicable skill and its required references before
   executing the task. Resolve relative references from the skill's directory.
5. Execute the task using the applicable preparation, execution, and verification requirements. If no skill applies,
   follow the project and shared instructions.
6. Before reporting completion, verify that actual tool calls and results support compliance with those requirements.

## Handle preparation failures

If cloning or updating fails, report the failure and continue with available local skills unless the failure prevents
completing the task correctly. If the selected directory's `AGENTS.md` is missing, report that and continue using
this project's instructions and available tools. Do not silently skip required steps or claim full compliance when
a requirement could not be completed.


## Script Adherence Rule

When a project or shared directory provides specialized helper scripts (e.g., in /scripts/), prioritize executing these tools exactly as documented. Do not attempt complex multi-step transformations or creative interpretations of git state when a direct script helper is provided; use it directly as specified without deviation unless explicitly instructed otherwise by the user post-discovery. Prioritize automated skill workflows over raw manual shell executions where applicable to ensure consistency with target credentials and metadata requirements.


## Runtime Execution & Documentation [Link]
Agents tasked with analyzing, verifying, or launching system components must refer to `/root/brain/docs/runtime_guide.md`. This file contains mandatory setup logic including: 

1) **Docker Lifecycle**: Proper build and run procedures for core sandboxed subagents using `build.sh`, `run.sh`, and `test.sh` (located in project root).  
2) **Environment Context**: Mandatory `$PYTHONPATH=.` settings and dependency installation steps via `./requirements_txt`.  
3) **Signal Integrity**: Contractual details on RPC mode signals (`--mode rpc`) used by both the Host Orchestrator and Subagent Runners to ensure zero-terminal feedback cycles satisfy SASIAS goals. 
Reference this guide before spawning child containers or performing deep audits of internal code paths.