import json
import logging
import sqlite3
import hashlib
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('patient', 'doctor')),
                patient_id TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()
    logger.info("Database operation completed: initialize schema")


def save_symptom_report(
    patient_id: str,
    symptoms: list[str],
    notes: str | None = None,
) -> dict[str, Any]:
    submitted_at = datetime.now(timezone.utc).isoformat()
    saved_notes = notes or ""

    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO symptom_reports (patient_id, submitted_at, symptoms_json, notes)
            VALUES (?, ?, ?, ?)
            """,
            (patient_id, submitted_at, json.dumps(symptoms), saved_notes),
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
            SELECT id, patient_id, submitted_at, symptoms_json, notes, review_status, doctor_note
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

    symptoms: list[str] = []
    for row in rows:
        symptoms.extend(json.loads(row["symptoms_json"]))

    counts: dict[str, int] = {}
    for symptom in symptoms:
        counts[symptom] = counts.get(symptom, 0) + 1

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

def create_user(
    email: str,
    password_hash: str,
    role: str = "patient",
    patient_id: str | None = None,
) -> int:
    """Save a new user account and return its ID."""
    if role not in ("patient", "doctor"):
        raise ValueError("Invalid user role.")

    with closing(get_connection()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, role, patient_id)
            VALUES (?, ?, ?, ?)
            """,
            (email.strip().lower(), password_hash, role, patient_id),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Find an existing user by email."""
    with closing(get_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, role, patient_id
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
                   review_status, doctor_note
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
    }
