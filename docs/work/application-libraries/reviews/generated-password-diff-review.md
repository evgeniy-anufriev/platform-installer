# APPLICATION-GENERATED-PASSWORD — FULL DIFF review

Independent architecture-reviewer `/root/generated_password_plan_review`,
2026-10-21. Verdict: **BLOCK**, one unresolved acceptance blocker.

## Reviewed identity

- Base/HEAD: `e2b965b4256e22185a4652ef0fb133444a228fd1`.
- All 40 staged files; compiled frontend assets treated as derived output.
- SHA-256 of raw `git diff --cached --binary --no-ext-diff`:
  `86C0FE9BAC418C4401E295636212BB998ABAE6D290D258053C218F8B8890CB0A`.
- Reviewer independently computed and reconfirmed the fingerprint.
- Scope: generation, protected invocation files, four provider reconciliations,
  Vault publication, namespace/Agent references, UI, tests and contracts.

## AGP-D01 — BLOCKING / OPEN

The agreed full production-flow acceptance is incomplete. Actual React/Wails/Go
editor selection, Save/reopen/reset passed without a Core run. Native real
Vault/PostgreSQL exercises production preflight/provider-stage and Agent config
rendering, but no application/Agent startup. Kafka evidence uses a CLI fixture,
not a live broker. The required prepared connection-probe image is absent.

Therefore saved revision → real Core plan → authorized Apply → generated
credential delivery through Agent is not yet demonstrated. A target-free
Wails/Core check alone cannot close this finding.

Minimum remaining evidence: obtain the prepared QA image through an authorized
standard route, then run bounded disposable-account acceptance using existing
React/Wails/Core bindings, real Agent delivery and live-broker Kafka reset.
Cover first generated Apply, published-value reuse and mismatch reconciliation;
record revision, runtime identity, run ID, terminal result and safe observations.
Infrastructure credentials must remain unchanged. This finding does not
authorize image download, infrastructure Apply or baseline-account changes.

## Code assessment

No new blocking code/security defect was established. Generation stays in the
existing Apply action; projections carry descriptors/refs only. Protected
runtime files and `no_log` preparation carry values. Provider success precedes
Vault publication; no early Vault persistence was introduced.

Managed ownership/witness/UUID guards remain. Kafka admin/default are excluded;
existing mode remains strict. Separate Verify playbooks are unchanged and shared
helpers retain read-only failure on mismatch. Managed documents, sourceJobs,
policies, readFields and Agent templates share the Core namespace without project
ID; project-bound ownership remains, external vault_ref is unchanged.

Overengineering blockers: zero. No new standalone plugin/layer, DTO/API, store,
migration or recovery subsystem. Shared generated_password_ref is justified by
the two projections; standard Ansible tasks and standard-library secrets match
the approved single-writer scope.

## Prior findings and validity

- AGP-P03: OWNER_ACCEPTED operational single-Apply prerequisite, no technical lock.
- AGP-P04: RESOLVED; retry is bounded by established ownership/witness.
- AGP-P05: RESOLVED; path transition may generate a new password; legacy documents
  are retained without fallback.
- AGP-P01/P02: SUPERSEDED.

Reviewer read the staged code/tests/contracts, plan/reports, journal and safe
editor acceptance JSON; did not run tests or inspect secrets/hosts. Parent test
results remain attributed evidence. Review is CURRENT for the fingerprint above;
later evidence-only documentation does not change the reviewed code. No second
automatic FULL review or redesign is authorized. Return AGP-D01 to the owner.
