import logging
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import (
    AVAILABLE_MEDICATIONS,
    AVAILABLE_SYMPTOMS,
    FIXED_PATIENT_ID,
    SECOND_DEMO_PATIENT_ID,
)
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
        self.assertTrue({
            "Acid reflux",
            "Change in appetite",
            "Congestion",
            "Cough",
            "Depression",
            "Diarrhea",
            "Dizziness",
            "Fainting",
            "Fatigue",
            "Fever",
            "Flatulence",
            "Hair loss",
            "Hearing impairment",
            "Indigestion",
            "Seizure",
            "Sleepiness",
            "Thirst",
            "Vomiting",
            "Vision impairment",
        }.issubset(AVAILABLE_SYMPTOMS))
        self.assertEqual(len(AVAILABLE_SYMPTOMS), len(set(AVAILABLE_SYMPTOMS)))

    def test_available_medications_endpoint_returns_supported_choices(self):
        response = self.client.get("/api/medications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"medications": AVAILABLE_MEDICATIONS})

    def test_public_routes_return_expected_responses(self):
        index_response = self.client.get("/")
        health_response = self.client.get("/health")
        auth_status_response = self.client.get("/api/auth/status")

        self.assertEqual(index_response.status_code, 200)
        self.assertTrue(index_response.headers["content-type"].startswith("text/html"))
        self.assertIn("<html", index_response.text.lower())
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json(), {"status": "ok"})
        self.assertEqual(auth_status_response.status_code, 200)
        self.assertEqual(
            auth_status_response.json(),
            {"message": "Healthwatch authentication router is working"},
        )

    def test_auth_login_me_and_logout_lifecycle(self):
        current_user = self.client.get("/api/auth/me")
        self.assertEqual(current_user.status_code, 200)
        self.assertEqual(
            current_user.json()["user"]["email"],
            "testpatient@example.com",
        )
        self.assertEqual(current_user.json()["user"]["role"], "patient")

        logout = self.client.post("/api/auth/logout")
        self.assertEqual(
            logout.json(),
            {"message": "Logged out successfully."},
        )
        self.assertIn("healthwatch_session", logout.headers.get("set-cookie", ""))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

        invalid_credentials = self.client.post(
            "/api/auth/login",
            json={
                "email": "testpatient@example.com",
                "password": "WrongPassword123!",
            },
        )
        unknown_user = self.client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "WrongPassword123!"},
        )
        self.assertEqual(invalid_credentials.status_code, 401)
        self.assertEqual(unknown_user.status_code, 401)
        self.assertEqual(
            invalid_credentials.json(),
            {"detail": "Invalid email or password."},
        )
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_login_can_set_secure_session_cookie(self):
        with patch("src.routes.auth.SESSION_COOKIE_SECURE", True):
            response = self.client.post(
                "/api/auth/login",
                json={
                    "email": "testpatient@example.com",
                    "password": "TestPassword123!",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("; Secure", response.headers["set-cookie"])

    def test_auth_me_rejects_missing_or_invalid_session(self):
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

        self.client.cookies.set("healthwatch_session", "invalid-session-token")
        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Invalid or expired session."},
        )

    def test_patient_profile_and_summary_routes(self):
        database.save_symptom_report(
            FIXED_PATIENT_ID, ["Nausea", "Headache"]
        )
        database.save_symptom_report(FIXED_PATIENT_ID, ["Nausea"])

        patient_response = self.client.get("/api/patient")
        summary_response = self.client.get("/api/symptom_report/summary")

        self.assertEqual(patient_response.status_code, 200)
        self.assertEqual(
            set(patient_response.json()["patient"]),
            {"id", "email"},
        )
        self.assertEqual(patient_response.json()["patient"]["id"], FIXED_PATIENT_ID)
        self.assertEqual(
            patient_response.json()["patient"]["email"],
            "testpatient@example.com",
        )
        self.assertNotIn("name", patient_response.json()["patient"])
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(
            summary_response.json()["summary"],
            {
                "patient_id": FIXED_PATIENT_ID,
                "total_reports": 2,
                "total_symptom_entries": 3,
                "top_symptoms": [
                    {"name": "Nausea", "count": 2},
                    {"name": "Headache", "count": 1},
                ],
            },
        )

    def test_second_demo_patient_can_access_own_data_only(self):
        self.client.post("/api/auth/logout")
        login = self.client.post(
            "/api/auth/login",
            json={
                "email": "patient2@example.com",
                "password": "PatientPassword456!",
            },
        )
        self.assertEqual(login.status_code, 200)

        patient = self.client.get("/api/patient")
        summary = self.client.get("/api/symptom_report/summary")
        reports = self.client.get("/api/symptom_report")
        medications = self.client.get("/api/medication")
        created = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Cough"], "notes": "Patient 2 report"},
        )

        self.assertEqual(patient.status_code, 200)
        self.assertEqual(patient.json()["patient"]["id"], SECOND_DEMO_PATIENT_ID)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(reports.status_code, 200)
        self.assertEqual(medications.status_code, 200)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            created.json()["report"]["patient_id"], SECOND_DEMO_PATIENT_ID
        )
        self.assertEqual(
            self.client.get(
                "/api/patient",
                params={"patient_id": FIXED_PATIENT_ID},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/symptom_report",
                params={"patient_id": FIXED_PATIENT_ID},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/symptom_report",
                json={
                    "patient_id": FIXED_PATIENT_ID,
                    "symptoms": ["Nausea"],
                },
            ).status_code,
            403,
        )
        deleted = self.client.delete("/api/symptom_report")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["deleted_rows"], 1)

    def test_symptom_report_accepts_details_and_associated_medication(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )
        response = self.client.post(
            "/api/symptom_report",
            json={
                "symptoms": [
                    {
                        "name": "Headache",
                        "severity": 7,
                        "location": "left temple",
                    }
                ],
                "associated_medication": "lexapro",
            },
        )

        self.assertEqual(response.status_code, 201)
        report = response.json()["report"]
        self.assertEqual(
            report["symptoms"],
            [{"name": "Headache", "severity": 7, "location": "left temple"}],
        )
        self.assertEqual(report["associated_medication"], "Lexapro")
        self.assertEqual(
            report["prescription_snapshot"],
            [
                {
                    "medication_name": "warfarin",
                    "dosage_value": 3,
                    "dosage_unit": "mg",
                }
            ],
        )

        listed = self.client.get("/api/symptom_report").json()["reports"]
        self.assertEqual(listed[0]["associated_medication"], "Lexapro")
        self.assertEqual(
            listed[0]["prescription_snapshot"],
            report["prescription_snapshot"],
        )

    def test_symptom_report_rejects_invalid_details_or_medication(self):
        for payload in (
            {
                "symptoms": [{"name": "Headache", "severity": 11}],
            },
            {
                "symptoms": ["Headache"],
                "associated_medication": "not supported",
            },
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/symptom_report", json=payload)
                self.assertEqual(response.status_code, 422)

    def test_patient_profile_and_summary_reject_unknown_patient(self):
        profile = self.client.get("/api/patient", params={"patient_id": "unknown"})
        summary = self.client.get(
            "/api/symptom_report/summary",
            params={"patient_id": "unknown"},
        )

        self.assertEqual(profile.status_code, 404)
        self.assertEqual(summary.status_code, 404)
        self.assertEqual(
            profile.json(),
            {"detail": "Patient not found."},
        )
        self.assertEqual(
            summary.json(),
            {"detail": "Patient not found."},
        )

    def test_clear_reports_only_deletes_authenticated_patient_history(self):
        database.save_symptom_report(FIXED_PATIENT_ID, ["Nausea"])
        database.save_symptom_report(FIXED_PATIENT_ID, ["Headache"])
        database.save_symptom_report("another-patient", ["Fatigue"])

        response = self.client.delete("/api/symptom_report")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"message": "Symptom history cleared.", "deleted_rows": 2},
        )
        self.assertEqual(database.list_symptom_reports(
            FIXED_PATIENT_ID, limit=20, offset=0
        ), ([], 0))
        self.assertEqual(
            database.list_symptom_reports(
                "another-patient", limit=20, offset=0
            )[1],
            1,
        )

    def test_patient_routes_require_authentication(self):
        self.client.post("/api/auth/logout")

        responses = [
            self.client.get("/api/patient"),
            self.client.get("/api/symptom_report/summary"),
            self.client.get("/api/symptom_report"),
            self.client.delete("/api/symptom_report"),
            self.client.post(
                "/api/symptom_report",
                json={"symptoms": ["Nausea"]},
            ),
        ]

        self.assertEqual([response.status_code for response in responses], [401] * 5)

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
            {
                "id",
                "patient_id",
                "submitted_at",
                "symptoms",
                "notes",
                "prescription_snapshot",
            },
        )
        self.assertEqual(create_body["report"]["patient_id"], FIXED_PATIENT_ID)
        self.assertEqual(create_body["report"]["symptoms"], ["Nausea", "Headache"])
        self.assertEqual(create_body["report"]["notes"], "Call after lunch")
        self.assertEqual(create_body["report"]["prescription_snapshot"], [])

        list_response = self.client.get(
            "/api/symptom_report",
            params={"limit": 1, "offset": 0},
        )

        self.assertEqual(list_response.status_code, 200)
        list_body = list_response.json()
        self.assertEqual(set(list_body), {"reports", "page"})
        self.assertEqual(len(list_body["reports"]), 1)

        listed_report = list_body["reports"][0]

        self.assertEqual(
            listed_report["review_status"],
            "pending",
        )
        self.assertEqual(
            {key: value for key, value in listed_report.items()
             if key != "review_status"},
            create_body["report"],
        )
        self.assertEqual(
            list_body["page"],
            {"limit": 1, "offset": 0, "total": 1},
        )


    def test_invalid_report_payloads_return_validation_errors(self):
        invalid_payloads = [
            ({"symptoms": []}, "Please select at least one symptom."),
            (
                {"symptoms": ["Unknown symptom"]},
                "Unsupported symptom: Unknown symptom",
            ),
            ({"symptoms": ["Nausea"], "notes": 123}, "Notes must be text."),
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

    def test_oversized_patient_notes_are_rejected_without_saving_report(self):
        response = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Nausea"], "notes": "x" * 1001},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(set(response.json()), {"detail"})
        self.assertEqual(
            self.client.get("/api/symptom_report").json()["page"]["total"],
            0,
        )

    def test_patient_notes_at_maximum_length_are_accepted(self):
        notes = "x" * 1000
        response = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Nausea"], "notes": notes},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["report"]["notes"], notes)
        reports, total = database.list_symptom_reports(
            FIXED_PATIENT_ID, limit=20, offset=0
        )
        self.assertEqual(total, 1)
        self.assertEqual(reports[0]["notes"], notes)

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
