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
| 3 | Architecture, API, and Delivery plan |  |
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
| US-01/Must | As a patient, I can view my medical information so I can keep track my treatment progress | | |
| US-02/Must | As a doctor, I can view my patient's medical information so I have all info to make a decision | | |
| US-03/Must | As a patient, I can report symptoms easily so I can keep update my doctor to my current condition| | |
| US-04/Must| As a doctor, I can view patients through a queue based on severity so I can focus on high-risk patients before lower priorities| | |
| US-05/Should | As a user, I can message my counterpart in severe cases so that we can discuss the next steps urgently | | |
| US-06/Could | As a patient, I can be alerted by a notification, so I can remember to take my medication| | | 

## Engineering Tasks 
|ID| Task & Output | Owner | Target & Dependencies|
|---|---|---|---|
|EN-00 | Initial repository setup, FastAPI/Client linting, and a local health-endpoint cURL check| | W4, no dependencies.|

## Definition of Done
- Acceptance criteria pass
- Lint, type checks, and unit/API test pass
- Documentation updated to match behaviour
- the change is integrated in shared environment when the environment exists.
## Testing, CI/CD, and release plan
Week 5: install lint; type check; unit tests; example validation. Use synthetic accounts for isolated test;

## Risks

## Fallback plan
