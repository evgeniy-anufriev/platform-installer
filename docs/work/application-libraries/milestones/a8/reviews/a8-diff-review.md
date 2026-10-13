# A8 FULL DIFF review

2026-10-13. Independent architecture-reviewer /root/a8_diff_review. Verdict: **BLOCK**. Open blockers: 2. This is the only FULL DIFF review; corrections and one TARGETED_RECHECK require owner decision under docs/agent-procedures/review.md.

## Identity and scope

HEAD 004a465796fcd3d1b75706d529de9d0d44126fa8, branch codex/application-libraries. All 20 files in ../evidence/a8-source-identity.txt were independently checked; SHA256 match. Source-set fingerprint (sorted path + space + SHA256, LF joined without trailing LF): 6ac71430874ff818f88bbb8a97f39f4bd25715b2cd7ff2a63f625d343fcfb9c2. Accepted plan SHA256: bfb0eb8622f139faac2b76ac334500a8a5c81961ef7130123a082cfd655eaabf.

Mixed Core planning/manifest/protocol, infrastructure barrier, Vault token handoff, existing controller lifecycle/target trust and bounded Docker PKI correction. No target contact, secret reads, edits or independently executed tests. No expected verdict supplied.

## A8-D01 — BLOCKING, OPEN

**Materialization failure can leave an active run and uncleared temporary secrets.**

Evidence: ansible-core/tools/execution_controller.py:837, file writes at 867 and 883, dispatch at 1030; handler at 1037 catches only LifecycleError. New _materialize_application_projection performs file/JSON I/O after infrastructure succeeds. OSError while creating/writing files or ValueError reading the projection escapes to the external handler at 1047, without _finish_run_with_outputs, terminal result or temporary-input/lease cleanup.

Smallest correction: convert errors at this materialization boundary to LifecycleError with a fixed safe code, retaining existing terminal/cleanup path. No recovery subsystem required.

Required checks: inject errors after the first application secret is created and during projection write; expect FAILED, no application dispatch, temporary secrets/lease removed, durable bootstrap outputs preserved. Check Cancel next to this boundary.

## A8-D02 — BLOCKING, OPEN

**Final-source acceptance remains incomplete.**

Evidence: evidence/a8-test-journal.md and accepted plan section 8. At review snapshot final fresh-Vault run was RUNNING. Bootstrap -> application hook -> Agent, explicit-token repeat, final mixed repeat/Cancel, infrastructure-only regression and full credential cleanup have no terminal acceptance. Interim success uses another version.

The current fixture checks a shared Vault marker and removes account-provider connections, while the accepted plan requires at least one account provider. The failure/cancel unit test simulates infrastructure failure on the first operation; it does not separately prove application Apply failure skips application Verify.

Smallest correction: finish the approved bounded QA matrix and record missing scenarios; no full A4/A5 security rerun.

Post-review observation by implementer: final run installer-3ad7e260db343aa3e6f6b2060a388721 reached FAILED in Vault member validation, without application start. This updates runtime evidence, not the review verdict or D01.

## Overengineering and evidence limitations

Proven overengineering findings: 0. Existing run/lease/custody/journal are reused. No scheduler, rollback/resume, competing desired-state store or duplicate DTO discovered. Contract versions are justified by explicit mixed execution/source binding; Docker selector adds no tasks/resolver.

Reviewer inspected instructions/procedure/skill checklist, accepted plan/P01 decision, changed Core files/schemas/tests and canonical contracts. git diff --check passed. Parent-reported RED OS 243 cases (239 PASS/4 skip), native planning5 PASS, bundle validation and runtime results were supplementary; incomplete broad regression was not treated as PASS.

Validity: CURRENT for reviewed source identity. Finishing QA alone does not resolve D01. Automatic implementation stopped after BLOCK; owner decision pending.

## Owner decision after FULL report

Owner accepted restoring previous write-error handling without a new mechanism. A8-D01 correction uses existing LifecycleError, terminal and Journal cleanup methods; focused RED OS 120 PASS, including partial-write and Cancel tests. This is implementer evidence, not an independent reviewer verdict. D01 is corrected pending independent recheck; D02 acceptance remains open. No automatic recheck was invoked.
