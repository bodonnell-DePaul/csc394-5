"""Command-line tools for inspecting and maintaining the local demo database."""
import argparse
from contextlib import closing
from datetime import datetime, timezone

from .config import DB_PATH
from .routes import database
from .routes.auth import DEMO_ACCOUNTS, hash_password, seed_demo_accounts


def show_status() -> None:
    with closing(database.get_connection()) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        def count_rows(table: str) -> int:
            if table not in tables:
                return 0
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        print(f"Database: {DB_PATH.resolve()}")
        print(f"Schema initialized: {'yes' if 'users' in tables else 'no'}")
        print(f"Users: {count_rows('users')}")
        print(f"Symptom reports: {count_rows('symptom_reports')}")
        print(f"Sessions: {count_rows('user_sessions')}")


def clean_expired_sessions() -> int:
    expires_before = datetime.now(timezone.utc).isoformat()
    with closing(database.get_connection()) as conn:
        cursor = conn.execute(
            "DELETE FROM user_sessions WHERE expires_at <= ?",
            (expires_before,),
        )
        conn.commit()
        return cursor.rowcount


def reset_demo_data() -> None:
    with closing(database.get_connection()) as conn:
        conn.execute("DELETE FROM symptom_reports")
        conn.execute("DELETE FROM user_sessions")
        conn.commit()
    seed_demo_accounts()


def repair_demo_doctor() -> None:
    """Restore only the documented demo doctor's login on an existing DB."""
    demo = next(account for account in DEMO_ACCOUNTS if account["role"] == "doctor")
    existing = database.get_user_by_email(demo["email"])
    if existing is None:
        seed_demo_accounts()
        return
    if existing["role"] != "doctor":
        raise ValueError("Demo doctor email belongs to a non-doctor account.")

    with closing(database.get_connection()) as conn:
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, doctor_staff_id = ?
            WHERE id = ? AND role = 'doctor'
            """,
            (hash_password(demo["password"]), demo["doctor_staff_id"], existing["id"]),
        )
        # Invalidate only the demo doctor's existing sessions.
        conn.execute(
            "DELETE FROM user_sessions WHERE user_id = ?", (existing["id"],)
        )
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and maintain the local Healthwatch demo database."
    )
    parser.add_argument(
        "command",
        choices=("status", "migrate", "seed", "clean", "repair-doctor", "reset"),
        help="status: show counts; migrate: initialize/upgrade schema; "
        "seed: add missing demo accounts; clean: remove expired sessions; "
        "repair-doctor: restore the demo doctor's login without deleting reports; "
        "reset: clear symptom reports and sessions, preserving user accounts",
    )
    args = parser.parse_args(argv)

    if args.command == "status":
        show_status()
    elif args.command == "migrate":
        database.init_db()
        print(f"Database schema is up to date: {DB_PATH.resolve()}")
    elif args.command == "seed":
        database.init_db()
        seed_demo_accounts()
        print("Demo accounts are present. No sample symptom reports were added.")
    elif args.command == "clean":
        database.init_db()
        removed = clean_expired_sessions()
        print(f"Removed {removed} expired session(s).")
    elif args.command == "repair-doctor":
        database.init_db()
        confirmation = input(
            "This restores the documented demo doctor's password and staff ID, "
            "and ends only that doctor's sessions. Type REPAIR DOCTOR to continue: "
        )
        if confirmation != "REPAIR DOCTOR":
            print("Doctor login repair cancelled.")
            return 1
        repair_demo_doctor()
        print("Demo doctor login restored; patient data and reports preserved.")
    else:
        database.init_db()
        confirmation = input(
            "This clears all symptom reports and active sessions while "
            f"preserving user accounts in {DB_PATH.resolve()}. Type RESET to continue: "
        )
        if confirmation != "RESET":
            print("Reset cancelled.")
            return 1
        reset_demo_data()
        print("Symptom reports and sessions cleared; user accounts preserved.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
