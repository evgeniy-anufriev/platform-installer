# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## server-information-check-plan.md

Source document: [server-information-check-plan.md](../server-information-check-plan.md).

<a id="server-information-check-plan-checkpoint-001"></a>

Owner correction accepted: a single explicit key approval supplies existing installation trust. FULL DIFF findings SC-D01/SC-D02 corrections implemented; TARGETED_RECHECK requested after real React/Wails target+exec, cancel, changed-credential and visual evidence. StrictMode duplicate probe race fixed in UI and backend. TARGETED_RECHECK: APPROVE, SC-D01/SC-D02/SC-D03 RESOLVED. Informational UI acceptance passed; installation acceptance is outside this change.


<a id="server-information-check-plan-checkpoint-002"></a>

Статус: IMPLEMENTED; real React/Wails informational checks and targeted review passed. Installation acceptance remains separate.
FULL PLAN review: APPROVE_WITH_CHANGES, no blockers. SC-04: reuse isolated OpenSSH builder and identity guard. SC-05: informational success remains independent of readiness failure. FULL DIFF initially BLOCKED on SC-D01/SC-D02; owner-approved corrections received APPROVE in the single TARGETED_RECHECK.
