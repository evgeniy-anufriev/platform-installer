# UI-01E2 — Servers page + Add/Edit/Delete architecture

> **Owner supersession, 2026-09-15:** ADR-027 and
> [Save / Project Verify / DeploymentPlan](ui-save-verify-architecture.md)
> replace every statement below that requires READY/Core candidate PASS before
> Save. Current UI semantics are typed server intents → EditSession → local
> structural preview → guarded Save; optional Project Verify is separate.
> Existing server CRUD, draft overlay, source ownership, revision/digest and
> generic-reference behavior otherwise remains. Historical Core-backed
> acceptance evidence is retained as evidence for the old implementation only.

Status: **DONE (2026-09-14)**. This milestone implements the
production Servers editor surface over the accepted UI-01D lifecycle and the
UI-01E1 server CRUD contract. It does not implement runtime credentials,
connection discovery, Execution Node management or readiness.

## 1. Goal

Provide one production Servers page for empty and existing managed projects:

```text
saved/local managed server view
        ↓
Servers page and server dialog
        ↓
acknowledged project-edit/v1alpha4 server intents
        ↓
existing bounded EditSession
        ↓
local structural preview → guarded Save
        ↓
new canonical revision (`UNVERIFIED` or `STALE`)
        ↓ optional
Project Verify of the saved revision through Core
```

E2 adds no direct YAML write, server repository, persistent draft, alternate
save path or desired-state database. The portable Ansible project remains the
only canonical desired state.

## 2. Preconditions and scope

The following accepted foundations are reused unchanged:

- UI-01D owns transient edit sessions, local structural plans and guarded
  commit; ADR-027 separates optional saved-revision Core verification;
- UI-01E1 owns `project-edit/v1alpha4` `CreateServer`, `UpdateServer` and
  `DeleteServer`, managed inventory mutation, final-state proof and generic
  host-reference protection;
- `ProjectSnapshot.hosts` is the server read model;
- local Application Config owns server-type choices and display labels only.

E2 contains:

- navigation from Project to Servers;
- the desired-server table and empty state;
- Add, Edit and Delete dialogs;
- draft indicators for commands acknowledged by the Go edit session;
- the existing global Review and Commit interaction for server changes;
- safe presentation of validation and transaction blockers.

E2 explicitly excludes:

- shared runtime credentials and SSH identity — E3;
- Execution Node bottom panel and auto-selection — E4;
- connection checks, discovered facts, preparation and readiness — E5;
- topology, placement, PKI and service editors — later milestones;
- target-host contact of any kind.

The owner accepted the bounded corrections from the first architecture review:

| Finding | Resolution |
| --- | --- |
| UI01E2-ARCH-001 | Metadata-only first save accepts CreateServer only. Draft-created rows cannot be edited or deleted until the first commit transitions the project to `MANAGED_PROJECT`. |
| UI01E2-ARCH-002 | Superseded by ADR-027 for new Save: no post-commit Core refresh occurs, so `COMMITTED_REFRESH_FAILED` is compatibility-only. A remaining local source-view refresh error is reported as local refresh/IO state without converting a committed Save into failure. |
| UI01E2-ARCH-003 | If E2 creates a session and its first append fails, it discards that still-empty session automatically. Existing non-empty sessions are retained on later append failures. |

The subsequent owner review adds four binding clarifications:

1. Post-commit authoritative recovery reuses the existing exported Go/Wails
   `App.OpenProject(root)` operation. E2 exposes that already-generated binding
   through the TypeScript backend facade; it does not add a new Go protocol.
2. Generic reference ownership is split explicitly: Core discovers canonical
   host references and projects safe records; the Go project writer owns the
   non-cascading delete guard and emits `REFERENCE_IN_USE`; React owns neither.
3. After first commit, draft-created rows lose their draft origin and become
   ordinary committed rows only from the returned authoritative snapshot.
4. Temporary Application Config failure does not block address, hostname, port
   or delete operations for a complete existing server when its type is left
   unchanged. It blocks type selection/change, CreateServer and completion of a
   legacy server whose required type is missing.

## 3. Mockup reconciliation

This plan was checked against `docs/ui-design-01-mockups.html`,
`docs/ui-design-01.md`, `docs/ui-01.md` and
`docs/ui-01e1-architecture.md` before implementation.

The mockup intentionally depicts the eventual combined Servers experience.
E2 implements only the desired-state subset. Its table columns are:

| Column | Source |
| --- | --- |
| Server ID | `ProjectSnapshot.hosts` key |
| Type | `hosts[hostId].type`, labelled through local Application Config |
| Desired hostname | `hosts[hostId].desiredHostname` |
| Address | `hosts[hostId].ansibleHost` |
| Effective SSH port | `hosts[hostId].ansiblePort` |
| Draft state | local rendering of Go-acknowledged intents only |
| Actions | Edit and Delete |

E2 does not render placeholder OS, architecture, capacity, connection or
readiness values. It also omits the mockup's session-credential input,
**Check all servers**, **Check configuration**, discovered-host detail and
Execution Node panel. Those controls appear only when their owning milestones
provide real behavior.

The server modal omits SSH username, authentication method, password and key
path. E3 owns one shared runtime session credential surface; none of those
values belongs to a portable server record.

The modal action remains labelled **Save** / **Сохранить**. Its tooltip is:

> Сохранить изменение в черновик. Файлы проекта будут изменены только после
> проверки и общего сохранения проекта.

This action appends a typed intent. It does not write project files.

The mockup must be checked again at E2 acceptance. Demo statuses and values are
not Core rules.

## 4. Navigation and empty project

E2 introduces only the minimum page selection needed by the current shell:

- Project remains available without an open project;
- Servers becomes available when a project is open;
- all later pages keep their current disabled/deferred state;
- this is not the READY-dependent navigation policy owned by E5;
- no router or navigation framework is introduced for two active pages.

An empty metadata-only project renders the same Servers page with zero rows and
a primary **Add server** action. The Project page links to that action instead
of maintaining a second server form. The narrow UI-01D/E1 first-save form is
therefore retired once E2 supplies the production page; first save still uses
the same backend classification and guarded first-write path.

Before the first successful commit, that guarded first-write path accepts only
one or more `CreateServer` commands. A draft-created row is displayed as
**New**, but its Edit and Delete actions are unavailable. Correcting an already
appended first-save command requires **Discard all changes** and re-entry. E2
does not expand the first-write reducer to Update/Delete. Full CRUD becomes
available only after the commit returns a managed project snapshot and the
project classification is `MANAGED_PROJECT`.

Creating a project leaves the operator on its Project summary. The explicit
**Add first server** action opens Servers; creation does not silently start an
edit session.

Closing or replacing the project remains blocked while an edit session is
active. Page navigation inside the same project preserves the transient draft.

## 5. Read model and UI draft projection

Committed rows are always rebuilt from the latest authoritative
`ProjectSnapshot.hosts`. React does not parse inventory, apply Ansible
precedence, validate server grammar or infer source ownership.

After Go successfully acknowledges an append, React retains the corresponding
safe v1alpha4 intent in process memory and overlays it on committed rows for
presentation only:

- create adds a row marked **New**;
- update of a previously committed managed row displays the entered fields and
  marks the row **Changed**;
- delete of a previously committed managed row keeps it visible but disabled
  and marked **Will be deleted**;
- multiple acknowledged updates are reduced in submission order only for this
  visual preview;
- a failed append never changes the overlay.

Metadata-only first-save rows support only the create preview described above.
The UI does not offer Update/Delete for them before their first commit.

The overlay is never a commit input. `EditSessionStore` retains ordered typed
commands; local structural Review independently reduces them into the exact
candidate and affected-document plan. If UI preview and backend plan disagree,
the backend plan wins. Optional Core Verify evaluates only the later saved
revision.

The overlay and edit session are intentionally transient. A process restart
destroys both. No local storage, SQLite, recovery journal or second draft
contract is added.

After a committed Save, a local revision-bound managed source view replaces
committed rows and the overlay clears. After discard it clears and the previous
saved view remains. After blocked structural review or pre-write failure the
overlay remains and canonical bytes are unchanged.

The old `COMMITTED_REFRESH_FAILED` behavior below is compatibility history.
New Save performs no Core refresh. If local source-view refresh fails after a
commit, the result states that bytes committed, consumes the plan exactly once
and offers a local reopen; it is not a Verify failure and does not retry Save.

The exact recovery seam is the existing exported Go method
`App.OpenProject(root string) ProjectOpenResult`, already present in generated
Wails bindings as `OpenProject(arg1: string)`. E2 adds only
`openProject(root)` to the TypeScript `ProjectBackend` facade and calls it with
the retained current absolute project root from an explicit **Refresh project
snapshot** action. `OpenProject` re-runs local project classification and, for
a managed project, the existing read-only `BuildSnapshot` path on the active
Execution Node. It performs no project-file mutation and is not a CRUD/save
operation.

On `COMMITTED_REFRESH_FAILED`, `App.CommitEditPlan` must first invalidate
application context before returning: set `a.current.Snapshot` to nil, clear
snapshot-derived diagnostics, retain root and safe local project metadata, and
set classification to `MANAGED_PROJECT`. The frontend clears session/overlay
and renders only the stale/unavailable state. A failed `OpenProject(currentRoot)`
returns a safe error while the invalidated backend context remains without an
authoritative snapshot. A successful result atomically replaces frontend and
backend project context. Until then, no old server row may be presented as
current. Commit is never retried and no new protocol is introduced.

For a successful first commit, every draft-created row is discarded as draft
UI state and reconstructed solely from the returned managed-project snapshot.
Only then do its normal Edit/Delete actions become available. No persistent
`draftCreated` marker or origin is carried into canonical or application state.

## 6. Add server dialog

The form emits only `CreateServer`:

```text
hostId           required, immutable after creation
type             required, selected from current Application Config
desiredHostname  required
address          required
sshPort          optional explicit intent
```

The dialog performs basic usability checks such as required fields and numeric
range hints, but Go contract validation remains authoritative. Client checks
must not recreate complete hostname, address or inventory semantics.

The create-port control has two modes:

| UI mode | Command |
| --- | --- |
| Use inherited/default value | omit `sshPort` |
| Set explicitly | send integer `sshPort`, including explicit `22` |

The empty numeric control may show `22` as a placeholder, but a placeholder is
not an explicit value. E2 must not silently turn omitted port into stored 22.

When Application Config is unavailable, new server creation is disabled with
the existing safe diagnostic. Existing server rows remain readable.

## 7. Edit server dialog

The dialog emits only the deliberate closed-semantic `UpdateServer` contract.
Server ID is read-only. Only changed fields are sent; unchanged fields are
omitted and preserve their canonical values.

The port control is explicitly three-state:

| UI mode | Command meaning |
| --- | --- |
| Do not change | omit both `sshPort` and `clearSSHPort` |
| Set explicitly | send integer `sshPort` |
| Remove Installer-owned override | send `clearSSHPort: true` |

The snapshot's port is labelled as the current **effective** value. The UI does
not claim that it knows whether that value came from the inline managed key,
another Ansible source or the default. Clearing is therefore described as
removing the Installer-owned override, not as setting port 22.

A legacy server missing `type` or `desiredHostname` remains readable. When it
is edited through v1alpha4, the form requires the missing metadata before the
intent can be appended, matching E1's legacy-completion rule.

A grammar-valid current type absent from Application Config is shown as
**Unknown configured type (`id`)**. Editing another field omits `type` and
preserves the canonical ID. The user may replace it with a configured type.
Local membership and labels never affect Core status or fingerprint.

If Application Config is temporarily unavailable, a complete existing server
remains editable for `address`, `desiredHostname` and SSH-port intent. Its
canonical type ID is displayed read-only and omitted from `UpdateServer`; type
selection/change is disabled. `DeleteServer` also remains available because it
does not consume Application Config. `CreateServer` remains blocked. A legacy
server with missing required `type` cannot be completed through v1alpha4 until
Application Config is restored, because supplying type is required and the
backend correctly rejects type-bearing commands without configured choices.
Missing `desiredHostname` alone may still be completed while type is preserved.

Saving with no changed field does not append a command. The dialog closes or
shows **No changes** without starting a session.

## 8. Delete server interaction

Delete uses a confirmation dialog and emits only `DeleteServer { hostId }`.
The confirmation states:

> Сервер будет удалён из inventory. Связанные сервисы и размещение
> автоматически не удаляются.

There is no cascade and no service-specific reference logic in React or Go
Wails application code. Ownership is deliberately divided at the existing
Core/Go boundary:

- Core owns discovery and projection of canonical references as safe generic
  `ProjectSnapshot.references.hosts[hostId][]` records. The current producer
  discovers `platform_deployments` placement references; future canonical host
  reference kinds must be added in Core, not in React or service-specific Go;
- the Go writer owns non-cascade mutation: DeleteServer removes no related
  service/placement document. Local Save does not require fresh Core evidence;
- during optional Verify (and fresh planning), Go may apply the same generic
  `serverReferenceInUse` policy to authoritative Core records. It does not
  interpret `kind`, `sourceId`, service type or placement semantics;
- remaining records make the saved revision `INVALID` with
  `REFERENCE_IN_USE`; they do not undo the already successful structural Save;
- React does not precompute references or independently decide whether delete
  is legal. It submits the intent and renders the Review finding.

Therefore `REFERENCE_IN_USE` is not service-specific Go logic or a UI guard.
Core is the reference-discovery authority; Go is the generic non-cascade and
verification-policy authority.
The required snapshot contract includes `references`; E2 does not add fallback
reference discovery or treat a UI-side cached relationship as proof.

Deleting the final server is not prohibited by React. Core and the existing
writer decide whether the complete candidate is valid.

## 9. Edit-session interaction

The first successful modal save lazily starts the existing edit session, then
appends the intent. Later operations reuse that session.

Starting a session and appending its first command are two calls. E2 tracks
whether the current form created the session. If that first append is rejected
and the returned/known command count is still zero, E2 immediately calls the
existing session discard operation and clears the session ID. It must not
discard a pre-existing session or any session containing an acknowledged
command after a later append failure.

The App Shell shows:

- a persistent **Unsaved changes** indicator;
- acknowledged command count;
- enabled **Review changes** action when the count is non-zero;
- one explicit **Discard all changes** action.

Modal **Cancel** discards only unsubmitted form input. It never discards an
existing session.

Appending after an earlier structural Review invalidates its local plan and
returns the shell to editing. Save consumes only the latest revision-bound
structural plan.

The existing review surface displays:

- ordered safe semantic summaries;
- affected documents and present/absent states;
- structural/safety findings (never labelled Core validation);
- **Return to editing**, **Discard all changes** and **Save project** actions.

The final action may remain labelled **Save** in the compact UI, but its nearby
text must say that it commits the complete reviewed draft to project files.

E2 intentionally does not add per-command removal to `EditSessionStore`.
Before append, modal Cancel is sufficient. After append, another update may
correct ordinary fields; an erroneous delete requires **Discard all changes**.
Adding command IDs, mutable command history or a replacement-session protocol
would expand the accepted UI-01D lifecycle for a convenience that is not yet
proven necessary. This limitation must be visible in help text and re-evaluated
from actual E2 usage rather than hidden.

## 10. Wails/Go integration

No new public Wails CRUD method is introduced. The existing
`AppendEditCommand(sessionId, command)` boundary is widened from Create-only to
an allow-list of exactly:

```text
CreateServer
UpdateServer
DeleteServer
```

All other operations remain `EDIT_OPERATION_NOT_AVAILABLE`. The session store
continues to stamp `apiVersion`, `kind` and `baseProjectRevision`; React does
not supply trusted envelope fields.

The Wails application adds safe user messages for server blockers that can be
returned before or during Review, including invalid command, duplicate/missing
host, legacy metadata completion, reference in use, shadowed effective state,
ownership conflict, stale revision and expired session. Raw parser output,
project content and credentials are not surfaced.

No Core, project-edit schema or project-writer change is expected in E2. If UI
implementation reveals a real contract defect, stop and document the defect
instead of silently changing E1 architecture.

## 11. React structure

The current single component is split only at stable UI responsibilities:

```text
App
├── ProjectPage
├── ServersPage
│   ├── ServerTable
│   ├── ServerDialog
│   └── DeleteServerDialog
└── EditReviewDialog
```

The exact filenames may remain compact, but the ownership must remain clear.
`App` owns project context, current page and shared edit-session state.
`ServersPage` receives snapshot rows, acknowledged draft intents and actions.
Dialogs own temporary form state only. `EditReviewDialog` renders the existing
typed plan/result.

No Redux, external router, form framework, generic entity editor, schema-driven
form engine or design-system migration is introduced for E2.

## 12. Failure and concurrency behavior

- Opening Add/Edit/Delete does not start Core work or contact a target.
- Append failure keeps the dialog/form visible and does not alter the overlay.
- If the failed append was the first command in a newly created empty session,
  that empty session is discarded; close/open/create are not left blocked.
- Structural Review/Save starts no Core or SSH work. Optional Project Verify is
  the first action that invokes target-free Core on READY.
- Execution Node unavailable blocks Verify/planning, not local Save.
- External project revision change blocks review/commit through existing
  revision guards.
- Busy operations disable conflicting actions and duplicate submission.
- A structurally blocked Review never enables Save.
- Commit failure retains the reviewed state when retry is supported by the
  existing lifecycle; stale/ownership failures are shown without local repair.
- `COMMITTED_REFRESH_FAILED` is compatibility-only. New Save performs no Core
  refresh; a local source-view refresh failure cannot make an already committed
  transaction false-failed or trigger a second commit.
- Closing/opening/creating a project remains disabled during an active session.
- React unmount cleanup must not attempt to commit or mutate project files.

## 13. Accessibility and layout

- Table and dialogs use explicit labels and accessible names.
- Keyboard order follows the visual form order.
- Escape and Cancel close a server form only when it is not submitting.
- Focus returns to the action that opened a dialog.
- Delete confirmation receives initial focus on the non-destructive action.
- Inline errors are associated with their field; global findings use a live
  status region without repeatedly stealing focus.
- At narrow widths the desired-state table may scroll horizontally; E2 does not
  redesign it into an unrelated mobile information architecture.
- The page retains independent content scrolling and does not implement E4's
  fixed Execution Node panel.

## 14. Implementation slices

1. Add current-page state and enable Project/Servers navigation for an open
   project; add empty and populated Servers page rendering.
2. Replace the narrow first-save form with the shared Add server dialog while
   retaining the accepted Create-only first-write backend path; hide Edit and
   Delete for first-save draft rows.
3. Widen the Wails allow-list to all three v1alpha4 server operations and add
   focused Go application tests.
4. Implement add/edit dialogs, Application Config type handling and exact port
   intent mapping.
5. Implement delete confirmation and generic blocker presentation.
6. Add acknowledged-intent overlay, local structural review/discard interaction
   and revision-bound local source-view reconciliation after Save. Keep old
   `COMMITTED_REFRESH_FAILED` only for compatibility callers.
7. Add accessibility states, responsive table styling and focused component
   tests.
8. Recheck the mockup and run E2 acceptance before updating milestone state.

## 15. Acceptance scenarios

Automated and native tests must prove:

- no-project, empty-project and populated-project Servers states;
- Servers navigation is available only in an open project;
- creating an empty project does not start a session;
- Add first server follows guarded local structural Review → Save;
- multiple CreateServer commands reuse one metadata-only first-save session;
- metadata-only Review contains CreateServer commands only, and draft-created
  rows expose no Edit/Delete actions before first commit;
- a rejected first append discards only the newly created empty session;
- partial edit emits only changed fields;
- missing legacy metadata is required on v1alpha4 edit without open-time
  backfill;
- unknown configured type is preserved when type is not changed;
- temporary Application Config failure leaves non-type edits and delete of a
  complete existing server available, while Create/type-change/legacy missing
  type completion remain blocked;
- create-port omission differs from explicit 22;
- update port modes map exactly to omit, explicit value and clear;
- no-change edit appends nothing;
- duplicate create and absent update/delete show safe blockers;
- delete confirmation is non-cascading;
- referenced delete never cascades; optional Verify may return
  `REFERENCE_IN_USE` and `INVALID` from generic Core records without undoing
  Save; React performs no independent reference validation;
- Create → Update, repeated Update and Create → Delete are exercised only after
  the first commit has produced a `MANAGED_PROJECT`, and render consistently
  with the final reviewed plan;
- append errors do not alter draft preview;
- a new append invalidates an older reviewed plan;
- modal Cancel preserves earlier draft commands;
- Discard restores the committed snapshot with unchanged project digests;
- before Review and before Commit canonical project digests are unchanged;
- successful Save refreshes rows from the local revision-bound managed view;
- after first commit, former draft-created rows are reconstructed as ordinary
  managed rows and immediately use normal post-commit CRUD semantics;
- old `COMMITTED_REFRESH_FAILED` remains compatibility-only; local post-Save
  refresh failure cannot falsely report rollback or repeat commit;
- stale revision, ownership conflict and expired session remain non-mutating;
  unavailable Execution Node does not prevent local Save;
- opening and editing forms contacts no target server;
- keyboard focus, Escape, labels and destructive confirmation behavior work.

### Historical native acceptance before ADR-027

The following records the completed Core-backed E2 acceptance and is not the
acceptance contract for new local Save.

Native Windows acceptance used temporary QA projects and the existing READY
Execution Node only for target-free candidate proof. It covers:

```text
metadata-only project
→ Add two servers
→ Review
→ Commit
→ Edit one server and exercise explicit/clear port
→ Review
→ Commit
→ reopen and compare authoritative rows
→ attempt referenced delete and observe BLOCKED with zero mutation
→ delete an unreferenced server and commit
```

QA must compare project digests around append, blocked review and commit, prove
remote candidate staging cleanup and avoid Kafka/service apply or any target
host contact.

Required gates:

```text
affected Go and Wails tests
go test ./...
go vet ./...
frontend test
frontend lint
frontend production build
wails build -nopackage -clean
affected RED OS race tests
target-free RED OS candidate acceptance on temporary projects
secret audit
git diff --check
```

Core full-suite and catalog/schema reproducibility are required only if a real
E2 defect forces changes to those boundaries; otherwise exhaustive combined
regression remains E6. All E2 QA workspaces are removed after evidence is
captured.

## 16. Non-goals

- runtime credentials, usernames, passwords, keys or SecretRef transport;
- SSH checks, host-key trust, facts, readiness or hostname application;
- Execution Node selection, preparation, activation or global readiness state;
- placement/topology/service/PKI editing;
- server rename, cascade delete, bulk import or individual command-history
  editing;
- generic JSON/YAML patching;
- persistent drafts, draft recovery after process restart or second state
  storage;
- target execution, service installation or Kafka changes;
- UI-01E3 or later milestone implementation.

## 17. Overengineering guard

E2 reuses the existing snapshot, EditCommand, EditSession, EditPlan and commit
contracts. The only Go boundary change is widening an existing operation
allow-list. UI decomposition follows visible responsibilities and does not add
a framework or generalized editor.

The temporary React draft overlay is justified only as feedback for
successfully acknowledged commands. It is not authoritative, persisted or
accepted by commit. A backend candidate-view DTO, command mutation API,
separate server repository, generic form engine and optimistic concurrency
layer would duplicate or expand the existing lifecycle and are excluded.

## 18. Historical final acceptance evidence (before ADR-027)

The Windows Wails production build passed with Go 1.25.0 and Wails 2.15.0.
Focused frontend coverage passed 11/11 tests, lint, TypeScript and Vite
production build. `go test ./...`, `go vet ./...` and the RED OS
`go test -race ./internal/installer` gate passed; the isolated RED OS QA
workspace was removed.

The opt-in Wails-bound remote acceptance used the active immutable runtime
`qa-ui-01e2-20260914-02`
(`sha256:dcdd5ea9bec9cc6bf842ae3a15f5f7ff9e71f144fadafc2ac8be79b37cd49ad8`)
on the READY QA Execution Node:

```text
metadata-only project
→ CreateServer node1 (explicit port 22)
→ Review → Commit
→ CreateServer node2 (explicit port 22)
→ Review → Commit
→ UpdateServer node1 (new address, clearSSHPort)
→ Review → Commit
→ DeleteServer node2
→ Review → Commit
```

`TestUI01E2RemoteServerCRUDAcceptance` passed in 56.90 seconds. Every
candidate snapshot returned `PASS`; the final authoritative state contained
only `node1` at `192.0.2.12`, with no Installer-owned `ansible_port` override.
The test uses TEST-NET addresses and performs only target-free snapshot proof.
No service playbook or Kafka deployment was invoked. Remote inspection after
the test confirmed the active release digest, advertised
`BuildProjectSnapshot` capability and zero residual candidate staging
directories. `git diff --check` passed.
