import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from fastapi.testclient import TestClient
from core.database import initialize_database
from ui_backend.bridge import create_app


class TestUIBridge(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "vault.db"
        self.client = self.enterContext(TestClient(create_app(self.db)))

    def test_report_persists_and_initialization_preserves_data(self):
        response = self.client.post("/api/report-bug", json={
            "title": "Broken task", "description": "Details",
            "client_viewport": {"width": 1920, "height": 1080},
            "context_blob": {"session_id": "session-1"},
        })
        self.assertEqual(response.status_code, 200)
        initialize_database(self.db)
        issues = self.client.get("/api/issues").json()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue_id"], response.json()["issue_id"])
        self.assertEqual(json.loads(issues[0]["content"])["description"], "Details")
        audit = self.client.get("/api/audit-trail").json()
        self.assertEqual(len(audit), 2)
        self.assertTrue(any(row["action_type"] == "INPUT" for row in audit))

    def test_invalid_report_is_rejected(self):
        self.assertEqual(self.client.post("/api/report-bug", json={"title": ""}).status_code, 422)

    def test_priority_order(self):
        for priority in [2, 10]:
            self.client.post("/api/report-bug", json={
                "title": str(priority), "description": "", "priority": priority})
        self.assertEqual([row["priority_score"] for row in self.client.get("/api/issues").json()], [10, 2])

    def test_votes_and_viewport_validation(self):
        response = self.client.post("/api/report-bug", json={
            "title": "Issue", "description": "Details", "client_viewport": {"width": 0}})
        self.assertEqual(response.status_code, 422)
        issue = self.client.post("/api/report-bug", json={"title": "Issue", "description": "Details"}).json()
        endpoint = f"/api/issues/{issue['issue_id']}/vote"
        self.assertEqual(self.client.post(endpoint, json={"delta": 1}).status_code, 200)
        self.assertEqual(self.client.post(endpoint, json={"delta": 7}).status_code, 422)
        self.assertEqual(self.client.get("/api/issues").json()[0]["priority_score"], 11)
        self.assertEqual(self.client.get("/api/sessions").json(), [])
