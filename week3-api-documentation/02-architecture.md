# 2. Architecture

## Component boundaries

flowchart LR
    subgraph Client["Client Layer"]
        UI["React Client<br/>Displays messages, medical information,<br/>severity queues, and symptom report form"]
    end

    subgraph Backend["Python Processing Layer"]
        PY["Python Backend / ETL Script<br/>Loads OpenFDA dataset<br/>Normalizes and validates records<br/>Writes to SQLite"]
    end

    subgraph Data["Local Data Layer"]
        Dataset["OpenFDA Drug Event Dataset"]
        SQLite["SQLite Database<br/>patients, symptom_reports, medications, tickets"]
    end

    Dataset --> PY
    PY --> SQLite
    UI <-->|"Read and write patient, medication, and ticket records"| SQLite

Component Descriptions

Component | Owns | Does Not Own|
|---|---|---|
|React Client| displays messages, medical information, and severity queues; symptom report form access| database access|
|SQLite + OpenFDA Drug Event Data Set| provides past information of patients, drug use, their physicians, and logged side effects; stores normalized patient, medication, symptom, and ticket records| direct decision-making on behalf of doctors|
|Data Loading / Normalization| imports and normalizes the OpenFDA dataset into SQLite so the app can query it locally without a backend API| user interface behavior|

## Data Entities & Relationships
- patients: id, name, gender, birthdate, current medication_ids
- symptom report: id, owner_id, timestamp, current_medication_ids , symptoms
- medications: id, name, manufacturer
- ticket: id, patient_id, symptom_report_ids, severity, status

Each patient owns multiple patient logs. Each symptom log references one or more medications. Each ticket owns one patient and references symptoms.

## Authentication, Authorization, Secrets, & Persistent Data
Authentication relies on lightweight JSON Web Tokens (JWT) generated after validating pre-seeded synthetic credentials for patients and doctors. Authorization is strictly enforced using role-based access controls before data is returned to the client. Sensitive credentials are kept in local configuration/secrets files rather than embedded in the frontend. Persistent data is stored in SQLite and seeded from the OpenFDA dataset; the patient, symptom, medication, and ticket tables provide local state across app sessions.

## Decisions & Tradeoffs
SQLite was chosen to ensure zero-configuration deployment and quick local setup, accepting the tradeoff that write concurrency is limited under heavy loads. The team opted to pre-load a normalized subset of the OpenFDA dataset into SQLite so the application can access historical patient and adverse event information without requiring a separate API server.

## Technical Risks and Unknowns
The primary technical risk involves unstandardized or inconsistent symptom terms within the OpenFDA adverse drug event dataset, which will be mitigated by a technical spike dedicated to cleaning and normalizing symptom names before they are stored in SQLite.
