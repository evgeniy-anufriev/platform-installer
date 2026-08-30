---
name: qa-test-plan
description: Create a focused QA test matrix from a Platform Installer V2 milestone.
---

# QA test plan

Use before implementation or milestone verification to turn acceptance criteria
into a test plan. QA plans scenarios; they do not design or implement product
behavior.

Cover only the affected scope and classify:

- required positive scenarios;
- negative and boundary scenarios;
- contract/schema scenarios;
- regression risks;
- environment requirements;
- cases not testable locally.

Python/Ansible Core tests normally target the RED OS QA VM when the Windows
workstation lacks the required runtime.

Return: `Test Scope`, `Required Scenarios`, `Negative Scenarios`, `Contract
Scenarios`, `Regression Risks`, `Environment Requirements`, and `Not Testable
Locally`. Do not request full regression unless the milestone requires it.
