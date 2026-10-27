"""Tests for startup seeding of demo login credentials."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.routes import database
from src.routes.demo_accounts import DEMO_ACCOUNTS, seed_demo_accounts
from src.server.main import create_app


class DemoAccountTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        db_patch = patch.object(
            database, "DB_PATH", Path(temp.name) / "demo-accounts.db"
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def test_startup_seeds_accounts_that_can_log_in(self):
        """Seed credentials on startup and retain them after another startup."""
        with TestClient(create_app()) as client:
            for account in DEMO_ACCOUNTS:
                with self.subTest(role=account.role):
                    response = client.post(
                        "/api/auth/login",
                        json={
                            "email": account.email,
                            "password": account.password,
                        },
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["user"]["role"], account.role)
                    client.post("/api/auth/logout")

        with TestClient(create_app()) as client:
            for account in DEMO_ACCOUNTS:
                with self.subTest(role=account.role, restart=True):
                    response = client.post(
                        "/api/auth/login",
                        json={
                            "email": account.email,
                            "password": account.password,
                        },
                    )
                    self.assertEqual(response.status_code, 200)

    def test_seeding_is_idempotent_and_does_not_replace_existing_user(self):
        """Avoid duplicates and leave an existing account's details unchanged."""
        database.init_db()
        original_user_id = database.create_user(
            email="patient@example.com",
            password_hash="existing-hash",
            role="patient",
            patient_id="existing-patient",
        )

        seed_demo_accounts()
        seed_demo_accounts()

        existing_patient = database.get_user_by_email("patient@example.com")
        self.assertEqual(existing_patient["id"], original_user_id)
        self.assertEqual(existing_patient["password_hash"], "existing-hash")
        self.assertEqual(existing_patient["patient_id"], "existing-patient")
        self.assertIsNotNone(database.get_user_by_email("doctor@example.com"))