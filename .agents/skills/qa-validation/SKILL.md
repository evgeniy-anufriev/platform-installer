---
name: qa-validation
description: Validate completed Platform Installer V2 changes with focused tests and concise evidence.
---

# QA validation

Use after implementation. Run targeted tests first; reserve full regression for
milestone completion. Do not modify production code by default. Do not paste
complete successful logs; report relevant failures and evidence. Mark unavailable
checks explicitly as `NOT TESTED`.

## Test Execution Location

A. If the required tools exist locally and the test is platform-independent, run targeted tests locally.

B. If Python/Ansible is unavailable on Windows, use the configured RED OS test VM.

C. Do not immediately return `NOT TESTED` merely because Windows lacks Python/Ansible.

D. Return `NOT TESTED` only when:

- the required RED OS environment is unavailable;
- credentials are unavailable;
- the environment cannot execute the required test;
- the test requires an unavailable platform such as ALT Linux.

For RED OS QA:

1. Resolve test VM connection credentials from the existing runtime-only test credential mechanism.
2. Never print passwords or sudo passwords.
3. Create a temporary remote workspace.
4. Transfer the exact current-working-tree files required for the test.
5. Run targeted tests first.
6. If targeted tests pass, run milestone regression as required.
7. Run offline checks such as `unshare -n` where applicable. If the RED OS
   VM requires elevation for `unshare -n`, resolve the sudo password only at
   runtime from the configured `.runtime/secrets` mechanism and pass it to
   `sudo` without placing it in argv, files, or logs. Never print, echo, or
   persist the credential. If the runtime-only sudo credential is unavailable,
   report the prerequisite failure as `NOT TESTED`.
8. Capture concise results.
9. Remove the temporary workspace.
10. Verify no unintended target contact or system mutation for read-only Core milestones.

Do not copy secrets into the remote workspace or logs. Do not use a stale
checkout or remote artifact in place of the current working tree.

For Ansible/Core changes, check when applicable:

- deterministic output and read-only `changed=0`;
- valid and invalid fixtures;
- schema and offline validation;
- secret non-leakage;
- standalone `ansible-playbook` behavior;
- no unexpected target contact or VM mutation.

Return: `Test Scope`, `Tests Executed`, `Passed`, `Failed`, `Not Tested`,
`Findings`, `Regression Risks`, and `Recommended Next Actions`.
