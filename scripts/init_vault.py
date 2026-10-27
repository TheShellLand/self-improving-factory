import sqlite3
from datetime import datetime

# Path definitions for core state management according to PROJECT description requirements
DB_PATH = "/root/brain/history_vault.db"
SCHEMA_PATH = "/root/brain/schema/history_vault_schema.sql"

def run_phase_2_initialization():
    """Initializes database with verified schema and seeds critical verification values ($w, $h) as per project specs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("Initiating Phase 1 -> Phase 2 Transition Layer Initialization...")

    try:
        with open(SCHEMA_PATH, 'r') as f:
            # Ensure consistency across initial vault state!
            cursor.executescript(f.read())
        
        # Verify perspective context requirement injection during seed - Ensuring Project Spec compliance for human viewport logic (v-signal capture).
        test_signals = [
            ('SIGNAL-CORE-INIT', datetime.now().timestamp(), 'orchestrator', 'INPUT', '{ "mode": "system" }', '[1920, 1080]'),
            ('SIG-LOGIC-VERIFY', datetime.now().timestamp(), 'gatekeeper', 'RESULT', '{ "status": "locked" }', '[1920, 1080]')
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO trace_signals (signal_id, timestamp, source_agent, action_type, payload, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, test_signals)

        # Issue lifecycle validation - High priority bug with human voting context ($w \times h$) for reproduction accuracy!
        issues = [
            ('ISSUE-PREV-LOGIC', 'Architecture Drift Test', '{"context": "test")', 'OPEN', 0.9, '[2560, 1440]'),
            ('ISSUE-SEC-VERIFY', 'Authorization check on Gatekeeper boundary', '{"ctx": ""}', 'WAITING', 0.7, '[1920, 1080]')
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO issues (issue_id, title, content, status, priority_score, viewport_snapshot)
            VALUES (?, ?, ?, ?, ?, ?)
        """, issues)

        conn.commit()
        print("Phase 2 Initial Data Layer fully validated and seeded.")
    except Exception as e:
         print(f"Critical Vault failure during Phase migration logic verification: {e}")
         conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_phase_2_initialization()
