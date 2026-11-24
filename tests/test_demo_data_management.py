import io
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.config import FIXED_PATIENT_ID, SECOND_DEMO_PATIENT_ID
from src import manage_demo_data
from src.routes import database


class DemoDataManagementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db_patch = patch.object(
            database, "DB_PATH", Path(temp.name) / "test.db"
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def run_command(self, command, input_value=None):
        output = io.StringIO()
        with redirect_stdout(output):
            if input_value is None:
                exit_code = manage_demo_data.main([command])
            else:
                with patch("builtins.input", return_value=input_value):
                    exit_code = manage_demo_data.main([command])
        return exit_code, output.getvalue()

    def test_seed_and_migrate_are_repeatable_without_adding_sample_reports(self):
        self.assertEqual(self.run_command("migrate")[0], 0)
        self.assertEqual(self.run_command("seed")[0], 0)
        first_patient = database.get_user_by_email("patient@example.com")
        second_patient = database.get_user_by_email("patient2@example.com")
        self.assertIsNotNone(first_patient)
        self.assertIsNotNone(second_patient)

        self.assertEqual(self.run_command("migrate")[0], 0)
        self.assertEqual(self.run_command("seed")[0], 0)

        self.assertEqual(
            database.get_user_by_email("patient@example.com")["id"],
            first_patient["id"],
        )
        self.assertEqual(
            database.get_user_by_email("patient2@example.com")["id"],
            second_patient["id"],
        )
        self.assertEqual(first_patient["patient_id"], FIXED_PATIENT_ID)
        self.assertEqual(second_patient["patient_id"], SECOND_DEMO_PATIENT_ID)
        self.assertEqual(database.list_symptom_reports(FIXED_PATIENT_ID, 20, 0), ([], 0))

    def test_seed_separates_existing_demo_patient_accounts(self):
        database.init_db()
        from src.routes.auth import hash_password, seed_demo_accounts

        database.create_user(
            "patient2@example.com",
            hash_password("PatientPassword456!"),
            patient_id=FIXED_PATIENT_ID,
        )
        seed_demo_accounts()

        self.assertEqual(
            database.get_user_by_email("patient2@example.com")["patient_id"],
            SECOND_DEMO_PATIENT_ID,
        )

    def test_status_reports_database_counts(self):
        self.run_command("seed")
        database.save_symptom_report(FIXED_PATIENT_ID, ["Headache"])

        exit_code, output = self.run_command("status")

        self.assertEqual(exit_code, 0)
        self.assertIn("Users: 3", output)
        self.assertIn("Symptom reports: 1", output)
        self.assertIn("Sessions: 0", output)

    def test_clean_removes_only_expired_sessions(self):
        self.run_command("seed")
        user = database.get_user_by_email("doctor@example.com")
        expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        database.create_session(user["id"], "expired-token", expired)
        database.create_session(user["id"], "active-token", future)

        exit_code, output = self.run_command("clean")

        self.assertEqual(exit_code, 0)
        self.assertIn("Removed 1 expired session(s).", output)
        self.assertEqual(self.run_command("status")[0], 0)
        with closing(database.get_connection()) as conn:
            sessions = conn.execute("SELECT COUNT(*) FROM user_sessions").fetchone()[0]
        self.assertEqual(sessions, 1)

    def test_repair_doctor_requires_confirmation_and_preserves_patient_records(self):
        from src.routes.auth import hash_password, verify_password

        self.run_command("seed")
        doctor = database.get_user_by_email("doctor@example.com")
        patient = database.get_user_by_email("patient@example.com")
        report = database.save_symptom_report(
            FIXED_PATIENT_ID, ["Nausea"], "Demo symptoms"
        )
        with closing(database.get_connection()) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, doctor_staff_id = ? WHERE id = ?",
                (hash_password("OldPassword!"), "111222", doctor["id"]),
            )
            conn.commit()
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        database.create_session(doctor["id"], "doctor-session", expires)
        database.create_session(patient["id"], "patient-session", expires)

        cancelled, _ = self.run_command("repair-doctor", "NO")
        self.assertEqual(cancelled, 1)
        self.assertEqual(
            database.get_user_by_email("doctor@example.com")["doctor_staff_id"],
            "111222",
        )

        code, output = self.run_command("repair-doctor", "REPAIR DOCTOR")
        self.assertEqual(code, 0)
        self.assertIn("patient data and reports preserved", output)
        restored = database.get_user_by_email("doctor@example.com")
        self.assertEqual(restored["id"], doctor["id"])
        self.assertEqual(restored["doctor_staff_id"], "742619")
        self.assertTrue(verify_password("DoctorPassword123!", restored["password_hash"]))
        self.assertFalse(verify_password("OldPassword!", restored["password_hash"]))
        self.assertIsNone(database.get_session_user("doctor-session"))
        self.assertIsNotNone(database.get_session_user("patient-session"))
        self.assertEqual(database.get_user_by_email("patient@example.com"), patient)
        reports, count = database.list_symptom_reports(FIXED_PATIENT_ID, 20, 0)
        self.assertEqual(count, 1)
        self.assertEqual(reports[0]["id"], report["id"])

    def test_reset_requires_confirmation_and_preserves_accounts(self):
        self.run_command("seed")
        user = database.get_user_by_email("patient@example.com")
        database.save_symptom_report(FIXED_PATIENT_ID, ["Nausea"])

        exit_code, output = self.run_command("reset", "no")

        self.assertEqual(exit_code, 1)
        self.assertIn("Reset cancelled.", output)
        self.assertEqual(database.list_symptom_reports(FIXED_PATIENT_ID, 20, 0)[1], 1)

        exit_code, output = self.run_command("reset", "RESET")

        self.assertEqual(exit_code, 0)
        self.assertIn("user accounts preserved", output)
        self.assertEqual(database.get_user_by_email("patient@example.com")["id"], user["id"])
        self.assertEqual(database.list_symptom_reports(FIXED_PATIENT_ID, 20, 0), ([], 0))


if __name__ == "__main__":
    unittest.main()
