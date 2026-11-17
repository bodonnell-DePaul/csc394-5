import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.config import FIXED_PATIENT_ID, SECOND_DEMO_PATIENT_ID
from src.middleware.schemas import DosageUpdateRequest
from src.routes import database
from src.routes.auth import password_hasher
from src.server.main import create_app


class MedicationSchemaTests(unittest.TestCase):
    def test_dosage_request_normalizes_medication_and_accepts_safe_boundaries(self):
        for dosage in (1, 10):
            with self.subTest(dosage=dosage):
                request = DosageUpdateRequest(
                    patient_id=FIXED_PATIENT_ID,
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
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "warfarin", "dosage_value": 0, "dosage_unit": "mg"},
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "warfarin", "dosage_value": -1, "dosage_unit": "mg"},
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "warfarin", "dosage_value": 0.9, "dosage_unit": "mg"},
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "warfarin", "dosage_value": 10.1, "dosage_unit": "mg"},
        )

        for request in invalid_requests:
            with self.subTest(request=request):
                with self.assertRaises(ValidationError):
                    DosageUpdateRequest(**request)

    def test_dosage_request_requires_medication_name_value_and_unit(self):
        for request in (
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "", "dosage_value": 5, "dosage_unit": "mg"},
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "warfarin", "dosage_unit": "mg"},
            {"patient_id": FIXED_PATIENT_ID, "medication_name": "warfarin", "dosage_value": 5},
            {"medication_name": "warfarin", "dosage_value": 5, "dosage_unit": "mg"},
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

    def test_list_prescriptions_returns_patient_scoped_pagination_including_inactive(self):
        database.update_prescription_dosage("patient-a", "warfarin", 2, "mg")
        database.update_prescription_dosage("patient-a", "aspirin", 81, "mg")
        database.update_prescription_dosage("patient-b", "warfarin", 4, "mg")
        database.deactivate_prescription("patient-a", "aspirin")

        prescriptions, total = database.list_prescriptions(
            "patient-a", limit=1, offset=0
        )
        next_page, next_total = database.list_prescriptions(
            "patient-a", limit=1, offset=1
        )
        empty_page, empty_total = database.list_prescriptions(
            "patient-a", limit=1, offset=2
        )

        self.assertEqual(total, 2)
        self.assertEqual(next_total, 2)
        self.assertEqual(empty_total, 2)
        self.assertEqual(len(prescriptions), 1)
        self.assertEqual(len(next_page), 1)
        self.assertEqual(empty_page, [])
        self.assertEqual(prescriptions[0]["patient_id"], "patient-a")
        self.assertEqual(prescriptions[0]["medication_name"], "warfarin")
        self.assertEqual(prescriptions[0]["dosage_value"], 2)
        self.assertEqual(prescriptions[0]["dosage_unit"], "mg")
        self.assertEqual(prescriptions[0]["is_active"], 1)
        self.assertEqual(next_page[0]["medication_name"], "aspirin")
        self.assertEqual(next_page[0]["is_active"], 0)
        self.assertTrue(prescriptions[0]["updated_at"])

    def test_list_prescriptions_returns_empty_collection_for_patient_without_prescriptions(self):
        prescriptions, total = database.list_prescriptions(
            "patient-without-prescriptions", limit=20, offset=0
        )

        self.assertEqual(prescriptions, [])
        self.assertEqual(total, 0)


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
            doctor_staff_id="518204",
        )
        database.create_user(
            email="medication-patient2@example.com",
            password_hash=password_hasher.hash("TestPassword456!"),
            patient_id=SECOND_DEMO_PATIENT_ID,
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
            json={
                "email": email,
                "password": password,
                **({"doctor_staff_id": "518204"} if role == "doctor" else {}),
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_doctor_can_add_and_list_patient_medications(self):
        forbidden = self.client.post(
            "/api/doctor/medications",
            json={
                "patient_id": FIXED_PATIENT_ID,
                "medication_name": "lexapro",
                "dosage_value": 10,
                "dosage_unit": "mg",
            },
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.post("/api/auth/logout")
        self.login("doctor")

        added = self.client.post(
            "/api/doctor/medications",
            json={
                "patient_id": FIXED_PATIENT_ID,
                "medication_name": "Lexapro",
                "dosage_value": 10,
                "dosage_unit": "mg",
            },
        )

        self.assertEqual(added.status_code, 201)
        medication = added.json()["medication"]
        self.assertEqual(medication["patient_id"], FIXED_PATIENT_ID)
        self.assertEqual(medication["medication_name"], "lexapro")
        self.assertEqual(medication["dosage_value"], 10)
        self.assertEqual(medication["dosage_unit"], "mg")
        self.assertEqual(medication["is_active"], True)

        listed = self.client.get(
            "/api/doctor/medications",
            params={"patient_id": FIXED_PATIENT_ID},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["medications"], [medication])

    def test_doctor_can_assign_medications_to_different_patients(self):
        self.client.post("/api/auth/logout")
        self.login("doctor")

        patient_list = self.client.get("/api/doctor/patients")
        self.assertEqual(patient_list.status_code, 200)
        patients = patient_list.json()["patients"]
        self.assertIn(
            SECOND_DEMO_PATIENT_ID,
            {patient["id"] for patient in patients},
        )

        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "lexapro", 10, "mg"
        )
        added = self.client.post(
            "/api/doctor/medications",
            json={
                "patient_id": SECOND_DEMO_PATIENT_ID,
                "medication_name": "fluoxetine",
                "dosage_value": 20,
                "dosage_unit": "mg",
            },
        )
        self.assertEqual(added.status_code, 201)
        self.assertEqual(added.json()["medication"]["patient_id"], SECOND_DEMO_PATIENT_ID)

        original_patient = self.client.get(
            "/api/doctor/medications",
            params={"patient_id": FIXED_PATIENT_ID},
        )
        second_patient = self.client.get(
            "/api/doctor/medications",
            params={"patient_id": SECOND_DEMO_PATIENT_ID},
        )
        self.assertEqual(
            [item["medication_name"] for item in original_patient.json()["medications"]],
            ["lexapro"],
        )
        self.assertEqual(
            [item["medication_name"] for item in second_patient.json()["medications"]],
            ["fluoxetine"],
        )

        deactivated = self.client.patch(
            "/api/medication",
            json={
                "patient_id": SECOND_DEMO_PATIENT_ID,
                "medication_name": "fluoxetine",
                "active": False,
            },
        )
        self.assertEqual(deactivated.status_code, 200)
        first_patient_after = self.client.get(
            "/api/doctor/medications",
            params={"patient_id": FIXED_PATIENT_ID},
        ).json()["medications"]
        second_patient_after = self.client.get(
            "/api/doctor/medications",
            params={"patient_id": SECOND_DEMO_PATIENT_ID},
        ).json()["medications"]
        self.assertEqual(first_patient_after[0]["is_active"], 1)
        self.assertEqual(second_patient_after[0]["is_active"], 0)

    def test_doctor_medication_endpoint_validates_patient_and_dose(self):
        self.client.post("/api/auth/logout")
        self.login("doctor")

        invalid_requests = (
            {
                "patient_id": "another-patient",
                "medication_name": "lexapro",
                "dosage_value": 10,
                "dosage_unit": "mg",
            },
            {
                "medication_name": "unlisted medication",
                "dosage_value": 10,
                "dosage_unit": "mg",
            },
            {
                "medication_name": "lexapro",
                "dosage_value": 100,
                "dosage_unit": "mg",
            },
            {
                "medication_name": "lexapro",
                "dosage_value": 10,
                "dosage_unit": "ml",
            },
        )
        for payload in invalid_requests:
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/doctor/medications", json=payload
                )
                self.assertIn(response.status_code, (404, 422))

        unauthenticated = TestClient(create_app())
        with unauthenticated:
            response = unauthenticated.get(
                "/api/doctor/medications",
                params={"patient_id": FIXED_PATIENT_ID},
            )
        self.assertEqual(response.status_code, 401)

    def test_doctor_cannot_add_inactive_medication(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "lexapro", 10, "mg"
        )
        database.deactivate_prescription(FIXED_PATIENT_ID, "lexapro")
        self.client.post("/api/auth/logout")
        self.login("doctor")

        response = self.client.post(
            "/api/doctor/medications",
            json={
                "patient_id": FIXED_PATIENT_ID,
                "medication_name": "lexapro",
                "dosage_value": 15,
                "dosage_unit": "mg",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"detail": "This medication is inactive and cannot be reactivated."},
        )

    def test_patient_can_get_own_prescriptions_with_pagination(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "aspirin", 81, "mg"
        )
        database.update_prescription_dosage("patient-b", "warfarin", 4, "mg")
        database.deactivate_prescription(FIXED_PATIENT_ID, "aspirin")

        response = self.client.get(
            "/api/medication",
            params={"limit": 1, "offset": 1},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"medications", "page"})
        self.assertEqual(
            body["page"],
            {"limit": 1, "offset": 1, "total": 2},
        )
        self.assertEqual(len(body["medications"]), 1)
        self.assertEqual(
            body["medications"][0]["patient_id"], FIXED_PATIENT_ID
        )
        self.assertEqual(body["medications"][0]["medication_name"], "aspirin")
        self.assertEqual(body["medications"][0]["is_active"], 0)

    def test_patient_cannot_get_another_patients_prescriptions(self):
        database.update_prescription_dosage("patient-b", "warfarin", 4, "mg")

        response = self.client.get(
            "/api/medication",
            params={"patient_id": "patient-b"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Cannot access another patient's medications."})

    def test_get_prescriptions_requires_authentication(self):
        self.client.post("/api/auth/logout")

        unauthenticated = self.client.get("/api/medication")
        self.assertEqual(unauthenticated.status_code, 401)

    def test_invalid_pagination_returns_validation_error(self):
        self.login("patient")
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
            with self.subTest(params=params):
                response = self.client.get("/api/medication", params=params)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(set(response.json()), {"detail"})

    def test_symptom_report_snapshots_active_prescriptions_at_submission(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "aspirin", 81, "mg"
        )
        database.deactivate_prescription(FIXED_PATIENT_ID, "aspirin")

        response = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Nausea"]},
        )

        self.assertEqual(response.status_code, 201)
        report = response.json()["report"]
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
        self.assertEqual(len(listed), 1)
        self.assertEqual(
            listed[0]["prescription_snapshot"],
            report["prescription_snapshot"],
        )

    def test_prescription_snapshot_is_immutable_after_medication_is_deactivated(self):
        database.update_prescription_dosage(
            FIXED_PATIENT_ID, "warfarin", 3, "mg"
        )

        first_response = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Nausea"]},
        )
        self.assertEqual(first_response.status_code, 201)

        database.deactivate_prescription(FIXED_PATIENT_ID, "warfarin")
        second_response = self.client.post(
            "/api/symptom_report",
            json={"symptoms": ["Headache"]},
        )

        self.assertEqual(second_response.status_code, 201)
        first_snapshot = first_response.json()["report"]["prescription_snapshot"]
        second_snapshot = second_response.json()["report"]["prescription_snapshot"]
        self.assertEqual(
            first_snapshot,
            [
                {
                    "medication_name": "warfarin",
                    "dosage_value": 3,
                    "dosage_unit": "mg",
                }
            ],
        )
        self.assertEqual(second_snapshot, [])

        listed = self.client.get("/api/symptom_report").json()["reports"]
        self.assertEqual(
            {report["id"]: report["prescription_snapshot"] for report in listed},
            {
                first_response.json()["report"]["id"]: first_snapshot,
                second_response.json()["report"]["id"]: [],
            },
        )

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

   