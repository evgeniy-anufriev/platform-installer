# Library-host lock removal — FULL DIFF review

Independent reviewer: /root/library_lock_removal_review, 2026-10-18.
Verdict: APPROVE_WITH_CHANGES. Blocking findings: 0.
Base: 61e75659265ccee62d71c76cfed8c8db70c7df52.
Scoped diff SHA256 (UTF8, LF joined, no terminal LF):
0e4cf9364799107ac92a4c0656f24f9d422b5368d7aa1b194538b921086c807e.

Scope: application-libraries-apply.yml and application_runtime/tasks/apply_library.yml.
Removed mkdir/.apply-lock, acquisition assertion, held-list and always/rmdir.
Preflight, all-selected materialize/Compose validation before activation,
any_errors_fatal, ownership, shared projection and image/source authority remain.
No residual Core references to removed symbols outside vendored sources found.

LOCK-R01 NON_BLOCKING: A2 plan still promised atomic mkdir/always release and
manual abandoned-lock recovery. Minimum correction: document current owner
removal decision and operator coordination of unsupported external concurrent Apply.
Disposition by implementer: RESOLVED in A2 plan and ADR-045; no re-review required.

Overengineering: zero new abstractions, DTOs, stores or replacement locks.
Explicit tradeoff: Core no longer prevents external simultaneous standalone Apply
to the same library directory; owner instructed removal in the sequential model.
Reviewer performed read-only code/doc/diff inspection and diff --check, no runtime
QA or real installation acceptance. Current for the two reviewed YAML files.