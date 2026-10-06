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
| 6 |  | |
| 7 | | |
| 8 | | | 
| 9 | Preview Demo | |
| 10 | | |
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
|ID| Task & Output | Target & Dependencies|
|---|---|---|
| | |

## Definition of Done
- Acceptance criteria pass
- Lint, type checks, and unit/API test pass
- Documentation updated to match behaviour
- the change is integrated in shared environment when the environment exists.
## Testing, CI/CD, and release plan
Week 5: install lint; type check; unit tests; example validation. Use synthetic accounts for isolated test;

## Risks

## Fallback plan
