# UI-01F — Catalog-backed deployments, topology and relations

Status: **DRAFT ARCHITECTURE PLAN**

Milestone: **UI-01F**

Implementation status: **NOT STARTED**

Prerequisites: UI-01D and UI-01E1 through UI-01E6 are DONE.

Baseline revision: `5bc38903c0ce2e477bf1cff7f519bcaaea8704c0`.

This document is the common architecture plan for UI-01F. It does not
authorize UI-NET-01, UI-01G, UI-01H, service execution, PKI materialization or changes to
the standalone Ansible runtime.

## 1. Goal

UI-01F adds a catalog-backed topology editor to the existing desktop
application. Its mutation scope is deployments, placement, consumer
endpoint-group CRUD/assignment and topology views:

- select a service type and mode from the project's pinned service catalog;
- create and delete independent service deployments;
- edit member-scoped and host-scoped placement without converting one form
  into the other;
- inspect topology by service and by server;
- create/update/delete endpoint groups and edit the direct consumer
  `endpointGroup` assignment;
- show provider relations, FQDN, VIP and PKI data read-only when fresh
  ProjectSnapshot evidence exists;
- preserve the selected deployment when navigating to the future common
  service editor.

UI-NET-01 owns provider-to-consumer relation editing, `endpointGroupRef`,
`virtualRouterId`, `virtualAddresses` and related integration semantics. F
does not add provider mutation commands.

All changes remain typed intents in the existing Go `EditSession`, use the
existing local structural Review/Save transaction, and modify the same
Ansible-native project documents. UI-01F creates neither a topology database
nor a second save mechanism.

## 2. Fixed architectural boundaries

1. The portable project remains canonical desired state.
2. Service package manifests are the authored source of service capabilities;
   `ServiceCatalog/v1alpha1` is their generated, reproducible projection.
3. React renders typed data and emits typed intents. It does not parse YAML,
   apply Ansible precedence, infer defaults, or validate infrastructure
   semantics.
4. Go owns edit-session lifecycle, closed command validation, generic
   referential checks, candidate construction and filesystem transactions. It
   does not recreate service-specific mode, role or placement rules.
5. Core remains authoritative for mode compatibility, role/cardinality and
   distinct-host constraints, endpoint/provider resolution, FQDN/VIP/PKI
   derivation and all execution planning.
6. Save is local structural persistence and needs no Execution Node or Core
   call. Optional Project Verify validates the exact saved revision through
   Core. Every semantic Save makes previous verification evidence stale.
7. A prior VERIFIED state never authorizes execution. A fresh
   `BuildDeploymentPlan` for the current saved revision and attested runtime is
   still mandatory before `StartExecution`.
8. Runtime credentials, facts, readiness, plans, generated state and execution
   results never enter the topology desired state.

## 3. Existing seams and the concrete gap

UI-01F extends these accepted seams rather than replacing them:

| Concern | Existing seam | UI-01F action |
| --- | --- | --- |
| Draft lifecycle | one Go `EditSession` per project context | Reuse; server and topology intents reduce as one final state |
| Save | `ReviewStructural` → guarded local transaction | Extend the same reducer and writer to F operations |
| Reopen without node | `ManagedProjectView` | Add directly owned deployment, endpoint-group and placement fields |
| Authoritative read | `ProjectSnapshot/v1alpha1` | Reuse for verified/derived semantics and previews |
| Deployment write | internal `CreateServiceDeployment`, `DeleteServiceDeployment` | Expose through the new closed command revision |
| Member-scoped placement shape | published `ReconcileDeploymentPlacement` validation/contract boundary | Implement its full schema-to-reopen path in F2; it is not implemented before then |
| Host-scoped placement | canonical direct host deployment entries; no public reconcile intent yet | Add closed `ReconcileHostScopedDeploymentPlacement` without synthetic members |
| Endpoint write | internal endpoint-group CRUD and assignment | Expose bounded existing forms |
| Catalog | verified immutable bundle plus project `catalogLock` | Add a lock-bound typed Installer catalog projection |

`project-edit/v1alpha4` is intentionally server-only and requires
`desiredHostname`. `project-edit/v1alpha3` contains deployment/topology
operations but its server shape is older. Normalizing new UI commands to either
version would therefore lose one accepted contract or reject the other.

UI-01F introduces `platform.installer/edit-command/v1alpha5` as one additive,
closed command revision. It combines the current v1alpha4 server CRUD shapes
with only the F operations listed in section 6. All versions normalize into
the same internal Go `EditCommand`; no `TopologyCommand`, parallel session, or
parallel server/deployment DTO is introduced. Existing v1alpha1–v1alpha4
contracts remain immutable compatibility input. New Installer edit sessions
emit v1alpha5 only.

## 4. Catalog identity and availability

### 4.1 Authoritative identity

The editable vocabulary must match the project, not merely the newest local
bundle. The Installer resolves a local verified immutable bundle whose:

- bundle digest equals `project.yml.artifactLock.digest`;
- catalog digest equals `project.yml.catalogLock.digest`;
- catalog service definition identities, versions and digests match the
  project's `catalogLock.services`.

The resolver accepts only Installer-controlled verified bundle roots. React
cannot submit a catalog path or an arbitrary digest. The catalog is revalidated
before projection; no file from the project overrides the generated catalog.

### 4.2 Typed projection

Go exposes a bounded `ProjectCatalogView` containing only data needed by F:

- catalog and bundle identity;
- service ID, display name, description, category and presentation hints;
- modes with display name and description;
- declared roles;
- explicit `placementKind`: `MEMBER_SCOPED` or `HOST_SCOPED`, projected
  generically from the manifest's placement capability;
- placement hints (`minMembers`, optional `maxMembers`, `distinctHosts`) for
  form guidance only;
- whether the manifest declares a generic endpoint or endpoint provider.

The mapping is service-agnostic: manifest `placement.hostScoped=true` produces
`HOST_SCOPED`; absent/false produces `MEMBER_SCOPED`. No service ID participates
in that decision. Role cardinality may be displayed as catalog guidance, but
React and Go do not use it to decide whether Save is valid. Core owns that
decision. Configuration schemas/settings are reserved for UI-01H; PKI editor
data is reserved for UI-01G.

The view is derived and never persisted into the project, application settings
or a database. Adding a service or mode through a new versioned service package
and regenerated catalog requires no React source change.

### 4.3 Missing or mismatched catalog

If the exact pinned catalog is unavailable or fails verification:

- direct Installer-owned saved topology remains visible through
  `ManagedProjectView`;
- catalog-dependent creation, mode change and role editing are disabled with a
  typed compatibility diagnostic;
- existing unknown service/mode/role values are preserved and displayed
  read-only;
- Save of unrelated already-supported draft changes is not silently rebound to
  another catalog;
- the Installer neither downloads a replacement nor rewrites locks.

Project Verify may still be unavailable for its independent Execution Node
prerequisites. Catalog absence is not solved by inventing local Core behavior.

## 5. Desired-state ownership and local projection

| Data | Canonical owner | Local reopen projection | Authoritative/derived projection |
| --- | --- | --- | --- |
| Deployment ID, service type, mode, consumer `endpointGroup` | Installer-owned managed group_vars | `ManagedProjectView.deployments` | `ProjectSnapshot.serviceDeployments` |
| Endpoint group desired fields | Installer-owned managed group_vars | `ManagedProjectView.endpointGroups` | `ProjectSnapshot.endpointGroups` and resolved endpoints |
| Member-scoped member ID, host ID and roles | Installer-owned managed host_vars member form | `ManagedProjectView.placements` | `ProjectSnapshot.topology` |
| Host-scoped host ID and optional roles | Installer-owned direct managed host_vars deployment form | `ManagedProjectView.placements` | `ProjectSnapshot.topology` |
| Provider `endpointGroupRef`, `virtualRouterId`, `virtualAddresses` | Existing canonical deployment desired state; editing deferred to G | Not locally exposed by F | Fresh `ProjectSnapshot` read-only |
| Host desired fields | Installer-owned inventory | existing `ManagedProjectView.servers` | `ProjectSnapshot.hosts` |
| Effective roles/cardinality, endpoints, providers, FQDN/VIP/PKI | Core-derived | not calculated locally | fresh `ProjectSnapshot` only |

`ReadManagedProjectView` is expanded through exact, bounded readers for the
Installer-owned managed documents. It does not merge arbitrary group_vars,
host_vars, role defaults, inventory groups or `project.yml.desiredState`; it
does not adopt external documents. Unknown files and unknown fields in owned
documents remain byte/semantic-preserved by the existing candidate writer.

For an empty metadata-only project, the first local Save may contain server and
topology intents together. The candidate creates the same fixed owned files as
today and reduces all commands to a single final state before writing. A
deployment may be saved without complete placement; it becomes UNVERIFIED and
may later be INVALID. A placement may reference only a host present in that
final state, including an acknowledged `CreateServer` intent in the same
session. The local projection preserves the canonical distinction between
member-scoped entries and direct host-scoped entries.

## 6. UI-01F command contract

The public v1alpha5 command set used by this milestone is closed:

### 6.1 Compatibility-complete server operations

- `CreateServer(hostId,address,sshPort?,type,desiredHostname)`;
- `UpdateServer(hostId,address?,sshPort?,clearSSHPort?,type?,desiredHostname?)`;
- `DeleteServer(hostId)`.

Their UI-01E1 semantics are unchanged, including omitted `sshPort` versus
explicit `22` versus `clearSSHPort`.

### 6.2 Deployments

- `CreateServiceDeployment(deploymentId,serviceType,mode)`;
- `DeleteServiceDeployment(deploymentId)`.

Deployment ID is immutable. Rename and mode change are not simulated as an
unsafe delete/create cascade. If mode editing is required by acceptance, a
future explicit `UpdateServiceDeploymentMode(deploymentId,mode)` may be added
to v1alpha5 before implementation only after candidate/reference semantics are
specified and tested; absence of that command does not authorize raw map
replacement.

Creation is allowed only for service/mode identifiers present in the exact
pinned catalog. This is compatibility-vocabulary admission, not replacement of
Core semantic validation. Multiple deployments of the same service type are
allowed.

### 6.3 Closed placement intents

Placement kind is explicit in `ProjectCatalogView` and selects one of two
closed, mutually exclusive command shapes:

- `ReconcileDeploymentPlacement(deploymentId,
  members[{memberId,hostId,roles?}])` for `MEMBER_SCOPED` deployments;
- `ReconcileHostScopedDeploymentPlacement(deploymentId,
  hosts[{hostId,roles?}])` for `HOST_SCOPED` deployments.

Each command is the complete desired placement list for one deployment, so
cross-host moves and removals are one atomic candidate change. The
host-scoped form writes direct `platform_deployments.<deploymentId>` entries in
the corresponding managed host_vars and never synthesizes a `memberId`. Roles
are optional so catalog-declared roleless modes remain representable.

Go validates only that the selected command shape matches the catalog-declared
`placementKind` and that any supplied role identifier belongs to that catalog
mode. This check is generic and must not branch on service IDs such as `bind`,
`haproxy`, `keepalived` or `dns-client`. Mode/cardinality, role cardinality and
distinct-host policy remain Core findings, not local Save authorization.

The UI does not emit legacy point operations. Duplicate member/host entries,
duplicate roles, malformed IDs and missing host/deployment references are
structural errors. Member or host `configuration` is not exposed by F; it is
reserved for schema-driven UI-01H.

The already-published `ReconcileDeploymentPlacement` shape is not considered
implemented merely because validation and schema fragments exist. F2 must
provide and test its complete path:

```text
schema
  → decoder
  → reducer
  → managed writer
  → candidate
  → local Save
  → reopen
```

The new host-scoped intent must pass the same complete path.

### 6.4 Endpoint groups and assignment

- `CreateEndpointGroup(endpointGroupId,endpointGroup)`;
- `UpdateEndpointGroup(endpointGroupId,endpointGroup)`;
- `DeleteEndpointGroup(endpointGroupId)`;
- `SetServiceEndpointGroup(deploymentId,endpointGroupId)`;
- `ClearServiceEndpointGroup(deploymentId)`.

The complete endpoint-group body reuses the existing desired-state
`endpointGroup` schema. Its owned desired fields are only
`address.domain` and `address.wildcard`. Consumer assignment writes only the
deployment's `endpointGroup`. It does not edit resolved bindings, aliases,
listener names, ports or Kafka listeners.

Provider-side `endpointGroupRef`, `virtualRouterId` and `virtualAddresses` do
not belong to the endpoint-group body. UI-01F adds no commands for them. They
are displayed only from fresh Core snapshot evidence and their editing is
deferred to UI-NET-01 with the related provider/consumer integration semantics.

Delete uses the generic reference graph and returns `REFERENCE_IN_USE` when
referenced. No Kafka, PostgreSQL, HAProxy or other service-specific delete rule
is added to Go.

### 6.5 Dependencies and other relations

The current service manifests declare no editable dependency relation shape;
their `dependencies` arrays do not provide a generic relation-editor contract.
Consequently UI-01F does not invent arbitrary dependency fields or expose
`SetHAProxyIntegration` merely because an internal compatibility operation
exists. Existing saved relations remain preserved and, when present in a fresh
snapshot, read-only.

A future editable relation requires a versioned catalog declaration, a closed
typed intent and Core validation evidence. UI-NET-01 owns the provider/consumer
relation and provider networking fields identified above; other generic
dependency editing remains separately gated. This is a deliberate boundary,
not a hidden service-specific switch in React or Go.

## 7. Reduction, references and deletion

The session reducer evaluates server, deployment, endpoint-group, assignment
and placement commands as one final candidate state. It must support legitimate
create-then-reference and clear/delete sequences independent of command order
where the existing final-state model promises that behavior.

Local checks are limited to:

- command schema and bounded sizes;
- exact project revision and session identity;
- duplicate identifiers in the final state;
- references to final-state hosts, deployments and endpoint groups;
- generic inbound-reference protection on delete;
- catalog-lock vocabulary admission and placement-kind matching for newly
  edited type/mode/role values;
- writer ownership, allow-listed paths, digest preconditions,
  symlink/reparse safety and transaction recovery.

The generic reference graph is data-structural. It includes both consumer
`endpointGroup` and preserved provider `endpointGroupRef` edges, contains no
per-service branch and performs no cascade deletion. The UI must show consumers
from current direct state or fresh snapshot evidence and require the operator
to clear/move editable references explicitly before deletion. A provider edge
that F cannot edit keeps deletion blocked until UI-NET-01.

## 8. Save, Verify and freshness

The flow is:

```text
pinned verified catalog ──> ProjectCatalogView ──> React choices
saved managed documents ──> ManagedProjectView ──> React saved state
                                      │
React typed intents ──> existing EditSession final-state reducer
                                      │
                                      v
                      local structural Review
                                      │
                                      v
                   existing guarded atomic Save
                                      │
                                      v
                  new canonical project revision
                                      │
                         verification = STALE/UNVERIFIED
                                      │
                     optional explicit Project Verify
                                      │
                                      v
                 fresh Core ProjectSnapshot/previews
```

Review shows semantic changes, affected owned documents and a bounded diff.
Canonical bytes do not change before Commit. Save never contacts target hosts,
the Execution Node or Core. A failed Verify never rolls back a successful Save.

Derived preview data is displayed only when evidence matches the current
canonical project revision and attested Core/runtime identity. Otherwise the
UI labels it stale or unavailable and continues to show direct desired fields
separately. It never combines stale derived values with a current draft as if
they were authoritative.

## 9. UX and mockup reconciliation

The implementation rechecks `docs/design/ui-design-01-mockups.html` before every F
sub-milestone and at acceptance. Demo service names, roles, counts and statuses
in the mockup are not product rules.

### 9.1 Topology page

The page follows the mockup's minimal layout and provides three local views:

1. **By services** — deployment list, placement-kind-aware member or direct
   host placement, roles and compact desired/verification summary.
2. **By servers** — server selector and the final draft assignments on that
   server. The server list and details scroll independently where needed.
3. **Entry points** — endpoint-capable deployments, editable consumer
   endpoint-group assignment and group address fields, plus fresh/stale
   read-only provider/VIP preview.

`Add service instance` opens a catalog-driven dialog. The dialog asks for a
stable deployment ID, service type and mode; it does not pre-create every
catalog service in `project.yml` or group_vars. Zero deployments is valid.

`Save topology` opens the existing common structural Review/Save flow. The App
Shell continues to show common “Сохранено / Есть изменения” and verification
status; the topology page does not create its own persistence status model.

### 9.2 Navigation

Selecting a deployment or `Configure service` preserves `deploymentId`, source
page and selection. Until UI-01H, the destination is an explicit read-only/not
yet available service-editor state and offers return to Topology; it does not
expose a partial settings editor. Certificate profile editing remains disabled
until UI-01G.

Topology editing requires an open managed project and an available compatible
catalog, not a READY Execution Node. Existing E5 navigation gates and the
Execution Node panel are not redesigned in F.

## 10. Error and compatibility behavior

- External/non-owned projects remain read-only.
- Unknown existing service, mode, role or relation values are preserved and
  displayed read-only, never normalized away.
- An absent exact catalog blocks catalog-backed mutation without changing the
  project.
- A stale base revision, changed document, unsafe path, reparse/symlink or
  ownership mismatch blocks Save before publication.
- Invalid Core semantics can be saved structurally and later produce INVALID
  verification; Installation remains blocked until a fresh valid
  `BuildDeploymentPlan` exists.
- Draft survives navigation and recoverable validation errors. Session discard
  removes only transient intents.
- No secret value or runtime credential appears in commands, projection, diff,
  logs or diagnostics.

## 11. Implementation slices

UI-01F remains one milestone and one architecture, implemented in bounded
slices:

### UI-01F1 — catalog and local read model

Status: **DONE**.

- lock-bound verified catalog resolver and `ProjectCatalogView`;
- extend `ManagedProjectView` with direct deployments, endpoint groups and
  both canonical placement forms;
- compatibility/missing-catalog behavior;
- no mutation UI yet.

### UI-01F2 — contract and local reducer/writer

Status: **DONE**. Detailed architecture and evidence:
`docs/work/ui-01/ui-01f2-architecture.md` and `docs/work/ui-01/reviews/ui-01f2-architecture-review.md`.

- immutable `project-edit/v1alpha5` schema;
- normalize v1alpha5 into existing `EditCommand`;
- implement both closed reconcile intents through schema, decoder, reducer,
  managed writer, candidate, local Save and reopen;
- extend final-state reducer and `ReviewStructural` to the remaining F command
  set;
- extend first Save and managed Save without adding a second path;
- generic reference/delete guards and preservation tests.

### UI-01F3 — deployment UI

Status: **DONE**. Evidence: `docs/work/ui-01/ui-01f3-architecture.md`.

- Topology navigation and catalog-driven Add/Delete deployment;
- By services view and stable selection;
- common draft and Review/Save integration.

### UI-01F4 — placement UI

Status: **DONE**. Evidence: `docs/work/ui-01/ui-01f4-architecture.md`.

- catalog-driven `MEMBER_SCOPED` members/roles form;
- catalog-driven `HOST_SCOPED` direct hosts/optional roles form;
- cross-form rejection and no synthetic members;
- whole-deployment reconcile through the matching closed intent only;
- By servers projection from the same final draft;
- no local service-semantic validation.

### UI-01F5 — endpoint groups and projections

Status: **NEXT**; separate owner gate. Plan: `docs/work/ui-01/ui-01f5-architecture.md`.

- Entry points view, endpoint-group CRUD and assignment;
- generic consumer/delete UX;
- provider relation and VIP fields read-only from fresh Core evidence, with
  explicit UI-NET-01 ownership for editing, through a minimal typed/bounded Go
  projection rather than raw ProjectSnapshot maps in React;
- INVALID verification exposes safe findings but no authoritative
  FQDN/provider/VIP preview;
- revision-bound Core preview and honest stale/unavailable states;
- service editor and its navigation remain outside F5.

### UI-01F6 — acceptance and regression — DONE

- Windows desktop end-to-end acceptance;
- RED OS target-free Core verification and affected race tests;
- contract/catalog reproducibility, safety and regression gates;
- docs/state/roadmap update only after all acceptance criteria pass.

Acceptance evidence is recorded in `docs/work/ui-01/ui-01f6.md`. It passed the built
Windows desktop check, deterministic web-view acceptance, RED OS target-free
Core and race gates, catalog/schema reproducibility and hygiene checks. UI-01F
is complete; UI-NET-01, UI-01G and UI-01H remain out of scope.

Before each slice, compare its screens and flows with the mockup and record any
material discrepancy. A discrepancy that changes ownership, contract or user
flow returns to the owner before implementation.

## 12. Verification plan

### 12.1 Positive behavior

- metadata-only project: server plus deployment plus placement saves locally
  with zero Execution Node/Core/target calls;
- create multiple independent deployments of one service type;
- catalog-driven type/mode/roles render without React hardcoding;
- create, move and remove Kafka-style logical members through the
  member-scoped reconcile intent;
- place roleless HAProxy/Keepalived/dns-client-style deployments directly on
  hosts through the host-scoped reconcile intent;
- preserve BIND host-scoped role placement without synthetic member IDs;
- endpoint-group create/update/assignment/clear/delete;
- provider relation/VIP values are read-only and appear only from matching
  fresh Core evidence;
- draft and selection survive Topology tabs and navigation;
- close/reopen without an Execution Node reproduces direct saved fields;
- explicit Verify returns Core findings/snapshot for the saved revision;
- fresh preview appears only for matching revision/runtime evidence.

### 12.2 Negative and safety behavior

- malformed/duplicate deployment, member, host and endpoint-group IDs;
- duplicate member/host entries, duplicate roles and oversized
  command/session bodies;
- member-scoped intent against `HOST_SCOPED`, host-scoped intent against
  `MEMBER_SCOPED`, and roleless catalog modes;
- unknown newly selected service/mode/role or mismatched catalog lock;
- missing host/deployment/endpoint-group reference;
- delete server, deployment or endpoint group while generically referenced;
- stale project revision/document digest and concurrent edit conflict;
- unknown owned fields and unrelated files are preserved;
- external project, missing ownership marker, unsafe path, symlink/reparse and
  interrupted transaction remain blocked/recoverable;
- INVALID Verify leaves saved bytes unchanged;
- stale snapshot is never presented as current draft truth;
- no plaintext secret or secret-like command payload is accepted or logged.

### 12.3 Contract and regression gates

- project-edit v1alpha1–v1alpha4 compatibility plus v1alpha5 schema/decoder
  tests for both placement forms;
- project/service/catalog schema reproducibility;
- catalog generator `--check` and no source/catalog drift;
- focused installer reducer, local Save, transaction, lifecycle, verification
  and Wails binding tests;
- frontend unit tests for all three views, catalog unavailable, draft,
  selection, navigation and Save/Verify freshness;
- frontend lint/test/build and `wails build -nopackage -clean`;
- `go test ./...`, `go vet ./...`, affected RED OS `go test -race` packages;
- target-free Core tests on RED OS using current working-tree sources;
- secret audit excluding `vendor/**` and `ansible-core/**/_vendor/**`;
- `git diff --check` and clean-worktree evidence after the focused commit.

Not required for F: provider/consumer relation or provider networking editing,
Kafka/PKI/service apply, target SSH, Execution Node prepare, certificate
issue/materialize, deployment execution or full installation E2E.

## 13. Overengineering check

The smallest architecture that satisfies F is one catalog projection, one new
closed command revision, the existing `EditCommand`/`EditSession`, an expanded
direct-owned local view, and the existing candidate/writer transaction.

Explicitly rejected:

- topology database, cache database or UI-owned desired-state store;
- generic YAML/JSON patch, arbitrary path/document command or raw manifest map;
- separate topology session, save button implementation or transaction engine;
- frontend catalog copy or hardcoded Kafka/PostgreSQL role logic;
- local Ansible precedence, local Core emulator or Go endpoint/FQDN/VIP logic;
- strategy/dependency graph framework without a versioned catalog relation
  contract;
- automatic catalog migration/download or lock mutation;
- speculative container, PKI, service-settings or execution abstractions.

No new abstraction is justified unless a concrete slice cannot be implemented
through the seams above and the owner accepts the documented contract change.

## 14. DONE criteria

UI-01F is DONE only when:

1. F1–F6 acceptance passes in the built Windows desktop application and the
   required RED OS gates pass.
2. New projects and reopened managed projects edit the same portable
   Ansible-native desired state with no READY Execution Node required for Save.
3. Service/mode/role choices are bound to the exact pinned verified catalog;
   future catalog services require no React change.
4. Deployment, both placement kinds and consumer endpoint-group changes use
   v1alpha5 typed intents, one EditSession and one guarded local Save path;
   provider networking remains read-only and owned by UI-NET-01.
5. Core remains the only authority for infrastructure semantics and derived
   previews; fresh planning remains the execution gate.
6. Unknown/unsupported data is preserved, references are protected generically,
   and all safety/secret/transaction regressions are green.
7. Architecture and safety review have zero blocking findings, docs/state/
   roadmap are updated, one focused commit exists, and the worktree is clean.

UI-NET-01, UI-01G and UI-01H do not begin as part of UI-01F completion.
