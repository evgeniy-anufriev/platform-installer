# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## ui-save-verify-architecture.md

Source document: [ui-save-verify-architecture.md](../ui-save-verify-architecture.md).

<a id="ui-save-verify-architecture-checkpoint-001"></a>

Status: **IMPLEMENTED PRE-UI-01E5 (2026-09-15)**. Milestone statuses are
unchanged: UI-01E5 remains not started and NEXT.


## ui-logs-01-plan.md

Source document: [ui-logs-01-plan.md](../ui-logs-01-plan.md).

<a id="ui-logs-01-plan-checkpoint-001"></a>

Status: owner-revised scope; targeted architecture recheck APPROVE_WITH_CHANGES (no blockers)

## Mixed-section reconciliation: ui-save-verify-architecture.md

Source: [ui-save-verify-architecture.md](../ui-save-verify-architecture.md). Extracted on 2026-10-12;
original dates, scopes and reviewer verdicts are preserved. This is historical
evidence, not current authorization.

<a id="ui-save-verify-architecture-reconciliation-001"></a>

The initial targeted recheck blocked only on AR-SV-001: `planningProtocol` had
not yet been compared with attested runtime protocol. The owner authorized the
bounded correction without a third architecture review. Verify now requires
`expected.planningProtocol == RuntimeEvidence.Protocol`; a mismatch or either
missing value returns the typed unverified result and cannot publish
`VERIFIED`. UI-01E5 remains not started.
