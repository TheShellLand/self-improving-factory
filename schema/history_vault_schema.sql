-- Database Schema Initialization for SASIAS History Vault

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS trace_signals (
    signal_id TEXT PRIMARY KEY,        -- UUIDv4 from SignalPulse class
    timestamp REAL NOT NULL,            -- UTC float time
    source_agent TEXT NOT NULL,         -- Source agent name ID
    action_type TEXT CHECK(action_type IN ('INPUT', 'ACTION_START', 'OBSERVATION', 'RESULT', 'REFLECTION')), 
    payload TEXT,                      -- Primary signal data packet as JSON string
    metadata TEXT                       -- Viewport context and system metadata ($w \times h$) of input/state view
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,       -- Execution/Session UUID
    start_time REAL NOT NULL,
    end_time REAL,
    status TEXT CHECK(status IN ('INITIATED', 'RUNNING', 'COMPLETED', 'FAILED')) ,
    success BOOLEAN DEFAULT TRUE,
    execution_summary TEXT              -- Log of results or crash error types
);

CREATE TABLE IF NOT EXISTS knowledge_updates (
    update_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applied_at REAL NOT NULL,
    version_number INTEGER NOT NULL,
    logic_description TEXT,             -- Describe why the update was made by Critic/Evolution engine
    prompt_weights TEXT                 -- Current adjusted prompt weights for specific models as JSON string
);

CREATE TABLE IF NOT EXISTS issues (
    issue_id TEXT PRIMARY KEY,         -- Unique issue tracking ID 
    title TEXT,                        -- Short desc from human input or log detection
    content TEXT,                      -- Context blob with raw state
    status TEXT CHECK(status IN ('OPEN', 'WAITING', 'IN PROGRESS', 'REJECTED', 'CLOSED', 'FAILED')),
    priority_score REAL DEFAULT 0.5,   -- Base logic score based on voting counts (+/-)
    viewport_snapshot TEXT              -- Metadata captured at bug report time ($w \times h$)
);

INSERT OR IGNORE INTO trace_signals (signal_id, timestamp, source_agent, action_type, payload, metadata) VALUES (
'INIT-SYSTEM-SYNC', strftime('%s','now'), 'orchestrator', 'ACTION_START', 
'{"meta": "system initialization"}', 
'{"requesting_resolution": [1920, 1080]}'
);
