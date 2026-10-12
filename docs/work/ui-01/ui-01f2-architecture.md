# UI-01F2 — Topology command contract, reducer and managed writer

Status: **DONE (2026-09-16)**

Milestone: **UI-01F2**

Implementation status: **DONE**

Parent architecture: `docs/work/ui-01/ui-01f-architecture.md`

Read-model prerequisite: `docs/work/ui-01/ui-01f1-architecture.md`

Baseline revision: `431c1704fcc9d4054305dfb2be216ad406a71b18`

Implementation baseline: `1e8d27a5fb50091ff2d1283b44068a9b289dd592`

Acceptance: the additive v1alpha5 contract, one local structural reducer,
member/host placement writers, fresh catalog admission, generic reference
guards and safe managed-host enumeration passed Windows and RED OS gates. The
revision-bound FULL DIFF review's two findings were corrected and its single
targeted recheck passed with zero blocking and zero overengineering findings.
UI-01F3 remains separately gated and was not started.

## 1. Goal

UI-01F2 adds the closed topology-editing backend beneath the later F3-F5
screens. New Installer edit sessions emit additive
`project-edit/v1alpha5` commands for deployments, member-scoped placement,
host-scoped placement, endpoint groups and consumer endpoint-group assignment.
Those commands reduce together with the existing server commands into one
candidate and use the existing local structural Review/Save transaction.

F2 completes both placement paths end to end:

```text
schema -> decoder -> final-state reducer -> managed writer
       -> candidate -> local Save -> local reopen
```

Save remains local-only. F2 does not contact Core, an Execution Node or target
hosts and does not make a saved project verified or installable.

## 2. Scope

F2 includes:

- additive `contracts/project-edit/v1alpha5/schema.json`;
- v1alpha5 normalization into the existing Go `EditCommand` model;
- new-session emission of v1alpha5 only;
- deployment create/delete;
- complete member-scoped and host-scoped placement reconciliation;
- endpoint-group create/update/delete;
- consumer endpoint-group set/clear;
- one final-state reducer across server and topology intents;
- exact project-lock-bound catalog admission at structural Review time;
- first Save and later managed Save through the same candidate reduction and
  existing guarded transaction;
- safe reopen through the F1 `ManagedProjectView`;
- focused schema, reducer, writer, reopen, safety and no-contact tests.

F2 explicitly excludes:

- React Topology screens, dialogs or navigation changes (F3-F5);
- provider relation, `endpointGroupRef`, `virtualRouterId` or
  `virtualAddresses` editing (UI-01G);
- service configuration/member configuration editing (UI-01H);
- mode update, rename, clone or generic patch commands;
- dependency or HAProxy-integration editing;
- Core Verify, DeploymentPlan, execution or service apply;
- catalog acquisition, migration, lock update or bundle publication;
- a topology database, cache, watcher, repository abstraction or second save
  path.

The old v1alpha1-v1alpha4 schemas remain byte-compatible. Legacy topology
operations accepted by historical contracts are not silently promoted into
the new local structural Save path. New sessions use only the closed v1alpha5
set below.

## 3. Mockup and contract reconciliation

The F2 design was checked against `docs/design/ui-design-01-mockups.html`,
`docs/design/ui-design-01.md`, the common F plan and the implemented F1 read model.

- The mockup's **By services**, **By servers** and **Entry points** views map
  to the same candidate, not separate desired-state models.
- `Add service instance`, member placement and endpoint controls are enabled
  only in F3-F5. F2 supplies their typed intents but changes no screen.
- The mockup action labelled `Save topology` uses the existing common
  structural Review/Save flow; it is not a topology-specific persistence API.
- Selecting a deployment and navigating to service settings remains required
  later; F2 does not remove or implement that transition.
- Mock service names, modes, roles, counts and status labels remain examples.
  Vocabulary and placement kind come from the exact project-pinned catalog.
- Provider/VIP data remains read-only fresh-Core evidence and is not written
  through endpoint-group commands.

No material mockup discrepancy remains inside the backend-only F2 scope.

## 4. Ownership and existing seams

| Concern | Authority / existing seam | F2 action |
| --- | --- | --- |
| Desired state | Portable Ansible project | Mutate only Installer-owned canonical files |
| Draft lifecycle | Existing Go `EditSessionStore` | Reuse ordering, bounds, expiry and invalidation |
| Public command model | Existing Go `EditCommand` | Add v1alpha5 and one host-placement value field; no parallel command DTO |
| Catalog vocabulary | F1 `projectlifecycle.Service` resolver | Resolve exact locked catalog again for each vocabulary/capability-dependent Review |
| Local saved projection | F1 `ManagedProjectView` | Use for typed final-state indexes and post-Save reopen |
| Full owned bytes | Existing narrow managed-document safe reader | Preserve fields omitted from `ManagedProjectView` while patching fixed paths |
| Source host-document names | New narrow managed-host enumerator | Enumerate one level under fixed `inventory/host_vars`, then delegate bytes to the existing handle-bound reader |
| Review/Save | `ReviewStructural` and existing guarded transaction | Extend; do not add another save path |
| Infrastructure semantics | Core on READY Execution Node | Unchanged; consulted only by separate Verify/Plan operations |

React never sends a bundle root, catalog path, arbitrary project path or raw
YAML map. The App remains the Wails boundary, Go owns the edit lifecycle and
transaction, and Core remains the later infrastructure-semantic authority.

## 5. Additive v1alpha5 contract

### 5.1 Versioning

The new schema ID is:

```text
https://platform-installer.local/contracts/project-edit/v1alpha5/schema.json
```

Its command base requires:

```text
apiVersion = platform.installer/edit-command/v1alpha5
kind       = EditCommand
baseProjectRevision = sha256:<64 lowercase hex>
operation  = one closed operation name
```

The schema references the existing v1alpha3 session/plan/result shapes where
their bytes and semantics are unchanged. It copies the v1alpha4 server command
shapes without changing omitted `sshPort`, explicit `sshPort=22`,
`clearSSHPort`, required CreateServer `type`, or `desiredHostname` semantics.
`unevaluatedProperties: false`/`additionalProperties: false` closes every new
command and nested value.

New sessions overwrite transport-supplied version/kind/revision with
v1alpha5, exactly as the current session boundary does for v1alpha4. Historical
versions remain compatibility inputs outside this new-session emission path.

### 5.2 Closed operations

| Operation | Required payload | Meaning |
| --- | --- | --- |
| `CreateServer` | existing v1alpha4 fields | Existing E1 behavior |
| `UpdateServer` | existing v1alpha4 fields | Existing E1 closed semantic patch |
| `DeleteServer` | `hostId` | Existing E1 delete plus generic placement references |
| `CreateServiceDeployment` | `deploymentId`, `serviceType`, `mode` | Add one minimal deployment |
| `DeleteServiceDeployment` | `deploymentId` | Delete only when generic inbound references are absent |
| `ReconcileDeploymentPlacement` | `deploymentId`, complete `members[]` | Replace member-scoped placement for one deployment |
| `ReconcileHostScopedDeploymentPlacement` | `deploymentId`, complete `hosts[]` | Replace direct host-scoped placement for one deployment |
| `CreateEndpointGroup` | `endpointGroupId`, complete `endpointGroup` | Add consumer address intent |
| `UpdateEndpointGroup` | `endpointGroupId`, complete `endpointGroup` | Replace only owned endpoint-group fields |
| `DeleteEndpointGroup` | `endpointGroupId` | Delete only when generic inbound references are absent |
| `SetServiceEndpointGroup` | `deploymentId`, `endpointGroupId` | Set consumer `endpointGroup` |
| `ClearServiceEndpointGroup` | `deploymentId` | Remove consumer `endpointGroup` |

`placementMember` contains only `memberId`, `hostId` and optional unique
`roles[]`. `placementHost` contains only `hostId` and optional unique
`roles[]`. Neither accepts `configuration`. Go adds only the corresponding
small `PlacementHost` value and `EditCommand.Hosts`; it does not add another
top-level command model.

An empty placement array is the explicit complete removal of that deployment's
placement. A member ID is unique within the command and a host ID is unique in
the host-scoped command. Roles are unique identifiers. The schema bounds one
member command to 16,384 members, one host command to 4,096 hosts and each role
list to 128 entries, matching the F1 reopen limits. Existing session storage
bounds of 1,024 commands and 4 MiB encoded commands remain outer retention
bounds, but F2 explicitly preserves the current effective structural Review
limit of **16 commands**. A seventeenth command returns the existing bounded
`EDIT_SESSION_COMMANDS_UNSUPPORTED` result. The limit is not increased for
topology: each placement reconcile already carries one bounded complete
deployment placement.

The endpoint-group body is exactly the current desired-state
`endpointGroup`: `address.domain` plus `address.wildcard`. It carries no
provider networking fields. Identifier/address/domain limits reuse published
project/edit contracts; Go's closed validator mirrors only these structural
constraints and does not invent DNS or routing semantics.

## 6. Fresh catalog admission and revision binding

F1's cached `ProjectCatalogView` in `App.current` is presentation only. It is
never mutation authorization.

F2 exports the already-designed narrow lifecycle operation with this exact
production seam:

```text
projectlifecycle.Service.ResolveProjectCatalog(
    context.Context,
    projectRoot string,
) (*ProjectCatalogView, error)
```

The existing App `projectLifecycle` interface gains that method. When the App
creates its existing Installer `Backend`, it supplies the bound method through
one `WithProjectCatalogResolver` function option matching the existing backend
option pattern. The backend invokes it only while planning a session containing
an operation that needs catalog vocabulary or capability admission. The
service safely rereads `project.yml`, resolves configured trusted roots and
verifies the exact artifact/catalog/service locks. The resulting typed view
remains inside Go; no bundle path or raw catalog map crosses the App/Wails
boundary. A deterministic function fake supplies the same narrow result in
unit tests. Server CRUD and catalog-independent cleanup do not become
dependent on catalog availability.

One Review attempt is revision coherent:

```text
R0 = canonical raw-byte ProjectRevision
require R0 == EditSession.baseProjectRevision
resolve exact locked ProjectCatalogView
safe-read all affected owned documents
reduce and serialize complete candidate
R1 = canonical raw-byte ProjectRevision
accept/store plan only when R1 == R0
```

Unlike Open, Review does not retry a changed project: it returns
`PROJECT_CHANGED`, invalidates the reviewed plan and preserves the draft for
explicit refresh/retry. Commit retains the existing per-document digest,
opened-object identity, security metadata, project revision, lock and rollback
guards.

Catalog dependency is operation-specific:

| Operation | READY catalog required | Reason |
| --- | --- | --- |
| `CreateServiceDeployment` | yes | service/mode vocabulary |
| non-empty member/host placement reconcile | yes | placement kind and role vocabulary |
| empty member/host placement reconcile | no | structural removal only |
| `SetServiceEndpointGroup` | yes | generic endpoint-consumer capability |
| `DeleteServiceDeployment` | no | guarded structural cleanup |
| endpoint-group create/update/delete | no | closed endpoint-group structural contract |
| `ClearServiceEndpointGroup` | no | structural removal only |
| server CRUD | no | existing E1/AppConfig contract |

For an operation that requires admission, `UNAVAILABLE` returns
`PROJECT_CATALOG_UNAVAILABLE` and `INCOMPATIBLE` returns
`PROJECT_CATALOG_INCOMPATIBLE`. The safe finding includes no filesystem path,
catalog payload or bundle validation detail. Catalog-independent operations
continue through all ordinary command, reference, ownership, path, revision
and transaction guards; they neither select a fallback catalog nor rewrite
project locks.

An empty reconcile is form-neutral cleanup: either closed reconcile operation
with an empty array removes the selected deployment's existing canonical
member-scoped or host-scoped placement and introduces no replacement form. It
does not infer placement kind, admit roles or make a catalog claim. If the
stored placement is structurally ambiguous or malformed, the normal managed
document guard still fails closed.

Catalog admission is generic:

- deployment `serviceType` and `mode` must exist in the exact view;
- reconcile command shape must equal the mode's `placementKind`;
- each supplied role, when present, must be declared by that mode;
- `SetServiceEndpointGroup` requires the deployment's service to declare the
  generic endpoint-consumer capability.

Go does not enforce mode cardinality, required role combinations, distinct
hosts, provider relation validity, FQDN/VIP behavior or installability. Those
remain Core Verify/BuildDeploymentPlan findings. Empty reconcile, deletion,
clear and endpoint-group structural CRUD do not validate catalog vocabulary
that they do not introduce. This prevents an unavailable exact bundle from
trapping existing desired state while preserving every generic reference and
writer safety guard.

## 7. Final-state reducer

F2 extends the existing structural candidate; it does not reuse the legacy
Core-backed `applyCommand` as local Save authority. The candidate contains:

- copies of the exact full Installer-owned YAML maps needed for preservation;
- bounded typed indexes equivalent to `ManagedProjectView` for entities,
  placement and references;
- semantic changes and fixed logical document outputs.

Reduction has three closed phases:

1. decode and structurally validate every command without touching files;
2. apply entity lifecycle intents, then property/assignment/complete-placement
   intents to the in-memory final state;
3. validate final references, generic delete guards, catalog admission and
   collection bounds, then serialize affected fixed documents.

Reference existence is checked only after all commands reduce. Therefore
`SetServiceEndpointGroup` may precede creation of both final entities, and a
clear/empty-reconcile may precede the corresponding delete. No intermediate
command order creates a false dangling-reference error.

The reducer does not provide generic last-write-wins behavior. Multiple
create/update/delete lifecycle intents for the same topology entity, both
set-and-clear for one consumer property, both placement command kinds for one
deployment, or more than one reconcile for the same deployment are ambiguous
and return `EDIT_COMMAND_CONFLICT`. Existing server reducer semantics remain
unchanged; its final server set participates in topology reference checks.

Create deployment writes only `serviceType` and `mode`. Zero deployments,
unplaced deployments and structurally incomplete-but-saveable topology are
allowed and become `UNVERIFIED`; this is not a claim that Core verification
will pass. Deployment ID, service type and mode are not silently renamed or
updated. Delete/create is never used as an implicit mode-change operation.

## 8. Generic reference and delete contract

The reducer builds a bounded reference graph from closed portable-contract
fields in the full owned documents and final candidate:

- member/host placement host -> server;
- member/host placement deployment -> service deployment;
- consumer `endpointGroup` -> endpoint group;
- preserved provider `endpointGroupRef` -> endpoint group;
- `dependencies.*.serviceDeployment` -> service deployment;
- `haproxy.deploymentRef` -> service deployment;
- `certificateScopes.*.sources.hosts[]` -> server;
- `certificateScopes.*.sources.serviceDeployments[]` -> service deployment;
- `certificateScopes.*.sources.members[]` -> the member identified by the
  canonical composite key `(deploymentId, memberId)`.

A member ID is scoped by its deployment in this graph; F2 never assumes that
`memberId` is globally unique. Removing a member is blocked when a preserved
certificate scope retains the matching composite reference. Deleting a
deployment or server is likewise blocked by the corresponding certificate
scope edge.

These are field contracts, not service-name rules. The implementation must not
branch on `kafka`, `postgresql`, `haproxy`, `bind`, `keepalived` or another
service ID and must not scan arbitrary strings for references.

`DeleteServer`, `DeleteServiceDeployment`, `DeleteEndpointGroup` and removal
of a deployment member return `REFERENCE_IN_USE` when the final candidate
retains an inbound edge. There is no cascade. Placement is explicitly removed
with the applicable complete reconcile command. Consumer endpoint assignment
is explicitly cleared. Provider, dependency and certificate-scope edges that
F2 cannot edit deliberately keep deletion/removal blocked until their owning
future milestone supplies a typed intent.

Malformed known reference fields in an Installer-owned document fail closed
as `MANAGED_DOCUMENT_INVALID`; they are not ignored merely because F2 cannot
edit them.

## 9. Managed document mutation

F2 writes only:

```text
ansible.cfg                                                   # first Save only
inventory/hosts.yml                                           # server changes
inventory/group_vars/all/platform-installer.yml               # deployments/groups
inventory/host_vars/<hostId>/platform-installer.yml           # placement
```

The existing root containment, allowed logical path, managed header,
symlink/reparse rejection, opened-object read, digest/identity, ACL/mode,
transaction journal, atomic replacement and rollback rules remain mandatory.
F2 reuses the F1 narrow safe managed-document reader for bytes that will be
decoded and changed; it must not reintroduce check-then-open reads.

`ManagedProjectView` is not serialized back to disk because it deliberately
omits fields. The reducer patches only these fixed owned paths in full parsed
documents and preserves all unrelated valid fields and `x-*` extensions:

- `platform_desired_state.serviceDeployments.<deploymentId>` lifecycle and
  consumer `endpointGroup`;
- `platform_desired_state.endpointGroups.<endpointGroupId>.address`;
- `platform_deployments.<deploymentId>.members` for member-scoped placement;
- direct `platform_deployments.<deploymentId>.roles` for host-scoped placement.

For retained member IDs, opaque member `configuration` and extensions are
preserved even when host or roles change. Removing a member intentionally
removes its whole member subtree. For retained direct host placements,
unowned sibling fields are preserved while roles are replaced; omitted/empty
roles serialize without a `roles` key. Removing a host placement removes that
deployment entry from that host document. A resulting otherwise-empty managed
host document is retained as a valid managed `platform_deployments: {}`
container; F2 adds no file/directory deletion transaction semantics.

The placement traversal set is the bounded union of:

1. source Installer-owned managed host documents returned by the narrow
   managed-host enumerator defined below; and
2. final-state server IDs.

The new enumerator is deliberately not `discoverOwnedPaths` and is not a
generic filesystem facility. It has one purpose and one fixed root:

```text
EnumerateManagedHostDocuments(projectRoot)
  -> sorted logical inventory/host_vars/<hostId>/platform-installer.yml paths
```

It opens fixed `inventory/host_vars` through the same platform-specific
no-follow/reparse-safe directory boundary used by the managed reader and
enumerates direct children only. Every direct host-directory candidate must be
a canonical host ID; symlink, junction and other reparse entries fail closed.
The enumerator accepts at most 4,096 host-document candidates and fails before
reading document content when a 4,097th candidate is observed. It constructs
only fixed logical paths and passes each one to the existing F1 handle-bound
managed-document reader, which verifies the opened file object, ownership
header, per-file/aggregate bounds and YAML bytes. Enumeration never opens a
file by pathname to authorize a later read. If a directory/file is replaced
between enumeration and handle-bound open, the read fails closed or observes
the replacement only after applying the same no-follow, ownership and content
checks; stale enumerated metadata is never trusted.

For the selected deployment, reconcile removes the old placement from every
source document in the union and then writes exactly the final
catalog-matching form to selected hosts. A same-session server delete or move
therefore cannot hide its source document before cleanup. A deleted server is
blocked while any retained placement still references it; after all placement
is explicitly removed, its otherwise-empty managed host document may remain
under the no-file-deletion policy. Reconcile never mixes `members` and direct
roles and never synthesizes member IDs for host-scoped services.

### 9.1 First Save and managed Save

Both classifications feed the same reducer and serializer:

- `EMPTY_MANAGED_PROJECT` verifies that managed outputs are absent, constructs
  the existing fixed empty inventory/desired-state containers in memory and
  applies all server/topology commands;
- `MANAGED_PROJECT` safe-reads existing managed documents and applies the same
  commands to their copies.

The first draft may contain only servers, only deployments/endpoint groups, or
a valid mixed final state. Placement still requires final-state hosts. First
Save creates `ansible.cfg`, inventory and group-vars; host-vars are created
only for selected placements. `project.yml` and its locks are never rewritten.

Both flows produce the existing `StructuralEditPlan`, use the existing
`storeStructuralPlan` and `CommitStructuralEditPlan`, and reopen through
`ReadManagedProjectView` after Commit. There is no second commit API or remote
refresh. Canonical bytes remain unchanged until Commit. Every semantic Save
produces a new revision and makes verification `UNVERIFIED`/stale under the
existing Save/Verify lifecycle.

## 10. App and Wails integration

`AppendEditCommand` expands its operation allow-list to the closed v1alpha5
set. The App does not expose arbitrary map mutation, file paths or catalog
objects from React. Existing `StartEditSession`, `ReviewStructuralEditSession`,
`CommitStructuralEditPlan` and discard methods remain the only lifecycle.

F2 may regenerate Wails bindings for the additive `EditCommand.Hosts` /
`PlacementHost` fields, but adds no topology page behavior. F3-F5 construct
these commands through thin typed frontend helpers. React does not validate
catalog membership as authority; any client-side disabling is presentation
and Go rechecks the exact catalog during Review.

## 11. Failure behavior

All failures are bounded and preserve canonical bytes and the draft:

| Code | Condition |
| --- | --- |
| `INVALID_EDIT_COMMAND` | unknown operation/field, malformed or oversized closed payload |
| `EDIT_COMMAND_CONFLICT` | ambiguous duplicate topology intents in one session |
| `PROJECT_CHANGED` | base or end-of-Review revision mismatch |
| `PROJECT_CATALOG_UNAVAILABLE` | exact locked catalog not locally available |
| `PROJECT_CATALOG_INCOMPATIBLE` | exact source exists but verification/lock matching fails |
| `CATALOG_VALUE_UNKNOWN` | edited service/mode/role is outside exact catalog vocabulary |
| `PLACEMENT_KIND_MISMATCH` | reconcile shape differs from catalog mode |
| `CAPABILITY_NOT_SUPPORTED` | consumer assignment requested for a non-consumer service |
| `REFERENCE_NOT_FOUND` | final state contains a missing server/deployment/endpoint group |
| `REFERENCE_IN_USE` | delete leaves a generic inbound reference |
| `MANAGED_DOCUMENT_INVALID` | known owned structure/reference is malformed or over limit |
| existing writer findings | ownership, path, identity, digest, security or transaction guard fails |

Safe messages identify the operation/field/entity ID only. They do not include
raw YAML/JSON, catalog content, filesystem source roots, arbitrary values,
credentials or diffs containing values.

## 12. QA and acceptance

### 12.1 Contract and compatibility

- v1alpha5 accepts every closed positive command and rejects unknown fields,
  operations, wrong nested shapes, member/host `configuration`, duplicates and
  bounds violations;
- v1alpha1-v1alpha4 schema bytes and acceptance remain unchanged;
- new sessions emit v1alpha5 only and still normalize into one Go
  `EditCommand`;
- catalog/schema generators are reproducible.

### 12.2 Reducer and catalog

- create deployments for multiple instances of one service;
- unknown service/mode/role, wrong placement kind and unsupported consumer
  capability fail safely;
- no service-ID branches exist;
- create/reference and clear/delete produce the same final candidate in either
  command order;
- conflicting repeated intents fail instead of becoming implicit
  last-write-wins;
- cardinality/distinct-host errors are not invented locally;
- cached UI catalog cannot authorize Review after exact source changes or
  becomes unavailable/incompatible;
- with catalog `UNAVAILABLE` and `INCOMPATIBLE`, deployment creation,
  non-empty placement and endpoint assignment block without fallback or lock
  rewrite;
- under the same catalog states, server CRUD, endpoint-group structural CRUD,
  clear, delete and empty placement reconcile remain available under normal
  reference/writer guards;
- server-only Save still works without a catalog;
- structural Review accepts at most 16 commands and rejects command 17 with
  the existing bounded finding.

### 12.3 Writer and reopen

- empty-project first Save supports server-only, topology-only and mixed
  candidates;
- member-scoped and host-scoped placement each pass the full
  schema-to-reopen path, including empty reconcile and cross-host move;
- deployments, endpoint groups, assignments and placements reopen exactly via
  `ManagedProjectView` without a node;
- existing provider/VIP, dependencies, configuration and extension fields are
  byte-semantically preserved outside edited paths;
- retained member configuration is preserved; removed members are removed;
- generated direct host placement never has a synthetic member ID;
- no mixed member/direct placement is produced;
- generic reference guards cover host, placement, consumer, provider,
  dependency and deploymentRef edges without cascade;
- certificate-scope host/deployment edges and composite
  `(deploymentId,memberId)` edges block the matching server, deployment or
  member removal with `REFERENCE_IN_USE`; the same `memberId` in another
  deployment is not treated as the referenced member;
- malformed known certificate-scope source/reference shapes fail closed;
- placement reconcile traverses the bounded union of initial owned managed
  host documents and final server IDs, including same-session delete/move,
  multiple deployments and an owned orphan host document, so no stale
  placement survives reopen;
- the narrow one-level enumerator accepts exactly 4,096 host-document
  candidates and rejects 4,097, invalid host-directory IDs and
  symlink/junction/reparse entries;
- replacement between enumeration and handle-bound open cannot authorize a
  stale or unsafe pathname read;
- malformed reference shapes, unsafe paths, symlink/reparse replacement,
  document/aggregate/entity bounds and revision races fail before commit;
- canonical bytes are unchanged before Commit and on every blocked Review;
- commit rollback/recovery, ACL/mode and stale-plan protections remain intact;
- post-Commit managed projection is bound to the new revision.

### 12.4 Isolation and regressions

- instrumented tests prove zero Core, Execution Node, SSH/SCP, Ansible and
  target-host calls during append/review/save/reopen;
- Save marks verification stale/unverified and does not bypass fresh
  BuildDeploymentPlan before execution;
- existing E1-E6 server CRUD, credentials, Execution Node, readiness,
  navigation and Save/Verify tests remain green;
- frontend lint/test/build and `wails build -nopackage -clean` run if generated
  bindings change;
- affected Windows tests and RED OS `go test -race` packages pass;
- `go test ./...`, `go vet ./...`, secret/security audit and
  `git diff --check` pass.

F2 implementation is classified **HIGH-RISK** because it changes a versioned
command contract and extends canonical multi-document transactions. Acceptance
therefore requires one revision-bound FULL DIFF architecture review in
addition to focused QA.

## 13. Overengineering check

F2 deliberately adds only:

- one additive schema revision required for the new closed commands;
- one small nested host-placement value required by the canonical host-scoped
  form;
- one narrow export/injection of the existing F1 catalog resolver;
- one fixed-root, one-level managed-host enumerator required to find owned
  orphan host documents without weakening the F1 handle-bound read;
- topology cases in the existing structural reducer and writer.

It adds no generic filesystem framework, topology repository, event bus,
database, background catalog cache, generic CRUD/patch API, service plugin,
second DTO graph or second Save transaction. A generic graph library is not
introduced: bounded reference extraction is a small closed table over current
portable-contract fields. A new mode-update or relation abstraction is
deferred until a concrete owner-approved command exists.

The simpler alternative of reusing v1alpha3 is rejected because that published
shape permits unrelated operations and member `configuration`, requires roles,
lacks host-scoped placement and is not the new local structural-save contract.
The simpler alternative of trusting `App.current.Catalog` is rejected because
it would make stale presentation state mutation authorization. These two
bounded additions are therefore required by current F2 acceptance, not future
speculation.

## 14. Done criteria

UI-01F2 is DONE only when:

1. v1alpha5 and both placement commands pass schema-to-reopen acceptance;
2. all F2 commands reduce with existing server commands through one local
   candidate and one existing transaction;
3. exact catalog admission is fresh, revision-bound and generic;
4. generic reference guards and preservation rules pass focused safety tests;
5. Save/reopen prove zero Core/Execution Node/target contact;
6. affected regression, race, build, reproducibility, secret and diff gates
   pass;
7. the required FULL DIFF review has zero blocking findings;
8. documentation/state/roadmap are updated, one focused implementation commit
   is created and the worktree is clean.

At F2 completion, F3 remained separately gated; it was subsequently
authorized and completed under `docs/work/ui-01/ui-01f3-architecture.md`.
