# Recovery operations

Recovery resolves interrupted state; it never reruns a task, resets Git, removes
files, or infers that a worker is stopped merely because its record is old.

## Host integration

Construct `RecoveryService(database_path, execution_stopped=verifier,
gatekeeper=gatekeeper)` using the same database and explicitly selected repository
as the coordinator. The synchronous verifier accepts a session ID and returns
the boolean `True` only after confirming that its parent task and all associated
child execution have permanently stopped. `False`, missing configuration, errors,
or an uncertain result prevent recovery. Hold exclusive checkout access during
proposal reconciliation. This callback is a trust boundary, not a heartbeat check.

To enable HTTP mutations, pass that service to `create_app` as `recovery_service`
and a synchronous `recovery_actor(request)` callback. The callback must authorize
the operator using the host's authentication system and return their identity,
or raise an HTTP authorization error. Empty identities are rejected. The default
API has no such adapters: inspection is available and mutations return HTTP 503.
Do not replace these adapters with unconditional success callbacks in deployment.

## Workflow

1. Inspect `GET /api/recovery` for RUNNING sessions and PREPARED proposals.
2. Stop and verify the session's parent task and child execution through the host.
3. Reconcile each PREPARED proposal. For an applied change, supply its full current
   HEAD hash. For an unapplied operation, omit the hash. Git must be clean and on
   the recorded branch in the recorded repository.
4. Fail the interrupted session, with an operator reason. This releases its claim
   while retaining a FAILED session and issue for inspection.
5. Explicitly retry the failed issue only if appropriate. A retry creates a later
   execution attempt; it never erases the old session. Issues with APPLIED or
   PREPARED proposals cannot be requeued. Create a follow-up issue for work whose
   code already changed, including failures during later reflection.

| Endpoint | Request body | Result |
| --- | --- | --- |
| `GET /api/recovery` | None | Pending sessions and proposals |
| `POST /api/proposals/{id}/recover` | `reason`, optional `commit_sha` | Verified APPLIED or FAILED proposal |
| `POST /api/sessions/{id}/recover` | `reason` | Interrupted session and issue become FAILED |
| `POST /api/issues/{id}/retry` | `reason` | Eligible failed issue becomes WAITING |

All mutations require host authorization. HTTP 409 means the requested transition
or evidence was rejected; HTTP 422 means the payload is invalid. Repeating an
already completed transition is rejected without duplicating recovery events.

## Evidence and atomicity

Schema version 2 adds `proposal_evidence` without replacing existing proposals.
New intent records capture repository path, branch, original HEAD, commit message,
and SHA-256 hashes of proposed file contents. Source text is not duplicated in
the recovery table. An applied commit must be the current HEAD, directly follow
the recorded revision, match the proposal's message, include no outside changes,
and match proposed file contents and modes. A no-op may match the original HEAD.
An unapplied operation requires unchanged HEAD and a clean checkout.

Legacy PREPARED records lack these fingerprints and cannot be automatically
reconciled. Dirty checkouts, changed branches, unrelated commits, and incomplete
evidence require manual investigation. Recovery makes no changes to Git while
checking these conditions.

Every successful recovery mutation and its operator/reason event are committed
together in SQLite. An audit insertion failure rolls back the state transition.
The stop verifier and exclusive checkout requirement remain host responsibilities;
these checks do not establish a transaction across running processes, Git, and
SQLite. Backup/restore and a production recovery UI are still pending.

## Verification

`tests/test_recovery.py` injects crashes before and after a real temporary Git
commit and verifies recovery against temporary SQLite. It also covers legacy
upgrades, wrong content, dirty/unrelated Git state, unknown worker state, audit
failure, repeated requests, authorization, retry restrictions, and no-op commits.
