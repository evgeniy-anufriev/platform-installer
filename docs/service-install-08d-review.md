# SI08-D — initial FULL DIFF review

## Current owner-authorized exact correction

SI08-D-DIFF-06: **RESOLVED BY OWNER-AUTHORIZED EXACT CORRECTION**.
No additional architecture review/recheck was run after the exhausted budget.
The historical independent verdict below remains unchanged.

Protected private reservations precede directory creation; shared controller
and terminal recovery publish full pairs, complete empty reservations, or retain
partial/init-response-only material with OUTPUT_RECOVERY_REQUIRED. Missing
metadata is not generally ignored. No incomplete Fetch/ACK is admitted; no
second plaintext copy or new public contract is introduced.

Current-source offline proof: storage 24 PASS; lifecycle 38 PASS, including
crash before READY, terminal-before-publication recovery, Fetch/ACK and journal
retention before directory creation. Full Core 351 PASS/4 skips; contracts
31 PASS; Vault role 15 PASS; catalog/schema checks PASS. Affected Go race
checks, Windows full Go/vet and frontend 67/lint/build PASS. See
[implementation evidence](service-install-08d.md). SI08-E remains NOT STARTED.

## Historical owner-authorized targeted recheck

Verdict **BLOCK**, exactly one blocker: **SI08-D-DIFF-06**.
DIFF-01–05 **RESOLVED**. DIFF-07/08 have focused correction QA and were not
reopened. Zero new overengineering findings. The single recheck is exhausted.

Base: `1e110789a25cf4721e38fb78c7bb369d73c6dcd0`.
Scoped fingerprint verified before/after:
`e453ee6cd882ba32ee41f39f1d24293b3389fcd19c9dcaaee31a203403e0b7dd`.
Documentation/state was synchronized afterwards; production code unchanged.

### Remaining DIFF-06

Double plaintext custody is removed, but preparing one retained directory
creates a protected package before metadata exists. Evidence: controller:439
prepares it; secret_output:298 creates it; publish_retained_outputs:307 returns
None for missing entries. Admission/listing (secret_output:190,449) require
metadata before project filtering and do not recognize reservation. Lifecycle
recovery:578 attempts completion rather than READY publication.

Failure/cancel before full outputs can block listing and next-run admission,
including other projects. Crash after material is written but before READY
does not automatically make the last retained copy deliverable.

Smallest correction: explicit protected pre-publication reservation handling
inside the existing lifecycle. Admission/listing must distinguish reservation
from corrupt READY state. Terminal recovery must publish the complete pair,
safely handle no outputs, or preserve partial/init-response material with an
explicit recovery status. Merely ignoring all missing-metadata packages is unsafe.

Required proof: prepare→failure/cancel→next run; partial/init-response-only;
full pair→crash before READY→recovery→Fetch/ACK; other-project listing;
last-copy preservation and no ACK of incomplete/non-durable packages.

QA PASS does not cover that intermediate lifecycle. Final root race PASS
51.889s is parent evidence, not reviewer-executed QA. SI08-E NOT STARTED.
Further correction or review requires owner authorization.

## Historical initial FULL report

Independent reviewer: architecture-reviewer / Peirce. Verdict: **BLOCK**.
Base commit: `1e110789a25cf4721e38fb78c7bb369d73c6dcd0`.
Reviewed scoped worktree fingerprint:
`093e3986ab8da44689298267cf492c0521bf9864f08ad75ae4323ae022c40deb`.
The reviewer verified that fingerprint before and after the read-only review.
This record was added afterwards; production code has not changed since review.

The latest owner decisions are represented correctly: password on Installation
Plan, fixed `<project-root>/secrets/<deploymentId>/`, no folder picker,
project/deployment package binding and aligned entry names.

## Open blocking findings

| ID | Evidence / impact | Smallest correction and proof |
| --- | --- | --- |
| SI08-D-DIFF-01 | `execution_secret_output_protocol.py:11,16` and `execution_controller.py:302` derive incorrect module-utils/schema paths; a real runtime entrypoint cannot resolve them. | Resolve from the established bundle root; exercise the exact production subprocess in representative bundle layout without test-import setup. |
| SI08-D-DIFF-02 | Start checks the password but does not negotiate output-delivery capability before bootstrap. | Add the attested capability gate before Start; negative tests must prove no StartExecution call on unsupported, malformed or failed handshake. |
| SI08-D-DIFF-03 | File Sync is followed by directory rename without directory durability barriers. ACK can precede crash-durable local publication. | Platform-specific directory flush barriers; injected flush failures must forbid ACK; provide Windows and Linux evidence. |
| SI08-D-DIFF-04 | Linux publish uses staging pathname rather than proving it renamed the held staging object. Returned receipt can describe different bytes. | Prove destination identity and full receipt/ciphertext contents after publication; substitution tests must preserve foreign objects and prevent ACK. |
| SI08-D-DIFF-05 | ACK retry requires Fetch, but cleanup-pending or delivered packages no longer offer that frame. | Recover from bound local receipt; retry identical ACK without Fetch, including lost response and restart/reopen. |
| SI08-D-DIFF-06 | Controller capture leaves an additional plaintext copy in the run project after package ACK. | Use the agreed retained custody location or safely remove the captured source after durable capture; test role/controller/verify/terminal/ACK with history retained. |

## Open nonblocking findings

- SI08-D-DIFF-07: Plan UI may retain password-present state after broker expiry.
  Synchronize presence and restore input after PASSWORD_REQUIRED; cover expiry
  and project/plan changes.
- SI08-D-DIFF-08: Linux selected-file Open can block on FIFO before Fstat.
  Use O_NONBLOCK while retaining regular-file admission; prove bounded FIFO
  rejection without a writer.

Mandatory overengineering review identified the double plaintext custody in
DIFF-06 as the one unnecessary mechanism. Other reviewed abstraction,
parallel-authority, premature-feature and speculative-mechanism categories
had zero findings.

QA PASS results in `service-install-08d.md` were supplied by the parent; the
reviewer did not rerun them. No target, runtime secret material or vendored
source was inspected. Native UI and real runtime-entrypoint/recovery proof
remain limited by the findings above.

Six blocking findings remain OPEN. No production correction, commit or review
rerun follows this report automatically. Owner agreement on the bounded fixes
is required before the single permitted targeted recheck. SI08-E remains
NOT STARTED.
