## Signal Propagation Map
The SASIAS system follows a strictly unidirectional flow from user intent to observation, creating an immutable trail that fuels the Evolution engine. Every action is mapped as follows:

### 1. Request Layer (Chat Bridge)
*   **Source**: User Browser / Frontend UI.
*   **Action**: Human input signal or automated request entry ("Report Bug").
*   **Ingestion Logic**: The **Chat Bridge** captures raw signals including `client_viewport` and standardizes they into initial components of our RPC pulse protocol (`SignalPulse`).
*   **Destination/Log**: Injected into `history_vault.db` in the `trace_signals` table with type 'INPUT'.
    * *Metadata captured*: `$w`, `$h$`, browser path, user timestamp.

### 2. Orchestration Layer (Parent Core)
*   **Processing Engine**: The Parent Container processes an allowed subset of "Input" logs to determine appropriate sub-tasks or issues priorities ($+/-$).
*   **Action Output**: The **ExecutorCore** receives a task ID from the bridge signal and proceeds to provision resources for child containers using `/var/run/docker.sock`.
*   **Bridge Communication**: Task initialization results are prepended as new signals in `trace_signals` via the RPC loop backend logic (`pi --mode rpc`).

### 3. Sandbox Execution Layer (Child Subagents)
*   **Subagent Run**: Spun up with environment standardization rules applied at launch time: Force $1920 \times 1080$ viewport resolutions unless specific overrides exist or were injected by high-level human perspective captures.
*   **Realtime Pulses**: During execution, subagents pulse pulses back to Parent containers using `--mode rpc`. These include standard telemetry and optional `base64` visual reports for observation logs ($w$, $h$).
    * *Output*: Logged into the vault as 'OBSERVATION' / 'RESULT'.

### 4. Reflection & Gateway Layer (Gatekeeper/Critic)
*   **Observation Analysis**: The **ObserverModule** consumes valid results from child agents; it tags successes versus friction points.
*   **Decision Outcome**: If a failure or bug is verified during reflection, the logic reaches the **GatekeeperVault**.
*   **Version Control Execution**: Only here does actual state change occur in Git via internal library calls (`GitPython`), ensuring that LLM-generated diffs are sanitized and applied according to atomic commit rules without direct shell access for source control commands!
    * *Log Closing*: Final signal pulse marks completion / closure of 'ACTION_START' signals with final execution status (SUCCESS/FAILURE).

---
### Verifiable Flow Summary: 
$\text{Chat Bridge} \rightarrow \text{history\_vault.db (INPUT)} \xrightarrow{\text{Parent Logic}} \text{Docker Launch ($\dots$ RPC pulses $\dots$)} \rightarrow \text{history\_vault.db (OBSERVATION, RESULT)}$
