import json
import sqlite3
import hashlib
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

from ..config import DB_PATH, PATIENT_PROFILE


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

    return {
        "id": report_id,
        "patient_id": patient_id,
        "submitted_at": submitted_at,
        "symptoms": symptoms,
        "notes": saved_notes,
    }


def list_symptom_reports(patient_id: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    with closing(get_connection()) as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) AS total FROM symptom_reports WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT id, patient_id, submitted_at, symptoms_json, notes
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
        }
        for row in rows
    ]

    return reports, total_row["total"] if total_row else 0


def clear_symptom_reports(patient_id: str | None = None) -> int:
    with closing(get_connection()) as conn:
        if patient_id is None:
            cursor = conn.execute("DELETE FROM symptom_reports")
        else:
            cursor = conn.execute("DELETE FROM symptom_reports WHERE patient_id = ?", (patient_id,))
        conn.commit()
        return cursor.rowcount


def get_patient_profile(patient_id: str) -> dict[str, Any]:
    profile = dict(PATIENT_PROFILE)
    profile["id"] = patient_id
    return profile


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