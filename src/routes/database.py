import json
import sqlite3
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
        if "review_status" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'"
            )
        if "doctor_note" not in columns:
            conn.execute(
                "ALTER TABLE symptom_reports ADD COLUMN doctor_note TEXT NOT NULL DEFAULT ''"
            )
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
