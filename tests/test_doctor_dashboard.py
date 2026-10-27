"""Tests for the synthetic doctor-review workflow."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.routes import database
from src.server.main import create_app


class DoctorDashboardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db_patch = patch.object(database, "DB_PATH", Path(temp.name) / "test.db")
        db_patch.start()
        self.addCleanup(db_patch.stop)
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_doctor_can_review_and_save_notes(self):
        created = self.client.post("/api/symptom_report", json={
            "symptoms": ["Headache"], "notes": "Woke with a headache"
        })
        self.assertEqual(created.status_code, 201)
        report_id = created.json()["report"]["id"]
        dashboard = self.client.get("/api/doctor/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["review_counts"]["pending"], 1)
        self.assertEqual(dashboard.json()["reports"][0]["review_status"], "pending")
        reviewed = self.client.patch(f"/api/doctor/reports/{report_id}", json={
            "review_status": "reviewed", "doctor_note": "  Follow up at next visit  "
        })
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["report"]["doctor_note"], "Follow up at next visit")
        refreshed = self.client.get("/api/doctor/dashboard").json()
        self.assertEqual(refreshed["review_counts"]["reviewed"], 1)
        self.assertEqual(refreshed["reports"][0]["review_status"], "reviewed")
        patient = self.client.get("/api/symptom_report").json()
        self.assertNotIn("doctor_note", patient["reports"][0])

    def test_missing_report_and_invalid_status(self):
        missing = self.client.patch("/api/doctor/reports/9999", json={
            "review_status": "reviewed", "doctor_note": ""
        })
        self.assertEqual(missing.status_code, 404)
        invalid = self.client.patch("/api/doctor/reports/1", json={
            "review_status": "urgent", "doctor_note": ""
        })
        self.assertEqual(invalid.status_code, 422)
