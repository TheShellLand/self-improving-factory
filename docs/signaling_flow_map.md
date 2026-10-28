# Signal and state flow

1. The API validates a report. The vault inserts its issue and INPUT signal in
   one SQLite transaction.
2. The coordinator exclusively claims the next issue, records its RUNNING session
   and ACTION_START, and loads the current configuration.
3. A host-supplied async runner executes the task. Its structured outcome becomes
   OBSERVATION and RESULT events with the host-assigned session ID.
4. Successful code proposals pass through CommitService and GatekeeperVault.
   PREPARED intent and ACTION_START precede Git changes; APPLIED/FAILED and a
   gatekeeper RESULT follow. Unresolved intent blocks another proposal.
5. The reflection provider sees exact-session evidence. A session-scoped update
   and REFLECTION signal are committed together, then loaded by insertion ID.
6. The vault records the pipeline RESULT and final session/issue states together.

Runner exceptions produce FAILED attempts. A failed execution cannot apply code
changes. A reflection failure after a Git commit does not undo that commit; the
audit record retains its hash. Cancellation retains RUNNING state for recovery.

The live pi RPC adapter, continuous scheduler, browser controls, and recovery UI
remain acceptance gaps. `tests/test_coordinator.py` verifies this flow using an
injected runner, not an external model.
