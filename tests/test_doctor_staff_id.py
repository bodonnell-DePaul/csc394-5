"""Regression tests for the extra doctor staff-ID sign-in requirement."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.routes import database
from src.routes.auth import seed_demo_accounts
from src.server.main import create_app


class DoctorStaffIdAuthenticationTests(unittest.TestCase):
    def setUp(self):
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        db_patch = patch.object(
            database, "DB_PATH", Path(temporary_dir.name) / "doctor-auth.db"
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def login(self, email, password, doctor_staff_id=None):
        data = {"email": email, "password": password}
        if doctor_staff_id is not None:
            data["doctor_staff_id"] = doctor_staff_id
        return self.client.post("/api/auth/login", json=data)

    def test_doctor_cannot_sign_in_without_matching_staff_id(self):
        for staff_id in (None, "", "000000", "742618", "not-a-number"):
            with self.subTest(staff_id=staff_id):
                response = self.login(
                    "doctor@example.com", "DoctorPassword123!", staff_id
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(
            self.login("doctor@example.com", "Incorrect", "742619").status_code,
            401,
        )

    def test_valid_doctor_staff_id_allows_doctor_dashboard(self):
        response = self.login(
            "doctor@example.com", "DoctorPassword123!", "742619"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "doctor")
        self.assertNotIn("doctor_staff_id", response.json()["user"])
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertNotIn("doctor_staff_id", me.json()["user"])
        self.assertEqual(self.client.get("/api/doctor/patients").status_code, 200)

    def test_patient_login_unchanged_and_staff_id_cannot_bypass_role(self):
        doctor_mode = self.login(
            "patient@example.com", "PatientPassword123!", "742619"
        )
        self.assertEqual(doctor_mode.status_code, 401)
        normal = self.login("patient@example.com", "PatientPassword123!")
        self.assertEqual(normal.status_code, 200)
        self.assertEqual(self.client.get("/api/doctor/patients").status_code, 403)

    def test_staff_ids_are_unique_per_doctor_and_required_for_new_doctors(self):
        with self.assertRaisesRegex(ValueError, "require a staff ID"):
            database.create_user("unprovisioned@example.com", "hash", role="doctor")
        with self.assertRaisesRegex(ValueError, "cannot have doctor staff"):
            database.create_user(
                "invalidpatient@example.com", "hash", doctor_staff_id="123456"
            )
        with self.assertRaisesRegex(ValueError, "six digits"):
            database.create_user(
                "badid@example.com", "hash", role="doctor", doctor_staff_id="ABC"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            database.create_user(
                "duplicate@example.com", "hash",
                role="doctor", doctor_staff_id="742619"
            )

    def test_staff_id_is_tied_to_the_correct_doctor(self):
        database.create_user(
            "otherdoctor@example.com",
            "unusable-hash",
            role="doctor",
            doctor_staff_id="000014",
        )
        self.assertEqual(
            self.login("doctor@example.com", "DoctorPassword123!", "000014")
            .status_code,
            401,
        )

    def test_seed_accounts_keep_id_on_repeated_startup(self):
        existing = database.get_user_by_email("doctor@example.com")
        seed_demo_accounts()
        updated = database.get_user_by_email("doctor@example.com")
        self.assertEqual(updated["id"], existing["id"])
        self.assertEqual(updated["doctor_staff_id"], "742619")


class DoctorStaffIdMigrationTests(unittest.TestCase):
    def test_legacy_doctor_account_gets_id_without_losing_password(self):
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        db_patch = patch.object(
            database, "DB_PATH", Path(temporary_dir.name) / "legacy.db"
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        with closing(database.get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    patient_id TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                ("doctor@example.com", "legacy-hash", "doctor"),
            )
            conn.commit()

        database.init_db()
        seed_demo_accounts()
        doctor = database.get_user_by_email("doctor@example.com")
        self.assertEqual(doctor["doctor_staff_id"], "742619")
        self.assertEqual(doctor["password_hash"], "legacy-hash")
        with closing(database.get_connection()) as conn:
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(users)")
            }
        self.assertIn("doctor_staff_id", columns)


if __name__ == "__main__":
    unittest.main()
