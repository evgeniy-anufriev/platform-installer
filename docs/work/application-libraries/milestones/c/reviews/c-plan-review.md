# C — independent FULL PLAN review

2026-10-15. Reviewer: independent `architecture-reviewer`, task `c_plan_review`.
Verdict: **APPROVE_WITH_CHANGES**, unresolved BLOCKING **0**.
Production implementation/target QA are not authorized by this verdict.

## Reviewed identity

- Base: `a7260c6f7cbe3f41dcdf8dd996234ec529e33caa`.
- C plan SHA256: `2512E65038945008E6AE74426D408BED30D46635808E61E165BDBB6A960BE1B1`.
- HTML SHA256: `A1607CC13C76EDBEA03DED8B227B7E9330C557E251B0D858B9B0D3B7D97FAE8F`.
- Project contract: `1F253BCED1383C8E8482258904F53C53899E5BDE8BC1ECBE2B2A119FDB712536`.
- Writer contract: `B344B08E9089C2A2018EFBD3152A9E3816B1B8B843B37A7DBA814FBD09AC5B14`.
- B plan: `4C62985A842326494EC5D593D38B683C7007FD1558CE1FEAFFCE18F60B727982`.

SHA identities verified by reviewer at beginning/end. Scope: entire C plan and new
mockup page, existing B1/B2 read/write/import and B4 lifecycle. Relevant owner
decisions: minimalism, arbitrary user parameters/files, typed credential boundary,
saved infra Verify and no hidden infrastructure Apply.

## Findings returned by reviewer

### C-P01 — NON_BLOCKING, OPEN at reviewed snapshot

Plan §6 promised refusal if source directory changes after preview. Existing
`internal/installer/application_package_import.go:205` captures reviewed content
in stored documents; commit uses those bytes, not a source re-read. A new source
lifecycle check is unnecessary and adds dependency on an external directory.

Smallest correction: state that commit publishes exactly reviewed bytes/digest;
new source bytes require a new preview. Preserve project revision rejection.
Verification: source change after preview cannot substitute reviewed bytes;
stale project revision still refuses commit.

### C-P02 — NON_BLOCKING, OPEN at reviewed snapshot

HTML create/import/Review actions are explanatory messages; switching selection/tab
rerenders and loses local input. This does not exercise the production dirty-navigation
flow required by §4/C-Q08. Label these actions as placeholders and document which
scenarios remain unimplemented. A small dirty-flow demonstration is optional;
do not build a second transaction framework for the mockup.

Verification: separate layout/navigation mockup QA from real C2/C4 draft/focus/save QA.

## Architecture and overengineering

Reviewer confirmed authored/resolved separation, honest RESOLUTION_SCOPE origin,
library membership, hostId/entityId exclusivity, no claimed default-slot disable,
Core-owned identities/providers/precedence/PKI, existing structural writer/lifecycle,
typed runtime-secret lease and no extra Start/polling/daemon.
ManagedProjectView already has ApplicationLibraries/ApplicationPlacements in
`internal/installer/types.go`; begin with these, not another desired-state DTO.

- Unnecessary abstractions: 0 proven; generic form engine excluded.
- Duplicate DTO/contracts: 0 proposed; extend existing view only if needed.
- New persistence: 0; existing project/edit session/PlanStore.
- Premature scope: 0 blocking; package IDE/rename/clone/Clear/download excluded.
- Speculative features: 0; absent observations display unknown.
- Missed simpler mechanism: 1 nonblocking, C-P01, existing captured bytes.

Application amendment/import transport may be narrow extensions of the existing
lifecycle; their production implementation must retain the current guards.

## Evidence and validity

Reviewer read root/scoped instructions, current state, review procedure, C plan,
mockup, UI design, B plan, project/writer contracts, targeted Core DTO/writer/import,
managed view, desktop structural bindings, frontend wrappers and secret component.
No tests, target actions, secret-file reads or visual inspection by reviewer.
Parent mockup checks are separately recorded in the design QA note.

Review CURRENT for the reviewed identities. Material ownership/security/transaction/
execution changes require assessment; these two documentary corrections do not
require automatic FULL re-review. Next step: present plan/design to owner.

## Author disposition after review

C-P01 and C-P02 addressed by bounded text corrections: reuse stored preview bytes,
explicitly label mockup placeholders and input reset. C-P02 banner added to HTML;
synthetic CSPA membership corrected to one host. No repeat independent review;
do not claim independent RESOLVED for modified bytes. Blocking count remains zero
in the original report. Implementation awaits owner approval.
