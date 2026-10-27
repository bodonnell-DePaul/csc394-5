"""Tests for the authenticated doctor-review workflow."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import FIXED_PATIENT_ID
from src.routes import database
from src.routes.auth import password_hasher
from src.server.main import create_app


class DoctorDashboardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        db_patch = patch.object(
            database, "DB_PATH", Path(temp.name) / "test.db"
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

        database.create_user(
            email="patient@example.com",
            password_hash=password_hasher.hash("PatientPassword123!"),
            role="patient",
            patient_id=FIXED_PATIENT_ID,
        )

        database.create_user(
            email="doctor@example.com",
            password_hash=password_hasher.hash("DoctorPassword123!"),
            role="doctor",
        )

    def login(self, role):
        credentials = {
            "patient": ("patient@example.com", "PatientPassword123!"),
            "doctor": ("doctor@example.com", "DoctorPassword123!"),
        }
        email, password = credentials[role]

        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200)

    def test_doctor_can_review_and_save_notes(self):
        self.login("patient")

        created = self.client.post(
            "/api/symptom_report",
            json={
                "symptoms": ["Headache"],
                "notes": "Woke with a headache",
            },
        )
        self.assertEqual(created.status_code, 201)
        report_id = created.json()["report"]["id"]

        # Patients must not access doctor-only endpoints.
        forbidden = self.client.get("/api/doctor/dashboard")
        self.assertEqual(forbidden.status_code, 403)

        self.client.post("/api/auth/logout")
        self.login("doctor")

        dashboard = self.client.get("/api/doctor/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["review_counts"]["pending"], 1)
        self.assertEqual(
            dashboard.json()["reports"][0]["review_status"], "pending"
        )

        reviewed = self.client.patch(
            f"/api/doctor/reports/{report_id}",
            json={
                "review_status": "reviewed",
                "doctor_note": "  Follow up at next visit  ",
            },
        )
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(
            reviewed.json()["report"]["doctor_note"],
            "Follow up at next visit",
        )

        refreshed = self.client.get("/api/doctor/dashboard").json()
        self.assertEqual(refreshed["review_counts"]["reviewed"], 1)
        self.assertEqual(
            refreshed["reports"][0]["review_status"], "reviewed"
        )

        # Doctor accounts must not access patient-only endpoints.
        patient_endpoint = self.client.get("/api/symptom_report")
        self.assertEqual(patient_endpoint.status_code, 403)

        self.client.post("/api/auth/logout")
        self.login("patient")

        patient = self.client.get("/api/symptom_report").json()
        self.assertNotIn("doctor_note", patient["reports"][0])

    def test_missing_report_and_invalid_status(self):
        # Unauthenticated requests are rejected.
        unauthenticated = self.client.get("/api/doctor/dashboard")
        self.assertEqual(unauthenticated.status_code, 401)

        self.login("doctor")

        missing = self.client.patch(
            "/api/doctor/reports/9999",
            json={"review_status": "reviewed", "doctor_note": ""},
        )
        self.assertEqual(missing.status_code, 404)

        invalid = self.client.patch(
            "/api/doctor/reports/1",
            json={"review_status": "urgent", "doctor_note": ""},
        )
        self.assertEqual(invalid.status_code, 422)