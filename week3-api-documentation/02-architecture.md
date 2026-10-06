# 2. Architecture

## Component boundaries
[A diagram showing the client, API, database, external services, and how they communicate]
   
 

Component Descriptions

Component | Owns | Does Not Own|
|---|---|---|
|React Client| displays messages, medical information, and severity queues; symptom report form access| database access|
|Backend Python FastAPI| management of data validation to ensure correctly identified symptoms match correct severity, management of data ingestion | decision-making on behalf of doctors|
|SqLite + OpenFDA Drug Event Data Set| provides past information of patients, drug use, their physicians, and logged side effects. Also links this data into a simple, zero-config relational database file| data visualization|

## Data Entities & Relationships
- patients: id, name, gender, birthdate
- symptom log: id, owner_id, timestamp, current_medication_ids , symptoms
- medications: id, name, manufacturer
- ticket: id, patient_id, symptom_ids, severity, status

Each patient owns multiple patient logs. Each symptom log references one or more medications. Each ticket owns one patient and references symptoms.

## Authentication, Authorization, Secrets, & Persistent Data
Authentication relies on lightweight JSON Web Tokens (JWT) generated after validating pre-seeded synthetic credentials for patients and doctors. Authorization is strictly enforced using role-based access control inside FastAPI route dependencies, allowing patients to only submit logs and view their own prescriptions, while restricting ticket queue access and patient log overviews to doctors. Application secrets, such as JWT signing keys and database connection paths, are managed through environment variables using Pydantic settings. Persistent data is stored directly in a local zero-configuration SQLite database file named healthwatch.db, which is populated with synthetic user records and OpenFDA reference maps upon application startup.

## Decisions & Tradeoffs
SQLite was chosen  to ensure zero-configuration deployment and quick local setup, accepting the tradeoff that write concurrency is limited under heavy loads. The team opted to pre-load a normalized subset of the OpenFDA adverse drug event dataset locally rather than consuming live external APIs, trading real-time data updates for deterministic offline performance and freedom from API rate limits. Furthermore, the application deliberately restricts symptom input to structured forms instead of open-text responses, sacrificing user input flexibility to eliminate the need for complex natural language processing and guarantee predictable risk-scoring accuracy. Finally, healthcare integration standards such as FHIR and regulatory compliance protocols like HIPAA were explicitly excluded from the stack to focus entirely on demonstrating core user-experience improvements.

## Technical Risks and Spikes
