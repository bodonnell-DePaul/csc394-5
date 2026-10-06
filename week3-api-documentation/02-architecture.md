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

## Decisions & Tradeoffs

## Technical Risks and Spikes
