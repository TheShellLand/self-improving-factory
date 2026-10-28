# Distributed architecture

The parent owns scheduling, SQLite state, and the Git gatekeeper. Sibling Docker
containers execute tasks with an explicit viewport. Docker daemon access belongs
to the parent; children do not receive the socket or parent source checkout.

The intended agent adapter communicates through `pi --mode rpc`. The current
executor runs explicit host-selected argument lists and the coordinator accepts
an injected async runner. Neither is a completed pi protocol adapter.

SQLite holds issues, sessions, signals, proposal status, and strategy updates.
Git holds source snapshots. CommitService links a session to a Git commit through
PREPARED/APPLIED/FAILED audit records. Git and SQLite are separate transactional
systems; interrupted intent requires reconciliation before another proposal.

GatekeeperVault is required for parent source modifications. Agents provide
filenames, full replacement contents, and a commit message as data. The parent
validates and applies them through GitPython in an exclusively owned clean checkout.
Validation does not replace OS isolation or establish crash-safe atomicity.

The browser interface will expose reports, votes, audit, and human controls.
Currently only its API is implemented. See PROJECT.md for each phase's verified
capabilities and remaining acceptance criteria.
