# UI-BE-01 — Installer UI / Backend boundary

Status: **DONE**. This milestone defines architecture and semantic contracts
only. It does not implement a Go backend, Wails transport, React pages, project
mutation, execution streaming, or another desired-state store.

## 1. Decision summary

The Installer is an editor and orchestrator over the same portable Ansible
project used by standalone operators. Standard inventory, `group_vars`,
`host_vars`, and role defaults remain authoritative. The backend composes Core
outputs into UI-oriented read models and accepts semantic commands; it does not
reimplement Ansible precedence, service topology, endpoint publication, PKI, or
provider ordering.

The owner decisions for this boundary are:

1. Open arbitrary supported Ansible projects read-only. Default write support
   to Installer-owned standard Ansible files. Permit a targeted edit to an
   existing human-owned file only after a future writer proves the selected
   subtree is supported and the operator explicitly adopts that write target.
2. Represent an effective value with its Core resolution state and semantic
   source, a separate physical origin, a logical path, and an edit policy with
   an optional override target. Do not model the whole Ansible precedence
   chain.
3. Derive `projectRevision` from sorted relevant relative paths and their raw
   byte digests. An edit also carries per-document preconditions for every file
   it may touch.
4. Use a mandatory `EditPlan -> explicit review -> CommitEditPlan` workflow for
   normal UI writes. Do not make an immediate write the primary command.
5. Keep project identity, canonical summaries, compact topology, findings, and
   readiness in `ProjectSnapshot`. Load complete catalog schemas, deployment
   settings, detailed topology, runtime observations, plans, events, and logs
   through separate queries.
6. Refresh observations through independently versioned, timestamped runtime
   queries or streams tied to the project revision. Do not rebuild the project
   snapshot for every poll.
7. Persist run, phase, and action boundaries; terminal failures/findings;
   per-host/action recaps; cancellation/interruption; and diagnostic
   references. Successful task-level progress is streamed and bounded, not
   retained as permanent history by default.
8. Preserve V1 interaction behavior for project navigation, host-key trust,
   runtime-only credentials, cancellation/recovery, structured progress,
   sanitized diagnostics, audit, and offline help. Reject V1's SQLite
   `config_json`, whole-project DTO save, duplicated service rules, and direct
   Wails-method-per-control API shape.

## 2. Overall architecture and ownership

```text
Frontend (React/TypeScript)
        |
        | versioned queries, semantic commands, event subscriptions
        v
Go facade / application services
  Project API   Catalog API   Editor API   Execution API
  Environment API             Secrets API  Journal API
        |             |             |
        v             v             v
 ProjectStore      CoreClient     Executor / SecretBroker / RunRepository
        |             |             |
        +-------------+-------------+
                      |
                      v
      canonical portable Ansible project + published Core artifacts
```

Domain contracts are defined before transport mapping. Wails-generated Go and
TypeScript bindings transport these contracts; they do not define their
semantics. A future non-Wails transport must be able to expose the same
operations.

### Canonical state

- inventory hosts and transport references;
- `platform_desired_state`, including service deployments, endpoint groups,
  PKI policy, and integration intent;
- inventory/host `platform_deployments`, member roles, placement, and
  member/host-scoped desired settings;
- ordinary documented role variables and role defaults.

### Derived state

- resolved topology and effective service configuration;
- resolved endpoints, integration/provider relations, PKI requests, and
  materialization plans;
- validation results, readiness, and plans;
- UI read models composed from those projections.

### Generated state

- generated identities, fingerprints, locks, BIND logical-content fingerprint
  and serial, and similar machine-owned metadata permitted by
  `platform_generated_state`.

### Runtime state

- discovered host facts and connectivity/preparation observations;
- current PostgreSQL, Keepalived, HAProxy, BIND, Kafka, and PKI observations;
- active runs, events, results, sanitized logs, and runtime secret
  availability.

SQLite or another local store may index project paths and revisions and retain
runtime/operational history. It must never contain an independently editable
copy of canonical topology, configuration, endpoint, integration, or PKI
desired state.

## 3. Contract rules

Externally consumed semantic contracts use names such as
`platform.installer/ui-project-snapshot/v1alpha1`. Internal Go structs and
Wails bindings are not versioned independently unless they cross that semantic
boundary.

All query responses use a common transport-neutral envelope:

```yaml
apiVersion: platform.installer/query-response/v1alpha1
kind: QueryResponse
projectRevision: sha256:...
data: {}
findings: []
error: null                 # structured and safe when present
```

`data` is one named versioned model, not an arbitrary map in an actual
implementation. Errors contain a stable code, safe message, optional finding
references, and retryability. They never rely on raw Ansible output.

## 4. ProjectSnapshot/v1alpha1

`ProjectSnapshot` is a read-only opening model. It is a consistent composition
at one `projectRevision`, not a persistence format and not a payload accepted
by save operations.

```yaml
apiVersion: platform.installer/ui-project-snapshot/v1alpha1
kind: ProjectSnapshot
project:
  id: local-stable-handle
  displayName: production-site
  path: C:/projects/production-site
  access: READ_ONLY | MANAGED | PARTIALLY_MANAGED
projectRevision: sha256:...
inputs:
  catalogDigest: sha256:...
  coreDigest: sha256:...
  generatedStateRevision: sha256:...   # optional, separate from desired revision
hosts: []
serviceDeployments: []
endpointGroups: []
topologySummary: {}
integrationSummary: []
pkiSummary: {}
validation:
  status: PASS | WARNING | BLOCKED | UNKNOWN
  actionRequiredCount: 0
  findings: []
readiness:
  status: READY | REQUIRES_PREPARATION | BLOCKED | UNKNOWN
  reasons: []
links:
  catalog: catalog-current
  topology: topology-current
```

The arrays expose stable IDs, display labels, service types/modes, compact
placement counts, endpoint assignment, and finding counts. They may include
canonical values needed to render the shell, but every field is marked in the
backend model as canonical or projected and no snapshot object can be written
back wholesale.

Excluded from the opening snapshot:

- full JSON Schemas and all service-manifest details;
- every effective setting and opaque variable;
- detailed topology graph and provider projection;
- host facts and service runtime observations unless explicitly requested as
  a bounded expansion;
- plan bodies, event history, and raw logs;
- secret values and private PKI material.

These exclusions keep project open deterministic and target-free. The
frontend obtains details with `GetCatalogView`, `GetServiceSettingsView`,
`GetTopologyView`, `GetEndpointViews`, `GetRuntimeObservations`,
`GetPlanPreview`, and run-history queries.

## 5. Field classification

| Read-model field | State class | UI policy | Authority |
| --- | --- | --- | --- |
| Inventory host identity/transport reference | CANONICAL | EDITABLE when bound | inventory/host vars |
| Service deployment ID, type, mode, configuration override | CANONICAL | EDITABLE when bound | `platform_desired_state` |
| Member role, host placement, member configuration | CANONICAL | EDITABLE when bound | inventory `platform_deployments` |
| Endpoint group domain/wildcard intent | CANONICAL | EDITABLE when bound | `platform_desired_state.endpointGroups` |
| Deployment endpoint-group assignment | CANONICAL | EDITABLE when bound | service deployment |
| PKI CA/profile/scope policy reference | CANONICAL | EDITABLE when bound | desired PKI policy |
| HAProxy publication / Keepalived tracking intent | CANONICAL | EDITABLE when manifest permits | service configuration/relations |
| Effective configuration and source | DERIVED | READ-ONLY; override may be offered | Core configuration projection |
| Resolved topology and FQDN/SAN | DERIVED | READ-ONLY | Core resolvers |
| BIND/HAProxy provider relation | DERIVED | READ-ONLY | integration projection |
| Installability/readiness and plan | DERIVED | READ-ONLY | validation/planning |
| Kafka IDs, PKI request/materialization fingerprints | GENERATED | READ-ONLY | generated state/Core projection |
| BIND serial | GENERATED | READ-ONLY | generated state |
| Discovered OS/CPU/memory | RUNTIME | READ-ONLY | observation store |
| PostgreSQL PRIMARY/SECONDARY | RUNTIME | READ-ONLY | verify/observation |
| Keepalived MASTER/BACKUP/FAULT and VIP owner | RUNTIME | READ-ONLY | verify/observation |
| HAProxy backend health | RUNTIME | READ-ONLY | verify/observation |
| Secret availability | RUNTIME | command-only set/reference; value unreadable | SecretBroker |

The UI must visually distinguish configured intent, calculated projection,
machine-generated metadata, and current observation.

## 6. EffectiveValue and provenance

The backend adapts the existing `ResolvedServiceConfiguration/v1alpha1`
states and sources. It does not load arbitrary YAML and simulate Ansible
precedence.

```yaml
logicalPath: serviceDeployments.postgres-main.configuration.port
state: RESOLVED | DEFERRED | UNRESOLVED | CYCLIC | REDACTED
value: 5432                         # present only when safe and resolved
expressionSummary: null             # never a plaintext secret
semanticSource:
  kind: ROLE_DEFAULT | DEPLOYMENT_OVERRIDE | MEMBER_OVERRIDE |
        STATIC_REFERENCE | INVENTORY | DERIVED | GENERATED |
        RUNTIME | UNKNOWN
  reference: null
physicalOrigin:
  kind: ROLE_DEFAULT | PROJECT_CONFIGURATION | GROUP_VARS | HOST_VARS |
        INVENTORY
  documentId: group-vars-all-platform
  relativePath: inventory/group_vars/all/platform.yml
  yamlPath: platform_desired_state.serviceDeployments.postgres-main.configuration.port
editPolicy:
  mode: READ_ONLY | DIRECT | OVERRIDE
  reasonCode: null
  overrideTarget:
    documentId: installer-desired-state
    logicalPath: serviceDeployments.postgres-main.configuration.port
```

Only `logicalPath`, `state`, `semanticSource.kind`, and `editPolicy.mode` are
always required. `physicalOrigin` is present only when Core or a trusted
project loader has exact evidence. `overrideTarget` is a backend writer
decision, never inferred from a role-variable naming convention.

Examples:

- A literal PostgreSQL port from a bound `group_vars` document is
  `DEPLOYMENT_OVERRIDE`, has a `GROUP_VARS` physical origin, and may be
  `DIRECT`.
- The same value from a role default is `ROLE_DEFAULT`, read-only at its
  origin, with an `OVERRIDE` target in an Installer-owned desired-state file.
- A Jinja expression is `DEFERRED` and normally `READ_ONLY`; the UI must not
  replace it with its observed value.
- Generated, derived, runtime, opaque-expression, and redacted values are
  never directly editable.

This is the smallest useful model: it explains what the UI shows and where a
safe override could go without representing the entire Ansible precedence
graph.

## 7. ServiceCatalogView and ServiceSettingsView

`ServiceCatalogView/v1alpha1` normalizes the tracked generated catalog and
service packages for presentation. Per service it exposes:

- ID, version, display name, description, category, maturity, and
  compatibility summary;
- modes and placement capabilities;
- listeners, endpoint/provider capability, declared dependencies and
  integration capabilities;
- configuration schema reference/digest and normalized UI metadata;
- apply/verify availability, never internal role task names.

`ServiceSettingsView/v1alpha1` is loaded for one deployment/member context:

```yaml
deploymentId: postgres-main
memberId: null
serviceType: postgresql
mode: pg_auto_failover
schemaDigest: sha256:...
sections:
  - id: network
    label: Network
    order: 10
    fields:
      - logicalPath: configuration.port
        label: PostgreSQL port
        description: ...
        valueType: integer
        constraints: {minimum: 1, maximum: 65535}
        effectiveValue: {}
        findings: []
advanced:
  supported: true
  schema: {}
  reservedProperties: []
opaqueVariables:
  count: 0
  detailsLink: null
```

Sections, labels, order, types, enum choices, validation, advanced schema, and
reserved properties come from `service.yml` and generated
`configuration.schema.json`. Role defaults remain the only semantic defaults.
The frontend may select a renderer hint, but it must not implement service
validation or defaulting.

Required manifest presentation gaps, to be added only when consumed, are:

- stable field help/description and optional `helpRef`;
- renderer hints for complex objects such as listener maps;
- declarative visibility/enabling hints where necessary;
- user-facing member-role labels/order;
- friendly reserved-property messages.

Secret-reference fields return the reference identifier and availability
state (`MISSING`, `PRESENT`, `EXPIRED`, or `UNKNOWN`), never a secret value.

## 8. TopologyView and placement capabilities

Topology is a separate domain, not a settings section.
`TopologyView/v1alpha1` contains deployment nodes, logical members or
host-scoped participants, host placements, role assignments, desired
placement properties, references, and Core findings. It may include a derived
graph but is never accepted as a save payload.

`PlacementCapabilities/v1alpha1` is adapted from the selected manifest mode:

```yaml
serviceType: postgresql
mode: pg_auto_failover
model: LOGICAL_MEMBERS | HOST_SCOPED
explicit: true
minMembers: 3
maxMembers: 3
distinctHosts: true
roles:
  - id: monitor
    minimum: 1
    maximum: 1
  - id: database
    minimum: 2
    maximum: 2
memberProperties: []
hostPlacementProperties: []
```

Current manifests already provide `hostScoped`, explicit placement,
member-role sets, member count, distinct-host policy, and role cardinality.
Exact gaps are typed declarations for member-specific and host-placement
properties (for example Keepalived priority or HAProxy `hostEndpoint`) and
user-facing role metadata. UI-BE-02 should expose existing data first;
manifest extensions are justified only for properties a generic editor must
render. A universal topology DSL is not required.

## 9. EndpointView and IntegrationView

`EndpointView/v1alpha1` composes canonical endpoint-group intent with
`ResolvedServiceEndpoint/v1alpha1` and provider projections:

```yaml
serviceDeploymentId: postgres-ha
serviceType: postgresql
endpointGroup:
  id: applications
  domain: asutp.scada.local
  wildcardDns: true
deploymentEndpoint:
  fqdn: postgres-ha.asutp.scada.local
hostEndpoints: []
providers:
  virtualAddressProvider: keepalived-a
  virtualAddresses: []
  dnsProvider: bind-main
  haproxyProvider: haproxy-a
status: READY | BLOCKED | UNKNOWN
findings: []
```

The UI never calculates FQDNs, VIP ownership, publication, or routing.
Transport ports and listener behavior remain service/package contracts rather
than generic endpoint fields.

`IntegrationView/v1alpha1` is read-only and expresses the resolved chain:

```text
target service deployment -> endpoint group -> BIND provider
                                      \-----> Keepalived VIP provider
                                      \-----> HAProxy provider
```

It contains target/provider IDs, relation kind, resulting endpoint IDs,
status, and findings. It is derived from canonical references and the
NET-04.2 integration projection and is never persisted as another relation.

## 10. PKI and runtime summaries

`PkiSummaryView/v1alpha1` may expose CA/profile/scope references, certificate
identity, SAN count/summary, request and materialization fingerprints,
materialization/verify status, expiry when observed, and reissue-required
findings. It never returns private keys, passwords, password-file paths, raw
stores, runtime secret values, or unrestricted tool output.

Canonical PKI policy is editable only through semantic edit commands. PKI
requests and materialization plans remain derived; identity/fingerprint state
remains generated; material and current validity remain runtime/backend-owned.

`RuntimeObservationSet/v1alpha1` is queried independently:

```yaml
projectRevision: sha256:...
observationRevision: sha256:...
observedAt: 2026-09-03T12:00:00Z
freshUntil: 2026-09-03T12:05:00Z
scope: {kind: serviceDeployment, id: postgres-ha}
observations: []
findings: []
```

Polling or subscription replaces an observation set atomically. An
observation is displayed only against its recorded project revision; a newer
desired revision marks it stale. This prevents observed PostgreSQL roles,
Keepalived ownership, or HAProxy health from becoming editable desired values.

## 11. Validation and readiness

`ValidateProject` invokes the existing target-free Core validation path and
returns `ValidationResult/v1alpha1`. The backend may add UI navigation metadata
without changing a finding's semantic code or status.

The existing `Finding/v1alpha1` already provides code, status, category,
subject, field, safe message/details, remediation, help URI, and evidence
references. UI adaptation adds only:

- logical path and exact physical origin when known;
- typed navigation target;
- a `blocking` convenience value derived from status, never a competing
  severity system.

The presentation vocabulary remains `PASS`, `WARNING`, `BLOCKED`, `UNKNOWN`,
and `ACTION_REQUIRED`. The existing plan readiness vocabulary remains
`READY`, `REQUIRES_PREPARATION`, `BLOCKED`, and `UNKNOWN`. Do not introduce
`VALID`, `READY_TO_APPLY`, or `APPLIED_WITH_DRIFT` as a second state machine;
validation status, plan readiness, and drift observation are separate fields.

One existing schema gap must be corrected before UI-BE-02 publishes findings:
`Finding.subject.kind` still lists the removed `endpointBinding`. It needs
current endpoint-group/service-endpoint subject kinds through a deliberate
alpha contract update, not a frontend workaround.

## 12. PlanPreview and execution

`PlanPreview/v1alpha1` is a presentation adapter over the existing immutable
`DeploymentPlan/v1alpha1`; it does not define a second plan. It preserves plan
ID and fingerprints and groups existing phases/actions for Servers, Services,
PKI, provider reconciles, and Verify. Each action shows targets, dependencies,
mutation/reboot/package-source classification, reason/summary, required
credentials, acknowledgements, and findings.

A plan can be executed only when its project, catalog, artifact, Core,
topology/configuration/runtime-projection, and relevant PKI fingerprints still
match. The UI submits `ExecutePlan { planId, planFingerprint,
projectRevision, acknowledgements }`. The backend selects and invokes existing
standalone playbooks and owns provider ordering, CLI construction, runtime
workspace, cancellation, and recovery.

The current repository publishes validation plus service-specific
apply/verify/reconcile entrypoints, but a complete generic public plan/apply
entrypoint remains incomplete. `PlanPreview` therefore describes the required
adapter boundary; it does not claim that every action is executable today.

## 13. ExecutionEvent and logs

Reuse `ExecutionEvent/v1alpha1`, `DeploymentResult/v1alpha1`, and their stable
run/plan IDs. The existing event carries sequence, timestamp, run, event type,
status, phase/action, host, deployment, task identity, elapsed time, safe
message/error, and redaction metadata. The frontend orders by sequence and
does not regex-parse callback output.

Persist by default:

- run started/completed and terminal result;
- phase/action started/completed;
- failed task events and structured findings;
- host/action recap outcomes and changed/failed state;
- cancellation, interruption, recovery, and diagnostic references.

Stream but do not retain indefinitely by default:

- successful `TASK_STARTED`/`TASK_COMPLETED` progress;
- repetitive skipped-task events;
- transient progress detail.

Raw stdout/stderr is a separate sanitized, bounded diagnostic artifact reached
through an explicit `diagnosticRef`. It is never embedded in
`ProjectSnapshot`, treated as a semantic event, or used by React to infer
status. Retention/export policy remains a UI-BE-04 owner decision.

## 14. Command side and EditPlan

The frontend sends one semantic intent, not a modified snapshot, raw YAML, or
an Ansible variable bag.

```yaml
apiVersion: platform.installer/edit-command/v1alpha1
kind: EditCommand
commandId: 01...
projectId: production-site
baseRevision: sha256:...
operation: UPDATE_SERVICE_CONFIGURATION
payload:
  deploymentId: postgres-main
  changes:
    - logicalPath: configuration.port
      value: 5433
```

Initial operation families are project/host, deployment/configuration,
placement, endpoint-group/assignment, integration intent, and PKI policy.
Concrete operation names are versioned only when implemented.

The backend returns an `EditPlan/v1alpha1`:

```yaml
editPlanId: 01...
baseRevision: sha256:...
expiresAt: ...
operation: UPDATE_SERVICE_CONFIGURATION
canonicalChanges: []
affectedDocuments:
  - documentId: installer-desired-state
    relativePath: inventory/group_vars/all/platform-installer.yml
    expectedDigest: sha256:...
    changeSummary: ...
findings: []
validation:
  status: PASS
applyImpact: REQUIRED | NOT_REQUIRED | UNKNOWN
committable: true
```

`CommitEditPlan { editPlanId, baseRevision, approvedDocumentDigests }` repeats
revision/precondition checks, stages only approved files, validates the staged
project, atomically replaces affected documents, reloads, validates again, and
returns the new revision and structured result. Rejection uses stable codes
such as `PROJECT_CHANGED`, `EDIT_CONFLICT`, `EDIT_UNSUPPORTED`, or
`VALIDATION_BLOCKED`.

The preview is mandatory for normal interactive edits because file placement,
opaque content, validation effects, and apply impact are material operator
information. A future automation API may offer a single call only as a server-
side composition of the same plan/commit checks.

## 15. Project revision and refresh

`projectRevision` is derived and is not written into desired state. The
backend builds it from a sorted manifest of every supported user-owned input
that can affect the project interpretation:

```text
relative POSIX path + NUL + file-kind + NUL + sha256(raw bytes)
```

The manifest includes supported static inventory sources, `group_vars`,
`host_vars`, `ansible.cfg`, and relevant optional `project.yml` metadata. It
excludes `.git`, `.runtime`, logs, secrets, temporary files, and machine-owned
generated-state content. Generated state, catalog locks, artifact locks, and
Core retain separate revisions/digests.

Paths are normalized and sorted; symlinks and unsupported dynamic inventory
must be rejected or explicitly treated read-only. Presence, deletion, and file
kind participate in the digest. Raw bytes are intentional: an external edit to
comments or formatting is still a concurrent human edit and must not be
silently overwritten.

Every edit plan additionally records the raw digest or absence marker for each
affected file. Commit requires both the same base project revision and matching
document preconditions. An external edit produces `PROJECT_CHANGED`; the UI
refreshes and asks the operator to recreate/review the edit plan. There is no
automatic last-write-wins merge.

Filesystem watching is an optimization. Correctness always comes from
recomputing the revision at query/plan/commit boundaries.

## 16. YAML writer and file ownership boundary

Whole-file parse/mutate/dump is not an acceptable production writer for
human-maintained YAML. It can reorder keys, change quoting, discard comments,
expand aliases, and overwrite opaque or unrelated values.

### Strategy comparison

| Strategy | Benefit | Risk | Decision |
| --- | --- | --- | --- |
| Round-trip edit arbitrary user YAML | edits existing operator layout directly | parser/library-specific loss of comments, anchors, styles, Jinja, vault tags, and unrelated structure; broad test surface | read-only by default; allow later only for explicitly supported/adopted subtrees |
| Installer-owned standard Ansible files | narrow ownership, deterministic serialization, predictable atomic replace and review | requires deliberate file layout and migration/adoption for existing projects | default write strategy |

Installer-owned does not mean a second desired-state model. These are ordinary
files naturally loaded by Ansible, for example a dedicated file under
`inventory/group_vars/all/` and dedicated host-variable documents in a layout
created or explicitly adopted by the Installer. Standalone `ansible-playbook`
continues to consume them directly.

UI-BE-03 must prove the exact inventory/host-vars layout before enabling
placement writes. Existing projects may use `host_vars/<host>.yml`, a
`host_vars/<host>/` directory, inline inventory vars, anchors, vault tags, or
dynamic inventory; the writer must not silently migrate among those forms.

### File policy

| Project content | Default policy |
| --- | --- |
| `ansible.cfg` | READ ONLY; validate required policy such as `hash_behaviour = merge` |
| Existing `inventory/hosts.yml` | READ ONLY until a supported inventory subtree is explicitly adopted |
| Existing human `group_vars/**/*.yml` | READ ONLY; exact-origin values may offer an override into an owned file |
| Existing human `host_vars/**/*.yml` | READ ONLY until exact document/subtree support and adoption |
| Installer-owned desired `group_vars` files | FULLY OWNED within declared schema; deterministic minimal document replacement |
| Installer-owned inventory/host-vars files | FULLY OWNED after UI-BE-03 proves natural Ansible loading and conflict rules |
| Service package role defaults/manifests/schemas | NEVER TOUCH from project editor |
| `platform_generated_state` / `platform-state.yml` | READ ONLY to UI; Core/service materializers only |
| `.runtime`, secrets, workspaces, logs | NEVER treat as desired state; backend lifecycle only |
| Unknown files, dynamic inventory, vault/Jinja/unsupported tagged nodes | READ ONLY |

For owned files, deterministic full-document serialization is acceptable
because ownership is explicit. For adopted human files, the writer must use a
round-trip-capable representation, touch only a typed subtree, preserve
unrelated nodes where reasonably possible, show a diff, and reject unsupported
constructs. Exact byte preservation is not promised, but destructive loss is
not acceptable.

## 17. Projects, servers, and secrets

Project operations are `CreateProject`, `OpenProject`, `RefreshProject`,
`ValidateProject`, and later explicit import/adopt/template operations.
Recent-project paths, window state, and UI preferences may be local metadata;
they are not portable desired state.

`ServerView/v1alpha1` composes canonical inventory identity, `ansible_host`,
transport references, and `platform_deployments` summary with separately
timestamped OS/architecture/CPU/memory, SSH host-key, reachability, elevation,
preparation, and compatibility observations. Current V2 has canonical host and
execution selection plus validation/resolution foundations, but no complete
generic discovery API; detailed observations are a UI-BE-02/04 integration
gap, not a reason to copy the V1 host domain.

Secret commands accept or create a `SecretReference` and may report only
availability and expiry. A secret value is write-only to the runtime broker,
never returned to a form, persisted in the project, included in an edit plan,
or embedded in logs/events.

## 18. V1 audit: reuse and reject

V1 is evidence for behavior only.

Reuse as requirements:

- project create/open/list navigation and active-project restoration;
- separate Servers, Installation, Logs, Settings, Help, and About areas;
- host discovery summaries and explicit SSH host-key trust with changed-key
  blocking;
- preparation/readiness workflow separate from service placement;
- active-run navigation safety, precise cancellation, and interrupted-run
  reconciliation;
- structured progress plus separately available sanitized output;
- immutable run/audit history, offline help links, and safe localized errors;
- runtime-only credential session and secret redaction.

Reject:

- `domain.PlatformProject/PlatformConfig` as a canonical desired-state model;
- SQLite `projects.config_json` and `ProjectDTO.Config` round trips;
- `SaveProject(ProjectDTO)` whole-object mutation without a base revision;
- Go/TypeScript/Ansible copies of service modes, defaults, topology, endpoint,
  or PKI rules;
- a Wails method or event channel for every button/workflow detail;
- frontend service-type conditionals as ordinary settings semantics;
- raw callback/stdout parsing as the UI status protocol;
- runtime/discovered roles being written back into desired configuration.

## 19. Screen-to-contract matrix

| Screen | Query contracts | Command contracts | Runtime events | Write requirement |
| --- | --- | --- | --- | --- |
| Projects | project index, `ProjectSnapshot` health | create/open/refresh/import-adopt later | optional import progress | owned project skeleton; no SQLite desired state |
| Servers | snapshot host summaries, `ServerView`, observations | host/transport edit plan; preparation command later | discovery/preparation events | inventory/host-var writer required for edits |
| Topology | `TopologyView`, `PlacementCapabilities`, `EndpointView`, `IntegrationView` | deployment, placement, endpoint-group/assignment, integration edit commands | optional validation refresh | desired-state plus inventory writer |
| Service settings | `ServiceCatalogView`, `ServiceSettingsView` | configuration edit command | none for editing | owned/bound group/host-vars writer |
| Installation / Summary | snapshot validation/readiness summaries | validate, request plan | validation/refresh progress | no project write |
| Installation / Preparation | execution environment and server readiness | prepare/cancel | preparation events | local operational state only |
| Installation / Services | plan/service summaries | request plan, execute confirmed plan | execution events | no direct desired-state write |
| Installation / Certificates | `PkiSummaryView`, secret availability | PKI policy edit plan; materialize/reissue/verify commands | execution events | PKI policy writer; runtime secrets remain write-only |
| Installation / Execution | `PlanPreview`, active run/result | execute/cancel/retry where contract permits | `ExecutionEvent/v1alpha1` | no project write |
| Logs | run index, persisted semantic events/results, diagnostic refs | retention/export/delete according to future policy | live events only for active run | operational store only |
| Settings | application preferences, environment bindings | update local settings | none | never portable desired state |
| Help/About | help metadata, build/Core/catalog diagnostics | open/copy/export diagnostics | none | read-only |

The UI-DESIGN-01 navigation remains valid. Its outdated assumption is timing:
production UI-01 cannot safely combine open/read, writer, and execution work in
one first implementation. Those backend capabilities are now separate gates.

## 20. Gaps and blockers

Before a write-capable production UI:

1. Publish and test the read-model adapter and exact source-document inventory
   without target contact.
2. Correct stale `Finding` endpoint subject terminology.
3. Add only consumed service-manifest presentation and placement-property
   metadata gaps.
4. Define supported static inventory/YAML subset, owned file names, directory
   form, adoption rules, round-trip library/implementation, backup/recovery,
   and atomic multi-file behavior.
5. Prove staged Core validation against the exact proposed files and preserve
   opaque variables/Jinja/vault/anchors or reject them safely.
6. Publish complete generic plan/apply invocation mapping over existing
   standalone entrypoints; the backend must not invent service order.
7. Define host discovery/observation adapters and freshness semantics.
8. Define run-history retention/export, event compaction, log bounds, and
   interrupted-run recovery.
9. Define secure SecretBroker lifetime and optional OS credential-store policy
   without exposing values.
10. Prohibit deployment-ID rename initially; a rename requires a separate
    cross-file transactional migration contract.

No target-host acceptance is required for this architecture document. These
are explicit future exit criteria, not implied implementation.

## 21. Milestone sequence

### UI-BE-02 — Read-only ProjectSnapshot

- implement project open/refresh and `projectRevision`;
- adapt catalog, validation, topology, effective configuration, endpoints,
  integrations, PKI summary, and compact readiness without target contact;
- publish query contracts and deterministic serialization tests;
- correct only the contract/manifest gaps consumed by the read models.

### UI-BE-03 — Safe Ansible-native writer

- define and create Installer-owned standard Ansible documents;
- implement semantic command, `EditPlan`, preview/diff, adoption policy,
  staged validation, optimistic concurrency, atomic commit, and recovery;
- begin with a small literal deployment-setting subset, then placement and
  endpoint edits only after their file layouts are proven;
- preserve standalone Ansible execution and opaque operator data.

### UI-BE-04 — Validate, plan, execute, and events

- expose target-free validation and readiness;
- implement immutable plan preview over Core plans/entrypoints;
- invoke existing standard playbooks through the execution-node boundary;
- stream/persist normalized events, results, sanitized diagnostics,
  cancellation, and interrupted-run recovery;
- add observation refresh and SecretBroker integration.

### UI-01 — Production UI

Build the Wails/React product only on the accepted UI-BE-02/03/04 contracts.
The frontend remains schema/catalog-driven and contains no second desired-state
model or service rule engine.

## 22. Contract artifact decision

UI-BE-01 adds no JSON Schemas or Go/TypeScript prototypes. Existing published
`Finding`, `ValidationResult`, `DeploymentPlan`, `ExecutionEvent`,
`DeploymentResult`, `ResolvedServiceConfiguration`,
`ResolvedServiceEndpoint`, `ServiceManifest`, and `ServiceCatalog` contracts
already provide the semantic foundation. Adding speculative schemas for every
view and command now would duplicate incomplete implementation decisions.

UI-BE-02 should publish the minimal query schemas it actually serializes;
UI-BE-03 should publish edit command/plan/result schemas when the write subset
and file ownership are proven; UI-BE-04 should reuse and minimally evolve the
existing plan/event/result contracts.

## 23. UI-BE-01 acceptance

UI-BE-01 is complete when this document is reviewed against the existing Core,
service manifest, UI-DESIGN-01, and V1 evidence; no production code or schema
is needed. The accepted boundary is:

```text
same Ansible project
  -> Core-owned validation/resolution/execution semantics
  -> backend-owned versioned read models, edit plans, concurrency, execution,
     observations, secrets, and history
  -> frontend-owned presentation and drafts
```

UI-BE-02 does not start automatically.
