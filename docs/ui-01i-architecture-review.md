# Architecture review — UI-01I

## 1. Verdict

**BLOCK — PLAN / FULL — UI-01I**

The verdict was formed independently. The review envelope contained no
expected result or self-review conclusion.

There are **3 unresolved BLOCKING** and **2 NON_BLOCKING** findings. The desired
state, Core/Go/React ownership and archive/template exclusions are sound, but
source/destination filesystem identity and cancellation are not yet defined
safely enough for implementation.

## 2. Review identity

- Plan: `docs/ui-01i-architecture.md`
- Verified SHA-256:
  `4CA72E66492C61E14B78B79B1BFF29763C0B1BE278FEA28F890C3A15235CC2A8`
- Base/HEAD: `82fcb2ecc4013597271e15fabdf357d83d0eed32`
- Worktree at review: only `?? docs/ui-01i-architecture.md`
- Confirmed state: UI-01H DONE; UI-01I NEXT.
- Mode/context: `PLAN / FULL`
- Scope: ownership/coherent revision, closed file set, opened-object reads,
  link/path limits, destination/publication, cancellation/cleanup, DTO
  boundaries, secrets, Core/Execution Node ownership, compatibility,
  acceptance and overengineering.

## 3. Findings

### UI01I-ARCH-001 — BLOCKING / OPEN

**Location:** `docs/ui-01i-architecture.md`, sections 6–7.

**Evidence:** the plan requires same-opened-object semantics for each file but
does not hold one no-follow, identity-bound source root for the whole preview
or commit observation. The current `ProjectRevision` uses `WalkDir` followed
by path-based reads. The F1 reader safely opens one file but reopens the root
by path for every call.

**Impact:** replacing or moving the source root or a subtree between reads may
produce a mixed manifest from different filesystem objects. A path-based
`ProjectRevision` is not a sufficient coherence oracle for this security
boundary.

**Smallest correction:** hold one no-follow root handle/FD and filesystem
identity for the entire preview/commit attempt. Enumerate, open, read and
repeat the closed-set check relative to that handle. Compute the observation
revision from those safely opened objects, or safely extend `ProjectRevision`;
do not rely on the current path-based implementation as the sole guarantee.
No generic secure-filesystem framework is needed.

**Required verification:** controlled replacement of the source root,
intermediate directory and file between discovery/open/read must never return
a mixed manifest or publish an export.

### UI01I-ARCH-002 — BLOCKING / OPEN

**Location:** `docs/ui-01i-architecture.md`, section 8.

**Evidence:** the plan rechecks destination-parent identity before publish,
but describes path-based staging creation and rename. Existing Linux
publication uses `renameat2` with `AT_FDCWD`; Windows uses path-based
`MoveFileExW`.

**Impact:** an ancestor or selected parent may be replaced after the recheck
and before staging/create/rename, allowing publication outside the verified
directory. A path check before the action does not close this TOCTOU gap.

**Smallest correction:** hold a verified parent handle/FD and perform staging
creation, file creation and final no-replace publication relative to it. Use
narrow `*at` operations on POSIX and an equivalent relative-handle/no-reparse
path on Windows, or fail closed. Cleanup must remain bound to the created
staging identity. Do not add a general transaction framework.

**Required verification:** race replacement of parent/ancestor during
validation, staging and publish; destination races; proof that publication and
cleanup cannot affect anything outside the identity-bound staging object.

### UI01I-ARCH-003 — BLOCKING / OPEN

**Location:** `docs/ui-01i-architecture.md`, sections 9 and 13.

**Evidence:** the plan promises user cancellation and `EXPORT_CANCELLED`, but
the Wails surface has no cancel operation. It also proposes an active commit
under the existing application lock; cancellation through that same lock
cannot interrupt a long-running commit.

**Impact:** React/Wails cannot meet the cancellation acceptance; cancellation
may become a no-op until after publication.

**Smallest correction:** either add one narrow `CancelProjectExport()` with an
owned context/cancel state accessible without the long-held lifecycle lock, or
remove user cancellation from scope by owner decision. Define atomic rename
as the linearization point: cancellation before it cleans staging; after it,
the export is successful and is not rolled back. No operation registry is
needed because only one export may run.

**Required verification:** cancellation during read/write, cleanup before
publish, cancel/rename race, cancel after publish, and blocking Open/Create/Edit
without blocking cancellation itself.

### UI01I-ARCH-004 — NON_BLOCKING / OPEN

**Location:** `docs/ui-01i-architecture.md`, section 8.

The referenced existing project-name grammar is a display-name validator and
is not safe for a destination leaf. Define a new narrow leaf-name validator or
identify an actually suitable existing primitive. Test `CON`, `NUL`, ADS,
trailing dot/space, separators, rooted names and Unicode/control bounds.

No re-review is required for this clarification.

### UI01I-ARCH-005 — NON_BLOCKING / OPEN

**Location:** `docs/ui-01.md`, UI-01I acceptance, and
`docs/ui-01i-architecture.md`, section 13.

The milestone requires semantic preservation by Core snapshot, while the plan
currently requires only byte/digest comparison plus validation of the output.
Add a direct comparison of source/export revision and relevant Core desired
projection under the same Core/catalog identity, accounting for intentionally
excluded generated state.

No re-review is required for this clarification.

## 4. Mandatory overengineering review

Overengineering findings: **0**.

- Unnecessary abstractions: 0. A narrow export collector/publisher is needed;
  the broad existing `copyProject` does not satisfy the current safety scope.
- Duplicate contracts/DTOs: 0. `ProjectExportPlan/Result` remain bounded
  application DTOs, and the existing `OpenProject` is reused.
- Premature scope: 0. Archive, import, template slots, migration, overwrite,
  history and background services are excluded.
- Speculative extension points: 0. No generic CRUD, plugin, persistence or
  general transaction framework is proposed.
- Missed simpler mechanism: 0. SHA-256, one in-memory active plan and narrow
  platform filesystem primitives match the current requirement. Corrections
  for ARCH-001/002 must remain narrow platform seams.

## 5. Evidence

The reviewer directly inspected:

- reviewer instructions, `AGENTS.md` and `CURRENT_STATE.md`;
- the exact plan and SHA-256;
- UI milestone plan, UX document and HTML mockup;
- portable project contract, architecture and ADRs;
- current `ProjectRevision`, F1 opened-object readers, lifecycle/OpenProject,
  staging and Windows/Linux publication seams; and
- Git HEAD and worktree state.

No tests were run because this was a read-only documentation PLAN review and
UI-01I has no implementation. Existing DONE labels and historical tests were
not treated as UI-01I acceptance. No hosts were contacted and no secret
material was read.

## 6. Review validity

**CURRENT** for plan SHA-256
`4CA72E66492C61E14B78B79B1BFF29763C0B1BE278FEA28F890C3A15235CC2A8`,
base/HEAD `82fcb2ecc4013597271e15fabdf357d83d0eed32`, and the stated owner decisions
and contract state.

The review becomes stale if the plan, relevant contracts or transaction/
security boundary changes. Implementation is not covered by this PLAN review;
the proposed FULL DIFF review remains a separate gate.

## 7. Unresolved blocking count

**3**

## 8. Next action

Return `UI01I-ARCH-001`, `UI01I-ARCH-002` and `UI01I-ARCH-003` to the owner.
Do not begin implementation under the current plan. If the owner approves
bounded corrections, one `TARGETED_RECHECK` may inspect only those IDs and the
immediately affected filesystem/cancellation boundary.
