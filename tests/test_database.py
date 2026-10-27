import logging
import sqlite3
import tempfile
import unittest
from contextlib import closing
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

        self.assertIn("notes", columns)

    def test_reports_are_persisted_and_paginated(self):
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
