# A8 DIFF TARGETED_RECHECK

2026-10-13. Independent architecture-reviewer /root/a8_diff_review. Owner explicitly requested recheck. Verdict: **BLOCK**. Scope: A8-D01–02 and immediately affected boundary only.

HEAD 004a465796fcd3d1b75706d529de9d0d44126fa8, branch codex/application-libraries. Current 20-file source identity independently confirmed: 652222971554b232dbea87abcbba8f26dcf20c96aff24c5f12a48258a68a2beb. See ../evidence/a8-recheck-source-identity.txt; sorted path + space + SHA256 joined LF without trailing LF. Since FULL only execution_controller.py and test_application_mixed_execution.py changed.

## A8-D01 — RESOLVED

execution_controller.py:907 converts OSError/ValueError to fixed LifecycleError('APPLICATION_RUNTIME_PREPARATION_FAILED'), handled by existing terminal path. Line315 calls existing application-input cleanup. test_application_mixed_execution.py:129 exercises four error/Cancel scenarios through real main/dispatch/terminal, physical temporary secret/projection and attached lease removal, bootstrap output preservation and safe result code. Owner-approved previous handling restored without a new mechanism.

## A8-D02 — OPEN, BLOCKING

Final fresh-Vault run installer-3ad7e260db343aa3e6f6b2060a388721 FAILED before application start because fixture member vault-one lacks the established numeric suffix. Bootstrap -> hook -> Agent is not proven. Explicit-token repeat, account-provider mixed integration, final mixed repeat/Cancel and infrastructure-only regression remain unverified. Unit fault injection is supplementary.

Smallest remaining action: fix the bounded QA fixture and finish accepted plan section8 scenarios on current code. No additional functionality required. No owner decision waiving this acceptance gate is recorded.

## Evidence, simplicity and budget

Reviewer directly checked SHA256, correction, test and journal; git diff --check PASS. Parent-reported RED OS120 PASS is journaled; tests not independently rerun. Fault-test subprocess/output delivery are mocked. No target contacts, edits or secret reads.

New overengineering findings: 0. Existing exception/terminal/cleanup/lease mechanisms reused; no DTO/store/lifecycle layer or expanded scope.

Validity CURRENT for this identity and targeted scope. One open blocker: A8-D02. One FULL plus one owner-authorized TARGETED_RECHECK consumed; further review requires explicit owner request. Automatic work stopped pending owner decision on remaining QA gate.
