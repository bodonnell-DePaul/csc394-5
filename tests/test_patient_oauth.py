"""Contract tests for patient-only Google OAuth authentication."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.routes import auth, database
from src.server.main import create_app


class PatientOAuthTests(unittest.TestCase):
    def setUp(self):
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        database_patch = patch.object(
            database, "DB_PATH", Path(temporary_dir.name) / "patient-oauth.db"
        )
        database_patch.start()
        self.addCleanup(database_patch.stop)

        # OAuth contract tests opt into mock provider settings, independent of Render.
        for name, value in (
            ("GOOGLE_CLIENT_ID", "test-google-client"),
            ("GOOGLE_CLIENT_SECRET", "test-google-secret"),
            ("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"),
        ):
            setting_patch = patch.object(auth, name, value)
            setting_patch.start()
            self.addCleanup(setting_patch.stop)

        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_google_provider_is_optional_without_blocking_password_login(self):
        self.assertTrue(
            self.client.get("/api/auth/providers").json()["google_patient_login"]
        )

        with patch.object(auth, "GOOGLE_CLIENT_SECRET", ""):
            provider = self.client.get("/api/auth/providers")
            self.assertEqual(provider.status_code, 200)
            self.assertFalse(provider.json()["google_patient_login"])

            google_start = self.client.get(
                "/api/auth/google", follow_redirects=False
            )
            self.assertEqual(google_start.status_code, 503)
            self.assertNotIn("location", google_start.headers)

            google_callback = self.client.get("/api/auth/google/callback")
            self.assertEqual(google_callback.status_code, 503)

            patient_login = self.client.post(
                "/api/auth/login",
                json={
                    "email": "patient@example.com",
                    "password": "PatientPassword123!",
                },
            )
            self.assertEqual(patient_login.status_code, 200)
            self.assertEqual(patient_login.json()["user"]["role"], "patient")

            doctor_login = self.client.post(
                "/api/auth/login",
                json={
                    "email": "doctor@example.com",
                    "password": "DoctorPassword123!",
                    "doctor_staff_id": "742619",
                },
            )
            self.assertEqual(doctor_login.status_code, 200)
            self.assertEqual(doctor_login.json()["user"]["role"], "doctor")

    def start_google_oauth(self):
        response = self.client.get(
            "/api/auth/google", follow_redirects=False
        )
        self.assertIn(response.status_code, (302, 307))
        authorization_url = urlparse(response.headers["location"])
        self.assertEqual(authorization_url.hostname, "accounts.google.com")

        parameters = parse_qs(authorization_url.query)
        self.assertEqual(parameters["response_type"], ["code"])
        self.assertIn("openid", parameters["scope"][0].split())
        self.assertIn("email", parameters["scope"][0].split())
        self.assertTrue(parameters["state"][0])
        return parameters["state"][0]

    def callback(self, state, code="test-authorization-code"):
        return self.client.get(
            "/api/auth/google/callback",
            params={"code": code, "state": state},
            follow_redirects=False,
        )

    def test_existing_patient_can_sign_in_and_receive_app_session(self):
        state = self.start_google_oauth()
        verified_google_identity = {
            "sub": "google-patient-subject",
            "email": "patient@example.com",
            "email_verified": True,
        }

        with patch.object(
            auth,
            "exchange_google_code",
            return_value=verified_google_identity,
            create=True,
        ) as exchange_code:
            response = self.callback(state)

        self.assertIn(response.status_code, (302, 303, 307, 308))
        exchange_code.assert_called_once()
        self.assertIn("healthwatch_session", response.headers["set-cookie"])

        current_user = self.client.get("/api/auth/me")
        self.assertEqual(current_user.status_code, 200)
        self.assertEqual(
            current_user.json()["user"]["email"], "patient@example.com"
        )
        self.assertEqual(current_user.json()["user"]["role"], "patient")
        self.assertEqual(
            self.client.get("/api/doctor/patients").status_code,
            403,
        )

    def test_callback_rejects_mismatched_state_without_exchanging_code(self):
        self.start_google_oauth()

        with patch.object(
            auth, "exchange_google_code", create=True
        ) as exchange_code:
            response = self.callback("not-the-issued-state")

        self.assertEqual(response.status_code, 400)
        exchange_code.assert_not_called()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_callback_requires_code_and_does_not_exchange_without_one(self):
        state = self.start_google_oauth()

        with patch.object(
            auth, "exchange_google_code", create=True
        ) as exchange_code:
            response = self.client.get(
                "/api/auth/google/callback",
                params={"state": state},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 400)
        exchange_code.assert_not_called()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_provider_error_callback_is_rejected_without_session(self):
        state = self.start_google_oauth()

        with patch.object(
            auth, "exchange_google_code", create=True
        ) as exchange_code:
            response = self.client.get(
                "/api/auth/google/callback",
                params={
                    "state": state,
                    "error": "access_denied",
                    "error_description": "The user denied access.",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 400)
        exchange_code.assert_not_called()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_provider_exchange_failure_is_safe_and_does_not_create_session(self):
        state = self.start_google_oauth()

        with patch.object(
            auth,
            "exchange_google_code",
            side_effect=RuntimeError("private provider response"),
            create=True,
        ):
            response = self.callback(state)

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider response", response.text)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_unverified_google_email_is_rejected(self):
        state = self.start_google_oauth()
        identity = {
            "sub": "unverified-subject",
            "email": "patient@example.com",
            "email_verified": False,
        }

        with patch.object(
            auth, "exchange_google_code", return_value=identity, create=True
        ):
            response = self.callback(state)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_missing_or_malformed_identity_fields_are_rejected(self):
        malformed_identities = (
            {},
            {"sub": "missing-email", "email_verified": True},
            {
                "sub": "missing-verification",
                "email": "patient@example.com",
            },
            {
                "sub": "",
                "email": "patient@example.com",
                "email_verified": True,
            },
            {
                "sub": "missing-string-email",
                "email": None,
                "email_verified": True,
            },
        )

        for identity in malformed_identities:
            with self.subTest(identity=identity):
                state = self.start_google_oauth()
                with patch.object(
                    auth,
                    "exchange_google_code",
                    return_value=identity,
                    create=True,
                ):
                    response = self.callback(state)

                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_google_email_match_is_case_insensitive(self):
        state = self.start_google_oauth()
        identity = {
            "sub": "uppercase-email-subject",
            "email": "PATIENT@EXAMPLE.COM",
            "email_verified": True,
        }

        with patch.object(
            auth, "exchange_google_code", return_value=identity, create=True
        ):
            response = self.callback(state)

        self.assertIn(response.status_code, (302, 303, 307, 308))
        patient = self.client.get("/api/patient")
        self.assertEqual(patient.status_code, 200)
        self.assertEqual(
            patient.json()["patient"]["email"], "patient@example.com"
        )

    def test_successful_callback_uses_configured_secure_cookie_setting(self):
        state = self.start_google_oauth()
        identity = {
            "sub": "secure-cookie-subject",
            "email": "patient@example.com",
            "email_verified": True,
        }

        with patch("src.routes.auth.SESSION_COOKIE_SECURE", True):
            with patch.object(
                auth,
                "exchange_google_code",
                return_value=identity,
                create=True,
            ):
                response = self.callback(state)

        self.assertIn(response.status_code, (302, 303, 307, 308))
        set_cookie = response.headers["set-cookie"]
        self.assertIn("healthwatch_session=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertIn("samesite=lax", set_cookie.lower())

    def test_oauth_state_is_one_time_use(self):
        state = self.start_google_oauth()
        identity = {
            "sub": "replay-subject",
            "email": "patient@example.com",
            "email_verified": True,
        }

        with patch.object(
            auth, "exchange_google_code", return_value=identity, create=True
        ) as exchange_code:
            first = self.callback(state)
            replay = self.callback(state)

        self.assertIn(first.status_code, (302, 303, 307, 308))
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(exchange_code.call_count, 1)

    def test_unknown_google_email_does_not_create_an_account(self):
        state = self.start_google_oauth()
        identity = {
            "sub": "unknown-subject",
            "email": "new-patient@example.com",
            "email_verified": True,
        }

        with patch.object(
            auth, "exchange_google_code", return_value=identity, create=True
        ):
            response = self.callback(state)

        self.assertEqual(response.status_code, 403)
        self.assertIsNone(database.get_user_by_email("new-patient@example.com"))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_doctor_google_identity_cannot_sign_in_as_a_patient(self):
        state = self.start_google_oauth()
        identity = {
            "sub": "google-doctor-subject",
            "email": "doctor@example.com",
            "email_verified": True,
        }

        with patch.object(
            auth, "exchange_google_code", return_value=identity, create=True
        ):
            response = self.callback(state)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
