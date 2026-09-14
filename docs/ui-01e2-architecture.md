# UI-01E2 — Servers page + Add/Edit/Delete architecture

Status: **PLAN / IMPLEMENTATION NOT STARTED**. This milestone implements the
production Servers editor surface over the accepted UI-01D lifecycle and the
UI-01E1 server CRUD contract. It does not implement runtime credentials,
connection discovery, Execution Node management or readiness.

## 1. Goal

Provide one production Servers page for empty and existing managed projects:

```text
authoritative ProjectSnapshot.hosts
        ↓
Servers page and server dialog
        ↓
acknowledged project-edit/v1alpha4 server intents
        ↓
existing bounded EditSession
        ↓
existing Review → target-free Core candidate proof → Commit
        ↓
refreshed authoritative ProjectSnapshot.hosts
```

E2 adds no direct YAML write, server repository, persistent draft, alternate
save path or desired-state database. The portable Ansible project remains the
only canonical desired state.

## 2. Preconditions and scope

The following accepted foundations are reused unchanged:

- UI-01D owns transient edit sessions, review plans, complete-candidate Core
  validation and guarded commit;
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
| UI01E2-ARCH-002 | `COMMITTED_REFRESH_FAILED` is a completed commit with unavailable current projection: stale rows are hidden and CRUD remains blocked until a fresh authoritative read-only snapshot succeeds. |
| UI01E2-ARCH-003 | If E2 creates a session and its first append fails, it discards that still-empty session automatically. Existing non-empty sessions are retained on later append failures. |

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

The overlay is not sent to Core as a snapshot and is never a commit input. The
Go `EditSessionStore` retains the actual ordered commands; Review independently
reduces them and Core proves the complete staged candidate. If UI preview and
review disagree, the plan and Core findings win.

The overlay and edit session are intentionally transient. A process restart
destroys both. No local storage, SQLite, recovery journal or second draft
contract is added.

After a `COMMITTED` result, the returned snapshot replaces committed rows and
the overlay is cleared. After discard, the overlay is cleared and the previous
snapshot remains. After blocked review or a pre-write failed commit, the
overlay remains available for inspection and the canonical project remains
unchanged.

`COMMITTED_REFRESH_FAILED` is different: canonical files have already been
committed, the plan is consumed and commit must not be retried. E2 clears the
session and overlay, removes the previous snapshot from the current
authoritative view, marks the project projection **Stale / unavailable**, and
blocks Add/Edit/Delete. The user receives a **Refresh project snapshot** action
that invokes the existing read-only project-open snapshot path for the current
root. Until that succeeds, no old server row may be presented as current. A
separate mutation, candidate or save path is not introduced.

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

Saving with no changed field does not append a command. The dialog closes or
shows **No changes** without starting a session.

## 8. Delete server interaction

Delete uses a confirmation dialog and emits only `DeleteServer { hostId }`.
The confirmation states:

> Сервер будет удалён из inventory. Связанные сервисы и размещение
> автоматически не удаляются.

There is no cascade and no service-specific reference logic in React or Go
Wails application code. The generic Core host-reference contract remains the
only reference source. `REFERENCE_IN_USE` appears during Review as a blocking
finding and leaves canonical files unchanged.

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

Appending after an earlier Review uses current session behavior: the previous
plan is invalidated and the shell returns to editing state. Commit is possible
only for the latest reviewed plan.

The existing review surface displays:

- ordered safe semantic summaries;
- affected documents and present/absent states;
- impacts;
- Core validation status and safe findings;
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
- Review is the first server-edit action that invokes target-free Core on the
  selected READY Execution Node.
- Execution Node unavailable keeps the session and project bytes unchanged.
- External project revision change blocks review/commit through existing
  revision guards.
- Busy operations disable conflicting actions and duplicate submission.
- A blocked Review never enables commit.
- Commit failure retains the reviewed state when retry is supported by the
  existing lifecycle; stale/ownership failures are shown without local repair.
- `COMMITTED_REFRESH_FAILED` is never retried as commit: the stale snapshot and
  draft are cleared, CRUD is blocked, and only read-only snapshot refresh is
  offered until authoritative state is restored.
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
6. Add acknowledged-intent overlay, global review/discard interaction and
   refreshed-snapshot reconciliation after commit, including fail-safe
   `COMMITTED_REFRESH_FAILED` recovery.
7. Add accessibility states, responsive table styling and focused component
   tests.
8. Recheck the mockup and run E2 acceptance before updating milestone state.

## 15. Acceptance scenarios

Automated and native tests must prove:

- no-project, empty-project and populated-project Servers states;
- Servers navigation is available only in an open project;
- creating an empty project does not start a session;
- Add first server follows the guarded first-write Review → Commit path;
- multiple CreateServer commands reuse one metadata-only first-save session;
- metadata-only Review contains CreateServer commands only, and draft-created
  rows expose no Edit/Delete actions before first commit;
- a rejected first append discards only the newly created empty session;
- partial edit emits only changed fields;
- missing legacy metadata is required on v1alpha4 edit without open-time
  backfill;
- unknown configured type is preserved when type is not changed;
- create-port omission differs from explicit 22;
- update port modes map exactly to omit, explicit value and clear;
- no-change edit appends nothing;
- duplicate create and absent update/delete show safe blockers;
- delete confirmation is non-cascading;
- referenced delete becomes `REFERENCE_IN_USE` at Review and writes nothing;
- Create → Update, repeated Update and Create → Delete are exercised only after
  the first commit has produced a `MANAGED_PROJECT`, and render consistently
  with the final reviewed plan;
- append errors do not alter draft preview;
- a new append invalidates an older reviewed plan;
- modal Cancel preserves earlier draft commands;
- Discard restores the committed snapshot with unchanged project digests;
- before Review and before Commit canonical project digests are unchanged;
- successful commit refreshes rows from the returned authoritative snapshot;
- `COMMITTED_REFRESH_FAILED` clears the session/overlay, hides the prior rows,
  blocks CRUD, does not retry commit, and recovers only through a fresh
  authoritative read-only snapshot;
- stale revision, ownership conflict, unavailable Execution Node and expired
  session remain non-mutating;
- opening and editing forms contacts no target server;
- keyboard focus, Escape, labels and destructive confirmation behavior work.

Native Windows acceptance uses temporary QA projects and the existing READY
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
