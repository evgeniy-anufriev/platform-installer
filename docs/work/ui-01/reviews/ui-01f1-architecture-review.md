# UI-01F1 architecture review

Plan: `docs/work/ui-01/ui-01f1-architecture.md`

Baseline: `6c52693af09fde94a18b9e0be94f37b49e505505`

Implementation status: **NOT STARTED**

## FULL PLAN review

Reviewed plan SHA-256:
`591f8eb47c41674d3a91034142cac42294eea7ab4c9efd903a40abaf2df6acc2`

Verdict: **BLOCK**

- `UI01F1-ARCH-001` — BLOCKING / OPEN. Catalog bytes were validated by
  `ValidateRoot` and then reopened for decoding, leaving a check/read race and
  no explicit root/intermediate/final reparse guarantee.
- `UI01F1-ARCH-002` — NON_BLOCKING / OPEN. Managed-document and aggregate
  collection limits were not explicit.
- Overengineering findings: **0**.

## Owner-authorized correction

The plan was changed only at the affected read-safety boundaries:

- a narrow `executionbundle.ReadVerifiedComponent` binds one bounded byte
  slice to the fixed manifest component size and SHA-256;
- the decoder consumes that exact slice without reopening the path;
- bundle root, intermediate `catalog` directory and final file must reject
  symlink/junction/reparse entries;
- catalog size is limited to 8 MiB;
- managed project reads are limited to 4 MiB per document and 64 MiB total;
- collection bounds are 4,096 host documents, servers, deployments and
  endpoint groups, 16,384 combined placements and 128 roles per placement;
- limit failure returns no partial projection;
- implementation of the bundle trust-boundary helper requires HIGH-RISK FULL
  DIFF architecture review.

Corrected plan SHA-256:
`29293a5862bc3a658af854a0e185009a512ebc5234129a967f534b31f9eabcc1`

## TARGETED_RECHECK — exact component bytes

Scope: `UI01F1-ARCH-001` and its immediately affected exact-component-byte and
root/intermediate/final reparse boundary.

Verdict: **APPROVE**

- `UI01F1-ARCH-001` — BLOCKING, **OPEN → RESOLVED**.
- Directly introduced blocking regressions: **0**.
- Unresolved blocking findings: **0**.
- Overengineering findings in the corrected boundary: **0**.
- `UI01F1-ARCH-002` was corrected in the plan but was not a reason to broaden
  the targeted review; it remains a nonblocking implementation verification
  obligation.

Review validity: **SUPERSEDED** by the later owner-authorized F1-01/F1-02 plan
correction. This result remains the historical closure evidence for
`UI01F1-ARCH-001` on plan SHA-256
`29293a5862bc3a658af854a0e185009a512ebc5234129a967f534b31f9eabcc1`
on baseline `6c52693af09fde94a18b9e0be94f37b49e505505`.

## Owner-authorized F1-01/F1-02 correction

The plan was changed only at the requested boundaries:

- `ReadVerifiedComponent` now binds root identity, opened-object safety,
  regular-file/reparse checks, bounded reads, SHA-256 and decoder input to the
  same opened file object, with explicit POSIX and Windows handle flows;
- each `ProjectOpenResult` now brackets the complete metadata/lock, catalog and
  managed projection observation with canonical raw-byte revisions `R0` and
  `R1`, accepts only `R0 == R1`, and retries the whole Open at most once;
- duplicate exact-source status semantics are explicit;
- ambiguous member-scoped plus host-scoped placement syntax fails closed.

Corrected plan SHA-256:
`e31a12341f6ef8b3b02f8fcaf5c3cf933d26cc7bdbea4a59885b86eb0ce22a59`

## TARGETED_RECHECK — F1-01 / F1-02

Scope: `F1-01`, `F1-02` and only their directly introduced blocking or
overengineering regressions. No full review was run.

Verdict: **APPROVE**

- `F1-01` — BLOCKING, **OPEN → RESOLVED**.
- `F1-02` — BLOCKING, **OPEN → RESOLVED**.
- Directly introduced blocking regressions: **0**.
- Unresolved blocking findings: **0**.
- Overengineering findings in the corrected boundaries: **0**.
- Duplicate-source semantics and ambiguous-placement fail-closed behavior were
  confirmed explicit and consistent with the corrected boundaries.

Review validity: **CURRENT** only for plan SHA-256
`e31a12341f6ef8b3b02f8fcaf5c3cf933d26cc7bdbea4a59885b86eb0ce22a59`
on baseline `6c52693af09fde94a18b9e0be94f37b49e505505`.

The review becomes stale if the affected plan bytes or binding parent
decisions change. It approves the architecture plan, not an implementation.
Starting UI-01F1 still requires an explicit owner instruction. After
implementation, the plan requires focused QA and HIGH-RISK FULL DIFF review.
