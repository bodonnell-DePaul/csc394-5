# csc394-5
This vertical slice demonstrates one patient feature: select symptoms, submit a report, and see the saved report in the patient's history. It uses a fixed synthetic patient and stores reports in SQLite. It does not include authentication, doctor views, diagnosis, or treatment recommendations.

API
- POST /api/symptom_report creates a report for the demo patient.
- GET /api/symptom_report?limit=20&offset=0 lists that patient's saved reports.
- GET /api/symptoms returns the symptom choices shown by the form.
- GET / returns the demo UI for symptom logging.

HTTP errors
- Invalid request bodies or query parameters return 422.
- Unknown patient IDs return 404.
- Successful symptom report creation returns 201.
- Database failures return 500 with a generic message; the server logs the underlying error.
- Reports may include optional notes up to 1,000 characters; notes are saved with report history.

Demo setup
1. Create a virtual environment and install dependencies:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
2. Start the server from the project root:
   python -m src.server.main
3. Open http://127.0.0.1:8000 in a browser.

Project structure
- src/server/main.py: FastAPI app factory, startup wiring, and development server entry point
- src/server/error_handlers.py: database exception logging and HTTP 500 responses
- src/config.py: shared app constants and synthetic patient profile
- src/server/database.py: SQLite access and report persistence
- src/routes/routes.py: endpoint definitions
- src/middleware/schemas.py: request validation models
- src/public/: browser UI assets
- src/data/healthwatch.db: demo database

The demo intentionally uses synthetic data only and is not suitable for real patient information or clinical use.
