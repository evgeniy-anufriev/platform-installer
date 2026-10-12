# UI-01F3 architecture review

## 1. Verdict

**BLOCK — PLAN / FULL — UI-01F3.**

The verdict was formed independently. There are **2 OPEN BLOCKING** findings
and **1 OPEN NON_BLOCKING** finding. Implementation is not authorized.

## 2. Review identity

- Plan: `docs/work/ui-01/ui-01f3-architecture.md`
- Reviewed plan SHA-256:
  `e1a236e5e34f839d48b5c8ef997b65dfa4f816e0fd990ddc4de39d2152a295f1`
- Baseline/HEAD: `836653d4def69467e017c50df96d8069acf0698b`
- Contract: `platform.installer/edit-command/v1alpha5`
- Context: `PLAN / FULL`
- Current state verified: UI-01F1 and UI-01F2 are DONE; UI-01F3 is NOT STARTED.
- Reviewed scope: ownership, current EditSession/Review/Commit reuse, catalog
  authority, React overlay, navigation/selection, command conflicts, deferred
  F4/F5/G/H scope, acceptance and overengineering.

The plan was untracked at review time, but its reviewed revision was
unambiguously bound by the supplied and independently verified SHA-256.

## 3. Findings

### UI01F3-PLAN-001 — BLOCKING — OPEN

**Location:** `docs/work/ui-01/ui-01f3-architecture.md` sections 2.1, 8 and 12.1;
`docs/work/ui-01/ui-01f-architecture.md` implementation slices F3-F5.

**Evidence:** the F3 plan includes navigation to a Service settings
placeholder, preservation of `deploymentId`/return context and acceptance for
that flow. The parent architecture assigns service-editor navigation context
to UI-01F5, while UI-01F3 is limited to Topology navigation, Add/Delete, By
services and common draft/Save.

**Impact:** unauthorized slice expansion and premature route/navigation
lifecycle from F5/H.

**Smallest correction:** remove the transition, navigation context and its
tests from F3. Configure service may remain honestly disabled with a future
milestone label. Alternatively, the owner may explicitly move this bounded
item into F3 and synchronize the parent architecture.

**Verification required:** one TARGETED_RECHECK for this finding after an
owner-approved correction.

**Owner decision reference:** F3 is only deployment UI; parent F5 ownership.

### UI01F3-PLAN-002 — BLOCKING — OPEN

**Location:** `docs/work/ui-01/ui-01f3-architecture.md` sections 1, 5.1, 8, 9 and 12;
`docs/work/ui-lifecycle/ui-save-verify-architecture.md`; `app.go` structural commit handling;
`frontend/src/App.tsx` Save handling.

**Evidence:** the plan describes successful Commit through
`response.current.managed` and says failed Commit preserves draft. However,
`COMMITTED_REFRESH_FAILED` means canonical bytes have already been written,
the plan and backend session are consumed, but a managed refresh was not
obtained. The canonical lifecycle requires stale rows to be cleared, CRUD to
be blocked and an explicit read-only reopen to be performed. The current
frontend clears draft only for exact `COMMITTED`, so simple reuse is
insufficient.

**Impact:** the UI can present already persisted intents as an unsaved overlay
and offer to repeat a consumed Commit, mixing canonical state with transient
draft state.

**Smallest correction:** define one App-level behavior:

- both `COMMITTED` and `COMMITTED_REFRESH_FAILED` terminate the session and
  clear all page overlays;
- for `COMMITTED_REFRESH_FAILED`, accept the invalidated `response.current`,
  show no stale rows and block CRUD;
- offer an explicit read-only `openProject(currentRoot)` recovery;
- never retry Commit and add no new API.

**Verification required:** App/Wails tests for both committed outcomes, clear
server/deployment overlays, no second Commit, blocked CRUD and successful or
failed reopen.

**Owner decision reference:** N/A — lifecycle/safety finding.

### UI01F3-PLAN-003 — NON_BLOCKING — OPEN

**Location:** `docs/work/ui-01/ui-01f3-architecture.md` sections 5.3, 10 and 12;
F2 reducer/session implementation.

**Evidence:** `AppendEditCommand` can acknowledge a structurally valid Create
with an already existing deployment ID; existence and repeated lifecycle
intents are blocked only at Review. The plan also says duplicate Add leaves
the view unchanged. Its `EDIT_COMMAND_CONFLICT` text offers Save or discard,
although a conflicting draft cannot be saved. Backend Append permits more
commands than the Structural Review limit of 16.

**Impact:** a misleading overlay or a 17-command draft can be produced and
then recovered only through full discard. Canonical bytes remain protected by
Review.

**Smallest correction:** add a presentation-only ID check against current
rows, enforce the common App-level limit of 16 across Servers and Topology,
and use discard-only UX after `EDIT_COMMAND_CONFLICT`. These checks must not
become a second reducer or authority.

**Verification required:** duplicate ID, double submit, create/delete of one
ID and common limit 16/17 across Servers and Topology.

## 4. Mandatory overengineering review

| Category | Result |
| --- | --- |
| Unnecessary abstractions | 0 — `TopologyPage` and pure presentation helpers are justified |
| Duplicate DTO/contracts | 0 — generated catalog/managed views and v1alpha5 are reused |
| New persistence/lifecycle | 0 — one process-local overlay and existing EditSession are the minimal mechanism |
| Premature scope | 1 — UI01F3-PLAN-001, navigation context from F5/H |
| Speculative features | 0 beyond that scope finding; later editing remains disabled |
| Missed simpler mechanism | 1 — disabled Configure action is sufficient for F3; navigation can wait for its assigned slice |

## 5. Evidence and limitations

Inspected directly:

- reviewer configuration, `AGENTS.md` and `CURRENT_STATE.md`;
- F3 plan and parent F/F2 architecture;
- UI design and mockup;
- Save/Verify and recovery contracts;
- current App, frontend backend/session/reducer/types and generated Wails
  models.

The plan SHA-256, HEAD and current-state claims were independently verified.
No tests were run because this was a read-only documentation PLAN review. F3
has no implementation or QA evidence yet; F1/F2 DONE status was not
revalidated.

## 6. Review validity

**CURRENT** only for the plan SHA-256 and baseline listed above.

The review becomes STALE if plan content, owner scope, parent slice ownership,
v1alpha5 semantics or App structural Commit/recovery lifecycle changes.

## 7. Exact unresolved blocking count

**2**

## 8. Next action

Report the findings to the owner and do not start implementation.

After owner-approved corrections, the remaining automatic review budget is
one **TARGETED_RECHECK only for UI01F3-PLAN-001 and UI01F3-PLAN-002**. No second
FULL review is authorized.

---

## Targeted recheck after owner-authorized corrections

### Verdict and identity

**APPROVE — PLAN / TARGETED_RECHECK — UI-01F3.**

- Corrected plan SHA-256:
  `16a5eb1f679be77b1284aadf0f61fba2e3b5dca1e5db8720b8461ec73ba32653`
- Baseline/HEAD: `836653d4def69467e017c50df96d8069acf0698b`
- Scope: only `UI01F3-PLAN-001`, `UI01F3-PLAN-002` and immediately adjacent
  regressions.
- Exact unresolved blocking count: **0**.

### Finding lifecycle

#### UI01F3-PLAN-001 — BLOCKING — OPEN → RESOLVED

The corrected plan makes Configure service a disabled/deferred control only.
F3 creates no destination page, route, return context or future editor
navigation state. Acceptance verifies this boundary. No further correction is
required.

#### UI01F3-PLAN-002 — BLOCKING — OPEN → RESOLVED

The corrected plan defines `COMMITTED_REFRESH_FAILED` as completed canonical
publication: no Commit retry, consumed session/plan/Review state, cleared
server/deployment overlays, hidden stale `ManagedProjectView`, disabled CRUD,
safe refresh-failed presentation and recovery only through the existing
read-only reopen of the current root. Successful reopen restores a fresh
managed projection and CRUD. No new API or recovery lifecycle is introduced.

#### UI01F3-PLAN-003 — NON_BLOCKING — OWNER-ACCEPTED CORRECTION RECORDED

This finding was outside the requested targeted verdict and therefore did not
receive a reviewer lifecycle transition. The owner-authorized plan correction
nevertheless records:

- presentation-only duplicate deployment-ID and in-flight submit checks;
- the common 16-command App-level limit across Servers and Topology;
- no command-history rewrite or per-command undo;
- discard-all and re-entry for a draft that Review reports as
  `EDIT_COMMAND_CONFLICT`.

Backend schema/Review remain authoritative.

### Overengineering recheck

No adjacent overengineering finding was introduced. The corrections use the
existing disabled-control, App session cleanup and read-only `OpenProject`
seams; they add no DTO, persistence, navigation layer or recovery lifecycle.

### Review validity and budget

The targeted verdict is CURRENT only for the corrected plan SHA-256 and
baseline above. It becomes stale if the corrected scope/recovery sections,
owner decisions, v1alpha5 semantics or App Commit/reopen contract change.

The automatic FULL plus TARGETED_RECHECK budget is exhausted. The next action
is owner approval and separate authorization of F3 implementation; no further
automatic architecture review is authorized.
