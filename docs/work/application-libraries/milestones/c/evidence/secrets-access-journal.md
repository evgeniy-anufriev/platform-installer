# Secrets access — implementation journal

2026-10-16. Owner approved the technical plan and implementation. Corrections
authorized; independent TARGETED_RECHECK APPROVE, zero blockers; QA IN PROGRESS;
not a completed Core/UI milestone. Existing unrelated UI work is preserved.

## Owner-requested commit checkpoint

2026-10-16: owner requested a commit of the implemented application UI/Core
access work and UX mockup refinements, not master synchronization or milestone
closure. Final production Core regression: 701 run, 680 PASS/21 standard SKIP,
4643.688s. PostgreSQL native11 PASS/1524.178s; Redis ACL focused2 PASS/0.390s.
The earlier Redis invocation discovered zero tests and is not counted as PASS.
Final frontend243 PASS/22files, lint/typecheck and Wails production build PASS.
Known-value source/evidence audit: 20 values, 374 files, zero matching paths;
values never printed. Generated Wails binding formatting churn was discarded.

Real run `installer-6cb2795b13d0ae21e04cc7ae807e75cc` used bundle
`sha256:53b140dabebf64bc4ed0944c3c6013d46a0b63bf30d9f68f18479e88e138796e`,
10 infrastructure Verify and library Apply/Verify, zero infrastructure Apply.
Observed library Apply completed and Verify started at14:22:25Z. The browser
observer ended with OBSERVATION_TIMEOUT_RUN_NOT_CANCELLED; no terminal success
is claimed, no cancellation/restart was issued. Final target result, repeat,
latest live UI/visual acceptance and new temporary-workspace cleanup remain
outstanding. This commit is an implementation checkpoint, not QA completion.

Mockup-only follow-ups remove instance Connections/Ports tabs, consolidate
General with ports/endpoint/readiness and service summary linking to library,
and use compact grouped credentials/access. Browser interaction checks and
1440/1024 screenshots inspected; General fits1024x900. Production tab removal
and full mockup parity are not claimed. Primary desktop widths1440/1024;
smaller/mobile composition is outside the accepted design baseline.

## Implemented scope

* Canonical account databaseAccess, capability-gated provider projection and
  one account across owned databases. Reconcile scope retains removed DB access.
* Existing Ansible combine order retained. A small Core filter makes the two
  grant-policy alternatives atomic; an explicit new policy clears inherited
  legacy databaseRef/grants, never credentials. Mixed declarations are rejected.
  No new Go DTO, writer operation or persistence is required: the existing typed
  accounts edit carries the complete selected policy. This implements the
  approved atomic switch through the existing edit session.
* PostgreSQL batch grants, database-wide defaults, owned reconciliation and
  readonly Verify reuse current SQL sessions/locks/quoting/markers.
* Compact credential/access tables, explicit legacy-policy switch, DB-filtered
  access CRUD and creator roles; structured Redis ACL. Runtime lease unchanged.

## Evidence so far

* Owner screenshot follow-up: compact credential rows now keep source/value and
  small Save/Reset actions on one line; inheritance metadata is a tooltip.
  Multi-field Vault/PKI references retain labels. Focused frontend24 PASS,
  typecheck/lint/build PASS. Visual acceptance pending current target terminal;
  no second browser client opened during the running real Wails execution.
  This layout-only delta does not change the reviewed Core policy or lease.
  Second screenshot refinement: connection title and collapsed Settings share
  one header row; account mode, administrative secrets and legacy settings are
  inside Settings. Removed the repeated connection line, reduced card/table
  spacing. Focused24 PASS; visual acceptance still pending target terminal.
  Owner then rejected the separate variable-bindings area, including a collapsed
  version: removed it from the instance screen. The existing secret_bindings
  editor now renders inline per credential in the variable column, with edit,
  save and reset. Package names remain inherited under the existing contract;
  authored aliases can be replaced/removed, other credentials/shared bindings
  and Agent settings are preserved. Added inline save/reset/collision tests;
  focused24 PASS, lint/typecheck/build PASS. Real bridge/visual check pending.
* RED OS workspace `/var/tmp/platform-installer-qa-cffb440b17364d94b40f1a179b41b902`:
  application libraries18 and providers17 unit tests PASS.
* Isolated PostgreSQL16.14 native provider suite9 PASS /242.046s, including the
  new existing/future/revoke/repeat test. Four DBs, one LOGIN; owner and explicit
  migration role create future schema/table/sequence; app INSERT/SELECT works,
  ungranted DELETE fails; revoke and unchanged repeat changed0. No deployed DB
  or service changed. Additional negative cases added afterwards, pending QA.
* Final frontend241 PASS /22files, typecheck/lint/Vite build PASS; focused20 PASS.
* Real React/Wails Save/reopen PASS: explicit legacy switch, add SELECT/INSERT,
  delete last access without deleting account. Safe evidence:
  `.runtime/qa/application-design/secrets-access-wails.json`. Earlier selector/
  disabled-control attempts FAILED and retained, not product execution failures.
* Catalog regenerated on RED OS, source locks copied back; configuration schema
  reproducibility PASS. Full Core regression running, not yet PASS.

## Open acceptance issue

ClickHouse currently refuses observed grants outside desired grants with
CLICKHOUSE_APPLICATION_GRANTS_DRIFT. Its existing contract can represent several
DBs but does not automatically revoke a removed grant. Therefore the UI can
stage removal, but target removal acceptance is NOT established. Do not relax
this guard or claim the whole Secrets flow PASS. Independent FULL DIFF review
must assess the smallest safe correction/required owner decision.

## Final review checkpoint

[Independent FULL DIFF](../reviews/secrets-access-diff-review.md): BLOCK, two
findings. SEC-D01 target-account ownership/self-creator rejection missing;
SEC-D02 CH revoke semantics need an explicit owner decision. No source correction
after review. Owner approval plus one targeted recheck are required to continue.
Additional isolated native negatives PASS /89.583s in current-source workspace
`/var/tmp/platform-installer-qa-6b838cce47eb4bc79a1928d173e1c84c`: unknown creator,
PUBLIC DML/default ACL, foreign ownership, missing defaults Verify failure,
INSERT reduction/sequence revoke, column ACL conflict. Catalog and configuration
schema reproducibility PASS. These do not cover/fix the SEC-D01 self-owner gap.
Real React/Wails final credential-table version CRUD Save/reopen PASS;
`.runtime/qa/application-design/secrets-access-wails.json` contains latest fixture.
Owned isolated test clusters/secrets removed by test teardown. Public source
workspaces retained while full Core regression remains active (exec session78721,
log `qa-core-regression.log` in cffb workspace); no final regression PASS claimed.

No infrastructure Apply, target clear, password reset, commit or master sync.
Runtime secrets/Agent/Vault end-to-end acceptance with the new contract, final
review, hygiene and cleanup remain outstanding.

## Owner-authorized correction / targeted recheck

SEC-D01 is OWNER_ACCEPTED: object ownership/self-creator is allowed; preserve its
authority and explain that DML revoke does not remove it. Native positive owner
case PASS65.554s: schema/table/sequence ownership and ACL unchanged, future objects,
removal and subsequent changed0. Existing membership/admin/foreign guards retained.
SEC-D02 RESOLVED: only direct SELECT/INSERT on the account's witnessed managed
library DBs are reconciled. Foreign/role/column/partial/grant-option conflicts
remain. Existing SQL batch/cluster/witness used, no ledger/concurrency/DTO.
[TARGETED_RECHECK](../reviews/secrets-access-targeted-recheck.md) APPROVE, no blockers,
identity2F5AE86A…907679. Canonical docs/ADR043/roadmap synchronized.

Current-source ClickHouse native suite4 PASS292.764s: standalone and real three-
server TLS/ON CLUSTER, two DBs, INSERT reduction, deletion of one/last access,
neighbor preservation, foreign assignment refused unchanged, Verify/repeat,
identity/witness and password/log safety. Full final Core regression is running
in workspace28036d8083f2457cb77ebe965e03da6d (session24911, qa-core-final.log).
No infrastructure Apply. New runtime built on trusted node2 from all237 rehashed
approved P2 runtime input files; standard validation/publication/real UI gates pending.
