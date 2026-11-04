import logging
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.config import FIXED_PATIENT_ID
from src.middleware.schemas import DosageUpdateRequest
from src.routes import database, routes
from src.routes.auth import password_hasher
from src.server.main import create_app


class MedicationSchemaTests(unittest.TestCase):
    def test_dosage_request_normalizes_medication_and_accepts_safe_boundaries(self):
        for dosage in (1, 10):
            with self.subTest(dosage=dosage):
                request = DosageUpdateRequest(
                    medication_name=" Warfarin ",
                    dosage_value=dosage,
                    dosage_unit="mg",
                )

                self.assertEqual(request.medication_name, "warfarin")
                self.assertEqual(request.dosage_value, float(dosage))
                self.assertEqual(request.dosage_unit, "mg")
                self.assertEqual(request.patient_id, FIXED_PATIENT_ID)

    def test_dosage_request_rejects_nonpositive_and_unsafe_doses(self):
        invalid_requests = (
            {"medication_name": "warfarin", "dosage_value": 0, "dosage_unit": "mg"},
            {"medication_name": "warfarin", "dosage_value": -1, "dosage_unit": "mg"},
            {"medication_name": "warfarin", "dosage_value": 0.9, "dosage_unit": "mg"},
            {"medication_name": "warfarin", "dosage_value": 10.1, "dosage_unit": "mg"},
        )

        for request in invalid_requests:
            with self.subTest(request=request):
                with self.assertRaises(ValidationError):
                    DosageUpdateRequest(**request)

    def test_dosage_request_requires_medication_name_value_and_unit(self):
        for request in (
            {"medication_name": "", "dosage_value": 5, "dosage_unit": "mg"},
            {"medication_name": "warfarin", "dosage_unit": "mg"},
            {"medication_name": "warfarin", "dosage_value": 5},
        ):
            with self.subTest(request=request):
                with self.assertRaises(ValidationError):
                    DosageUpdateRequest(**request)

class MedicationDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path = Path(self.temp_dir.name) / "healthwatch-test.db"
        self.database_path_patch = patch.object(
            database, "DB_PATH", self.database_path
        )
        self.database_path_patch.start()
        self.addCleanup(self.database_path_patch.stop)
        database.init_db()

    def test_init_db_creates_patient_scoped_prescriptions_table(self):
        with closing(database.get_connection()) as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(prescriptions)")
            }
            unique_indexes = conn.execute(
                "PRAGMA index_list(prescriptions)"
            ).fetchall()
            unique_column_sets = [
                {
                    item["name"]
                    for item in conn.execute(
                        f"PRAGMA index_info({index['name']})"
                    )
                }
                for index in unique_indexes
                if index["unique"]
            ]

        self.assertTrue(
            {
                "patient_id",
                "medication_name",
                "dosage_value",
                "dosage_unit",
                "updated_at",
                "is_active",
            }
            <= columns
        )
        self.assertIn({"patient_id", "medication_name"}, unique_column_sets)

    def test_dosage_upsert_persists_and_updates_one_patient_prescription(self):
        first = database.update_prescription_dosage(
            "patient-a", " Warfarin ", 2, "mg"
        )
        second = database.update_prescription_dosage(
            "patient-a", "WARFARIN", 3, "mg"
        )
        database.update_prescription_dosage("patient-b", "warfarin", 4, "mg")

        with closing(database.get_connection()) as conn:
            rows = conn.execute(
                """
                SELECT patient_id, medication_name, dosage_value, dosage_unit, updated_at
                FROM prescriptions
                ORDER BY patient_id
                """
            ).fetchall()

        self.assertEqual(first["medication_name"], "warfarin")
        self.assertEqual(first["dosage_value"], 2)
        self.assertEqual(second["dosage_value"], 3)
        self.assertEqual(
            [(row["patient_id"], row["medication_name"], row["dosage_value"]) for row in rows],
            [("patient-a", "warfarin", 3), ("patient-b", "warfarin", 4)],
        )
        self.assertEqual(second["updated_at"], rows[0]["updated_at"])
        self.assertGreaterEqual(second["updated_at"], first["updated_at"])

    def test_deactivate_prescription_keeps_record_and_is_patient_scoped(self):
        database.update_prescription_dosage("patient-a", "warfarin", 2, "mg")
        database.update_prescription_dosage("patient-b", "warfarin", 4, "mg")

        self.assertEqual(
            database.deactivate_prescription("patient-a", "warfarin"), 1
        )
        self.assertEqual(
            database.deactivate_prescription("patient-a", "warfarin"), 0
        )

        with closing(database.get_connection()) as conn:
            remaining = conn.execute(
                """
                SELECT patient_id, medication_name, dosage_value, is_active
                FROM prescriptions
                ORDER BY patient_id
                """
            ).fetchall()

        self.assertEqual(
            [
                (
                    row["patient_id"],
                    row["medication_name"],
                    row["dosage_value"],
                    row["is_active"],
                )
                for row in remaining
            ],
            [("patient-a", "warfarin", 2, 0), ("patient-b", "warfarin", 4, 1)],
        )


class MedicationRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path_patch = patch.object(
            database,
            "DB_PATH",
            Path(self.temp_dir.name) / "healthwatch-test.db",
        )
        self.database_path_patch.start()
        self.addCleanup(self.database_path_patch.stop)

        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

        database.create_user(
            email="medication-patient@example.com",
            password_hash=password_hasher.hash("TestPassword123!"),
            patient_id=FIXED_PATIENT_ID,
        )
        database.create_user(
            email="medication-doctor@example.com",
            password_hash=password_hasher.hash("TestPassword123!"),
            role="doctor",
        )
        self.login("patient")

    def login(self, role):
        credentials = {
            "patient": ("medication-patient@example.com", "TestPassword123!"),
            "doctor": ("medication-doctor@example.com", "TestPassword123!"),
        }
        email, password = credentials[role]
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200)

    def test_doctor_can_mark_prescription_inactive_without_deleting_it(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )
        self.client.post("/api/auth/logout")
        self.login("doctor")

        response = self.client.patch(
            "/api/medication",
            json={
                "patient_id": FIXED_PATIENT_ID,
                "medication_name": "warfarin",
                "active": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        with closing(database.get_connection()) as conn:
            prescription = conn.execute(
                """
                SELECT patient_id, medication_name, dosage_value, dosage_unit, is_active
                FROM prescriptions
                WHERE patient_id = ? AND medication_name = ?
                """,
                (FIXED_PATIENT_ID, "warfarin"),
            ).fetchone()
        self.assertEqual(
            tuple(prescription),
            (FIXED_PATIENT_ID, "warfarin", 3, "mg", 0),
        )

    def test_patients_cannot_update_medication(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 4, "mg"
        )
        payload = {
            "patient_id": FIXED_PATIENT_ID,
            "medication_name": "warfarin",
            "active": False,
        }
        update_response = self.client.patch("/api/medication", json=payload)

        self.assertEqual(update_response.status_code, 403)
        with closing(database.get_connection()) as conn:
            prescription = conn.execute(
                """
                SELECT dosage_value, is_active
                FROM prescriptions
                WHERE patient_id = ? AND medication_name = ?
                """,
                (FIXED_PATIENT_ID, "warfarin"),
            ).fetchone()

        self.assertEqual(tuple(prescription), (4, 1))

    def test_medication_cannot_be_deleted(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )
        self.client.post("/api/auth/logout")
        self.login("doctor")

        response = self.client.delete("/api/medication")

        self.assertEqual(response.status_code, 405)
        with closing(database.get_connection()) as conn:
            prescription = conn.execute(
                """
                SELECT dosage_value, is_active
                FROM prescriptions
                WHERE patient_id = ? AND medication_name = ?
                """,
                (FIXED_PATIENT_ID, "warfarin"),
            ).fetchone()
        self.assertEqual(tuple(prescription), (3, 1))

    def test_doctor_cannot_reactivate_an_inactive_prescription(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )
        database.deactivate_prescription(FIXED_PATIENT_ID, "warfarin")
        self.client.post("/api/auth/logout")
        self.login("doctor")

        response = self.client.patch(
            "/api/medication",
            json={
                "patient_id": FIXED_PATIENT_ID,
                "medication_name": "warfarin",
                "active": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        with closing(database.get_connection()) as conn:
            prescription = conn.execute(
                """
                SELECT dosage_value, is_active
                FROM prescriptions
                WHERE patient_id = ? AND medication_name = ?
                """,
                (FIXED_PATIENT_ID, "warfarin"),
            ).fetchone()
        self.assertEqual(tuple(prescription), (3, 0))

    def test_patient_cannot_mark_another_patients_prescription_inactive(self):
        database.update_prescription_dosage("patient-b", "warfarin", 4, "mg")

        update_response = self.client.patch(
            "/api/medication",
            json={
                "patient_id": "patient-b",
                "medication_name": "warfarin",
                "active": False,
            },
        )

        self.assertEqual(update_response.status_code, 403)
        with closing(database.get_connection()) as conn:
            other_patient_prescription = conn.execute(
                """
                SELECT dosage_value, is_active FROM prescriptions
                WHERE patient_id = ? AND medication_name = ?
                """,
                ("patient-b", "warfarin"),
            ).fetchone()
        self.assertEqual(tuple(other_patient_prescription), (4, 1))

    def test_medication_update_requires_authentication_and_delete_is_unsupported(self):
        self.client.post("/api/auth/logout")

        update_response = self.client.patch(
            "/api/medication",
            json={
                "patient_id": FIXED_PATIENT_ID,
                "medication_name": "warfarin",
                "active": False,
            },
        )
        delete_response = self.client.delete("/api/medication")

        self.assertEqual(update_response.status_code, 401)
        self.assertEqual(delete_response.status_code, 405)

   