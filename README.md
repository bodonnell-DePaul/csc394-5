# Healthwatch

Healthwatch is a local demo application for patient symptom reports and
clinician review. The React web client talks to a FastAPI server, which stores
accounts, sessions, and reports in SQLite. It uses synthetic demo accounts and
is not for real patient information or clinical use.

## Project Presentation and Demonstration

Our team presentation provides an overview of Healthwatch, its
architecture, implemented features, and application functionality.

[![Watch the Healthwatch Project Presentation](https://img.youtube.com/vi/5_FdQUTyuTg/0.jpg)](https://youtu.be/5_FdQUTyuTg)

[Watch the full presentation on YouTube](https://youtu.be/5_FdQUTyuTg)

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

| Role | Email | Password | Doctor staff ID |
|---|---|---|---|
| Patient | `patient@example.com` | `PatientPassword123!` | Not required |
| Patient | `patient2@example.com` | `PatientPassword456!` | Not required |
| Doctor | `doctor@example.com` | `DoctorPassword123!` | `742619` |

The two patient demo accounts represent separate patients. In the clinician
workspace, select a patient before adding or reviewing that patient's
medications.

At startup the server initializes the SQLite schema and creates any missing
demo accounts. Passwords are stored as Argon2 hashes. The existing demo doctor
account is assigned its staff ID if it did not have one. Startup does not insert
sample reports.

Select **Doctor** on the sign-in screen to enter the six-digit staff ID as well
as email and password. Patient sign-in supports email and password or Google Sign-In
for authorized patient accounts. The backend checks the doctor ID against the signed-in
account before issuing a session; entering an ID on the patient sign-in path is rejected.
Non-demo doctor accounts need a staff ID provisioned before they can sign in.

**Security limitation:** The doctor ID is an internal demo identifier, not a
verified medical license, a secret, or multi-factor authentication. Demo
credentials are intentionally shared in this README; use synthetic data only.

## OAuth integration and Set-up Instructions 
The repository implements Google OAuth authentication to support external verification of our google accounts to access the patient portal.
When employing OAuth, here we updated the patient portal to allow patients to select **Sign in with Google** when attempting to log in.
On the other hand, we already established a **staff Id** for the doctor interface as an additional step for verifying their login credentials.

**Front-end and back-end O-auth Architecture**: To deploy Google OAuth integration, we updated our frontend to include code that renders a 'Google Sign-in' 
button on the patient log-in page, triggering a Google OAuth Consent Flow. Once Google authenticates the user, the frontend passes an authorization code/token 
to our FastApi Backend. Our FastApi validates the token against Google's OAuth Servers using environment variables, creates the patient session, and redirects the user to the patient dashboard. 
**Set-up**: When accessing Google API using OAuth 2.0 to integrate it with HealthWatch, follow  (https://developers.google.com/identity/protocols/oauth2), which essentially describes how to obtain OAuth 2.0 credentials
to access Google APIs, and ultimately set up this verification to our web server. But first,
1. **Create a project from the the Google Cloud Console** (https://console.cloud.google.com) and select the Healthwatch project
2. **Configure the Consent screen**: Navigate to **API and Services -> OAuth Consent Screen** and select **External** to fill in the required app details and test user details.
3. **Obtain OAuth 2.0 Credentials**: Under **API and Services -> Credentials -> Create Credentials-> OAuth Client ID** create a client ID (GOOGLE_CLIENT_ID) to identify HealthWatch to Google when initiating login, and a client secret (GOOGLE_CLIENT_SECRET) that authenticates the backend server when exchanging authorization codes for access tokens. Since we creating a client appropriate for a web application, configure these credentials to access Google APIs from a web application built on Python/Fast-Api (Server-side web application).
4. **Configure the Redirect URIS**: Under **Authorized Redirect URIs** the backend callback URL ('GOOGLE_REDIRECT_URI' , http://localhost:8000/api/auth/google/callback") for local deployment, as well as the Render callback URL (https://csc394-5.onrender.com/) for production deployment.
5. **Save the Environment Variables**: Add "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SERCRET", and "GOOGLE_REDIRECT_URI" under the .env file located in the root directory of our repository (src/server/config.py), and loaded automatically via python-dotvenv in config.py. Also save the variables pointed to the Render callback URL  under the "Environments Tab" to match the environment variables in config.py.

**Note**: At the point of finishing our project, Google login is only restricted to authorized users, indicating that not everyone with a Google account gets automatic access to the Healthwatch portal. Google verifies the user identity, but the backend also checks whether the email is associated with an authorized patient account in our database. If not, then access is denied.

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

### Google OAuth configuration

Google Sign-In requires the following environment variables to be
configured in the Render web service:

| Variable | Purpose |
|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth client identifier |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Authorized OAuth callback URL |
| `GOOGLE_ALLOWED_PATIENT_EMAILS` | Comma-separated list of patient emails to provision |

Authorized email addresses must also be configured as test users in
Google Cloud while the OAuth application remains in testing mode.

At startup, Healthwatch automatically provisions missing patient
accounts for the configured email addresses. Existing accounts are
preserved, and new accounts receive unique patient IDs and securely
generated, hashed passwords.

Credentials and authorized email addresses must not be committed to
source control.

Removing an email from the provisioning environment variable does not
automatically revoke an existing account. Revocation must be managed
separately.

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
- `GET /api/auth/google` initiates Google OAuth authentication.
- `GET /api/auth/google/callback` verifies the Google identity,
  checks patient authorization, and creates an authenticated session.
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
