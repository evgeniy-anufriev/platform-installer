# UI-01E5 — Local Save, authoritative Verify, Execution Node readiness and gating

Status: **DRAFT — revised after OWNER-UI-SAVE-VERIFY-01..06; E5 not started**.

Implementation note (2026-09-15): the owner explicitly moved structural Save
and basic saved-revision Verify before E5. Those portions are now implemented
under ADR-027 without starting this milestone. UI-01E5 remains responsible only
for readiness inspection, explicitly confirmed preparation, Verify continuation
after preparation, and navigation/Installation gating. The detailed Save/Verify
sections below remain contract rationale, not unfinished E5 work.

Binding owner change: [Save / Project Verify / DeploymentPlan](ui-save-verify-architecture.md).
E5 is not advanced by this documentation update.

## 1. Goal and binding decisions

UI-01E5 separates persistence from infrastructure verification and connects the
existing `executionnode.Service` readiness/preparation lifecycle to Verify. It
corrects the old UI-01D coupling without adding another desired-state store,
writer, SSH path or local implementation of Core semantics.

- **OWNER-UI-SAVE-VERIFY-01:** Save writes a structurally valid
  Installer-managed candidate through the guarded local transaction and does
  not require an Execution Node.
- **OWNER-UI-SAVE-VERIFY-02:** `UNVERIFIED`, `INVALID` and `STALE` projects
  remain editable/saveable; none authorizes execution.
- **OWNER-UI-SAVE-VERIFY-03:** Verify validates the current saved canonical
  revision through Core on a READY Execution Node and never writes project files.
- **OWNER-UI-SAVE-VERIFY-04:** evidence is bound to exact canonical revision and
  Core/runtime identity; every semantic Save makes prior evidence stale.
- **OWNER-UI-SAVE-VERIFY-05:** fresh `BuildDeploymentPlan` remains mandatory
  before every execution and is never bypassed by Project Verify.
- **OWNER-UI-SAVE-VERIFY-06:** Verify may check readiness automatically. Any
  mutating preparation requires explicit confirmation before Verify resumes.

Thus OWNER-UI-SAVE-EXECNODE-01..02 now applies to **Verify**, never Save. The
old UI-01D requirement that Review/Save requires READY and candidate Core PASS
is superseded for new Installer sessions. Published old contracts retain their
meaning and are not reinterpreted.

## 2. Scope and sequence

The original two-slice proposal is superseded. Slice 1 was completed as the
pre-E5 ADR-027 correction; only slice 2 belongs to future UI-01E5:

1. **PRE-E5 (DONE; not E5) — Save/Verify separation:** additive structural plan/result, local
   guarded Save, saved-revision verification state and explicit Verify.
2. **E5B — readiness/preparation and gates:** immutable trusted-node binding,
   read-only check, confirmed preparation, Verify continuation and Installation
   prerequisite rendering.

It includes local structural Review/Save for typed commands exposed by the
current UI; reuse of existing lock, path, ownership, revision, digest,
transaction, rollback and recovery guards; read-only Verify through the fixed
`BuildProjectSnapshot` protocol; bounded in-memory verification evidence; and
reuse of `InspectExecutionNode`, `PlanExecutionNodePreparation` and `Prepare`.

## 3. Non-goals

- No preparation of E4 project/local candidates or arbitrary addresses and no
  synthesis of an `executionnode.Node`.
- No E3 target credential use, generic remote-command API, UI-02 transport,
  target preparation or service deployment.
- No local Ansible precedence, service validation, topology resolution,
  reference discovery, effective-state proof or snapshot fingerprinting.
- No Core candidate proof before Save and no post-Save Core refresh.
- No readiness/verification database, worker, polling daemon or project-file
  verification marker.
- No automatic preparation and no preparation from Installation.

## 4. Ownership

| Concern | Authority |
| --- | --- |
| Canonical desired state | portable Ansible project |
| Typed edit/session lifecycle | Go Installer |
| Structural candidate | existing Go managed-project writer |
| Locking, stale checks, transaction, rollback | existing guarded transaction |
| Infrastructure semantics and validation | Core on a READY Execution Node |
| Node inspect/plan/prepare | existing `executionnode.Service` |
| Rendering and transient form state | React/Wails |

The local editable view is a bounded projection of Installer-owned source
documents, read from canonical bytes and bound to `projectRevision`. It is not
a `ProjectSnapshot`, does not resolve Ansible precedence and is not separately
persisted. E5 exposes the already implemented server CRUD operations. A future
editor may use local Save only after its typed operation has a structural
reducer in the same writer; unsupported operations fail closed.

## 5. Additive Save contract

Existing project-edit schemas remain byte-for-byte unchanged. New Installer
sessions continue emitting `edit-command/v1alpha4`. Local Review/Save uses a
separate additive closed envelope at
`contracts/project-save/v1alpha1/schema.json`:

```text
platform.installer/project-save/v1alpha1
kind: StructuralEditPlan
  reviewMode: STRUCTURAL
  status: READY | BLOCKED | NO_CHANGE
  planId, baseProjectRevision
  semanticChanges, affectedDocuments
  structuralValidation: {status: PASS | BLOCKED, findings}
  reviewDiff, commitAllowed, expiresAt

platform.installer/project-save/v1alpha1
kind: StructuralCommitResult
  status: COMMITTED | BLOCKED | DISCARDED
  changed, oldProjectRevision, newProjectRevision
  affectedDocuments
  verificationStatus: UNVERIFIED | STALE
```

The schema is Draft 2020-12, `additionalProperties:false` at every object and
uses these exact bounds: plan/opaque ID 16..128 ASCII `[A-Za-z0-9_-]`, at most
1024 semantic changes, 1026 affected documents, 256 findings and 65536 UTF-8
bytes of review diff. A finding has code `[A-Z][A-Z0-9_]{0,127}`, safe message
1..512 characters and optional safe field at most 256 characters. Existing
digest and logical-path patterns are reused by `$ref`, not copied with changed
semantics. Unknown fields and unknown kinds are rejected.

The new plan deliberately has no Core validation status, expected effective
state or expected snapshot fingerprint. `COMMITTED_REFRESH_FAILED` is absent:
Save performs no remote refresh. The old planner remains compatibility-only;
new Wails Save uses the structural plan.

Structural Review may check only command schema and closed fields, bounds,
identifier grammar, supported operation, managed ownership, safe paths, YAML
shape/serialization, duplicate source keys, and current document/revision
digests. It never labels these checks as Core validation.

The Go decoder accepts old project-edit payloads only on old methods and the
new project-save payloads only on the new structural Review/Save methods. It
does not cross-decode or translate plan versions. Wails emits only the new
project-save plan/result for new sessions.

Save consumes the exact stored plan and reuses `commitDocuments` and all
pre-write guards. It makes no `candidateReadyReader`, candidate/saved snapshot,
SSH or target call. It computes the new raw-byte revision locally, discards the
plan/session and returns no Core snapshot. Its `verificationStatus` is
`UNVERIFIED` when no older evidence exists and `STALE` when retained evidence
was invalidated by the new revision.

## 6. Generic references and invalid saved state

Core remains the only source of generic reference records. Go adds no
service-specific reference rules and React never decides delete legality.
Absence of current Core evidence cannot make Save depend on an Execution Node:

- current revision-bound references may be shown as a safe Review warning;
- structural Save never cascades;
- stale/absent evidence is not proof that references are absent;
- a structurally valid delete may be saved; during Verify, Go applies its
  existing generic non-cascading guard to the returned Core `references.hosts`
  contract and marks the revision `INVALID` with `REFERENCE_IN_USE` when a
  deleted host is still referenced;
- no saved verification state authorizes execution; a fresh DeploymentPlan is
  still required.

This supersedes only the old save-time Core dependency. Core discovers the
safe generic records; Go checks target presence without knowing a service;
new reference kinds still belong in Core, never in service-specific Go.

## 7. Verification and exact binding

Verification is runtime application state, not desired state. Its closed
Draft 2020-12 schema is published additively at
`contracts/project-verification/v1alpha1/schema.json`; it neither references
nor modifies project-edit schemas:

```text
ProjectVerification/v1alpha1
  apiVersion: platform.installer/project-verification/v1alpha1
  kind: ProjectVerification
  status: UNVERIFIED | VERIFYING | VERIFIED | INVALID | STALE | UNAVAILABLE
  projectIdentity, projectRevision
  runtimeIdentity: {bundleDigest, coreVersion, catalogDigest, protocol}
  checkedAt
  findings: bounded [{code, safeMessage, optional safe field}]
```

The object is `additionalProperties:false`; findings use the same code/message/
field bounds as project-save and are limited to 256. Runtime identity is closed,
all three digests use the canonical sha256 pattern, and Core version/protocol
are 1..64 printable safe identifier characters. Verification payloads are
decoded/emitted only by the verification methods.

`INVALID` means Core completed authoritatively for the bound revision and
returned blocking semantic findings. Transport, readiness, protocol, timeout
or staging failure is `UNAVAILABLE`, never `INVALID`. `STALE` means old evidence
no longer matches revision/runtime; without evidence the state is `UNVERIFIED`.

The existing `BuildProjectSnapshot` operation gains an additive negotiated
verification-evidence mode, not a new operation. `GetCapabilities` advertises
`platform.installer/project-verification/v1alpha1`. In this mode the runtime:

- reads actual bundle/Core/catalog/protocol identity from the active immutable
  release and its validated manifest;
- requires every expected identity field in the request to match that actual
  identity before Core runs;
- returns the same actual closed runtime identity alongside `projectSnapshot`;
- fails with a stable safe mismatch error instead of returning a snapshot when
  identity changes or cannot be attested.

Old runtimes may still serve UI-01B read-only snapshots, but are not
verification-capable. Verify requires the advertised capability. The Go
transport shares the existing staging/cleanup implementation and exposes an
evidence-bearing result internally; it does not create a duplicate remote
operation. Bundle digest attests the immutable manifest, while Core/catalog/
protocol fields are also compared explicitly.

`VerifyCurrentProject()` runs under the App operation lock:

1. require an open saved project and no active write transaction;
2. compute canonical revision `R0` locally;
3. resolve only the immutable startup trusted-node/runtime binding;
4. automatically perform existing read-only readiness/capability inspection
   when readiness is absent or stale;
5. if preparation is needed, return a safe confirmation request without
   changing the project or edit session;
6. after explicit confirmation, run the existing plan, re-inspect, and resume
   the same bound Verify only on READY;
7. call existing read-only `BuildProjectSnapshot` for the saved project, never
   the candidate operation;
8. require returned `snapshot.ProjectRevision == R0`, returned actual identity
   equal to the verified startup binding, and the capability still advertised;
9. recompute `R1`; publish `VERIFIED`/`INVALID` only if `R1 == R0`, otherwise
   publish `STALE` and discard the projection as current evidence.

Existing request-owned staging cleanup is reused. Verify never writes project
files. A semantic Save marks prior evidence stale before exposing its revision.

### 7.1 Deterministic state transitions

Evidence is retained only to explain `STALE`; it is never accepted by the
display unless status is `VERIFIED` and both bindings are current. Even current
evidence never authorizes execution without a fresh DeploymentPlan.

| Event | Resulting state | Evidence handling |
| --- | --- | --- |
| Open/restart with no in-memory evidence | `UNVERIFIED` | none |
| Save `NO_CHANGE` | unchanged | unchanged |
| Semantic Save, no prior evidence | `UNVERIFIED` | none |
| Semantic Save, prior evidence present | `STALE` | retain old evidence for display only |
| Verify starts | `VERIFYING` | retain previous terminal state internally until completion |
| Authoritative `PASS`, `partial=false`, no dangling generic host reference | `VERIFIED` | replace with exact current revision/runtime evidence |
| Authoritative non-`PASS` or `partial=true` | `INVALID` | replace with current evidence and bounded Core findings |
| Authoritative snapshot has a generic reference to an absent host | `INVALID` | current evidence plus Go `REFERENCE_IN_USE`; no service rule |
| Readiness/protocol/transport/staging failure before authoritative response | previous current terminal state, otherwise `UNAVAILABLE` | retain only still-current evidence; return attempt error separately |
| User cancels readiness preparation or Verify | previous terminal state, otherwise `UNVERIFIED` | no new evidence |
| Returned revision differs from `R0`, or `R1 != R0` | `STALE` if old evidence exists, otherwise `UNVERIFIED` | discard returned evidence |
| Actual runtime identity/capability differs from expected | `STALE` if old evidence exists, otherwise `UNAVAILABLE` | discard returned evidence |
| Fresh DeploymentPlan succeeds for exact revision/runtime and its existing result explicitly proves the same project-validation claim | may become `VERIFIED` | reuse plan evidence; no duplicate Core call |
| Any other DeploymentPlan result | unchanged | plan keeps its own findings/status; do not infer a Project Verify result |
| Retry | follows Verify-start row | no special transition |

`StructuralCommitResult.verificationStatus` follows the two semantic-Save rows:
`UNVERIFIED` without prior evidence, `STALE` with retained prior evidence.
`VERIFYING` is transient and never installation-eligible. A failed attempt does
not destroy still-current prior `VERIFIED` evidence.

## 8. Trusted node and readiness contract

`App` receives one immutable startup binding containing the same trusted
`executionnode.Node`, verified bundle root/runtime identity, transport and
`executionnode.Service` used by `projectReader`. `WithExplicitExecutionNode`
remains display-only. E4 candidate IDs can never be resolved into transport
coordinates.

`main.go` constructs one private `executionNodeBinding` after validating the
bundle and all trust inputs, then derives both the `projectReader` and the E5
facade from that object. `NewApp` receives the binding as an option; tests may
inject a private interface implementation, but no Wails DTO can construct it.
This removes duplicated node configuration and guarantees that project reads,
attested Verify and preparation address the same immutable authority.

Only an E4 selection denoting that exact startup binding may inspect, prepare
or Verify. Project/local candidates stay `NOT_PREPARED`, `canPrepare=false`,
with a safe explanation. E3 credentials are never read or transmitted.

The read model is also a closed additive schema at
`contracts/execution-node-readiness/v1alpha1/schema.json`. It reuses the safe
finding/digest patterns, limits findings to 64 and preparation actions to four.
Actions are enum values `VERIFY`, `TRANSFER`, `ACTIVATE`, `BLOCKED`; step IDs
and transport internals are not exposed.

```text
ExecutionNodeReadiness/v1alpha1
  selection: ExecutionNodeContext
  state: NOT_CONFIGURED | UNREACHABLE | UNPREPARED |
         PREPARATION_REQUIRED | READY | UPDATE_REQUIRED |
         INCOMPATIBLE | BROKEN
  checkedAt, safe runtime identity, safe findings, canPrepare
  preparation:
    planId, bundleDigest
    actions: bounded allow-listed labels
    mutating, expiresAt
```

The preparation summary allow-list is state, bundle digest, fixed action labels,
mutability and expiry only. It excludes addresses, identity/known-host paths,
host-key fingerprints, commands, output, staging paths and transport internals.

Fixed Wails methods:

```text
GetExecutionNodeReadiness()
CheckExecutionNodeReadiness()
PlanExecutionNodePreparation()
PrepareExecutionNode(planId, confirmed bool)
SelectStartupExecutionNode()
VerifyCurrentProject()
```

Preparation rejects `confirmed=false`, stale/foreign plans and absent trusted
binding. Existing Service expiry, node and bundle checks remain authoritative.
`SelectStartupExecutionNode` only reselects the already bound safe external
context and is unavailable without that binding; it accepts no node/address/
credential input. This supports trusted binding → project candidate → trusted
binding without deriving transport authority from the candidate.
App stores one readiness record, one pending plan and one pending Verify
continuation under its operation lock; all clear on close/replacement,
selection change, completion and shutdown. No background goroutine is added.
Every Verify attempt performs a fresh read-only inspect/capability check, so a
cached shell status never authorizes verification. Cached readiness is display
state only and has no security TTL semantics.

## 9. UI and navigation reconciliation

- App Shell and Servers render one backend readiness record.
- **Check** is read-only.
- **Prepare** is enabled only for the trusted startup binding and always opens
  confirmation containing the safe allow-listed summary.
- Project/local candidates remain selectable context but cannot prepare.
- **Save project** is local structural persistence.
- **Verify saved project** is separate and shows verification state/findings.
- Installation shows optional Project Verify separately from plan state; it
  never prepares a node.

OWNER-UI-SAVE-VERIFY-02 narrows the older navigation gate: readiness and
verification must not disable implemented editor pages or Save. Only Project
and Servers editors currently exist; E5 does not expose placeholder editors.
Future Topology/Certificates/Services are gated by their own milestone, not
READY. Requesting an Installation plan does not require prior Project Verify:

```text
READY trusted Execution Node
AND saved canonical project
AND no unsaved edit-session changes
THEN fresh BuildDeploymentPlan for that exact revision/runtime
THEN plan findings/blockers and explicit approval
THEN StartExecution bound to the approved plan
```

`VERIFIED` never skips `BuildDeploymentPlan`. `UNVERIFIED`, `INVALID` and
`STALE` do not by themselves prevent requesting a fresh plan. A successful plan
may refresh the derived badge only when its existing result proves the same
claim; no duplicate Core call is made solely for a badge.

Readiness loss, `UNVERIFIED`, `INVALID`, `STALE`, failed Verify, cancelled or
failed preparation preserves page, draft and canonical project. Editing and
Save remain available.

## 10. Concurrency and failure semantics

- UI gating is presentation only; backend Verify and future Installation
  recheck their distinct prerequisites. StartExecution always rechecks its
  current approved DeploymentPlan binding.
- Save and Verify serialize under the App operation lock; transaction locks and
  before-digests remain filesystem authority.
- External writes are caught by Save revision/digests and Verify `R0/R1`.
- A continuation is bound to `VERIFY`, project root, `R0`, startup node/runtime
  identity and preparation plan ID/expiry. Any mismatch cancels it safely.
- Close/replace, selection change, Save, shutdown or expiry clears continuation.
  After preparation all bindings/readiness are rechecked before Verify resumes.
- Findings use safe fixed messages; raw output, paths and secrets never cross
  Wails.

## 11. Tests and acceptance

### Backend

- structural Review/Save works without an Execution Node and never invokes
  Core, SSH, candidate capability or target transport;
- old plan/result versions remain unchanged;
- revision/document, ownership, path, lock, transaction and rollback guards
  still fail closed;
- Save returns a revision and no snapshot; its status is `UNVERIFIED` without
  prior evidence or `STALE` when prior evidence is retained. Another edit/Save
  is possible while `UNVERIFIED`, `STALE` or `INVALID`;
- Verify covers exact `R0/snapshot/R1` and runtime binding plus `VERIFIED`,
  `INVALID`, `STALE`, `UNAVAILABLE`;
- DeploymentPlan never consumes a Verify badge as authorization; only an
  explicitly equivalent successful plan result may update that badge;
- no-binding/project-candidate behavior, confirmation, expiry/node mismatch,
  safe summary allow-list and resume-only-bound-Verify;
- no E3 broker call and no project mutation from Verify/readiness/preparation.

### UI and platform

- Save/Verify are visibly separate; Save remains available without READY;
- confirmation appears only for trusted binding; shell/panel share one source;
- Installation separates optional Verify state from mandatory plan state and
  cannot bypass fresh planning;
- Windows Wails offline Save changes canonical digest and performs no SSH;
- RED OS real inspect → optional confirmed prepare → READY → read-only Verify,
  with exact binding and unchanged project digest during Verify;
- a structurally valid Core-invalid fixture saves, verifies `INVALID`, remains
  editable/saveable, may request a fresh plan, and cannot reach StartExecution
  unless that authoritative plan independently succeeds and is approved;
- before E5 is marked DONE, synchronize `docs/architecture-decisions.md`,
  `docs/ui-design-01.md`, `docs/ui-01d-architecture.md`,
  `docs/ui-01e4-architecture.md`, the UI-01 plan/state/roadmap and
  `docs/ui-design-01-mockups.html` with the new Save/Verify and navigation
  semantics; preserve old contract behavior as compatibility history;
- `go test ./...`, `go vet ./...`, affected RED OS race, frontend
  test/lint/build, Playwright, Wails build, Core suite when Core-facing behavior
  changes, schema/catalog reproducibility, secret audit and `git diff --check`.

## 12. Overengineering guard

E5 refactors the existing writer into a structural planning seam and reuses its
plan store/transaction. It reuses `BuildProjectSnapshot` for Verify and the
existing `executionnode.Service` for readiness. A local Core emulator, second
writer, database, event bus, workflow engine, poller, transport registry,
generic patch API or new SSH adapter is excluded.

## 13. Review status

Earlier E5 reviews are stale because ADR-027 materially changes Save,
verification and Installation gating. This document participates in the one
bounded FULL PLAN review of the exact owner-change documentation revision.
