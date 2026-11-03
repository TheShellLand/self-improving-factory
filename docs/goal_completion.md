# Multi-step goal completion contract

Status: design contract for Phase 8; implementation and live verification remain
pending. The current PiRunner performs one structured invocation. No `/goal`
command or durable goal state is implemented by this document.

## Ownership and completion

The host must own a goal identifier, immutable acceptance requirements, and a
versioned record of progress linked to the claimed issue and session. Model text
may propose progress but cannot change requirements or set the terminal state.
Each requirement needs a host-selected verifier and retained evidence. Unsupported
requirements must block completion with an explicit reason.

An assistant response, `agent_end`, `agent_settled`, and an ExecutionOutcome with
`success=true` establish neither requirement satisfaction nor overall completion.
The host declares completion only after every requirement passes verification
against the final artifacts. Code requirements additionally depend on Phase 10's
isolated checks and exact-proposal promotion; model approval cannot replace them.

## Iteration and stopping

Within one exclusive issue claim, the runner repeatedly supplies the original
requirements, verified progress, and previous failure evidence to the agent.
After each settled response it validates the structured result, records the
attempt, and verifies progress before deciding whether another iteration is needed.
Because PiClient currently starts a fresh process per operation, continuation
must explicitly carry this context rather than assume persistent pi memory.

Host configuration must bound total elapsed time, iteration count, and retained
output. Exhausting a bound records an incomplete outcome with unsatisfied
requirements; it must never close the issue as successfully completed. Repeated
unchanged progress must stop with a recorded reason under a configured limit.
Malformed results, transport failures, and verifier failures retain their evidence
and follow an explicit bounded retry policy. No unbounded retry is permitted.

Cancellation preserves the existing unresolved RUNNING claim. Restart must not
automatically launch another invocation until recovery confirms execution has
stopped. Unknown cleanup status blocks subsequent work. Durable continuation and
automatic scheduling remain dependent on Phases 11 and 14.

## Evidence and acceptance checks

Persist the goal/version, requirement identifiers, iteration number, invocation
events, structured result or error, verifier identity and result, artifact hashes
where applicable, and host stopping decision. Distinguish intermediate iteration
results from the coordinator's final session RESULT. A storage failure must stop
execution through the client's cleanup path rather than silently lose evidence.

Implementation acceptance requires tests demonstrating:

- An early model success with unmet requirements triggers another iteration.
- Multiple iterations finish only when all host verifiers pass.
- Changed final artifacts invalidate earlier verification of those artifacts.
- Unknown requirements, malformed output, and verifier errors cannot yield success.
- Iteration, time, output, and no-progress limits stop with incomplete evidence.
- Cancellation, uncertain cleanup, and restart cannot create overlapping runs.
- Storage failure stops execution and preserves already committed observations.
- Proposed source changes remain subject to the gatekeeper and Phase 10 checks.

A live demonstration must retain at least two iterations and show the unmet
requirement after the first, the final verification evidence, and the resulting
session/issue states. Passing simulated tests alone cannot complete the Phase 8
live goal-loop milestone.
