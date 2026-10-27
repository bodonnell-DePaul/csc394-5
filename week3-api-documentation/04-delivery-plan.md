# 4. Delivery plan

## MVP Scope
For this course project, the EHR data is seeded by the team. Healthwatch will not be integrated with other healthcare applications to receive data. Neither will Healthwatch comply with the regulations necessary to legally handle medical data.

## Smallest useful end-to-end journey
1. The patient signs in on an synthetic account
2. The patient selects Log Symptoms and opens the report form.
3. The patient fills out the form and selects Submit; the API records the symptom log on the client and updates both patient and doctors log list.
4. Both the patient and the doctor can review the details of the symptom log.

## Milestones
|Week| Goal | Exit Evidence|
|---|---|---|
| 3 | Architecture, API, and Delivery plan | Mapped documentation plans; reviewed initial risks, responsibilities, and uncertainties |
| 4 | Architecture, integration | Spike records; thin deployed skeleton; concept demo script|
| 5 | Concept Demo + CI/testing | Patients report symptoms and see record of symptom; tests and reviewed build recorded|
| 6 | Midterm check-in demo | check client-API integration and deployment of doctor interface functions and shared environment; rehearse check-in|
| 7 | Deployment automation/peer feedback |configure push notifications/alerts for patient pill intake/reported side effects/created appointments; setting up automatic deployment  |
| 8 |Security and performance |fixing bugs associated with api and testing code to ensure project functionality | 
| 9 | Preview Demo |Address any remaining technical debt or bugs and update documentation; essentially checking for demo readiness to present project deliverable |
| 10 | Presentation and hand-off preparation| contribution/reflection drafts; walkthrough of software project |
| 11 | Final demo and presentation| functional release|

## User Story Backlog
|ID & Priority| User story & Acceptance Criteria |Owner| Target & Dependencies|
|---|---|---|---|
| US-01/Must | As a patient, I can view my medical information so I can keep track my treatment progress | | W4 | 
| US-02/Must | As a doctor, I can view my patient's medical information so I have all info to make a decision | | W5 |
| US-03/Must | As a patient, I can report symptoms easily so I can keep update my doctor to my current condition| Ethan M | W4, EN-04 |
| US-04/Must| As a doctor, I can view patients through a queue based on severity so I can focus on high-risk patients before lower priorities| | W5, EN-05 |
| US-05/Should | As a user, I can message my counterpart in severe cases so that we can discuss the next steps urgently | | W6, EN-05 |
| US-06/Could | As a patient, I can be alerted by a notification, so I can remember to take my medication| Ethan M| W6 | 

## Engineering Tasks 
|ID| Task & Output | Owner | Target & Dependencies|
|---|---|---|---|
| EN-01 | Initial repository setup, FastAPI/Client linting, and a local health-endpoint cURL check| Ethan M| W4, no dependencies.|
| EN-02 | Identity-provider token spike | | W5, EN-01|
| EN-03 | Automate all acceptance tests | Ethan M | W5 |
| EN-04 | Data normalization of the OpenFDA's Drug Adverse Event database | Ethan M | W4|
| EN-05 | Develop the backend risk calculator based on OpenFDA's Drug Adverse Event database|  | W5, EN-04|

## Definition of Done
- Acceptance criteria pass
- Lint, type checks, and unit/API test pass
- Documentation updated to match behaviour
- the change is integrated in shared environment when the environment exists.
  
## Testing, deployment, and release plan

The current supported deployment is a local, single-instance demo. The
repository does not currently configure a cloud host, container image,
infrastructure-as-code, CI/CD pipeline, TLS termination, or managed database.
Do not expose the demo publicly or use it with real health information.

### Environment requirements

| Requirement | Current need |
|---|---|
| Python | Python 3.12 is the configured type-check/lint target and tested runtime. |
| Node.js/npm | Node.js 18 or newer; npm installs and builds the React client. |
| Python dependencies | `requirements.txt` for runtime. `requirements-dev.txt` includes runtime plus `httpx`, mypy, and Ruff. |
| Storage | Writable directory for SQLite. Defaults to `src/data/healthwatch.db`; override with `HEALTHWATCH_DB_PATH`. |
| Ports | FastAPI: `127.0.0.1:8000`. Vite: port `5173`, with `/api` proxied to port 8000. |

No separate database server, API key, or external service is required for the
local demo.

### Local deployment

Run from the repository root in PowerShell:

1. Install Node.js 18+ and Python 3.12.
2. Install client dependencies and create the production client:

   ```powershell
   npm install
   npm run build
   ```

   The build is written to `src/public/`; rebuild after frontend changes.

3. Create and activate a Python environment, then install packages:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-dev.txt
   ```

4. Optionally select a separate SQLite file. Create its parent directory
   first and ensure it is writable:

   ```powershell
   $env:HEALTHWATCH_DB_PATH = "C:\healthwatch-data\healthwatch.db"
   ```

   If unset, the database is `src/data/healthwatch.db`.

5. Run checks in the next section, then start the server:

   ```powershell
   python -m src.server.main
   ```

   Startup initializes/upgrades the current schema and seeds the patient and
   doctor demo accounts if they are missing. It does not create sample
   symptom reports. Open http://127.0.0.1:8000 and use the local demo
   credentials documented in the root README.

For frontend hot reload, run `python -m src.server.main` and `npm run dev` in
separate terminals, then open http://127.0.0.1:5173/static/. Vite proxies
`/api` calls to FastAPI; this is a development setup, not the production
serving path.

### Automated testing and release checks

Run from the repository root:

```powershell
# Backend unit and API integration tests; uses temporary SQLite databases
python -m unittest discover -s tests -v

# Frontend lint and production bundle
npm run lint
npm run build

# Optional Python lint and type checks (install requirements-dev.txt)
ruff check src tests
mypy
```

Tests cover database operations and schema upgrades, authentication and role
authorization, request validation, report persistence, clinician review, and
demo-data maintenance. They use isolated temporary databases and do not
require clearing the development database. The repository uses standard
library `unittest`; it does not define a pytest test command.

Before a local demo release:

1. Run the backend tests, frontend lint, and production build and require all
   to pass. Run Ruff and mypy when the development extras are installed.
2. Confirm `npm run build` updated `src/public/`.
3. Start the server and verify `GET /health` returns `{"status":"ok"}`.
4. Sign in with both demo roles and check patient report submission/history
   and clinician refresh/filter/review-save against the running API.
5. Run `python -m src.manage_demo_data status` and check the database path
   and counts. Do not use `reset` as a routine test.

### Database maintenance and production readiness

Use `python -m src.manage_demo_data status|migrate|seed|clean|reset` from the
repository root. These commands honor `HEALTHWATCH_DB_PATH`. `migrate`
initializes/upgrades the current schema (also run at app startup); `seed`
adds missing demo accounts without changing existing accounts or inserting
sample reports; `clean` removes expired sessions; `reset` asks for `RESET`
before permanently deleting reports and active sessions while preserving user
accounts. Stop the app before a reset or copying/replacing the SQLite file;
back up the database before maintenance.

Schema upgrades are idempotent initialization code, not a versioned migration
history. Introduce reviewed, versioned migrations if schema evolution or
deployed database upgrades become more complex.

The app is not production-ready. Before internet-facing deployment, remove
fixed demo credentials and startup account creation; require HTTPS and secure
session cookies; review CSRF, session, proxy, and secret-management behavior;
replace fixed-patient demo assumptions; complete security, privacy, and
clinical compliance reviews; select backed-up storage suitable for concurrent
instances; and define platform-specific infrastructure, CI/CD, migrations,
health checks, retention, recovery, and monitoring. Until then, use synthetic
demo data only on a trusted local machine.

## Risks
| Risks | Fallback | Owner |
|---|---|---|
|Data Inconsistency | Spike for data normalization and processing| Ethan M |
|Scope Creep Delays Development| maintain strict development guidelines; delay optional feature development | |
|Key Member becomes unavailable| rearrange owners of tasks; update documentation; inform the owner| |
