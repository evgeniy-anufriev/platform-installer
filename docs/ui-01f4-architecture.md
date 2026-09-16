# UI-01F4 — Placement UI architecture

Status: **PLAN / NOT STARTED**

Milestone: **UI-01F4**

Parent architecture: `docs/ui-01f-architecture.md`

Prerequisites:

- UI-01F1 local catalog and managed topology projection — DONE;
- UI-01F2 v1alpha5 placement contracts/reducer/writer/reopen — DONE;
- UI-01F3 deployment UI and common structural draft — DONE.

Implementation baseline: `a516228`

This document authorizes no implementation by itself. UI-01F4 remains a
separate owner gate until the plan review is accepted.

## 1. Goal

UI-01F4 adds placement editing to the existing Topology page without adding a
new desired-state model or save mechanism.

It implements both catalog-declared placement forms:

```text
MEMBER_SCOPED
  deployment -> members[{memberId, hostId, roles?}]

HOST_SCOPED
  deployment -> hosts[{hostId, roles?}]
```

Both **By services** and **By servers** may open the same complete-placement
editor. The selected deployment remains the mutation scope: either entry point
produces exactly one existing v1alpha5 complete reconcile command and uses the
same App-level EditSession -> Review -> local Commit lifecycle. **By servers**
passes the selected host only as initial editor context; it does not introduce
per-host mutation commands, a second reducer or a second placement buffer.

F4 does not validate infrastructure semantics. Cardinality, required role
combinations, distinct-host constraints and installability remain Core Verify
and fresh BuildDeploymentPlan responsibilities.

## 2. Scope

### 2.1 Included

- enable the existing **By servers** Topology tab;
- show saved and acknowledged draft placement in **By services**;
- allow placement editing from either Topology tab through one shared
  complete-deployment editor;
- edit one complete `MEMBER_SCOPED` placement through
  `ReconcileDeploymentPlacement`;
- edit one complete `HOST_SCOPED` placement through
  `ReconcileHostScopedDeploymentPlacement`;
- clear either placement form through an empty complete reconcile;
- use project-pinned READY catalog data for placement kind, role vocabulary
  and read-only guidance;
- use the shared final server/deployment draft, including acknowledged
  Create/Update/Delete server and Create/Delete deployment intents;
- project both placement forms by host without synthetic member IDs;
- preserve the common 16-command limit, Review/Save, discard and committed
  refresh-failure recovery;
- focused frontend/App tests and Windows Wails acceptance.

### 2.2 Excluded

- new Go commands, reducers, writers, schemas, Wails methods or DTO versions;
- endpoint-group CRUD/assignment or the **Entry points** tab — UI-01F5;
- provider relations, `endpointGroupRef`, `virtualRouterId`, VIP or
  `virtualAddresses` editing — UI-01G;
- service settings, member configuration or mode changes — UI-01H;
- certificate-scope editing or automatic reference cleanup;
- service-specific Kafka/PostgreSQL/BIND/HAProxy/Keepalived branches;
- client-side cardinality, role-combination, distinct-host or capacity
  enforcement;
- drag-and-drop, topology graphs, auto-placement, placement templates or bulk
  recommendation engines;
- Core Verify, DeploymentPlan, execution, host contact or readiness probing;
- a page-specific Save button with separate state, undo log or command-history
  rewrite.

## 3. Mockup reconciliation

The plan was checked against `docs/ui-design-01-mockups.html`,
`docs/ui-design-01.md`, the parent F plan and the implemented F1-F3 contracts.

| Mockup intent | F4 behavior |
| --- | --- |
| By services shows members/roles/hosts | Live for both placement kinds from managed state plus acknowledged draft |
| Add member | Available only inside the member-scoped complete-placement editor |
| By servers lists roles/services on a host | Live reverse projection of the same final draft, with edit actions entering the shared complete-placement editor |
| Add member from By servers | Select a deployment and open the same editor with the current host as preferred initial context; Apply still reconciles the whole deployment |
| Topology validation PASS | Replaced with honest local draft/guidance state; only explicit Core Verify may claim validity |
| Kafka controller/broker examples | Treated as catalog role IDs, never hard-coded UI rules |
| Server readiness PASS | Not calculated by F4; physical readiness remains the Servers/Execution Node boundary |
| Configure service | Remains disabled/deferred; F4 creates no service-editor route |
| Entry points | Remains disabled for UI-01F5 |

The two tabs are entry points into one mutation seam, not two editing
implementations. **By services** starts from a deployment; **By servers** starts
from a host and then selects an eligible deployment. Both open the same modal,
load the same complete deployment placement and acknowledge the same closed
intent. This preserves the mockup affordance without duplicating the reducer or
creating competing reconcile buffers.

## 4. Authority and existing seams

| Concern | Authority | F4 use |
| --- | --- | --- |
| Canonical desired state | Portable Ansible project | Never duplicated in React |
| Saved editable projection | `ManagedProjectView` | Read servers, deployments and both placement lists |
| Placement vocabulary | Exact project-pinned `ProjectCatalogView` | Presentation choices/guidance only |
| Mutation authorization | F2 structural Review | Re-resolves exact catalog and validates final references |
| Draft lifecycle | Existing App EditSession | One shared session across Servers and Topology |
| Persistence | Existing guarded local transaction | No F4 write path |
| Infrastructure semantics | Core Verify/BuildDeploymentPlan | Never reimplemented locally |

The data flow remains:

```text
ManagedProjectView
  + acknowledged typed structural intents
  -> bounded presentation-only final-draft selectors
  -> By services / By servers rendering

placement editor Apply
  -> one v1alpha5 complete reconcile intent
  -> existing AppendEditCommand
  -> existing ReviewStructuralEditSession
  -> existing CommitStructuralEditPlan
  -> fresh ManagedProjectView
```

React never parses YAML, reads canonical paths, receives raw catalog maps or
persists its projection. The presentation selectors do not authorize Save and
do not replace the Go final-state reducer.

## 5. Reused contract

F4 introduces a frontend-only closed union matching the already published
v1alpha5 shapes:

```text
PlacementIntent =
  ReconcileDeploymentPlacement {
    deploymentId,
    members[{memberId, hostId, roles?}]
  }
  |
  ReconcileHostScopedDeploymentPlacement {
    deploymentId,
    hosts[{hostId, roles?}]
  }
```

`apiVersion`, `kind` and `baseProjectRevision` continue to be normalized by
the existing Go session boundary. F4 sends no configuration, path, catalog
object, arbitrary property or secret.

One intent is the complete desired placement for one deployment. An empty
array is explicit complete removal. F4 never emits per-member add/move/delete
commands and never synthesizes member IDs for host-scoped placement.

After one placement reconcile for a deployment is acknowledged, that
deployment's placement editor is locked until common Save or discard. F2
deliberately rejects a second reconcile or both reconcile kinds for the same
deployment in one session. F4 does not rewrite or replace acknowledged
command history to simulate undo.

## 6. Presentation-only final draft

### 6.1 Small shared selectors

F4 needs the Servers page and both Topology tabs to observe the same
acknowledged structural draft. The implementation may extract the existing
pure server/deployment row overlay logic into one small frontend module and
add a placement overlay selector. This module:

- accepts only typed `ManagedProjectView` fields and acknowledged closed
  intents;
- performs no validation, persistence, I/O or backend calls;
- exports no second project DTO and stores no state;
- exists only to avoid duplicating presentation overlay logic between Servers
  and Topology.

A state manager, generic reducer framework or event bus is not justified.

### 6.2 Server and deployment projection

The host chooser uses the same final presentation set as Servers:

- saved managed servers;
- acknowledged CreateServer and UpdateServer overlays;
- acknowledged DeleteServer rows retained visibly as pending deletion but not
  offered as new placement targets.

Draft-created servers are valid placement targets because F2 validates final
state after all commands reduce. Draft-created deployments may likewise be
placed in the same session. A deployment pending deletion remains visible but
cannot open a new non-empty placement edit.

Missing referenced host/deployment IDs are shown safely as unknown IDs and are
never normalized or silently dropped.

### 6.3 Placement projection

The selector starts from `ManagedProjectView.memberPlacements` and
`hostPlacements`, grouped by `deploymentId`. For each acknowledged placement
intent it removes both visible forms for that deployment and inserts exactly
the intent's replacement form. Empty reconcile inserts nothing.

This mirrors only the public complete-reconcile presentation semantics. Go
still decides command conflicts, reference validity, catalog admission and
canonical output.

If saved projection unexpectedly contains both member-scoped and host-scoped
entries for one deployment, F4 shows a safe inconsistent-state message and
does not guess a form. Normal managed-document/Review guards remain
authoritative.

### 6.4 Deterministic presentation

- deployments and hosts sort by technical ID;
- member rows sort by `memberId`;
- host-scoped rows sort by `hostId`;
- selected roles follow catalog DTO order;
- unknown saved role IDs follow after known roles in stable lexical order.

Sorting is presentation/canonical-churn control only, not infrastructure
semantics.

## 7. Catalog behavior

### 7.1 READY and known deployment mode

The selected deployment's exact service/mode supplies:

- `placementKind` (`MEMBER_SCOPED` or `HOST_SCOPED`);
- ordered role IDs;
- `minParticipants`, optional `maxParticipants`, `distinctHosts` and role
  cardinality guidance.

Placement kind selects the one matching editor and command shape. Role fields
offer only catalog role IDs. Guidance is rendered as non-authoritative help;
it does not disable local Save or claim PASS/FAIL.

Go F2 Review independently re-resolves the exact catalog and returns
`PLACEMENT_KIND_MISMATCH` or `CATALOG_VALUE_UNKNOWN` when appropriate.

### 7.2 UNAVAILABLE, INCOMPATIBLE or unknown saved mode

Saved and already acknowledged placement remains visible. F4 must not use a
different local/global catalog.

- non-empty placement editing is disabled;
- an existing placement may still be cleared through one empty reconcile,
  because F2 defines empty reconcile as catalog-independent structural
  cleanup;
- deployment/server structural cleanup and common Save remain available under
  their existing guards;
- unknown service/mode/role IDs remain visible and read-only.

For clear, F4 uses the currently observed saved/draft form when one exists.
If no placement exists and no READY declared kind exists, no clear action is
shown. Empty reconcile remains form-neutral in Go; React does not infer a
service rule.

## 8. MEMBER_SCOPED editor

### 8.1 Interaction shape

The By-services detail pane displays current members, host assignment, role
chips and saved/draft state. **Edit placement** opens one bounded modal for the
selected deployment. A modal is preferred over a second persistent page-level
buffer: tab/page navigation is inaccessible until Apply or Cancel, so unsent
form edits cannot disappear silently.

The modal edits a complete local working copy before any command is appended.
Cancel discards only this unacknowledged modal copy. Apply sends exactly one
`ReconcileDeploymentPlacement` and closes only after backend acknowledgement.
An append failure retains the modal and safe error.

### 8.2 Member rows

Each row contains:

- stable technical `memberId`;
- one final-draft `hostId` selection;
- zero or more catalog role selections.

Existing member IDs are read-only. Adding a new member creates an editable UI
candidate `memberId`: `<normalized-serviceType>-<n>` (for example, `kafka-2`).
`n` is the smallest positive integer for which that full candidate is not
already used by members of the deployment. `normalized-serviceType` is a
display-only candidate base, never a changed catalog/service value: lowercase;
replace each `_` or `.` with `-`; collapse repeated `-`; trim leading/trailing
`-`; then truncate the base so the final candidate, including `-<n>`, is at
most 63 characters. If that produces an empty base, F4 leaves the field empty
for explicit operator input. This deterministic convenience matches the usual
service-type/node-number notation without reading or changing service
configuration, without parsing a hostname, and without introducing a Core
identity rule.

The operator may replace the generated candidate before Apply. Changing the
selected host never silently rewrites an already generated or edited member ID.
The final field must be non-empty, match the closed identifier grammar and be
unique within this deployment before Apply; schema/Review remain authoritative.
The same rule applies when **By servers** creates a member row with its host
preselected. If catalog type vocabulary is unavailable, F4 cannot create a new
non-empty member row; existing placement may still be cleared under the
catalog-independent cleanup rule.

Several members may use the same host. F4 does not enforce distinct hosts,
minimum/maximum members or role cardinality. It may display the resulting
counts beside catalog guidance without calling them valid or invalid.

Retained member IDs preserve opaque member configuration and extensions in the
F2 writer even when host/roles change. F4 neither reads nor edits that opaque
configuration. Removing a member intentionally requests removal of the whole
member subtree and may be blocked by generic certificate-scope references.

### 8.3 Empty placement and deletion workflow

**Clear placement** produces `members: []`. It is explicit and non-cascading.
To delete a placed deployment in one common draft, the operator first queues
empty placement and then queues DeleteServiceDeployment. F4 does not
automatically cascade or reorder commands.

If DeleteServiceDeployment was already acknowledged while references remain,
the UI cannot rewrite that command history; Review may return
`REFERENCE_IN_USE`/`REFERENCE_NOT_FOUND`, and recovery is discard-all and
re-entry in the correct explicit sequence.

## 9. HOST_SCOPED editor

The same modal pattern edits a complete host list. Each final host may appear
at most once and contains:

- `hostId`;
- zero or more catalog role IDs.

The editor sends exactly one
`ReconcileHostScopedDeploymentPlacement`. Roleless services naturally emit
hosts without `roles`; roleful host-scoped services use the same generic role
selector. There is no `memberId` field and no hidden/generated member identity.

F4 does not branch on BIND, HAProxy, Keepalived, dns-client or another service
ID. Optional/empty roles serialize through the existing writer semantics.
**Clear placement** sends `hosts: []` and remains available without a READY
catalog when an existing host-scoped form is observed.

## 10. By-services view

The existing three-pane layout becomes:

1. deployment list from F3;
2. selected deployment identity plus placement rows and Edit/Clear actions;
3. local summary: declared placement kind, participant/host/role counts,
   catalog guidance and saved/draft/unverified state.

The third pane never renders mock `PASS`. It states that local Save permits an
unverified topology and that Core Verify/fresh planning are separate.

Placement actions are disabled when:

- common structural CRUD is disabled;
- the command limit is reached;
- the deployment is pending deletion;
- a placement intent for that deployment is already acknowledged;
- a non-empty edit lacks a READY known catalog mode.

After an acknowledged empty placement, deployment Delete remains available so
the explicit clear-then-delete workflow can complete.

## 11. By-servers view

This tab is a reverse projection and a second entry point into the same shared
complete-placement editor. It uses no second placement buffer and never emits a
per-host patch.

1. **Server picker** — final-draft servers, address/hostname label, search and
   New/Changed/Deleting badges;
2. **Assignments** — placements grouped by deployment for the selected host;
   member-scoped rows show member ID and roles, host-scoped rows show the
   deployment and optional roles;
3. **Summary** — counts of deployments, member rows, host-scoped assignments
   and unique role IDs, plus honest draft/saved status.

The tab exposes two actions:

- **Edit placement** on an existing assignment opens the selected deployment's
  complete editor with the selected host highlighted;
- **Add placement** selects an eligible deployment and opens that same editor.
  For `MEMBER_SCOPED`, the selected host is the default host for one new member
  row, with the same editable deterministic member-ID candidate. For
  `HOST_SCOPED`, it is pre-added when absent. These are editable defaults only;
  Apply always sends the complete final placement for the deployment.

The deployment picker excludes deployments pending deletion. A non-empty edit
requires the same READY exact catalog evidence as the By-services entry point.
Clear remains available under the existing catalog-independent cleanup rules.
If a placement reconcile for that deployment is already acknowledged, editing
is disabled from both tabs until Save or Discard; there cannot be two pending
placement intents for one deployment.

The selected server may remain visible while pending deletion so retained
references are not hidden. It is not offered as a target in new edits. The tab
does not calculate readiness, capacity, service health or Core validity.

Selecting an assignment synchronizes the controlled selected deployment ID
used by By services. Opening or cancelling the editor performs no mutation;
only successful acknowledgement of its one complete reconcile intent changes
the common draft.

## 12. Selection and navigation state

`App` owns three small runtime-only UI identities and passes them to
`TopologyPage` as controlled values/callbacks; `TopologyPage` must not own a
second copy because the App conditionally unmounts pages:

- active Topology tab;
- selected deployment ID;
- selected host ID.

They survive switching Topology tabs and temporary navigation to Servers or
Project. App resets all three on project close/open/switch. It revalidates them
after acknowledged intent, Discard and a successful Commit refresh; if an ID
disappears, App falls back once to the first stable sorted row or the empty
state. `COMMITTED_REFRESH_FAILED` clears selection together with the stale
managed view; the existing read-only reopen then establishes a new selection.

Search text and an unacknowledged placement modal are not persisted. The modal
blocks background navigation until Apply or Cancel. No router, local storage or
global state library is introduced.

## 13. Common session, Save and recovery

F4 extends the existing App `StructuralIntent` union with `PlacementIntent`.
Servers, deployment CRUD and placement continue to share:

- one `sessionId`;
- one total `commandCount` and effective limit of 16;
- one Review dialog and plan;
- one local Commit;
- one discard-all action.

Canonical files remain unchanged before Commit. Save requires neither Core nor
a READY Execution Node. A semantic Save makes previous verification stale or
unverified. Verify remains a separate target-free operation; every execution
still requires a fresh BuildDeploymentPlan.

`COMMITTED_REFRESH_FAILED` retains the F3 App-level semantics: canonical bytes
are already committed, the session/plan and all overlays are consumed, stale
managed rows are hidden, all structural CRUD is blocked and recovery uses only
read-only reopen of the current root. F4 adds no retry-Commit or recovery API.

## 14. Failure behavior

| Existing code/status | F4 behavior |
| --- | --- |
| `PROJECT_CATALOG_UNAVAILABLE` / `INCOMPATIBLE` | retain placement display; disable non-empty edit; preserve clear |
| `CATALOG_VALUE_UNKNOWN` | retain modal/draft and identify only safe entity/field |
| `PLACEMENT_KIND_MISMATCH` | retain draft; do not convert command shape |
| `REFERENCE_NOT_FOUND` | retain draft; show safe missing entity ID |
| `REFERENCE_IN_USE` | retain draft; require explicit clear/reassignment, never cascade |
| `EDIT_COMMAND_CONFLICT` | retain bounded draft for inspection; discard-all and re-enter |
| `PROJECT_CHANGED` / session expiry | use existing reopen/session reconciliation and clear stale overlays |
| managed-document/writer safety finding | preserve canonical bytes and existing safe message |
| `COMMITTED_REFRESH_FAILED` | never retry Commit; block CRUD until read-only reopen |

No message includes raw YAML/JSON, catalog payload, filesystem source roots,
opaque member configuration, credentials or secret values.

## 15. Implementation shape

Expected bounded changes:

- extend `frontend/src/TopologyPage.tsx` with controlled tabs, both placement
  editors and the By-servers projection;
- add `PlacementIntent` to the existing common structural-intent union;
- minimally extract/reuse pure presentation selectors needed by Servers and
  Topology;
- extend focused React/App tests and CSS;
- regenerate checked frontend assets through the normal Wails build.

No Go production code, contract schema, generated Go/Wails model, backend API
or canonical writer change is planned. Any such requirement is a material
architecture divergence and returns to the owner before implementation.

## 16. QA and acceptance

### 16.1 Focused frontend/App tests

- MEMBER_SCOPED modal loads saved members and emits exactly one complete
  reconcile after acknowledgement;
- retained member identity, host move, role replacement, add/remove and
  duplicate-ID presentation checks;
- new MEMBER_SCOPED rows derive the smallest unused valid
  `<normalized-serviceType>-<n>` candidate, including `_`/`.` normalization,
  63-character bound and empty-base fallback; operator override is allowed and
  a selected-host change never rewrites the ID;
- several members may share one host; cardinality/distinct-host guidance never
  becomes local authorization;
- HOST_SCOPED modal emits only hosts/roles and never a synthetic member ID;
- roleless and roleful host-scoped modes;
- deterministic ordering and unknown saved IDs/roles;
- draft-created servers/deployments participate in placement;
- pending-delete servers stay visible but are not selectable as targets;
- placement overlay replaces both old visible forms for its deployment;
- empty reconcile works without READY catalog; non-empty reconcile does not;
- one acknowledged reconcile locks further placement edits for that deployment;
- clear-then-delete works in one common final-state draft;
- both Topology tabs open the same editor and acknowledge the same complete
  reconcile intent;
- By-servers host context supplies only the initial host/default row and never
  emits a per-host patch or creates a second buffer;
- tab/selection state survives Topology tabs and App navigation and resets on
  project switch;
- the common 16-command limit includes placement intents;
- Review failure, discard, Commit and `COMMITTED_REFRESH_FAILED` clear or retain
  overlays according to the existing lifecycle;
- no Core, Execution Node, target contact or secret path is invoked.

### 16.2 Existing backend regressions

F2 remains authoritative for schema, decoder, reducer, writer, reference graph
and reopen behavior. F4 runs affected existing suites but does not duplicate
their implementation in React:

- correct placement-kind/role admission;
- complete reconcile and empty cleanup;
- opaque member configuration preservation;
- source-managed-host union traversal;
- no mixed placement or synthetic members;
- generic server/deployment/member reference guards;
- local Save, rollback and reopen.

### 16.3 Windows Wails acceptance

Using the production Wails executable and an isolated QA project:

1. create/open a managed project without an Execution Node;
2. create final-draft servers and deployments;
3. configure one MEMBER_SCOPED deployment, including multiple members on one
   host and catalog role choices;
4. edit the same member-scoped placement from By servers, confirm the selected
   host is initial context, and confirm one complete deployment reconcile;
5. configure one roleless and one roleful HOST_SCOPED deployment and confirm no
   member IDs are generated;
6. Review and local Save once, close/reopen and verify both placement forms;
7. clear placement explicitly, Review/Save/reopen and verify removal;
8. confirm canonical bytes do not change before Commit and no Core, Execution
   Node or target host is contacted.

### 16.4 Gates

- focused frontend/App tests;
- `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`;
- `go test ./...` and `go vet ./...` as regressions;
- `wails build -nopackage -clean`;
- affected RED OS/race tests only if Go production behavior changes;
- catalog/schema reproducibility only if generated inputs change;
- changed-scope secret/security audit;
- `git diff --check`;
- mockup recheck at acceptance.

## 17. Overengineering assessment

| Category | Decision |
| --- | --- |
| New contract/DTO | None; reuse v1alpha5, ManagedProjectView and ProjectCatalogView |
| New persistence | None; one existing App EditSession and guarded transaction |
| Duplicate editing implementations | Avoided; two entry points share one modal, buffer, intent and reducer |
| Frontend reducer risk | Limited to pure acknowledged-overlay selectors; Go remains authoritative |
| Generic framework | Rejected; no form engine, state manager, graph library or drag-and-drop |
| Service-specific logic | Rejected; placement kind/roles come only from catalog |
| Automatic semantics | Rejected; no auto-placement, cardinality enforcement or cascade |
| Simplest interaction | One complete-placement modal and one intent per deployment |

The smallest viable F4 change is a pair of typed placement forms, two contextual
entry points into one shared editor and a reverse projection over already
existing contracts. A new backend endpoint, per-host/per-row mutation protocol,
second placement buffer, generic topology graph or second Save lifecycle would
be overengineering.

## 18. Exit criteria

UI-01F4 may be marked DONE only when:

- this plan has an accepted bounded architecture review with zero blocking
  findings;
- both placement kinds pass focused UI and existing backend regressions;
- By servers is proven to project the same acknowledged final draft and to edit
  through the same complete-placement intent as By services;
- Windows Wails acceptance proves local Save/reopen/clear without an Execution
  Node or target contact;
- no new desired-state persistence, Core semantics or service-specific branch
  is introduced;
- docs, `CURRENT_STATE.md` and roadmap record UI-01F4 DONE and UI-01F5 NEXT;
- one focused implementation commit exists and the worktree is clean.

Until then UI-01F4 remains **NOT STARTED** and UI-01F5 is not authorized.
