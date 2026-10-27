# Healthwatch

Healthwatch is a synthetic patient-monitoring demo with authenticated patient
and doctor dashboards. Doctors maintain a patient's medication list; patients
can review the list and associate an active medication with a symptom report.
The medication and symptom history is stored in SQLite.

## Run locally

1. Install Node.js 18 or newer, then build the React client:

   ```powershell
   npm install
   npm run build
   ```

2. Create and activate a Python virtual environment, then install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Start the API and open `http://127.0.0.1:8000`:

   ```powershell
   python -m src.server.main
   ```

On startup, the demo seeds these login accounts if they do not already exist:

| Role | Email | Password |
|---|---|---|
| Patient | `patient@example.com` | `PatientPassword123!` |
| Doctor | `doctor@example.com` | `DoctorPassword123!` |

Seeding is idempotent and does not reset credentials for existing accounts.
These public demo credentials are for local synthetic data only; do not use
them for a deployed or production system.

For frontend development with hot reload, run `npm run dev` in a second
terminal. Vite proxies `/api` requests to the FastAPI server. The server
initializes and migrates the SQLite schema at startup. Set
`HEALTHWATCH_DB_PATH` to use a different database file.

## Medication and report access

- Patients can read their medication list with `GET /api/medications`. There is
  no patient medication write endpoint.
- Authenticated doctors can add medications with
  `POST /api/doctor/medications` and edit dosage, frequency, instructions, or
  active status with
  `PATCH /api/doctor/medications/{medication_id}`.
- Medication names are fixed when created and cannot be changed. Creation
  requests include `name`, `dosage_value`, `dosage_unit`, and optionally
  `frequency`, `instructions`, and `active`. Supported units
  are `mg`, `mcg`, `ml`, `g`, and `tablets`.
- Every symptom report automatically includes a snapshot of all medications
  active for the patient when it is submitted. Patients do not select
  medications manually. Later medication edits or discontinuations do not
  rewrite report history.
- Doctors see medication information alongside symptom reports in the doctor
  dashboard. The patient dashboard shows medication history and report-linked
  medication details.

## Other API endpoints

- `POST /api/symptom_report` creates a symptom report.
- `GET /api/symptom_report?limit=20&offset=0` lists the authenticated patient's
  reports.
- `GET /api/symptom_report/summary` returns that patient's report summary.
- `GET /api/doctor/dashboard` returns the doctor dashboard, including
  medications and symptom reports.
- Patients cannot delete symptom reports; the API does not expose a delete
  endpoint for symptom history.

API requests that require a role return `401` when unauthenticated and `403`
when the account does not have the required role. Invalid request data returns
`422`.

## Project structure

- `src/server/main.py`: FastAPI app factory, startup wiring, and server entry point
- `src/routes/database.py`: SQLite schema, migrations, and persistence
- `src/routes/routes.py`: API endpoints
- `src/routes/auth.py`: authentication and role checks
- `src/middleware/schemas.py`: request validation models
- `frontend/src/`: React client
- `src/public/`: production frontend build served by FastAPI
- `tests/`: API, persistence, authentication, and dashboard tests

This project uses synthetic demo data only. It is not intended for real patient
information or clinical use.
