# B0 — independent FULL DIFF review

Date: 2026-10-14. Reviewer: independent read-only architecture-reviewer
`/root/b_plan_review`. **Verdict: BLOCK. Unresolved blockers: 4.**
No code correction or TARGETED_RECHECK is authorized by this report.

## Identity

Base `cee36a3f737f70eb10347f0e3c50bfed398bf188`, branch
`codex/application-libraries-b0`. Deterministic identity manifest:
`.runtime/qa/b0/review-identity.txt`, SHA256
`235D4596A1D89C3B35600B5C0C59BB86ECE0C2781E04130DAB10528A4714E970`.
All 18 listed file hashes were verified before/after review. Scope: B0 source,
tests, versioned schemas and canonical docs. B1–B4/Go/UI excluded.
Owner approved B plan including B-P01/B-P02 clarifications and requested B0 implementation.
Verdict formed independently. Review validity: **CURRENT** for this identity.

## B0-D01 — BLOCKING, OPEN: staged account is compared before lease attachment

Locations: execution_protocol.py:655–659; infrastructure_verification.py:170–174;
existing execution_secret_lease.py:242–265.

start() calls infra.assert_admission before prelaunch=commit_binding. Only that
callback commits attached/<run_id>.json. target_username_for_run therefore returns
None before attachment. Evidence created with a normal credentialed Verify and
platform-automation account is rejected by library-only Start, even with the same
valid staged lease. Synthetic native tests bypass this _start_v2 ordering.

Smallest correction: compare against already validated staged lease identity before
commit, or align checking with existing commit/rollback ordering. Do not accept an
untrusted request account or weaken the account check.

Required proof: complete _start_v2 with staged trust/typed lease; same account allowed,
different account denied before target operations; rejected/uncertain Start does not
leave a wrong attempt mapping or duplicate run.

## B0-D02 — BLOCKING, OPEN: newer failure can leave an older PASS usable

Locations: infrastructure_verification.py:238–243,284–298;
execution_controller.py:1035–1043.

Verify-only with the same model/trust/account preserves all old index verifies.
If a newer SERVICE_VERIFY fails, publish only adds successful proofs and never
revokes old ones. summary can still return PASS by looking at the older successful
journals. Library-only publish returns immediately, so plan §6 provider/unknown
failure invalidation is also absent. This is a known newer negative observation,
not merely the limitation of historical Verify against undetected external changes.

Smallest correction: revoke usable evidence on failed/incomplete verification;
implement the agreed conservative invalidation for provider/unknown library failure.
Explicit application-only missing-binary failure must retain infrastructure evidence
as agreed. Use structured diagnostics, not stdout parsing.

Required proof: PASS→failed Verify-only→BLOCKED; incomplete coverage→BLOCKED;
provider/unknown library failure→UNKNOWN/BLOCKED; confirmed app-only failure retains evidence.

## B0-D03 — BLOCKING, OPEN: old publisher can restore an invalidated generation

Locations: execution_controller.py:646–649; infrastructure_verification.py:230–243,
288–298; execution_protocol.py:637–655.

Terminal becomes visible before infra.publish. Its index read/check/write is not
serialized with new-run begin/invalidation. Interleaving: old publisher reads G;
new infrastructure run begins G+1; old publisher replaces the index with its G;
new run fails and cannot repair the mismatch. Atomic replacement does not prevent
this lost update; old evidence may become usable after a newer infrastructure mutation.

Smallest correction: serialize generation invalidation and publisher read/check/write
with the existing admission/ownership lock, including terminal/cleanup/recovery ordering.
No new transaction manager or distributed lock service is needed.

Required proof: deterministic interleaving test; old publisher cannot restore G after
new begin, including FAILED/CANCELLED new runs.

## B0-D04 — BLOCKING, OPEN: BLOCKED Build violates new plan schema

Location: infrastructure_verification.py:306–310; plan/v1alpha5 required fields.

scope_plan sets v1alpha5 and executionMode, then immediately returns when the base
planner has no manifest. It omits required infrastructureVerification. Ordinary
validation/configuration failure thus produces a schema-invalid BLOCKED response.

Smallest correction: supply a bounded valid UNKNOWN/BLOCKED summary even when no
infrastructure model can be computed, preserving findings and absence of executable
manifest, or define the corresponding schema shape explicitly.

Required proof: schema-valid BLOCKED results for all modes: invalid project, missing
requirements and missing manifest.

## B0-D05 — NON_BLOCKING, OPEN: evidence objects are not closed wire schemas

Locations: plan/v1alpha5/schema.json:155; execution-manifest/v1alpha3/schema.json:279.
infrastructureVerification has only type:object. Python validates some private data,
but public status/code/deployments/evidenceRevision types, nullability and limits are
not specified. This risks divergence in B1 independent consumers.

Smallest correction: describe existing fields, enums, additionalProperties and bounds
in these versioned schemas; no new DTO/schema framework. Test valid PASS/BLOCKED/UNKNOWN
and invalid unknown-field/type/oversize objects.

## Overengineering and evidence

Unnecessary lifecycle/daemon/persistence frameworks:0; second desired-state authority:0;
premature B1–B4/UI scope:0; speculative execution paths:0. The module/index satisfy
the real cross-run requirement. Existing planner/controller and application-operation
$ref are reused. For D03 the existing active-run lock is the simpler mechanism.
Correctness/security must not be traded for fewer lines.

Reviewer directly inspected applicable AGENTS/procedure, owner-approved plan, exact
18 files, existing planner/lease/controller/trust/admission paths and test bodies.
No tests or target calls performed by reviewer; no files changed or secret material read.
Parent supplied focused25 PASS, earlier97 PASS; broad/offline completion was pending
at the review envelope. Synthetic localhost tests are not credentialed _start_v2 or
real infrastructure acceptance and do not disprove the findings.

## Process outcome

Implementation changes stopped on BLOCK. Four corrections and the single permitted
TARGETED_RECHECK need owner authorization under the review procedure. No finding has
been marked RESOLVED or OWNER_ACCEPTED. No automatic correction cycle was started.
