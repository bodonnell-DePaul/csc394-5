"""Tests for the authenticated doctor-review workflow."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import FIXED_PATIENT_ID
from src.routes import database
from src.routes.auth import seed_demo_accounts
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

    def test_demo_accounts_are_seeded_and_seeding_is_idempotent(self):
        patient = database.get_user_by_email("patient@example.com")
        doctor = database.get_user_by_email("doctor@example.com")

        self.assertIsNotNone(patient)
        self.assertEqual(patient["role"], "patient")
        self.assertIsNotNone(doctor)
        self.assertEqual(doctor["role"], "doctor")

        seed_demo_accounts()

        self.assertEqual(
            database.get_user_by_email("patient@example.com")["id"],
            patient["id"],
        )
        self.assertEqual(
            database.get_user_by_email("doctor@example.com")["id"],
            doctor["id"],
        )
        self.login("patient")
        self.client.post("/api/auth/logout")
        self.login("doctor")

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

    def test_dashboard_paginates_and_includes_review_details(self):
        first = database.save_symptom_report(
            FIXED_PATIENT_ID, ["Nausea"], "First patient note"
        )
        second = database.save_symptom_report(
            FIXED_PATIENT_ID, ["Headache"], "Second patient note"
        )
        third = database.save_symptom_report(
            FIXED_PATIENT_ID, ["Fatigue"], "Third patient note"
        )
        database.update_report_review(
            second["id"], FIXED_PATIENT_ID, "reviewed", "Check in tomorrow"
        )
        self.login("doctor")

        response = self.client.get(
            "/api/doctor/dashboard",
            params={"limit": 1, "offset": 1},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body["patient"]), {"id", "email"})
        self.assertEqual(body["patient"]["id"], FIXED_PATIENT_ID)
        self.assertEqual(body["summary"]["total_reports"], 3)
        self.assertEqual(body["review_counts"], {"pending": 2, "reviewed": 1})
        self.assertEqual(body["page"], {"limit": 1, "offset": 1, "total": 3})
        self.assertEqual(len(body["reports"]), 1)
        self.assertEqual(
            body["reports"][0],
            {
                **second,
                "review_status": "reviewed",
                "doctor_note": "Check in tomorrow",
            },
        )
        self.assertNotEqual(body["reports"][0]["id"], first["id"])
        self.assertNotEqual(body["reports"][0]["id"], third["id"])

    def test_review_endpoint_rejects_patients_and_oversized_notes(self):
        report = database.save_symptom_report(FIXED_PATIENT_ID, ["Nausea"])
        self.login("patient")

        forbidden = self.client.patch(
            f"/api/doctor/reports/{report['id']}",
            json={"review_status": "reviewed", "doctor_note": "Not allowed"},
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.post("/api/auth/logout")
        self.login("doctor")
        invalid_note = self.client.patch(
            f"/api/doctor/reports/{report['id']}",
            json={"review_status": "reviewed", "doctor_note": "x" * 1001},
        )
        self.assertEqual(invalid_note.status_code, 422)

        reports, total = database.list_symptom_reports(
            FIXED_PATIENT_ID, limit=20, offset=0, include_doctor_notes=True
        )
        self.assertEqual(total, 1)
        self.assertEqual(reports[0]["review_status"], "pending")
        self.assertEqual(reports[0]["doctor_note"], "")

    def test_doctor_routes_require_auth_and_validate_pagination_and_report_id(self):
        unauthenticated_review = self.client.patch(
            "/api/doctor/reports/1",
            json={"review_status": "reviewed", "doctor_note": ""},
        )
        self.assertEqual(unauthenticated_review.status_code, 401)

        self.login("doctor")
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.subTest(params=params):
                response = self.client.get(
                    "/api/doctor/dashboard",
                    params=params,
                )
                self.assertEqual(response.status_code, 422)

        invalid_report_id = self.client.patch(
            "/api/doctor/reports/not-a-number",
            json={"review_status": "reviewed", "doctor_note": ""},
        )
        self.assertEqual(invalid_report_id.status_code, 422)

    def test_empty_doctor_note_is_saved_when_reviewing_report(self):
        report = database.save_symptom_report(
            FIXED_PATIENT_ID, ["Nausea"], "Patient report note"
        )
        self.login("doctor")

        response = self.client.patch(
            f"/api/doctor/reports/{report['id']}",
            json={"review_status": "reviewed", "doctor_note": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report"]["review_status"], "reviewed")
        self.assertEqual(response.json()["report"]["doctor_note"], "")
        reports, total = database.list_symptom_reports(
            FIXED_PATIENT_ID,
            limit=20,
            offset=0,
            include_doctor_notes=True,
        )
        self.assertEqual(total, 1)
        self.assertEqual(reports[0]["doctor_note"], "")
        self.assertEqual(reports[0]["review_status"], "reviewed")

    def test_doctor_note_at_maximum_length_is_accepted(self):
        report = database.save_symptom_report(FIXED_PATIENT_ID, ["Headache"])
        note = "x" * 1000
        self.login("doctor")

        response = self.client.patch(
            f"/api/doctor/reports/{report['id']}",
            json={"review_status": "reviewed", "doctor_note": note},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report"]["doctor_note"], note)
        reports, total = database.list_symptom_reports(
            FIXED_PATIENT_ID,
            limit=20,
            offset=0,
            include_doctor_notes=True,
        )
        self.assertEqual(total, 1)
        self.assertEqual(reports[0]["doctor_note"], note)