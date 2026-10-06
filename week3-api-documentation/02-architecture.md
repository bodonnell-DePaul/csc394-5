# 2. Architecture

## Component boundaries
[A diagram showing the client, API, database, external services, and how they communicate]
   
 

Component Descriptions

Component | Owns | Does Not Own

|Backend Python FastAPI| management of data validation to ensure correctly identified symptoms match correct severity, management of data ingestion | decision-making on behalf of doctors|
|SqLite + OpenFDA Drug Event Data Set| provides past information of patients, drug use, their physicians, and logged side effects. Also links this data into a simple, zero-config relational database file| data visualization



## Data Entities & Relationships

## Authentication, Authorization, Secrets, & Persistent Data

## Decisions & Tradeoffs

## Technical Risks and Spikes
