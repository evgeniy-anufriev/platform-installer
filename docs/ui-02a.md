# UI-02A — read-only Installation state

Status: **DONE**

## Scope

UI-02A adds the first bounded Installation surface: a closed Wails
`InstallationState`, local prerequisite projection, and read-only Summary,
Plan, Execution and Result tabs. It does not create a deployment plan, call
Core, contact an Execution Node or target, stage a secret, start/cancel work,
or retain run history.

## Mockup and contract check

The design requires four Installation tabs and a persistent
Plan -> Execute -> Result strip. The mockup had Plan and Result generated only
by demo JavaScript; UI-02A makes both tabs explicit in its navigation. The
application continues to honour the earlier UI-01E5 rule: Installation becomes
available only after an Execution Node is READY. This slice does not alter
Execution Node selection or preparation.

`InstallationState` is application memory, never a portable-project field. It
contains only the saved canonical revision, optional Verify status, unsaved
draft indication, safe Execution Node status/label, fixed `NOT_CREATED` plan
state and one bounded prerequisite. The backend reads the revision locally and
does not invoke the snapshot reader, lifecycle, execution service or secret
broker.

## Acceptance intent

- A missing project, unreadable revision, unsaved draft, non-READY node or
  missing trusted node binding produces a closed prerequisite state.
- `READY_TO_PLAN` means only the visible prerequisites are present; UI-02A has
  no action that can create, approve or start a plan.
- React receives no raw Core data, runtime path, secret, lease, event or
  target information.
- The next slice, UI-02B, alone may add fresh plan creation and approval.

## Evidence

- Focused Go tests prove local-only prerequisite projection, saved revision
  binding, draft gating, trusted-binding gating and safe unreadable-revision
  handling.
- Frontend tests cover the safe prerequisite display, Servers hand-off and all
  four read-only stages; the full frontend suite passes 59 tests.
- `go test ./...`, `go vet ./...`, frontend lint/build, Wails Windows build and
  `git diff --check` pass. No Core, Execution Node or target operation is
  called by this slice.
