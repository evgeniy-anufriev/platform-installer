# UI-01F3 — Deployment UI architecture

Status: **DRAFT FOR OWNER APPROVAL; IMPLEMENTATION NOT STARTED**  
Parent milestone: `UI-01F — topology editor`  
Approved implementation baseline: `836653d4def69467e017c50df96d8069acf0698b`  
Contract baseline: `platform.installer/edit-command/v1alpha5`

## 1. Goal

UI-01F3 adds the first production Topology page slice:

- enable Topology navigation for an open Installer-managed project;
- render the saved and acknowledged-draft deployment list in the **By
  services** view;
- create a deployment from the exact locked `ProjectCatalogView` vocabulary;
- mark a saved deployment for deletion through the generic guarded delete;
- keep one stable selected deployment while the list changes;
- use the existing common `EditSession -> ReviewStructural -> CommitStructural`
  lifecycle and post-commit authoritative `ManagedProjectView` refresh.

F3 edits only deployment identity, service type and mode through the already
implemented `CreateServiceDeployment` and `DeleteServiceDeployment` intents.
It introduces no new desired-state owner, persistence path or infrastructure
semantics.

## 2. Scope boundary

### 2.1 In scope

- a `TopologyPage` React component and bounded presentation helpers;
- **By services** deployment list and selected-deployment summary;
- catalog-driven Add service instance dialog;
- explicit Delete confirmation and pending-delete presentation;
- empty, loading, incompatible-catalog and unknown-saved-value states;
- integration with the current App Shell draft, Review, Save, discard and
  verification-staleness behavior;
- a disabled **Configure service** control that identifies the deferred
  service-editor milestone without creating navigation or route state;
- focused frontend and Wails-boundary tests.

### 2.2 Out of scope

- member- or host-scoped placement editing, member IDs, roles and **By
  servers** projection — UI-01F4;
- endpoint-group CRUD/assignment and **Entry points** — UI-01F5;
- provider relations, `endpointGroupRef`, virtual router ID or virtual
  addresses — UI-NET-01;
- service configuration or schema-driven Service settings — UI-01H;
- Service-settings routing, destination placeholders, return context or
  preservation of a future editor navigation context;
- deployment rename, mode change or service-type change after creation;
- Core Verify, DeploymentPlan or execution changes;
- Execution Node readiness/preparation changes;
- service-specific branches or local Ansible/Core semantic validation;
- a new backend endpoint, edit protocol revision, reducer, writer, transaction
  or local cache.

The **By servers** and **Entry points** tabs remain visible as disabled
milestone placeholders so the information architecture matches the approved
mockup without implying partial functionality.

## 3. Mockup and contract reconciliation

The plan was checked against `docs/design/ui-design-01-mockups.html`,
`docs/design/ui-design-01.md`, `docs/work/ui-01/ui-01f-architecture.md` and the implemented F1/F2
contracts before design.

| Mockup intent | F3 behavior |
| --- | --- |
| Topology follows Servers | Enable Topology for every open managed project; it does not require a READY Execution Node |
| Add service instance | Catalog-driven dialog for `deploymentId`, `serviceType` and `mode` |
| Save topology | Reuse the App Shell's common Review/Save; no page-specific save path or status |
| Three-pane By services view | Deployment list and compact identity/mode summary are live; placement/member and Core validation panes explicitly say they belong to later slices |
| Configure service | Render a disabled/deferred control only; the milestone that implements the service editor owns its route and navigation context |
| Demo Kafka/member/PASS values | Never treat them as defaults, cardinality rules or validation evidence |

Zero deployments is valid. F3 does not eagerly write all catalog services to
`project.yml` or managed group variables. The technical deployment ID is
stable; there is no rename command.

## 4. Existing authority and data flow

F3 reuses the existing ownership chain:

```text
locked immutable bundle
  -> ProjectCatalogView (presentation vocabulary)
  -> React Add dialog choices
  -> CreateServiceDeployment typed intent
  -> Go Review resolves the exact locked catalog again

Installer-owned canonical documents
  -> ManagedProjectView.deployments (saved direct fields)
  -> React saved rows

acknowledged EditSession commands
  -> React draft overlay for current process/session only
  -> ReviewStructural
  -> existing guarded local transaction
  -> post-commit ManagedProjectView replaces the draft overlay
```

`ProjectCatalogView` is presentation input, not authorization. Go F2 Review
re-resolves the exact locked catalog for deployment creation. React never
parses catalog YAML, Ansible files or service manifests and never calculates
service, topology, placement or cardinality semantics.

`ManagedProjectView.deployments` remains the saved local projection for reopen
without an Execution Node. A fresh Core `ProjectSnapshot`, when available, is
derived verification context only and is not mixed into the editable saved
deployment list.

## 5. Frontend model

### 5.1 No parallel desired-state DTO

`frontend/src/backend.ts` expands its existing `ManagedProjectView` TypeScript
shape to match the already generated Wails binding fields used by F3:

```text
deployments[id] = { deploymentId, serviceType, mode, endpointGroup? }
```

It also exposes the existing generated `ProjectCatalogView` shape needed by
the dialog. No F3-specific backend DTO is added.

The page uses a narrow presentation row derived from:

1. saved `ManagedProjectView.deployments`;
2. acknowledged deployment intents already accepted into the current Go
   `EditSession`.

The overlay is runtime UI state only. It is cleared on discard, successful
commit, project close/open and session invalidation. It is never written to
preferences, indexed as desired state or used to bypass Go Review.

### 5.2 Typed frontend intent

The frontend defines one closed union:

```text
CreateServiceDeployment {
  operation, deploymentId, serviceType, mode
}

DeleteServiceDeployment {
  operation, deploymentId
}
```

`apiVersion`, `kind` and `baseProjectRevision` continue to be normalized by
the existing Go session boundary. React sends no path, arbitrary map,
configuration, placement, endpoint or secret field.

### 5.3 Intent acknowledgement and conflicts

Rows change only after `AppendEditCommand` acknowledges the command. A failed
append leaves the visible final draft unchanged and shows the returned safe
error.

F2 deliberately rejects conflicting repeated intents in one session. F3 does
not add frontend command rewriting or an undo protocol. For immediate UX only,
the Add dialog rejects a `deploymentId` already present in the current visible
saved/draft rows and prevents double submit while append is in flight. This is
a presentation check, not authority: Go/schema/Review still decide whether a
command is valid.

The shared App-level command count is capped at the existing effective
Structural Review limit of **16 commands across Servers and Topology**. The UI
does not append command 17; Go retains its existing authoritative bound.

Within that bounded session:

- a newly created unsaved deployment is labelled **New** and cannot be edited
  or deleted individually until the draft is saved;
- a saved deployment can be marked for deletion once and is then disabled;
- changing a newly created identity/type/mode or undoing one pending deletion
  uses **Discard all changes**, then starts a new bounded session;
- Save or discard clears all acknowledged intent overlays.

If Review nevertheless returns `EDIT_COMMAND_CONFLICT`, the bounded draft is
retained for inspection but cannot be rewritten or undone command-by-command.
That conflicting draft is not offered as saveable: recovery is **Discard all
changes** and re-enter the intended commands. Save remains available only for
a draft whose Review is valid.

This mirrors the established Servers-page first-save behavior and avoids a
second reducer in React. The common effective Review limit remains 16 commands
and the page displays remaining capacity or the safe bounded error; F3 does
not increase the limit.

## 6. Catalog behavior

### 6.1 READY

For `catalog.status == READY`, the Add dialog uses only stable ordered fields
already present in `ProjectCatalogView`:

- service `id`, `displayName`, optional description/category and UI icon;
- mode `id`, `displayName`, optional description and `placementKind`.

The dialog selection order follows the DTO order supplied by Go. Service type
selection resets an incompatible mode selection. Submit requires a non-empty
closed identifier, service and mode, but client validation is convenience
only; Go/schema/Review remain authoritative.

Mode guidance, roles and cardinality may be shown as read-only explanatory
text but do not become F3 validation rules.

### 6.2 UNAVAILABLE or INCOMPATIBLE

Existing saved deployment rows remain visible from `ManagedProjectView`.
Their service/mode IDs are rendered safely even when no matching catalog label
exists.

- Add service instance is disabled with the catalog's safe status/error;
- Delete remains available because F2 defines it as catalog-independent
  structural cleanup under generic reference and writer guards;
- Save remains available for already acknowledged catalog-independent
  commands;
- the UI never falls back to a global/current catalog or rewrites locks.

### 6.3 Unknown saved IDs

An existing service type or mode absent from the current READY catalog is
shown as `Unknown saved value (<id>)`, remains selected/read-only and is never
normalized. Delete can still be requested. No edit/repair command is invented
in F3.

## 7. By-services UX

### 7.1 Page layout

The minimal page retains the mockup's three-column visual rhythm without
claiming later functionality:

1. **Deployments** — search/filter, stable ordered rows, state badges and Add;
2. **Selected deployment** — saved/draft service and mode identity, catalog
   labels when available, placement-kind label and Delete/Configure actions;
3. **Topology status** — local draft/saved status and honest messages that
   placement and authoritative verification are not part of F3.

The left deployment list scrolls independently. Empty state offers Add only
when the catalog is READY. The page uses the common App Shell Save/Verify
statuses and does not create a separate “topology saved” indicator.

### 7.2 Stable selection

Selection is a UI identity keyed only by `deploymentId`:

1. preserve the explicit selected ID while it remains visible, including a
   row pending deletion;
2. otherwise select the lexicographically first visible deployment once;
3. after a successful create, select the acknowledged new deployment;
4. after commit removes the selected deployment, select the first remaining
   row or the empty state;
5. project close/open and draft discard reset selection against the resulting
   authoritative saved rows.

Search filtering does not destroy explicit selection; if the selected row is
temporarily filtered out, the detail pane asks to clear the filter rather than
silently selecting another deployment.

### 7.3 Add dialog

Fields:

- technical deployment ID, with short explanation that it is stable;
- service type;
- mode filtered by selected service;
- read-only placement-kind and guidance summary.

The dialog does not create placement, endpoints, configuration, certificate
profiles or default hosts. Submit appends exactly one
`CreateServiceDeployment` intent and closes only after acknowledgement.

### 7.4 Delete dialog

Deletion is explicit and non-cascading. The dialog states that placement,
endpoint, dependency, provider and certificate-scope references are not
automatically removed. It appends exactly one `DeleteServiceDeployment`
intent. Generic `REFERENCE_IN_USE` from Review is presented against the
deployment without service-specific interpretation.

The canonical project is unchanged until common Commit. A failed Review or a
Commit that did not publish canonical bytes preserves the bounded draft and
permits retry, discard or further non-conflicting edits. A
`COMMITTED_REFRESH_FAILED` result is not a failed publication and follows the
consumed-session recovery in section 9.1.

## 8. App Shell and navigation integration

`Page` gains `topology`; the navigation button is enabled when:

- a project is open; and
- classification is `EMPTY_MANAGED_PROJECT` or `MANAGED_PROJECT` with its
  required local managed projection available.

It does not depend on Execution Node readiness. External/non-owned projects
remain read-only under the existing open classification rules.

The existing App-level session is shared by Servers and Topology. F3 extracts
or minimally generalizes the current append helper so both pages append typed
intents to the same `sessionId`, `commandCount`, Review dialog, Commit and
discard actions. It does not introduce one session per page.

Switching between Servers and Topology preserves acknowledged intents. The
App prevents project close/open/create while a session exists as it does
today. A stale/expired session clears all page overlays together after the
existing safe failure/discard reconciliation; it never leaves a deployment
row presented as saved.

The App Shell's common **Save** button and page-level **Review changes** affordance
both invoke the same Review flow. The topology header may retain the mockup's
**Save topology** wording only as an alias to that common action; it cannot
have separate save state or behavior.

## 9. Review, Save and verification

The lifecycle is unchanged:

```text
first acknowledged intent
  -> StartEditSession (only when no active common session exists)
  -> AppendEditCommand
  -> ReviewStructuralEditSession
  -> existing review dialog
  -> CommitStructuralEditPlan
  -> response.current.managed
  -> clear all intent overlays
```

- canonical bytes are unchanged before Commit;
- Save is local-only and requires neither Core nor a READY Execution Node;
- successful semantic Save makes previous verification stale/unverified under
  the existing lifecycle;
- Verify remains a separate target-free Core operation on the saved revision;
- fresh `BuildDeploymentPlan` remains the mandatory execution gate;
- F3 does not restore the old remote-review authorization model.

### 9.1 Committed refresh failure

`COMMITTED_REFRESH_FAILED` means canonical bytes are already committed. It is
therefore a terminal outcome for the consumed plan/session, not a retryable
Commit error. The common App-level Save handler, shared by Servers and
Topology, must:

1. never retry `CommitStructuralEditPlan`;
2. clear all acknowledged server/deployment overlays and consume the finished
   session, plan and Review state exactly as for `COMMITTED`;
3. accept the invalidated `response.current`, hide the previous
   `ManagedProjectView` instead of presenting it as current authoritative
   state, and disable Add/Delete and all other structural CRUD;
4. show a safe **Saved, but the current project view could not be refreshed**
   state;
5. offer only the existing read-only `openProject(currentRoot)` reopen/refresh
   action.

After a successful read-only reopen, the App uses the fresh
`ManagedProjectView` and restores normal CRUD. If reopen fails, the invalidated
safe state and disabled CRUD remain; Commit is never repeated. This is the
existing application reopen/recovery seam, not an F3-specific lifecycle or
API.

## 10. Failures and diagnostics

The page maps existing safe codes without exposing raw payloads:

| Code/status | UX |
| --- | --- |
| `PROJECT_CATALOG_UNAVAILABLE` / catalog `UNAVAILABLE` | Add disabled; existing rows and guarded Delete remain usable |
| `PROJECT_CATALOG_INCOMPATIBLE` / catalog `INCOMPATIBLE` | Same, with incompatibility message |
| `CATALOG_VALUE_UNKNOWN` | Keep dialog/draft; identify only the rejected field/entity safely |
| `EDIT_COMMAND_CONFLICT` | Retain the bounded draft for inspection; no history rewrite or undo; discard all and re-enter because the conflicting draft is not saveable |
| `REFERENCE_IN_USE` | Preserve draft and canonical files; explain that referenced deployment cannot be deleted |
| `PROJECT_CHANGED` | Preserve canonical files; require reopen/restart of the draft through existing lifecycle |
| `EDIT_SESSION_EXPIRED` | Clear local intent overlays after reconciliation; reload saved projection or surface the existing refresh prerequisite |
| writer/path/ownership failures | Preserve draft and canonical files; show existing safe message |

No diagnostic includes raw catalog data, arbitrary YAML/JSON, filesystem
source roots, secret values or configuration diffs.

## 11. Implementation shape

Expected bounded changes:

- add `frontend/src/TopologyPage.tsx` and focused style rules;
- extend existing frontend backend types to expose generated catalog and
  managed deployment fields;
- generalize App's existing server-only `intents` and append callback into the
  closed common structural-intent union;
- enable the Topology route and render Configure service as a disabled/deferred
  control only;
- add focused React tests and, only where the Wails call seam needs proof,
  App integration tests;
- regenerate Wails bindings only if actual Go-exported types change (none are
  planned).

No new Go production package, Wails method, journal, state manager, event bus,
generic form engine or routing library is justified for F3.

## 12. QA and acceptance

### 12.1 Focused frontend tests

- Topology navigation is available for open empty/managed projects without a
  READY Execution Node and unavailable with no project;
- zero-deployment empty state;
- READY catalog renders stable service/mode choices and mode filtering;
- Add sends exactly one closed Create intent and updates UI only after backend
  acknowledgement;
- presentation-only duplicate-ID validation and in-flight double-submit guard
  leave the view unchanged; backend Review remains authoritative;
- multiple instances of one service are supported through distinct IDs;
- selected deployment remains stable through filters, append, navigation,
  Review failure and rerender;
- Delete sends exactly one closed Delete intent, is non-cascading and marks the
  row pending only after acknowledgement;
- newly created and pending-delete rows cannot emit conflicting second intents;
- catalog unavailable/incompatible disables Add but preserves rows and Delete;
- unknown saved service/mode values remain visible and read-only;
- Servers and Topology share one session and one total command count;
- the common App-level command count accepts commands 1-16 and prevents
  command 17 across Servers and Topology;
- `EDIT_COMMAND_CONFLICT` retains the bounded draft but offers no per-command
  undo or Save; recovery is discard-all and re-entry;
- discard clears both pages' overlays; Save replaces them with
  `response.current.managed`;
- Configure service remains disabled and creates no destination, route or
  navigation context;
- By servers and Entry points are honest disabled placeholders.

### 12.2 Backend-boundary regression

Existing F2 tests remain the authority for reducer/writer behavior. F3 adds no
duplicate reducer tests in React. App/Wails tests prove:

- emitted command field names match v1alpha5 normalization;
- Review and Commit use the existing structural endpoints;
- Save succeeds with zero Execution Node/Core calls;
- post-commit managed deployments are rendered from the returned authoritative
  current result;
- both `COMMITTED` and `COMMITTED_REFRESH_FAILED` consume the session and clear
  all page overlays;
- `COMMITTED_REFRESH_FAILED` hides stale managed rows, blocks structural CRUD,
  never retries Commit and uses only read-only reopen of the current root to
  restore a fresh managed projection;
- `REFERENCE_IN_USE`, catalog failure and session expiry remain bounded.

### 12.3 Manual Windows acceptance

Using the built Wails executable:

1. open a metadata-only project and navigate to Topology without an Execution
   Node;
2. create two deployments of one catalog service with distinct IDs;
3. navigate to Servers and back without losing the common draft;
4. Review and Save once, then close/reopen without an Execution Node;
5. confirm both saved deployment identities/types/modes;
6. request guarded deletion, inspect Review, Save and reopen;
7. confirm project files do not change before Commit and no target host is
   contacted.

### 12.4 Gates

- focused frontend tests;
- `go test ./...`;
- `go vet ./...`;
- `npm run lint`, `npm test`, `npm run build` in `frontend`;
- `wails build -nopackage -clean`;
- affected race tests when Go code changes; otherwise document N/A;
- catalog/schema reproducibility if generated inputs are touched; otherwise
  document N/A;
- secret/security audit over the changed scope;
- `git diff --check`;
- mockup recheck at acceptance.

No RED OS or target-host acceptance is required for a frontend-only F3 diff;
if implementation changes Go backend behavior, risk is reassessed and the
affected RED OS/race boundary is added before DONE.

## 13. Overengineering assessment

| Category | Decision |
| --- | --- |
| New abstraction | One page component plus narrow pure presentation helpers; no generic topology framework |
| DTO/contract | Reuse generated `ProjectCatalogView`, `ManagedProjectView` and v1alpha5; no F3 DTO/version |
| Persistence | Reuse one EditSession and guarded transaction; no browser/local cache |
| Lifecycle | Reuse App-level append/Review/Commit/discard; no per-page lifecycle |
| Future scope | F4 placement, F5 endpoints, G provider networking and H settings remain placeholders only |
| State management | Existing React state is sufficient; no store/router/event bus |

The smallest implementation is a frontend projection and transport over the
already completed F1/F2 seams. Any new Go topology API, generic CRUD layer,
catalog parser, undo log or page-specific save mechanism is outside this plan
and requires a new owner/architecture decision.

## 14. Exit criteria

UI-01F3 may be marked DONE only when:

- the owner has approved this architecture;
- one implementation diff review required by repository risk rules has zero
  blocking findings if the implementation materially diverges from this plan;
- focused and regression gates pass;
- Windows Wails acceptance proves add, shared draft, Review/Save, reopen and
  guarded delete with no Execution Node or target contact;
- docs, `CURRENT_STATE.md` and roadmap record F3 DONE and F4 NEXT;
- one focused implementation commit exists and the worktree is clean.

## 15. Implementation evidence

Status: **DONE**, 2026-09-16. UI-01F4 is **NEXT** and remains a separate owner
gate.

- the Wails executable created two Kafka deployments without an Execution
  Node, preserved the shared draft across Servers and Topology, committed once
  through the common Review/Save flow and restored both deployments after a
  native-dialog close/reopen;
- focused frontend coverage proves Add/Delete, stable selection, duplicate-ID
  presentation validation, the shared 16-command limit, conflict recovery and
  `COMMITTED_REFRESH_FAILED` invalidation/reopen behavior;
- the acceptance run exposed and fixed one pre-existing F1 contract defect:
  the catalog reader now accepts the exact published service-manifest
  identifier grammar, including `pg_auto_failover`;
- frontend tests (33), lint, typecheck, production build, `go test ./...`,
  `go vet ./...`, Wails production build, changed-scope secret audit and
  `git diff --check` passed;
- generated catalog/schema inputs were unchanged; the narrow Go grammar fix
  additionally passed `CGO_ENABLED=1 go test -race
  ./internal/projectlifecycle` on RED OS in an isolated workspace, which was
  removed and its absence verified;
- no Core operation, Execution Node or target host was contacted during the
  Windows Save/reopen acceptance.
