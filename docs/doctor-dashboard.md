# Doctor Dashboard — Healthwatch Integration

This branch is a **doctor-focused feature branch**, not a separate application.
It is based on the authenticated Healthwatch app and preserves the existing
patient symptom reporting, FastAPI routes, SQLite tables, and React build.

## Patient-to-doctor workflow

1. A fictional patient signs in with a **patient** account and records symptoms
   and optional notes through the patient dashboard.
2. FastAPI validates the report and saves it in the `symptom_reports` SQLite
   table under the fixed demo patient ID.
3. An authorized **doctor** account signs in and sees those reports in the
   doctor dashboard, initially marked **pending**.
4. The doctor can filter reports by pending/reviewed status, read the submitted
   symptoms, add an internal review note (up to 1,000 characters), and mark the
   report **reviewed** or return it to **pending**.
5. The doctor can refresh the list. The review status and note persist in
   SQLite. Doctor notes are excluded from the patient history API.

## Feature boundaries

- The doctor view is **not** a stand-alone app; do not split out its FastAPI or
  SQLite implementation from the shared project.
- Authentication, session management, and patient/doctor role checks are
  implemented in `src/routes/auth.py`; the doctor endpoints require
  `require_doctor_user`.
- Doctor API endpoints are `GET /api/doctor/dashboard` and
  `PATCH /api/doctor/reports/{report_id}`.
- The current project supports a **single fixed synthetic patient**; it is not
  a complete multi-patient clinic system.
- Medication changes, appointment scheduling, clinical assessment, and real
  healthcare data are **outside the scope** of this doctor feature.
- This remains a classroom prototype. The development session cookie is not
  configured for production HTTPS deployment; do not use real health data.

## Integration testing

From the repository root, with development dependencies installed:

```bash
python -m pytest tests/test_doctor_dashboard.py -q
python -m pytest tests -q
npm ci
npm run build
```

The patient and doctor test accounts are created by the test suite in an
isolated temporary SQLite database. The app does not automatically create
interactive demo login accounts on a fresh database.

## Git branching

This branch was brought up to date with `main` after the original doctor
dashboard PR was merged. Subsequent changes on this branch are **not**
automatically applied to `main`; any new merge should be discussed with the
project team and reviewed separately.
