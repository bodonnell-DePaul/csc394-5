import hashlib
import logging
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.routes import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database_path = Path(self.temp_dir.name) / "healthwatch-test.db"
        self.database_path_patch = patch.object(database, "DB_PATH", self.database_path)
        self.database_path_patch.start()
        self.addCleanup(self.database_path_patch.stop)
        database.init_db()

    def test_init_db_adds_notes_to_existing_report_table(self):
        """Migrate a legacy report table and create medication storage."""
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        with patch.object(database, "DB_PATH", legacy_path):
            with closing(sqlite3.connect(legacy_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE symptom_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id TEXT NOT NULL,
                        submitted_at TEXT NOT NULL,
                        symptoms_json TEXT NOT NULL
                    )
                    """
                )
                conn.commit()

            database.init_db()

        with closing(sqlite3.connect(legacy_path)) as conn:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(symptom_reports)")
            }

        self.assertTrue(
            {
                "notes",
                "review_status",
                "doctor_note",
                "medication_id",
                "medication_name",
                "dosage_value",
                "dosage_unit",
                "medication_frequency",
                "medications_json",
            }
            <= columns
        )
        with closing(sqlite3.connect(legacy_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertIn("patient_medications", tables)

    def test_init_db_migrates_existing_single_medication_snapshots(self):
        legacy_path = Path(self.temp_dir.name) / "legacy-medication.db"
        with closing(sqlite3.connect(legacy_path)) as conn:
            conn.execute(
                """
                CREATE TABLE symptom_reports (
                    id INTEGER PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    symptoms_json TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    doctor_note TEXT NOT NULL DEFAULT '',
                    medication_id INTEGER,
                    medication_name TEXT NOT NULL DEFAULT '',
                    dosage_value REAL,
                    dosage_unit TEXT NOT NULL DEFAULT '',
                    medication_frequency TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO symptom_reports (
                    id, patient_id, submitted_at, symptoms_json, medication_id,
                    medication_name, dosage_value, dosage_unit, medication_frequency
                )
                VALUES (1, 'patient-a', '2026-01-01', '["Nausea"]',
                        9, 'Legacy medication', 5, 'mg', 'daily')
                """
            )
            conn.commit()

        with patch.object(database, "DB_PATH", legacy_path):
            database.init_db()
            reports, total = database.list_symptom_reports(
                "patient-a", limit=20, offset=0
            )

        self.assertEqual(total, 1)
        self.assertEqual(
            reports[0]["medications"],
            [
                {
                    "id": 9,
                    "name": "Legacy medication",
                    "dosage_value": 5.0,
                    "dosage_unit": "mg",
                    "frequency": "daily",
                }
            ],
        )

    def test_users_are_normalized_and_sessions_expire_and_can_be_deleted(self):
        """Normalize email, hash session tokens, and enforce session expiry."""
        user_id = database.create_user(
            " Patient@Example.com ",
            "stored-password-hash",
            patient_id="patient-a",
        )

        user = database.get_user_by_email("PATIENT@example.com")
        self.assertEqual(
            user,
            {
                "id": user_id,
                "email": "patient@example.com",
                "password_hash": "stored-password-hash",
                "role": "patient",
                "patient_id": "patient-a",
            },
        )
        self.assertIsNone(database.get_user_by_email("missing@example.com"))

        token = "session-secret"
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        database.create_session(user_id, token, expires_at)

        with closing(database.get_connection()) as conn:
            stored_token_hash = conn.execute(
                "SELECT token_hash FROM user_sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()["token_hash"]
        self.assertEqual(
            stored_token_hash,
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
        )

        self.assertEqual(
            database.get_session_user(token),
            {
                "id": user_id,
                "email": "patient@example.com",
                "role": "patient",
                "patient_id": "patient-a",
            },
        )
        self.assertIsNone(database.get_session_user("incorrect-token"))

        expired_token = "expired-session"
        database.create_session(
            user_id,
            expired_token,
            (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        )
        self.assertIsNone(database.get_session_user(expired_token))

        database.delete_session(token)
        self.assertIsNone(database.get_session_user(token))

    def test_user_role_and_email_constraints(self):
        """Reject invalid roles and duplicate emails regardless of case."""
        with self.assertRaisesRegex(ValueError, "Invalid user role"):
            database.create_user("invalid@example.com", "hash", role="admin")

        database.create_user("patient@example.com", "hash")
        with self.assertRaises(sqlite3.IntegrityError):
            database.create_user("PATIENT@example.com", "another-hash")

    def test_review_updates_and_counts_are_patient_scoped(self):
        """Limit report review updates and doctor notes to the target patient."""
        report = database.save_symptom_report("patient-a", ["Nausea"])
        database.save_symptom_report("patient-b", ["Fatigue"])

        updated = database.update_report_review(
            report["id"], "patient-a", "reviewed", "Call next week"
        )

        self.assertEqual(updated["review_status"], "reviewed")
        self.assertEqual(updated["doctor_note"], "Call next week")
        self.assertIsNone(
            database.update_report_review(
                report["id"], "patient-b", "reviewed", "Wrong patient"
            )
        )
        self.assertEqual(
            database.get_review_counts("patient-a"),
            {"pending": 0, "reviewed": 1},
        )
        self.assertEqual(
            database.get_review_counts("patient-b"),
            {"pending": 1, "reviewed": 0},
        )

        patient_reports, _ = database.list_symptom_reports(
            "patient-a", limit=20, offset=0
        )
        doctor_reports, _ = database.list_symptom_reports(
            "patient-a", limit=20, offset=0, include_doctor_notes=True
        )
        self.assertNotIn("doctor_note", patient_reports[0])
        self.assertEqual(doctor_reports[0]["doctor_note"], "Call next week")

    def test_reports_are_persisted_and_paginated(self):
        """Persist reports and return patient-scoped pages newest first."""
        patient_id = "patient-a"
        first = database.save_symptom_report(patient_id, ["Nausea"])
        second = database.save_symptom_report(patient_id, ["Headache"], "Follow up")
        database.save_symptom_report("patient-b", ["Fatigue"])

        reports, total = database.list_symptom_reports(
            patient_id, limit=1, offset=0
        )
        next_reports, next_total = database.list_symptom_reports(
            patient_id, limit=1, offset=1
        )

        self.assertEqual(total, 2)
        self.assertEqual(next_total, 2)
        self.assertEqual(len(reports), 1)
        self.assertEqual(len(next_reports), 1)

        self.assertEqual(reports[0]["review_status"], "pending")
        self.assertEqual(next_reports[0]["review_status"], "pending")

        self.assertEqual(
            {k: v for k, v in reports[0].items() if k != "review_status"},
            second,
        )
        self.assertEqual(
            {k: v for k, v in next_reports[0].items() if k != "review_status"},
            first,
        )
        self.assertEqual(reports[0]["notes"], "Follow up")
        self.assertEqual(reports[0]["symptoms"], ["Headache"])

    def test_successful_database_operations_are_logged_without_report_data(self):
        """Log database activity without exposing report contents."""
        with self.assertLogs("uvicorn.error", level=logging.INFO) as captured:
            database.init_db()
            database.save_symptom_report("patient-a", ["Private symptom"], "Private note")
            database.list_symptom_reports("patient-a", limit=20, offset=0)
            database.get_report_summary("patient-a")
            database.clear_symptom_reports("patient-a")

        output = "\n".join(captured.output)
        self.assertIn("initialize schema", output)
        self.assertIn("save symptom report", output)
        self.assertIn("list symptom reports", output)
        self.assertIn("get report summary", output)
        self.assertIn("clear symptom reports", output)
        self.assertNotIn("Private symptom", output)
        self.assertNotIn("Private note", output)

    def test_summary_and_patient_scoped_clear(self):
        """Summarize symptoms by patient and clear only the requested history."""
        database.save_symptom_report("patient-a", ["Nausea", "Headache"])
        database.save_symptom_report("patient-a", ["Nausea"])
        database.save_symptom_report("patient-b", ["Fatigue"])

        summary = database.get_report_summary("patient-a")

        self.assertEqual(
            summary,
            {
                "patient_id": "patient-a",
                "total_reports": 2,
                "total_symptom_entries": 3,
                "top_symptoms": [
                    {"name": "Nausea", "count": 2},
                    {"name": "Headache", "count": 1},
                ],
            },
        )
        self.assertEqual(database.clear_symptom_reports("patient-a"), 2)
        self.assertEqual(
            database.list_symptom_reports("patient-a", limit=20, offset=0),
            ([], 0),
        )
        self.assertEqual(
            database.list_symptom_reports("patient-b", limit=20, offset=0)[1], 1
        )
