"""Tests for patient-owned medication records and report integration."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import FIXED_PATIENT_ID
from src.routes import database
from src.routes.auth import password_hasher
from src.server.main import create_app


class MedicationWorkflowTests(unittest.TestCase):
    """Exercise medication permissions and report integration through the API."""

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

        # App startup seeds demo users; create them only if startup did not.
        if database.get_user_by_email("patient@example.com") is None:
            database.create_user(
                email="patient@example.com",
                password_hash=password_hasher.hash("PatientPassword123!"),
                role="patient",
                patient_id=FIXED_PATIENT_ID,
            )
        if database.get_user_by_email("doctor@example.com") is None:
            database.create_user(
                email="doctor@example.com",
                password_hash=password_hasher.hash("DoctorPassword123!"),
                role="doctor",
            )

    def login(self, role):
        """Authenticate as one of the patient/doctor test users."""
        email = f"{role}@example.com"
        password = f"{role.title()}Password123!"
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200)

    def add_medication(self, **overrides):
        """Create a valid medication request with optional field overrides."""
        payload = {
            "name": "Example medication",
            "dosage_value": 10,
            "dosage_unit": "mg",
            "frequency": "once daily",
            "instructions": "Take with food",
        }
        payload.update(overrides)
        return self.client.post("/api/doctor/medications", json=payload)

    def test_medication_routes_require_the_correct_role(self):
        """Require authentication for reads and doctor access for writes."""
        self.assertEqual(self.client.get("/api/medications").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/doctor/medications",
                json={
                    "name": "Example medication",
                    "dosage_value": 10,
                    "dosage_unit": "mg",
                },
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.patch(
                "/api/doctor/medications/1",
                json={"dosage_value": 10, "dosage_unit": "mg"},
            ).status_code,
            401,
        )

        self.login("patient")
        self.assertEqual(self.client.get("/api/medications").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/doctor/medications",
                json={
                    "name": "Example medication",
                    "dosage_value": 10,
                    "dosage_unit": "mg",
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                "/api/doctor/medications/1",
                json={"dosage_value": 10, "dosage_unit": "mg"},
            ).status_code,
            403,
        )

    def test_patient_can_review_medications_but_only_doctor_can_change_them(self):
        """Patients can read their list, but only doctors can add or edit entries."""
        self.login("patient")

        forbidden_add = self.add_medication()
        self.assertEqual(forbidden_add.status_code, 403)
        self.assertEqual(
            self.client.get("/api/medications").json(),
            {"medications": []},
        )

        self.client.post("/api/auth/logout")
        self.login("doctor")
        added = self.add_medication()
        self.assertEqual(added.status_code, 201)
        medication = added.json()["medication"]
        self.assertEqual(medication["patient_id"], FIXED_PATIENT_ID)
        self.assertTrue(medication["active"])

        self.client.post("/api/auth/logout")
        self.login("patient")
        listed = self.client.get("/api/medications")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["medications"], [medication])

        # Directly calling the doctor endpoint as a patient must be forbidden.
        forbidden_update = self.client.patch(
            f"/api/doctor/medications/{medication['id']}",
            json={
                "dosage_value": 20,
                "dosage_unit": "mg",
            },
        )
        self.assertEqual(forbidden_update.status_code, 403)
        forbidden_patient_write = self.client.post(
            "/api/medications",
            json={"name": "Patient-created medication"},
        )
        self.assertEqual(forbidden_patient_write.status_code, 405)

    def test_report_automatically_saves_all_active_medication_snapshots(self):
        """Reports include all active medications and preserve their submitted details."""
        self.login("doctor")
        added = self.add_medication()
        medication = added.json()["medication"]
        second_added = self.add_medication(
            name="Second medication",
            dosage_value=25,
            dosage_unit="mcg",
            frequency="twice daily",
        )
        second_medication = second_added.json()["medication"]
        inactive_added = self.add_medication(
            name="Discontinued medication",
            dosage_value=2,
            dosage_unit="mg",
            active=False,
        )
        inactive_medication = inactive_added.json()["medication"]
        self.client.post("/api/auth/logout")
        self.login("patient")

        report_response = self.client.post(
            "/api/symptom_report",
            json={
                "symptoms": ["Nausea"],
                "notes": "Felt unwell after taking it",
            },
        )
        self.assertEqual(report_response.status_code, 201)
        report = report_response.json()["report"]
        self.assertEqual(
            report["medications"],
            [
                {
                    "id": medication["id"],
                    "name": "Example medication",
                    "dosage_value": 10,
                    "dosage_unit": "mg",
                    "frequency": "once daily",
                },
                {
                    "id": second_medication["id"],
                    "name": "Second medication",
                    "dosage_value": 25,
                    "dosage_unit": "mcg",
                    "frequency": "twice daily",
                },
            ],
        )
        self.assertNotIn(
            inactive_medication["id"],
            [entry["id"] for entry in report["medications"]],
        )
        self.assertEqual(
            self.client.post(
                "/api/symptom_report",
                json={
                    "symptoms": ["Nausea"],
                    "medication_id": inactive_medication["id"],
                },
            ).status_code,
            422,
        )

        self.client.post("/api/auth/logout")
        self.login("doctor")
        updated = self.client.patch(
            f"/api/doctor/medications/{medication['id']}",
            json={
                "dosage_value": 20,
                "dosage_unit": "mg",
                "frequency": "twice daily",
                "instructions": "Updated directions",
                "active": True,
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["medication"]["name"], "Example medication")
        dashboard = self.client.get("/api/doctor/dashboard").json()
        self.assertEqual(
            dashboard["reports"][0]["medications"][0]["dosage_value"],
            10,
        )
        # Names are immutable once the medication record has been created.
        attempted_rename = self.client.patch(
            f"/api/doctor/medications/{medication['id']}",
            json={
                "name": "Renamed medication",
                "dosage_value": 20,
                "dosage_unit": "mg",
            },
        )
        self.assertEqual(attempted_rename.status_code, 422)

        self.client.post("/api/auth/logout")
        self.login("patient")
        listed = self.client.get("/api/symptom_report").json()
        self.assertEqual(
            listed["reports"][0]["medications"][0]["dosage_value"],
            10,
        )

        self.client.post("/api/auth/logout")
        self.login("doctor")
        discontinued = self.client.patch(
            f"/api/doctor/medications/{medication['id']}",
            json={
                "dosage_value": 20,
                "dosage_unit": "mg",
                "frequency": "twice daily",
                "instructions": "Updated directions",
                "active": False,
            },
        )
        self.assertEqual(discontinued.status_code, 200)
        self.client.post("/api/auth/logout")
        self.login("patient")
        after_discontinue = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Nausea"]},
        )
        self.assertEqual(after_discontinue.status_code, 201)
        later_report = after_discontinue.json()["report"]
        self.assertEqual(
            [entry["id"] for entry in later_report["medications"]],
            [second_medication["id"]],
        )

    def test_report_without_active_medications_submits_without_snapshot(self):
        """Allow symptom submissions when the patient has no active medications."""
        self.login("patient")
        response = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Nausea"]},
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("medications", response.json()["report"])

    def test_medication_api_validates_values_and_patient_scope(self):
        """Invalid fields fail validation and medications stay patient-scoped."""
        self.login("doctor")
        invalid = self.add_medication(
            name="   ",
            dosage_value="Infinity",
        )
        self.assertEqual(invalid.status_code, 422)

        other_patient_medication = database.create_patient_medication(
            "another-patient",
            "Other patient's medication",
            5,
            "mg",
            "daily",
            "",
        )
        missing = self.client.patch(
            f"/api/doctor/medications/{other_patient_medication['id']}",
            json={
                "dosage_value": 6,
                "dosage_unit": "mg",
            },
        )
        self.assertEqual(missing.status_code, 404)

        # Even a doctor cannot attach a different patient's medication to this
        # patient's symptom report.
        self.client.post("/api/auth/logout")
        self.login("patient")
        cross_patient_report = self.client.post(
            "/api/symptom_report",
            json={
                "symptoms": ["Nausea"],
                "medication_id": other_patient_medication["id"],
            },
        )
        self.assertEqual(cross_patient_report.status_code, 422)

        self.client.post("/api/auth/logout")
        self.login("doctor")
        invalid_update = self.client.patch(
            "/api/doctor/medications/1",
            json={
                "dosage_value": 5,
                "dosage_unit": "ounces",
            },
        )
        self.assertEqual(invalid_update.status_code, 422)
