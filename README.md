# Healthwatch

Healthwatch is a local demo application for patient symptom reports and
clinician review. The React web client talks to a FastAPI server, which stores
accounts, sessions, and reports in SQLite. It uses synthetic demo accounts and
is not for real patient information or clinical use.


## Run the application locally

### Requirements

- Python 3.12
- Node.js 18 or newer (includes npm)
- Windows PowerShell for the commands below

### One-time setup

Run these commands from the repository root:

```powershell
npm install
npm run build
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`npm run build` creates the client files in `src/public/`. The FastAPI server
serves both the built UI and API.

### Start and sign in

With the virtual environment activated, run the built app without the
development file watcher:

```powershell
python -m uvicorn src.server.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

| Role | Email | Password |
|---|---|---|
| Patient | `patient@example.com` | `PatientPassword123!` |
| Patient | `patient2@example.com` | `PatientPassword456!` |
| Doctor | `doctor@example.com` | `DoctorPassword123!` |

The two patient demo accounts represent separate patients. In the clinician
workspace, select a patient before adding or reviewing that patient's
medications.

At startup the server initializes the SQLite schema and creates any missing
demo accounts. Passwords are stored as Argon2 hashes. Startup does not insert
sample reports.

## Run checks locally

Install the development tools once:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Then run the required checks:

```powershell
python -m unittest discover -s tests -v
npm run lint
npm run build
```

The backend tests use temporary SQLite databases. They cover database
operations and schema upgrades, authentication and authorization, report
validation and persistence, clinician reviews, and demo-data commands. They
do not clear the local demo database. Optional checks, if desired, are
`ruff check src tests` and `mypy`.

For a manual smoke test, start the server, confirm
`http://127.0.0.1:8000/health` returns `{"status":"ok"}`, then sign in as both
roles. Submit a patient report and verify it appears in the patient history
and clinician review list; save a clinician review and confirm its status
updates.

## Automated Render deployment

The repository includes a Render Blueprint in [`render.yaml`](./render.yaml)
and a multi-stage [`Dockerfile`](./Dockerfile). The container builds the React
client and runs FastAPI; Render serves both from the same web service. The
Blueprint configures `/health` as its health check, stores SQLite at
`/var/data/healthwatch.db` on a persistent disk, and enables secure session
cookies over HTTPS.

To create the Render service:

1. Push this repository to GitHub and connect it to Render.
2. In Render, create a **Blueprint** from this repository and confirm the
   resources described in `render.yaml`. The persistent disk requires a paid
   web-service plan; the Blueprint selects the 0.5 CPU/512 MB plan and a 1 GB
   disk.
3. After the initial deployment, open the service URL and confirm `/health`
   returns `{"status":"ok"}`. Use the demo accounts listed above; only use
   synthetic demo data.

<<<<<<< HEAD
The existing [GitHub Actions workflow](./.github/workflows/ci.yml) runs backend
tests and frontend lint/build on pushes and pull requests to `main`. Render is
configured to deploy a `main` commit only after its GitHub checks pass. No
deployment token or GitHub Actions secret is needed. Review the **Actions**
tab for CI results and the Render dashboard's **Events** and **Logs** for
deployment status.

The persistent disk keeps the SQLite file across deploys and service restarts,
but it is not a backup and this SQLite setup is for one demo instance only.
This app retains fixed, documented demo credentials and is not production
ready. Never enter real patient information.
=======
>>>>>>> aacb78101429d9b994b4da77c98b9d38126aa845

## Local database maintenance

The database commands run from the repository root and use
`HEALTHWATCH_DB_PATH` if it is set; otherwise, they use
`src/data/healthwatch.db`.

```powershell
python -m src.manage_demo_data status
python -m src.manage_demo_data migrate
python -m src.manage_demo_data seed
python -m src.manage_demo_data clean
python -m src.manage_demo_data reset
```

- `status`: show the database path and counts.
- `migrate`: initialize or upgrade the current schema. The server does this
  automatically at startup.
- `seed`: add missing demo accounts without changing existing accounts or
  inserting reports.
- `clean`: delete expired sessions only.
- `reset`: type `RESET` when prompted to permanently delete all reports and
  sessions while preserving accounts. Stop the server first. Back up the
  database before maintenance.

The current schema setup is idempotent but is not a versioned migration
system.

## API quick reference

- `GET /health` checks server availability.
- `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`
  handle the session lifecycle.
- `GET /api/patient` returns the signed-in patient's account.
- `GET /api/symptoms` returns symptom choices.
- `POST /api/symptom_report` creates a patient report.
- `GET /api/symptom_report?limit=20&offset=0` lists patient reports.
- `GET /api/symptom_report/summary` returns report counts.
- `GET /api/doctor/patients` lists patients for the clinician portal.
- `GET /api/doctor/dashboard?patient_id=...&limit=20&offset=0` lists a
  selected patient's reports and summary for clinicians.
- `PATCH /api/doctor/reports/{report_id}?patient_id=...` saves a review for the
  selected patient.
- `GET` and `POST /api/doctor/medications` list and add prescriptions for a
  patient; `PATCH /api/medication` deactivates one.

Invalid request bodies or query parameters return 422. Unauthenticated
requests return 401, and role or patient access violations return 403.

## Project structure

- `frontend/src/`: React application and styles
- `src/server/main.py`: FastAPI app, startup, and local server entry point
- `src/routes/`: API, authentication, and SQLite operations
- `src/middleware/`: request schemas and error handling
- `src/manage_demo_data.py`: database status, migrate, seed, clean, and reset
- `src/data/healthwatch.db`: default local SQLite database
- `week3-api-documentation/02-architecture.md`: architecture diagram and
  component responsibilities
