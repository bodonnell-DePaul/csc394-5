import json
import logging
import sqlite3
import hashlib
import re
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

from ..config import DB_PATH

logger = logging.getLogger("uvicorn.error")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS symptom_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                symptoms_json TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(symptom_reports)").fetchall()
        }
        if "notes" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN notes TEXT NOT NULL DEFAULT ''"
            )
        if "review_status" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'"
            )
        if "doctor_note" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN doctor_note TEXT NOT NULL DEFAULT ''"
            )
        if "prescription_snapshot_json" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN prescription_snapshot_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "associated_medication" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN associated_medication TEXT DEFAULT NULL"
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('patient', 'doctor')),
                patient_id TEXT,
                doctor_staff_id TEXT
            )
        """)
        # Upgrade existing databases without losing any accounts or sessions.
        user_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)")
        }
        if "doctor_staff_id" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN doctor_staff_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_doctor_staff_id "
            "ON users(doctor_staff_id) WHERE doctor_staff_id IS NOT NULL"
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prescriptions (
                patient_id TEXT NOT NULL,
                medication_name TEXT NOT NULL,
                dosage_value REAL NOT NULL CHECK (dosage_value > 0),
                dosage_unit TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                PRIMARY KEY (patient_id, medication_name)
            )
            """
        )
        conn.commit()
    logger.info("Database operation completed: initialize schema")


def save_symptom_report(
    patient_id: str,
    symptoms: list[str | dict[str, Any]],
    notes: str | None = None,
    associated_medication: str | None = None,
) -> dict[str, Any]:
    submitted_at = datetime.now(timezone.utc).isoformat()
    saved_notes = notes or ""

    with closing(get_connection()) as conn:
        prescriptions = conn.execute(
            """
            SELECT medication_name, dosage_value, dosage_unit
            FROM prescriptions
            WHERE patient_id = ? AND is_active = 1
            ORDER BY medication_name
            """,
            (patient_id,),
        ).fetchall()
        prescription_snapshot = [
            {
                "medication_name": row["medication_name"],
                "dosage_value": row["dosage_value"],
                "dosage_unit": row["dosage_unit"],
            }
            for row in prescriptions
        ]
        cursor = conn.execute(
            """
            INSERT INTO symptom_reports (
                patient_id, submitted_at, symptoms_json, notes,
                prescription_snapshot_json, associated_medication
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                submitted_at,
                json.dumps(symptoms),
                saved_notes,
                json.dumps(prescription_snapshot),
                associated_medication,
            ),
        )
        conn.commit()
        report_id = cursor.lastrowid

    logger.info("Database operation completed: save symptom report")
    return {
        "id": report_id,
        "patient_id": patient_id,
        "submitted_at": submitted_at,
        "symptoms": symptoms,
        "notes": saved_notes,
        "prescription_snapshot": prescription_snapshot,
        **(
            {"associated_medication": associated_medication}
            if associated_medication is not None
            else {}
        ),
    }


def list_symptom_reports(
    patient_id: str,
    limit: int,
    offset: int,
    include_doctor_notes: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    with closing(get_connection()) as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) AS total FROM symptom_reports WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT id, patient_id, submitted_at, symptoms_json, notes,
                   review_status, doctor_note, prescription_snapshot_json,
                   associated_medication
            FROM symptom_reports
            WHERE patient_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (patient_id, limit, offset),
        ).fetchall()

    reports = [
        {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "submitted_at": row["submitted_at"],
            "symptoms": json.loads(row["symptoms_json"]),
            "notes": row["notes"],
            "review_status": row["review_status"],
            "prescription_snapshot": json.loads(
                row["prescription_snapshot_json"] or "[]"
            ),
            **(
                {"associated_medication": row["associated_medication"]}
                if row["associated_medication"] is not None
                else {}
            ),
            **({"doctor_note": row["doctor_note"]} if include_doctor_notes else {}),
        }
        for row in rows
    ]

    total = total_row["total"] if total_row else 0
    logger.info("Database operation completed: list symptom reports")
    return reports, total


def clear_symptom_reports(patient_id: str | None = None) -> int:
    with closing(get_connection()) as conn:
        if patient_id is None:
            cursor = conn.execute("DELETE FROM symptom_reports")
        else:
            cursor = conn.execute("DELETE FROM symptom_reports WHERE patient_id = ?", (patient_id,))
        conn.commit()
        deleted_rows = cursor.rowcount
    logger.info(
        "Database operation completed: clear symptom reports (%d rows deleted)",
        deleted_rows,
    )
    return deleted_rows


def get_patient_profile(patient_id: str) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT patient_id AS id, email
            FROM users
            WHERE patient_id = ? AND role = 'patient'
            ORDER BY id
            LIMIT 1
            """,
            (patient_id,),
        ).fetchone()

    return dict(row) if row else None


def list_patient_profiles() -> list[dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT patient_id AS id, MIN(email) AS email
            FROM users
            WHERE role = 'patient' AND patient_id IS NOT NULL
            GROUP BY patient_id
            ORDER BY email
            """
        ).fetchall()
    return [dict(row) for row in rows]


def update_user_patient_id(email: str, patient_id: str) -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            UPDATE users
            SET patient_id = ?
            WHERE email = ? AND role = 'patient'
            """,
            (patient_id, email.strip().lower()),
        )
        conn.commit()


def get_report_summary(patient_id: str) -> dict[str, Any]:
    with closing(get_connection()) as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM symptom_reports WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()["total"]
        rows = conn.execute(
            "SELECT symptoms_json FROM symptom_reports WHERE patient_id = ? ORDER BY id DESC LIMIT 20",
            (patient_id,),
        ).fetchall()

    symptoms: list[str | dict[str, Any]] = []
    for row in rows:
        symptoms.extend(json.loads(row["symptoms_json"]))

    counts: dict[str, int] = {}
    for symptom in symptoms:
        name = symptom["name"] if isinstance(symptom, dict) else symptom
        counts[name] = counts.get(name, 0) + 1

    top_symptoms = [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

    logger.info("Database operation completed: get report summary")
    return {
        "patient_id": patient_id,
        "total_reports": total,
        "total_symptom_entries": len(symptoms),
        "top_symptoms": top_symptoms,
    }

def normalize_doctor_staff_id(doctor_staff_id: str) -> str:
    """Require a six-digit demo staff ID, preserving leading zeroes."""
    if not isinstance(doctor_staff_id, str):
        raise ValueError("Doctor staff ID must be six digits.")
    normalized = doctor_staff_id.strip()
    if re.fullmatch(r"[0-9]{6}", normalized) is None:
        raise ValueError("Doctor staff ID must be six digits.")
    return normalized


def create_user(
    email: str,
    password_hash: str,
    role: str = "patient",
    patient_id: str | None = None,
    doctor_staff_id: str | None = None,
) -> int:
    """Save a user; new doctor accounts must have an assigned staff ID."""
    if role not in ("patient", "doctor"):
        raise ValueError("Invalid user role.")
    if role == "doctor" and doctor_staff_id is None:
        raise ValueError("Doctor accounts require a staff ID.")
    if role == "patient" and doctor_staff_id is not None:
        raise ValueError("Patient accounts cannot have doctor staff IDs.")
    staff_id = (
        normalize_doctor_staff_id(doctor_staff_id)
        if doctor_staff_id is not None else None
    )

    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, role, patient_id, doctor_staff_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email.strip().lower(), password_hash, role, patient_id, staff_id),
        )
        conn.commit()
        return cursor.lastrowid


def assign_doctor_staff_id(email: str, doctor_staff_id: str) -> None:
    """Provision an existing doctor once, including legacy accounts."""
    normalized = normalize_doctor_staff_id(doctor_staff_id)
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            UPDATE users SET doctor_staff_id = ?
            WHERE email = ? AND role = 'doctor' AND doctor_staff_id IS NULL
            """,
            (normalized, email.strip().lower()),
        )
        if cursor.rowcount != 1:
            raise ValueError("Doctor not found or already provisioned.")
        conn.commit()


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Find an existing user by email."""
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, role, patient_id, doctor_staff_id
            FROM users
            WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()

    return dict(row) if row else None
def create_session(user_id: int, token: str, expires_at: str) -> None:
    """Store a hashed session token in SQLite."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO user_sessions (token_hash, user_id, expires_at)
            VALUES (?, ?, ?)
            """,
            (token_hash, user_id, expires_at),
        )
        conn.commit()


def get_session_user(token: str) -> dict[str, Any] | None:
    """Return the user associated with a valid, unexpired session."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    current_time = datetime.now(timezone.utc).isoformat()

    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT users.id, users.email, users.role, users.patient_id
            FROM user_sessions
            JOIN users ON users.id = user_sessions.user_id
            WHERE user_sessions.token_hash = ?
              AND user_sessions.expires_at > ?
            """,
            (token_hash, current_time),
        ).fetchone()

    return dict(row) if row else None


def delete_session(token: str) -> None:
    """Invalidate a session when a user logs out."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with closing(get_connection()) as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE token_hash = ?",
            (token_hash,),
        )
        conn.commit()

def get_review_counts(patient_id: str) -> dict[str, int]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            """
            SELECT review_status, COUNT(*) AS count
            FROM symptom_reports
            WHERE patient_id = ?
            GROUP BY review_status
            """,
            (patient_id,),
        ).fetchall()
    counts = {"pending": 0, "reviewed": 0}
    for row in rows:
        if row["review_status"] in counts:
            counts[row["review_status"]] = row["count"]
    return counts


def update_report_review(
    report_id: int,
    patient_id: str,
    review_status: str,
    doctor_note: str,
) -> dict[str, Any] | None:
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            UPDATE symptom_reports
            SET review_status = ?, doctor_note = ?
            WHERE id = ? AND patient_id = ?
            """,
            (review_status, doctor_note, report_id, patient_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            """
            SELECT id, patient_id, submitted_at, symptoms_json, notes,
                   review_status, doctor_note, prescription_snapshot_json,
                   associated_medication
            FROM symptom_reports WHERE id = ? AND patient_id = ?
            """,
            (report_id, patient_id),
        ).fetchone()
        conn.commit()

    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "submitted_at": row["submitted_at"],
        "symptoms": json.loads(row["symptoms_json"]),
        "notes": row["notes"],
        "review_status": row["review_status"],
        "doctor_note": row["doctor_note"],
        "prescription_snapshot": json.loads(
            row["prescription_snapshot_json"] or "[]"
        ),
        **(
            {"associated_medication": row["associated_medication"]}
            if row["associated_medication"] is not None
            else {}
        ),
    }


def update_prescription_dosage(
    patient_id: str,
    medication_name: str,
    dosage_value: float,
    dosage_unit: str,
) -> dict[str, Any]:
    updated_at = datetime.now(timezone.utc).isoformat()
    normalized_name = medication_name.strip().lower()
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO prescriptions (patient_id, medication_name, dosage_value, dosage_unit, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(patient_id, medication_name) 
            DO UPDATE SET 
                dosage_value = excluded.dosage_value,
                dosage_unit = excluded.dosage_unit,
                updated_at = excluded.updated_at
            """,
            (patient_id, normalized_name, dosage_value, dosage_unit, updated_at),
        )
        conn.commit()
    return {
        "patient_id": patient_id,
        "medication_name": normalized_name,
        "dosage_value": dosage_value,
        "dosage_unit": dosage_unit,
        "updated_at": updated_at,
    }


def deactivate_prescription(patient_id: str, medication_name: str) -> int:
    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            UPDATE prescriptions
            SET is_active = 0
            WHERE patient_id = ? AND medication_name = ? AND is_active = 1
            """,
            (patient_id, medication_name.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount


def list_prescriptions(
    patient_id: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    with closing(get_connection()) as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM prescriptions WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()["total"]
        rows = conn.execute(
            """
            SELECT patient_id, medication_name, dosage_value, dosage_unit,
                   updated_at, is_active
            FROM prescriptions
            WHERE patient_id = ?
            ORDER BY medication_name DESC
            LIMIT ? OFFSET ?
            """,
            (patient_id, limit, offset),
        ).fetchall()

    return [dict(row) for row in rows], total