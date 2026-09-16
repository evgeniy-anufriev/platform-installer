# UI-01F2 architecture review

Plan: `docs/ui-01f2-architecture.md`

Baseline and HEAD:
`431c1704fcc9d4054305dfb2be216ad406a71b18`

Implementation status: **NOT STARTED**

## FULL PLAN review

Reviewed plan SHA-256:
`4f7b9e5cafd9bcfaf48b65fb8b718c2046024a4d8c69a07e261ee63a782bd405`

Parent architecture blob:
`adb2e444be49535580b18c1b365da94d2048e2fb`

F1 architecture blob:
`aafc99ed64ae1b1d731c95a24bae64f08a06bb5b`

Verdict: **BLOCK**

### Blocking findings

#### UI01F2-PLAN-001 — certificate-scope references

Status: **BLOCKING / OPEN**

The proposed closed reference graph omits canonical certificate-scope source
references to hosts, service deployments and deployment/member pairs. A server
or deployment delete, or member removal, could therefore publish dangling PKI
references even though PKI editing itself remains deferred.

Smallest correction:

- add certificate-scope host, deployment and deployment/member edges to the
  closed generic reference table;
- apply `REFERENCE_IN_USE` to entity/member removal while those preserved
  references remain;
- fail closed on malformed known certificate-scope reference fields;
- add positive/negative host, deployment and member removal tests for each
  canonical certificate-scope source form.

#### UI01F2-PLAN-002 — placement mutation universe

Status: **BLOCKING / OPEN**

The plan reconciles placement only across the final server set. If one session
deletes a server and removes its placement, the old managed host document may
fall outside that set and retain stale canonical placement.

Smallest correction:

- define the mutation universe as the bounded union of safely discovered
  initial managed host documents and final-state hosts;
- reconcile across that union;
- block server deletion while any retained placement remains;
- permit the empty managed host document to remain after all explicit
  placement removals;
- test delete-plus-reconcile in either command order, multiple deployments,
  orphan managed host documents, unsafe paths and reopen.

#### UI01F2-PLAN-003 — catalog availability authority

Status: **BLOCKING / OPEN**

The F2 draft requires a READY catalog for every topology command. That is
stricter than the parent architecture, which assigns catalog admission to
catalog-dependent vocabulary/capability edits and preserves unrelated safe
structural operations when the exact catalog is unavailable.

Smallest correction:

- require fresh READY catalog admission for deployment creation, placement
  reconcile and consumer endpoint assignment;
- allow clear/delete and endpoint-group structural CRUD under the closed
  structural/reference guards when catalog is `UNAVAILABLE` or
  `INCOMPATIBLE`;
- prove no fallback catalog or lock rewrite occurs.

An alternative would require an explicit owner-approved parent-architecture
change expanding catalog authority.

### Nonblocking finding

#### UI01F2-PLAN-004 — effective command count

Status: **NON_BLOCKING / OPEN**

The draft names the 1,024-command session bound, while current structural
Review has an effective 16-command bound. The plan must explicitly retain 16
or deliberately change it and align resource/boundary tests.

### Overengineering review

- unnecessary abstractions: **0**;
- duplicate contracts/DTOs: **0**;
- premature scope: **0**;
- speculative features: **0**;
- missed simpler mechanisms: **0**;
- blocking overengineering findings: **0**.

The narrow fresh-catalog resolver injection, reuse of `EditCommand`,
`ManagedProjectView` and the existing structural transaction, and a closed
reference table were considered proportionate. No generic graph/filesystem
framework is justified.

## Evidence and validity

The reviewer directly inspected repository instructions/state, the exact F2
plan, parent F architecture, F1 architecture/implementation, UX/mockup,
published edit/project contracts and targeted current Go integration seams.
No tests were run because this was a documentation-only PLAN review. No F2
implementation or QA evidence exists, and no Core, Execution Node or target
host was contacted.

Review validity: **CURRENT** only for the reviewed plan SHA-256 and baseline
above. Any plan correction changes the SHA-256 and makes this FULL review
historical. The allowed next review, if authorized by the owner after bounded
corrections, is one `TARGETED_RECHECK` of `UI01F2-PLAN-001`,
`UI01F2-PLAN-002` and `UI01F2-PLAN-003` plus immediately introduced
regressions. The nonblocking command-limit clarification can be included in
the correction but does not broaden that recheck.

Unresolved blocking findings: **3**.

UI-01F2 implementation must not begin under this blocked plan.

## Owner-authorized blocker correction

The owner authorized a plan-only correction limited to the three original
blocking findings and the nonblocking command-limit clarification:

- `UI01F2-PLAN-001`: the closed reference graph now includes canonical
  `certificateScopes.sources.hosts`, `serviceDeployments` and member references;
  member identity is the contract's composite `(deploymentId, memberId)`, not
  a globally unique `memberId`;
- `UI01F2-PLAN-002`: placement traversal is now the bounded union of source
  Installer-owned managed host documents and final-state server IDs;
- `UI01F2-PLAN-003`: the plan now contains an explicit operation matrix;
  catalog vocabulary/capability operations require fresh READY evidence while
  safe structural clear/delete/endpoint-group CRUD/server CRUD do not;
- `UI01F2-PLAN-004`: F2 preserves the current effective structural Review
  limit of 16 commands and uses whole-deployment reconcile for bounded bulk
  mutation.

No reducer/session/save redesign or implementation was made.

Corrected plan SHA-256:
`76f3028f7d5a985b965c778ec4672b98b9e1128b43e2f23712f8a305aa65a33f`

The original FULL review above is historical for its original plan hash. One
owner-authorized `TARGETED_RECHECK` is permitted only for
`UI01F2-PLAN-001`, `UI01F2-PLAN-002`, `UI01F2-PLAN-003` and immediately
introduced regressions.

## TARGETED_RECHECK — PLAN-001 / PLAN-002 / PLAN-003

Reviewed corrected plan SHA-256:
`76f3028f7d5a985b965c778ec4672b98b9e1128b43e2f23712f8a305aa65a33f`

Verdict: **BLOCK**

- `UI01F2-PLAN-001` — BLOCKING, **OPEN → RESOLVED**. Canonical
  certificate-scope host, deployment and composite deployment/member edges,
  reference guards and QA coverage are explicit.
- `UI01F2-PLAN-002` — BLOCKING, **OPEN → OPEN**. The source-union semantics
  are corrected, but the plan refers to an existing bounded managed-document
  discovery seam that does not exist. Current `discoverOwnedPaths` is
  unbounded and uses a pathname check followed by a separate read; the F1
  handle-bound reader safely reads a supplied logical path but does not
  discover orphan managed host-document names.
- `UI01F2-PLAN-003` — BLOCKING, **OPEN → RESOLVED**. The operation-specific
  catalog matrix and unavailable/incompatible QA preserve structural cleanup
  without fallback catalog or lock mutation.
- The effective structural Review limit of 16 commands is explicit and creates
  no adjacent blocker.
- New blocking findings: **0**.
- Blocking overengineering findings: **0**.

Smallest remaining correction for `UI01F2-PLAN-002`:

- specify one narrow, one-level managed-host-document enumerator under fixed
  `inventory/host_vars`;
- enforce valid host IDs and the 4,096-document limit during enumeration;
- reject symlink/junction/reparse entries;
- pass each discovered logical path to the existing handle-bound managed
  document reader;
- never use a pathname read as ownership authorization and do not introduce a
  generic filesystem/repository framework;
- test orphan discovery, 4,096/4,097 boundaries, invalid names,
  symlink/reparse entries, replacement between enumeration and open, and
  delete/move reconciliation across the union.

Review validity: **CURRENT** for the corrected plan hash and baseline above,
limited to the three targeted findings. Exact unresolved blocking count:
**1**.

This targeted recheck consumes the permitted automatic recheck cycle. No
further correction or review is automatic. UI-01F2 implementation remains
blocked pending a new explicit owner instruction.

## Owner-accepted PLAN-002 correction after recheck

The owner explicitly accepted the reviewer's smallest remaining correction.
The plan now specifies one narrow, fixed-root, one-level
`EnumerateManagedHostDocuments` seam instead of claiming that a suitable
bounded discovery seam already exists. It:

- enumerates only direct children of fixed `inventory/host_vars` through a
  no-follow/reparse-safe directory boundary;
- validates canonical host IDs and enforces the 4,096-candidate limit;
- rejects symlink/junction/reparse entries;
- constructs only fixed logical paths and delegates bytes, ownership-header
  validation and read bounds to the existing handle-bound managed reader;
- does not use a pathname read as later ownership authorization;
- remains a narrow F2 integration helper, not a generic filesystem or
  repository abstraction.

The QA plan now covers 4,096/4,097 boundaries, invalid IDs, reparse entries,
replacement between enumeration and open, orphan documents and delete/move
reconciliation.

Updated plan SHA-256:
`5f601728f7a55bb44b652d7ddab9e7278b98aeb2b36ed0c356eb4e57414531fe`

No third review was run. The preceding targeted verdict remains historical for
SHA-256 `76f3028f7d5a985b965c778ec4672b98b9e1128b43e2f23712f8a305aa65a33f`;
it does not independently approve the updated plan bytes. A further review
requires an explicit owner request. No production implementation has started.
