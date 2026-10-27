import sqlite3
from typing import List, Dict, Any
import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

logger = logging.getLogger("BridgeAPI")
logging.basicConfig(level=logging.INFO)

# This represents the path to our local audit trail database
DB_PATH = "/root/brain/history_vault.db"

from pydantic import BaseModel

class BugReport(BaseModel):
    title: str
    description: str
    path_depth: int
    client_viewport: Dict[str, int]
    context_blob: Dict[str, Any]

@app.get("/api/audit-trail")
async def get_audit_trail():
    """Retrieves raw firehose of signals from trace_signals table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Fetching latest 100 for UI display performance
        cur.execute("SELECT * FROM trace_signals ORDER BY timestamp DESC LIMIT 100")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching audit trail: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/api/report-bug")
async def report_bug(data: dict):
    """Captures user reports and inserts them into the IMS issue queue."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Standardizing inputs based on Phase 2 & Project Specs requirements (w*h included)
        query = """INSERT INTO issues (title, description, context_blob, status, priority_score)
                    VALUES (?, ?, ?, 'OPEN', ?)"""
        
        priority = data.get('priority', 10.0) # Default to high for immediate attention
        cur.execute(query, (data['title'], data['description'], json.dumps(data), priority))
        conn.commit()
        return {"status": "recorded", "issue_id": cur.lastrowid}
    except Exception as e:
        logger.error(f"Error reporting bug via Bridge UI: {e}")
        raise HTTPException(status_code=500, detail="Persistence failed")

@app.get("/api/issues")
async def list_priority_issues():
    """Retrieves and sorts issues by status in the voting lifecycle."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Fetching OPEN or WAITING to showcase priority sorting for human triage loop
        cur.execute("SELECT * FROM issues WHERE status IN ('OPEN', 'WAITING') ORDER BY priority_score DESC LIMIT 20")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listing issues: {e}")
        raise HTTPException(status_code=500, detail="Persistence failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
