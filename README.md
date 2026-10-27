# Healthwatch symptom-reporting demo

This demo provides a patient portal for submitting symptom reports and viewing saved history, along with a clinician dashboard for reviewing reports. It stores account and report data in SQLite; the patient screen displays the signed-in account email and does not invent demographics or care-team details. It does not provide diagnosis or treatment recommendations.

## API


HTTP errors
- Invalid request bodies or query parameters return 422.
- Unknown patient IDs return 404.
- Successful symptom report creation returns 201.
- Database failures return 500 with a generic message; the server logs the underlying error.
- The server logs each request's method, path, status code, and duration; query parameters and request bodies are not logged.
- Reports may include optional notes up to 1,000 characters; notes are saved with report history.

Demo setup
1. Install Node.js (18 or newer) and create a production build of the React client:
   npm install
   npm run build
   The build output is written to src/public/, which is served by FastAPI.
2. Create a virtual environment and install Python dependencies:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
3. Start the server from the project root:
   python -m src.server.main
4. Open http://127.0.0.1:8000 in a browser.

### Demo sign-in accounts

The server creates these accounts at startup if they do not already exist:

| Role | Email | Password |
| --- | --- | --- |
| Patient | `patient@example.com` | `PatientPassword123!` |
| Doctor | `doctor@example.com` | `DoctorPassword123!` |

Passwords are stored as Argon2 hashes. Existing accounts with these email addresses are left unchanged. These fixed credentials are for local demonstration only; do not use them in a deployed environment or with real patient information.

### Server-side demo data tools

The FastAPI server and SQLite database can be inspected and maintained from the project root using `python -m src.manage_demo_data`. The commands use `HEALTHWATCH_DB_PATH` when set; otherwise, they target `src/data/healthwatch.db`.

```powershell
python -m src.manage_demo_data status
python -m src.manage_demo_data migrate
python -m src.manage_demo_data seed
python -m src.manage_demo_data clean
python -m src.manage_demo_data reset
```

- `status` prints the database path, initialization state, and user, report, and session counts.
- `migrate` safely initializes or upgrades the SQLite schema. The server also runs these idempotent migrations at startup.
- `seed` creates the demo patient and doctor accounts if missing. It does not insert fake symptom reports.
- `clean` removes expired login sessions; it does not delete reports or user accounts.
- `reset` asks you to type `RESET`, then deletes all symptom reports and login sessions while preserving user accounts. Stop the server first to avoid concurrent database activity. This reset is permanent.

To point commands at a separate local database in PowerShell, set the path for the current terminal before running them:

```powershell
$env:HEALTHWATCH_DB_PATH = "C:\path\to\healthwatch-demo.db"
python -m src.manage_demo_data status
```

For client development with hot reload, start the API with
`python -m src.server.main` and, in a second terminal, run `npm run dev`.
Vite serves the client and proxies `/api` requests to the FastAPI server.

Project structure
- src/server/main.py: FastAPI app factory, startup wiring, and development server entry point
- src/server/error_handlers.py: database exception logging and HTTP 500 responses
- src/config.py: shared app constants
- src/server/database.py: SQLite access and report persistence
- src/routes/routes.py: endpoint definitions
- src/middleware/schemas.py: request validation models
- src/public/: browser UI assets
- frontend/src/: React client source
- vite.config.js: Vite development proxy and production build configuration
- src/data/healthwatch.db: demo database
=======
- `POST /api/symptom_report` creates a report for the demo patient.
- `GET /api/symptom_report?limit=20&offset=0` lists that patient's saved reports.
- `GET /api/symptoms` returns the symptom choices shown by the form.

The demo intentionally uses synthetic data only and is not suitable for real patient information or clinical use.

## MCP
In order to allow doctors to make instantaneous changes such as changing prescription dosages or create appointments for patients, an AI assistant will orchestrate multiple MCP tools to run these processes seamlessly:
1. code_grep_search: Examine all medications in the database whose status declares they must be modified.
2. file_write_contents: Generates new React components for the doctor dashboard patient logging screen; implements push notifications in relation to database changes.
3. sql_execute_query: Ensures that patient's logged symptoms were saved, or to ensure the database the recorded the patients and their corresponding medications that are being updated/are updated.
4. run_terminal_command: runs integration tests to ensure that notifications are triggered once doctors make alterations.
5. 
