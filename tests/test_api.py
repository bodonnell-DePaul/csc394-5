import logging
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import AVAILABLE_SYMPTOMS, FIXED_PATIENT_ID
from src.routes import database
from src.routes.auth import password_hasher
from src.routes import routes
from src.server.main import create_app


class ApiIntegrationTests(unittest.TestCase):
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
        email="testpatient@example.com",
        password_hash=password_hasher.hash("TestPassword123!"),
        role="patient",
        patient_id=FIXED_PATIENT_ID,
    )

        login_response = self.client.post(
            "/api/auth/login",
            json={
                "email": "testpatient@example.com",
                "password": "TestPassword123!",
            },
        )

        self.assertEqual(login_response.status_code, 200)


    def test_symptoms_endpoint_returns_supported_choices(self):
        response = self.client.get("/api/symptoms")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"symptoms": AVAILABLE_SYMPTOMS})

    def test_requests_are_logged_with_method_path_and_status(self):
        with self.assertLogs("uvicorn.error", level=logging.INFO) as captured:
            success_response = self.client.get("/health")
            error_response = self.client.get(
                "/api/symptom_report",
                params={"patient_id": "unknown"},
            )

        self.assertEqual(success_response.status_code, 200)
        self.assertEqual(error_response.status_code, 403)
        output = "\n".join(captured.output)
        self.assertIn("GET /health completed with status 200", output)
        self.assertIn("GET /api/symptom_report completed with status 403", output)

    def test_create_then_list_report_preserves_json_data_and_page_schema(self):
        create_response = self.client.post(
            "/api/symptom_report",
            json={
                "symptoms": [" Nausea ", "Headache", "Nausea"],
                "notes": "  Call after lunch  ",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        create_body = create_response.json()
        self.assertEqual(set(create_body), {"message", "report"})
        self.assertEqual(create_body["message"], "Symptom report saved.")
        self.assertEqual(
            set(create_body["report"]),
            {"id", "patient_id", "submitted_at", "symptoms", "notes"},
        )
        self.assertEqual(create_body["report"]["patient_id"], FIXED_PATIENT_ID)
        self.assertEqual(create_body["report"]["symptoms"], ["Nausea", "Headache"])
        self.assertEqual(create_body["report"]["notes"], "Call after lunch")

        list_response = self.client.get(
            "/api/symptom_report",
            params={"limit": 1, "offset": 0},
        )

        self.assertEqual(list_response.status_code, 200)
        list_body = list_response.json()
        self.assertEqual(set(list_body), {"reports", "page"})
        self.assertEqual(list_body["reports"], [create_body["report"]])
        self.assertEqual(list_body["page"], {"limit": 1, "offset": 0, "total": 1})


    def test_invalid_report_payloads_return_validation_errors(self):
        invalid_payloads = [
            ({"symptoms": []}, "Please select at least one symptom."),
            (
                {"symptoms": ["Unknown symptom"]},
                "Unsupported symptom: Unknown symptom",
            ),
            ({"symptoms": ["Nausea"], "notes": 123}, "Notes must be text."),
            ({"symptoms": ["Nausea"], "notes": "x" * 1001}, None),
        ]
        for payload, expected_message in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/api/symptom_report", json=payload)

                self.assertEqual(response.status_code, 422)
                error_body = response.json()
                self.assertEqual(set(error_body), {"detail"})
                if expected_message is not None:
                    self.assertIn(expected_message, str(error_body["detail"]))
                self.assertEqual(
                    self.client.get("/api/symptom_report").json()["page"]["total"],
                    0,
                )

    def test_invalid_pagination_returns_validation_error(self):
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.subTest(params=params):
                response = self.client.get("/api/symptom_report", params=params)

                self.assertEqual(response.status_code, 422)
                self.assertEqual(set(response.json()), {"detail"})

    def test_unknown_patient_is_not_found(self):
        response = self.client.get(
            "/api/symptom_report",
            params={"patient_id": "unknown"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "Cannot access another patient's reports."},
)

    def test_database_failure_returns_safe_error_and_logs_details(self):
        def fail_to_save(*args, **kwargs):
            raise sqlite3.OperationalError("private database details")

        with patch.object(routes, "save_symptom_report", fail_to_save):
            with self.assertLogs(
                "src.middleware.error_handlers", level=logging.ERROR
            ) as captured:
                response = self.client.post(
                    "/api/symptom_report",
                    json={"symptoms": ["Nausea"]},
                )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "A database error occurred."})
        self.assertIn("private database details", "\n".join(captured.output))
        self.assertNotIn("private database details", response.text)
