---
name: qa-validation
description: Validate completed Platform Installer V2 changes with focused tests and concise evidence.
---

# QA validation

Use after implementation. Read [QA procedure](../../../docs/agent-procedures/qa.md)
before Core/service QA or real WebView tests; it owns environment, exact source
transfer/cleanup, PEM/session/trust and established EXEC-01 SSH/sudo prerequisites.
The Windows workstation is not the Core/Python QA runtime. Use current sources
on RED OS; missing Windows Python/Ansible is not a reason to skip available QA.
Do not use admin/password sudo fallback for the configured EXEC-01 connection.

Run targeted tests first; full regression follows the milestone's applicable
gates. Supported platform-independent Go/frontend/static checks may run locally.
Do not modify production code by default or repeat unaffected accepted
failure/recovery scenarios. Read [runtime bundle procedure](../../../docs/agent-procedures/runtime-bundle.md)
before updated-bundle UI QA, and [SI11 procedure](../../../docs/agent-procedures/si11.md)
for that user-flow cycle. Real React/Wails acceptance is mandatory for affected
flows; mocked bindings/direct harnesses do not replace it. Visual PASS is separate.

For Core/service changes check, as applicable:

- deterministic output, read-only `changed=0`, valid/invalid representative fixtures;
- schemas/catalog reproducibility and standalone playbook behavior;
- target-free/offline guarantees and no unintended host mutation;
- secret exclusion from project, events, output and diagnostics.

Record unavailable checks and prerequisite failures explicitly as `NOT TESTED`
only when the required environment, credentials or execution capability is
unavailable (including a required ALT-specific platform). An unavailable required
real bridge is blocking. Report executed scope, passed, failed/unavailable gates,
relevant failure evidence and remaining acceptance limits. Never dump successful
logs or credential values. Do not copy secrets into remote QA workspaces.
