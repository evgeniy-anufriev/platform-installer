# SZI-STAGE3 — independent FULL DIFF review

Date: 2026-10-24. Reviewer: `/root/szi_stage3_diff_review`, architecture-reviewer.
Verdict: **BLOCK**, independently formed; **2 OPEN BLOCKING findings** on the
reviewed revision. No overengineering findings. Target acceptance was not run.

## Reviewed identity

Base/HEAD `24e24f9594b38b484682d27e433bc25b572935b5`, branch `codex/szi-stage3`.
Worktree fingerprint SHA-256
`3DC952DAA99744B9A43BB106269972742FBB315BB8186516711BFD84CAE87441`;
81 file hashes/deletions verified by the reviewer. The local input manifest is
`.runtime/qa/szi-stage3/results/diff-review-input.json`.
Plan SHA-256 `4DE51E6D62E5EB71FE62B57DEF88D8E703B4507DBD46D93EC237F16EAF87BBEA`.

Scope: complete Stage3 Core/Ansible, versioned contracts, Go/UI, CSPA/nginx,
tests and documentation. Generated dist checked by identity without minified
code review. Review was read-only; no target or secret access, no tests run by
the reviewer. Parent-reported evidence is recorded in the implementation journal.

## SZI3-D01 — BLOCKING / OPEN on reviewed revision

`contracts/execution-manifest/v1alpha6/schema.json:134` allows only the exact
Apply+Verify operation array for application secret requirements. Core correctly
produces Apply-only requirements for connection/integration callbacks, including
the credentials of a skipped provider. Real BuildDeploymentPlan subsequently
validates the emitted manifest and rejects it with EXECUTION_MANIFEST_INVALID.
The existing model/native callback tests did not exercise that admission boundary.

Smallest correction: allow supported canonical operation scopes in the new
v1alpha6 schema. Do not broaden secret delivery to Verify or modify old schemas.
Verification: real target-free protocol Build with skipped provider callback
credentials, integration_apply credentials, manifest admission and rejection of
an unknown operation.

## SZI3-D02 — BLOCKING / OPEN on reviewed revision

`contracts/execution-runtime/v1alpha7/build-deployment-plan.schema.json:31`
declares project as an object, while production Go/runtime and the native protocol
test use an absolute path string. The canonical public request contract disagrees
with the production boundary.

Smallest correction: use the existing string path contract, without a new DTO.
Verification: the same request must pass both canonical SchemaValidator and
execution_protocol.request; an object must fail both. Check required/phase fields
of v1alpha7 image DESCRIBE/PREPARE as well.

## Overengineering and validity

Confirmed unnecessary mechanisms: **0**. The shared Core selection helper,
minimal provider script contexts, integration_apply phase, versioned closed
schemas and invocation selection in PlanRecord each serve the current requirement.
No new persistence, speculative plugins, generic CRUD or premature concurrency.

FULL verdict remains historical evidence for the exact fingerprint above.
Corrections require a new exact identity and one owner-authorized targeted recheck
of D01/D02 and their immediately affected boundaries, rather than another FULL.

Owner subsequently authorized D01/D02 corrections, real protocol tests and one
TARGETED_RECHECK on 2026-10-24. Real installation plans/runs remain forbidden.
Correction and recheck results will be recorded separately; this initial BLOCK
verdict is not retroactively changed.
