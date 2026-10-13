# A8 FULL PLAN review

2026-10-13. Independent architecture-reviewer: `/root/a8_plan_review`.
Verdict: **BLOCK**. One blocking finding, zero proven overengineering findings.
HEAD `004a465796fcd3d1b75706d529de9d0d44126fa8`, branch codex/application-libraries.
Reviewed plan SHA256:
`74b9b00ef73ed29a529f548c4b7de68e9db379373714d643fd662f7776fa81d8`.

## A8-P01 — OPEN, BLOCKING

Fresh Vault same-run token handoff lacks an executable source contract.
Plan section 5 promises bootstrap reuse, but current A7 requires the token in
operator lease and materializes application inputs before infrastructure dispatch.
Output capture currently occurs only at terminal run handling.

Evidence: application_plan.py:70; execution_secret_lease.py:292;
execution_controller.py:591,628,747,928. Paths are relative to the existing
Core module_utils/tools directories. The reviewer read these source boundaries;
no tests, target contact or secret files were used for this PLAN review.

Impact: a fresh Vault cannot supply its newly generated token to the application
hook during the same run under the described current sequence.

Smallest correction proposed by reviewer:

1. Digest-bound manifest distinguishes operator input from bootstrap output of
   exactly this run and this Vault deployment, by extending current descriptors.
2. Bootstrap-derived token is not required as a preexisting operator lease value.
3. Materialize the dependent application inputs after all infrastructure Verify
   succeeds and before application dispatch, from existing protected run outputs.
4. Reuse existing file protection/custody/cleanup; expose token only, not unseal
   shares; missing output or provider mismatch blocks application mutation.
5. Specify an unambiguous source selection if both sources exist and describe
   repeat behavior when Vault is already initialized.

Required evidence after implementation: actual fresh-Vault mixed run without
operator admin token, missing output/provider mismatch negatives, boundary cancel
and cleanup, existing-Vault operator-input regression.

## Other conclusions

One mixed manifest/run, two fixed application operations, all-infrastructure
Verify barrier, existing sequential fail-fast controller and no barrier play
are appropriate. Schema completion and negotiation are necessary. No new
scheduler, desired-state persistence or custody subsystem is justified.
Go/UI/selective/resume/rollback/Kafka ACL remain outside A8.

Review validity: CURRENT for the identity above. FULL PLAN budget consumed.
Stop for owner decision on P01; no automatic correction or new FULL review.
At most one owner-approved TARGETED_RECHECK may inspect the corrected finding.
This report does not authorize implementation or claim DIFF/QA acceptance.
