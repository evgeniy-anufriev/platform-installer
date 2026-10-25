# SZI-STAGE3 — TARGETED_RECHECK D01/D02

Date: 2026-10-24. Reviewer: `/root/szi_stage3_diff_review`, architecture-reviewer.
Owner explicitly authorized corrections, actual protocol tests and one targeted
recheck. Verdict: **APPROVE**, independently formed. Open BLOCKING findings: **0**.

## Identity and scope

Base/HEAD `24e24f9594b38b484682d27e433bc25b572935b5`.
Reviewed worktree fingerprint SHA-256:
`E6CDB25B500BC821D58AA4E2D588B06BB38B9E5E62FDB45CDAD7493CB52A76EB`.
The reviewer verified all listed hashes/deletions in the local input manifest
`.runtime/qa/szi-stage3/results/diff-recheck-input.json`. The original FULL input
and [BLOCK report](szi-stage3-diff-review.md) remain historical evidence unchanged.

Scope is limited to SZI3-D01/D02 and their immediately affected schema, parser,
protocol and manifest admission boundaries. No second FULL review was performed.

## Findings

- **SZI3-D01: OPEN → RESOLVED.** Manifest v1alpha6 permits exactly Apply-only and
  Apply+Verify. Callback credential scope is not broadened. The native test covers
  resolver → image preparation → Ansible planner → manifest admission with a
  skipped provider and Apply-only token reference; Apply+Verify is accepted and
  unknown/Verify-only operation scopes rejected. Old schema versions are unchanged.
- **SZI3-D02: OPEN → RESOLVED.** Build v1alpha7 uses a nonempty project path string;
  its parser rejects an object and empty string. Image phase field sets agree.
  The same JSON is checked by canonical SchemaValidator and actual request();
  native subprocess requests also undergo schema validation before sending.

New blocking regressions in these boundaries: **0**. Overengineering findings:
**0**. Existing schemas/parser/tests are reused without new DTO, persistence,
lifecycle or speculative mechanisms.

## Evidence and limitations

Reviewer directly inspected corrections, tests, admission code and saved results:
protocol **2 PASS / 91.294 seconds**; current application regression **220 tests,
218 passed / 2 skipped / 548.723 seconds**. Parent executed these on RED OS;
reviewer did not run tests or access hosts/secrets.

The broader Core regression was still running on the pre-correction source at
review time; its PASS was not assumed. Real Wails and SDKU/CSPA stand acceptance
remain unperformed under the owner hold. No deployment plan/run is authorized.

Validity: **CURRENT** for the reviewed implementation identity. Subsequent changes
to checked schema/parser/admission code require reassessment of that boundary.
Post-review evidence/status documentation does not modify the reviewed code.
