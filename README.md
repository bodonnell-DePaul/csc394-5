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
| Doctor | `doctor@example.com` | `DoctorPassword123!` |

At startup the server initializes the SQLite schema and creates either demo
account if it is missing. Passwords are stored as Argon2 hashes. Startup does
not insert sample reports.

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

## GitHub Actions deployment process


The workflow is [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).
GitHub runs it automatically:

1. **On every push:** checkout the commit, run backend tests on Python 3.12,
   and, in parallel, install Node dependencies with `npm ci`, lint the
   frontend, and build the frontend.
2. **On pull requests targeting `main`:** run the same backend and frontend
   checks against the proposed changes.
3. **Review the result:** open the repository's **Actions** tab, select the
   `Healthwatch CI` run for the commit or pull request, and wait for both
   jobs—**Backend tests** and **Frontend lint and build**—to pass.
4. **Merge only after success:** optionally configure repository branch
   protection for `main` and require both jobs before merging.
5. **After a push to `main`:** Actions runs the checks again. No deployment
   job runs; there is no hosted URL or deployed environment produced by this
   workflow.

The workflow needs no deployment secrets. It uses GitHub-hosted Ubuntu
runners, installs dependencies from `requirements-dev.txt` and
`package-lock.json`, then runs:

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
- `GET /api/doctor/dashboard?limit=20&offset=0` lists reports for clinicians.
- `PATCH /api/doctor/reports/{report_id}` saves a clinician review.

Invalid request bodies or query parameters return 422. Unauthenticated
requests return 401, and role or patient access violations return 403.

## Project structure

- `frontend/src/`: React application and styles
- `src/server/main.py`: FastAPI app, startup, and local server entry point
- `src/routes/`: API, authentication, and SQLite operations
- `src/middleware/`: request schemas and error handling
- `src/manage_demo_data.py`: database status, migrate, seed, clean, and reset
- `src/data/healthwatch.db`: default local SQLite database
- `src/public/`: built frontend served by FastAPI
- `week3-api-documentation/02-architecture.md`: architecture diagram and
  component responsibilities
