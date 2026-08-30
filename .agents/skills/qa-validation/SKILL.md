---
name: qa-validation
description: Validate completed Platform Installer V2 changes with focused tests and concise evidence.
---

# QA validation

Use after implementation. Run targeted tests first; reserve full regression for
milestone completion. Do not modify production code by default. Do not paste
complete successful logs; report relevant failures and evidence. Mark unavailable
checks explicitly as `NOT TESTED`.

For Ansible/Core changes, check when applicable:

- deterministic output and read-only `changed=0`;
- valid and invalid fixtures;
- schema and offline validation;
- secret non-leakage;
- standalone `ansible-playbook` behavior;
- no unexpected target contact or VM mutation.

Return: `Test Scope`, `Tests Executed`, `Passed`, `Failed`, `Not Tested`,
`Findings`, `Regression Risks`, and `Recommended Next Actions`.
