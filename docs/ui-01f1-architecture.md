# UI-01F1 — Lock-bound catalog and local managed read model

Status: **IMPLEMENTED**

Milestone: **UI-01F1**

Implementation status: **DONE**

Parent architecture: `docs/ui-01f-architecture.md`

Baseline revision: `6c52693af09fde94a18b9e0be94f37b49e505505`

## 1. Goal

UI-01F1 provides the two read-only inputs required by later UI-01F slices:

1. a bounded service/mode/placement capability projection from the exact
   verified local catalog pinned by the open project;
2. a local projection of directly Installer-owned deployments, endpoint
   groups and both canonical placement forms.

The result is available when opening either an empty managed project or an
Installer-managed saved project without contacting Core, an Execution Node or
target hosts. F1 does not expose topology mutations or enable the Topology page.

## 2. Scope

F1 includes:

- project-lock-to-local-bundle resolution through existing trusted bundle
  roots;
- bounded catalog decoding and `ProjectCatalogView`;
- expansion of the existing `ManagedProjectView` read path;
- inclusion of those projections in the existing `ProjectOpenResult` and
  `CurrentProject` state;
- safe unavailable/incompatible diagnostics;
- Go, Wails binding and focused frontend contract tests for the read model.

F1 explicitly excludes:

- `project-edit/v1alpha5` and every edit command;
- reducers, candidate construction, managed writes and Save changes;
- Topology page navigation or Add/Edit/Delete controls;
- catalog migration, acquisition, download, lock update or bundle publication;
- local Core/Ansible execution or precedence resolution;
- service settings, PKI editing and provider/VIP editing;
- Project Verify, DeploymentPlan or execution changes;
- a new cache, database, watcher or background refresh lifecycle.

## 3. Mockup and contract reconciliation

The F1 design was compared with `docs/ui-design-01-mockups.html`,
`docs/ui-design-01.md` and the approved common UI-01F plan.

- The mockup's service names, modes, roles and counts are examples. F1 obtains
  them from the project-pinned catalog and does not hardcode them.
- The future Topology views need both logical-member and direct host-scoped
  placement. F1 preserves those canonical forms separately.
- Entry-point provider/VIP values remain Core-derived and are not added to the
  local managed projection.
- F1 changes no navigation. The Topology page becomes interactive only in F3
  through F5.
- The existing App Shell Save/Verify and Execution Node behavior remains
  unchanged.

No material mockup discrepancy remains inside F1 scope.

## 4. Existing integration seams

| Concern | Existing owner/seam | F1 extension |
| --- | --- | --- |
| Trusted local bundle roots | `projectlifecycle.Service.sources` populated by desktop startup | Resolve an exact source for an already-open project's locks |
| Bundle integrity | `executionbundle.ValidateRoot` | Reuse before every catalog projection |
| Project lock parsing | `projectlifecycle.readManifest` | Compare artifact/catalog/service locks with the verified source |
| Catalog parsing | private `projectlifecycle.readCatalog` | Decode the bounded F1 view and validate every consumed field |
| Local owned read | `installer.ReadManagedProjectView` and `loadOwnedDocument` | Read desired deployments/groups and owned host placement files |
| Desktop state | `ProjectOpenResult.Managed` and `App.current` | Add catalog state and expanded managed fields |
| Wails transport | existing bound `App` and generated models | Carry the added typed fields; no new transport protocol |

The implementation must not create a generic catalog repository package or a
second project reader. The current lifecycle service already has the required
trusted source roots and project-lock context; the current Installer reader
already has owned-path and managed-header enforcement.

## 5. Read architecture

```text
Installer-controlled bundle roots
              │
              v
    executionbundle.ValidateRoot
              │
              +---- bundle manifest digest/catalog digest
              │
project.yml --+---- artifactLock/catalogLock/service locks
              │
              v
     exact lock-bound source match
              │
              v
      bounded ProjectCatalogView

Installer-owned inventory/group_vars/host_vars
              │
              v
 safe path + managed header + bounded YAML read
              │
              v
       expanded ManagedProjectView

ProjectCatalogView + ManagedProjectView
              │
              v
 existing ProjectOpenResult / CurrentProject / Wails binding
```

Neither branch writes files. The two projections are independent: a missing
catalog does not erase locally readable desired fields, and a malformed owned
document does not make another catalog version authoritative.

## 6. Exact catalog source resolution

### 6.1 Authority

`projectlifecycle.Service` remains the authority for Installer-controlled local
compatibility sources. F1 adds one read-only operation conceptually equivalent
to:

```text
ResolveProjectCatalog(projectRoot) -> ProjectCatalogView
```

The caller supplies the already-open project root, not a bundle path, source
ID, catalog path or digest. The service safely rereads `project.yml` and
revalidates configured source roots on each resolution. A cached
`ProjectCatalogView` in `App.current` is presentation state only and is never
trusted later as mutation authorization; F2 must call the same resolver again
when admitting catalog-backed commands.

### 6.2 Match invariants

A source is eligible only when all of the following are true:

1. `executionbundle.ValidateRoot` succeeds;
2. the verified manifest digest equals `project.yml.artifactLock.digest`;
3. the verified manifest catalog digest equals
   `project.yml.catalogLock.digest`;
4. the catalog root digest equals that same catalog digest;
5. catalog definition IDs exactly match `catalogLock.services` IDs;
6. each definition's metadata ID, definition version and
   `x-definitionDigest` equal its corresponding service lock.

Source IDs are creation-time opaque handles and are not reconstructed from a
reopened project. Resolution is by immutable lock identity. Configured source
IDs are sorted before inspection so behavior is deterministic. Every configured
root that declares the exact locked artifact/catalog identity is an exact-source
candidate. All exact-source candidates are considered until one verifies; a
corrupted duplicate does not block another healthy exact copy. Multiple healthy
roots with the same verified bundle digest are semantically equivalent, and the
first by stable source ID supplies the bytes. A different digest is never used
as a fallback.

Resolution status is closed:

- at least one exact-source candidate passes full root and component
  verification -> `READY`;
- at least one source declares the exact locked identity but no exact-source
  candidate verifies -> `INCOMPATIBLE`;
- no configured source declares the exact locked identity -> `UNAVAILABLE`.

Candidate identity inspection remains bounded and safe; malformed or unreadable
metadata cannot manufacture an exact match. Failure details from a corrupted
duplicate are retained only as redacted diagnostics and do not override a
healthy exact copy.

The current desktop may expose only one verified current bundle. Therefore an
older project whose exact bundle was pruned legitimately receives catalog
status `UNAVAILABLE`; F1 does not search arbitrary filesystem locations or
download a replacement.

### 6.3 Catalog read safety

The catalog file must be the verified bundle component at the fixed relative
path `catalog/service-catalog.yml`. It is never taken from the project.
`ValidateRoot` alone is not the byte-to-decode authority because reopening the
component after validation would create a check/read race.

F1 adds one narrow `executionbundle.ReadVerifiedComponent` helper. It receives
the `Verified` value returned by a fresh `ValidateRoot`, including the opaque
root-object identity observed by that validation, the fixed component path and
an 8 MiB catalog limit. It:

- finds exactly one matching component entry in the already validated
  manifest;
- opens the bundle root and fixed component through a platform-specific,
  component-by-component handle-relative flow that does not follow links;
- proves that the opened root is the same root object recorded by the fresh
  validation and rejects a symlink/reparse root, every opened intermediate
  object and the final object;
- verifies on the opened final handle that the object is a regular file;
- reads from that same final handle, bounds the read to the lower of the
  declared component size and 8 MiB, and rejects size drift;
- computes SHA-256 over the returned byte slice and compares it with the fixed
  component entry;
- returns only those verified bytes.

The platform implementations are explicit and private to this helper:

- POSIX opens the root directory with no-follow/directory semantics, compares
  its `dev`/`ino` identity with the identity captured by `ValidateRoot`, then
  walks `catalog` and `service-catalog.yml` with descriptor-relative `openat`
  calls using no-follow semantics. `fstat` on each opened descriptor rejects
  non-directory intermediates, and `fstat` on the final descriptor requires a
  regular file. The final bytes are read only from that descriptor.
- Windows opens the root directory handle without traversing a reparse point,
  compares its volume/file identity with the identity captured by
  `ValidateRoot`, and uses component-by-component handle-relative native opens
  with open-reparse-point semantics. Handle metadata rejects every reparse-tag
  object, requires directory intermediates and a non-directory regular final
  file, and proves each child remains under the anchored root handle. The final
  bytes are read only from that final handle.

Neither implementation performs a path check followed by an unbound later
`Open(path)`. A pathname replacement before or during the operation either
changes the bound root/object identity and is rejected or cannot change the
already opened object whose bytes are read. These small OS-specific files are
an implementation detail of `ReadVerifiedComponent`, not a generic secure
filesystem framework.

The catalog decoder receives that returned byte slice directly. It never
reopens the path. Therefore the bytes read from the proved opened regular-file
object, bounded by size and matched by SHA-256, are the same bytes that become
`ProjectCatalogView`. Catalog projection may be `READY` only after opened-object
safety, size and digest checks all pass. This helper is bundle-component-
specific and is not a generic repository/filesystem framework.

After the byte binding, the reader:

- decodes only the catalog and manifest fields consumed by F1;
- validates required types, identifier grammar, collection bounds and
  duplicate-free role lists;
- ignores unrelated valid manifest content instead of projecting settings,
  role entrypoints, artifacts or runtime requirements into React;
- accepts allowed versioned extension fields without assigning them F1
  semantics;
- never resolves catalog `$ref` values or opens service paths while building
  the F1 projection.

Exceeding 8 MiB returns a safe unavailable/incompatible result, not a partial
projection. The generated catalog is checked against this limit in
reproducibility QA.

## 7. ProjectCatalogView

F1 introduces one bounded application projection; it is not portable desired
state and is not a second service catalog contract.

```text
ProjectCatalogView
  status: READY | UNAVAILABLE | INCOMPATIBLE
  expectedBundleDigest
  expectedCatalogDigest
  bundleVersion?                 # READY only
  services[]                     # READY only, stable order
  error?                         # fixed safe code/message

ProjectCatalogService
  id
  definitionVersion
  displayName
  description?
  category?
  ui: { icon?, order?, documentationTopic? }
  endpointConsumer: bool
  endpointProvider: bool
  modes[]

ProjectCatalogMode
  id
  displayName
  description?
  placementKind: MEMBER_SCOPED | HOST_SCOPED
  roles[]
  guidance:
    minParticipants
    maxParticipants?
    distinctHosts
    roleCardinality?             # display guidance only
```

`placementKind` is the service-agnostic UI capability required by the common
plan: `placement.hostScoped=true` maps to `HOST_SCOPED`; absent/false maps to
`MEMBER_SCOPED`. No service ID appears in this mapping.

Services and modes use deterministic presentation ordering: declared UI order
first, then display name and stable ID. Roles are emitted in manifest order.
Ordering is presentation metadata, never topology semantics or fingerprint
input.

`minParticipants`, `maxParticipants`, `distinctHosts` and role cardinality are
guidance for later forms. They do not authorize Save and do not replace Core
validation.

### 7.1 Availability behavior

- `READY`: exact source and every consumed field passed validation.
- `UNAVAILABLE`: no configured verified source has the project's exact bundle
  identity.
- `INCOMPATIBLE`: the exact candidate source exists but its catalog/lock
  envelope or consumed catalog fields are invalid/mismatched.

Open/Create remains successful for a valid managed project when catalog status
is not READY. The safe status is returned alongside direct local project data;
later catalog-dependent mutations remain disabled. No raw parser error, local
path or catalog content is returned to React.

## 8. Expanded ManagedProjectView

The existing `ManagedProjectView` remains the sole local Installer-owned
projection. F1 extends it rather than introducing a parallel topology snapshot:

```text
ManagedProjectView
  projectRevision
  servers{}                     # existing E1 fields unchanged
  deployments{}
  endpointGroups{}
  memberPlacements[]
  hostPlacements[]

ManagedDeployment
  deploymentId
  serviceType
  mode
  endpointGroup?                # direct consumer assignment only

ManagedEndpointGroup
  endpointGroupId
  domain
  wildcard

ManagedMemberPlacement
  deploymentId
  memberId
  hostId
  roles[]

ManagedHostPlacement
  deploymentId
  hostId
  roles[]?                      # absent/empty is preserved as roleless
```

Separate placement arrays describe observed canonical syntax; they do not use
catalog rules to reinterpret it. An entry containing `members` contributes
member placements. A direct `platform_deployments.<deploymentId>` entry
without `members` contributes one host placement. F1 never invents member IDs.
If one owned placement entry structurally expresses both the member-scoped
`members` form and direct host-scoped fields, the managed read fails closed.
Neither service identity nor catalog `placementKind` is used to guess which
form the author intended.

### 8.1 Exact local sources

The reader consumes only:

- `inventory/hosts.yml` with the Installer managed header for existing server
  fields;
- `inventory/group_vars/all/platform-installer.yml` with the managed header,
  limited to `platform_desired_state.serviceDeployments` and
  `platform_desired_state.endpointGroups`;
- managed `inventory/host_vars/<hostId>/platform-installer.yml`, limited to
  `platform_deployments` and the two structural placement forms.

The existing safe-root, path-containment, symlink/reparse and managed-header
checks remain mandatory. F1 does not read similarly named unowned files,
general group_vars, generated `platform-state.yml`, role defaults, inventory
groups or inline `project.yml.desiredState`.

### 8.2 Projection behavior

- Each Installer-owned inventory/group_vars/host_vars document is limited to
  4 MiB and all documents read for one managed projection are limited to
  64 MiB total, matching the existing candidate archive safety envelope.
- One projection accepts at most 4,096 owned host documents, 4,096 servers,
  4,096 deployments, 4,096 endpoint groups and 16,384 combined member/host
  placement records. Each placement accepts at most 128 roles. Limits are
  checked while accumulating, before returning any partial projection.
- Known fields must have bounded expected types; malformed known roots,
  identifiers or exceeded limits return the existing safe managed-document
  error class.
- Unknown fields, configurations and extension data are ignored by the view
  and remain untouched because F1 never writes.
- Provider `endpointGroupRef`, `virtualRouterId` and `virtualAddresses` are not
  exposed locally in F; they remain fresh-Core-only read-only data.
- The reader does not validate service/mode/role compatibility, cardinality,
  distinct-host policy, dangling references or endpoint semantics.
- Stable maps/slices and role lists are copied before returning so callers
  cannot mutate internal parsed state.
- `projectRevision` is computed through the existing raw-byte revision path.

For `EMPTY_MANAGED_PROJECT`, existing metadata-only open semantics remain: no
inventory or variable file is fabricated or required. The catalog view can be
READY while `ManagedProjectView` remains absent and counts remain zero.

For `MANAGED_PROJECT`, deployment count comes from the direct local deployment
map. It is not taken from stale Core evidence.

## 9. App and Wails integration

`ProjectOpenResult` gains one optional `Catalog` field using
`ProjectCatalogView`; its existing `Managed` field carries the expanded view.
No standalone `GetCatalog` polling API is added in F1.

On successful Create/Open:

1. compute `R0`, the existing canonical raw-byte `projectRevision`, before
   consuming project metadata or managed documents;
2. perform the whole local lifecycle classification, read `project.yml` and its
   locks, resolve READY/UNAVAILABLE/INCOMPATIBLE catalog state, and build the
   expanded managed view without remote calls;
3. compute `R1` through the same canonical raw-byte revision function after all
   reads;
4. accept the observation only when `R0 == R1` and, for a managed project,
   `ManagedProjectView.projectRevision == R0`;
5. only after acceptance, store copies in `App.current`; `ProjectOpenResult`,
   `CurrentProject` and generated Wails bindings expose that same observation.

If either equality fails, the entire observation is discarded and the whole
Open attempt restarts once from step 1. Catalog resolution or managed projection
is never retried independently. A second mismatch returns the existing safe
`PROJECT_CHANGED` (or its already established equivalent) result and publishes
no mixed or partial current state. Thus each `ProjectOpenResult` corresponds to
one coherent canonical revision.

Catalog unavailability adds a safe application diagnostic but does not convert
a valid project open into `Status=ERROR`. A malformed required Installer-owned
document retains the existing fail-closed open behavior.

The frontend adapter receives generated Go/Wails types. It must not maintain a
handwritten second catalog model beyond the narrow TypeScript interface needed
for test doubles; any such interface must remain structurally identical and be
covered by compilation/tests.

F1 does not render the Topology page. Existing Project page counts may use the
expanded deployment count, but no new service editor or topology action is
enabled.

## 10. Error, freshness and concurrency semantics

- Catalog resolution is synchronous, bounded and read-only under the existing
  project-open operation; no goroutine, watcher or mutable catalog cache is
  introduced.
- One Open observation is explicitly bracketed by canonical raw-byte revisions
  `R0` and `R1`. Project metadata/locks, catalog resolution and managed files
  are accepted together only when `R0 == R1` and the managed view revision is
  `R0`; otherwise the entire Open is discarded and retried once. A second
  change returns `PROJECT_CHANGED`/the existing equivalent.
- The bundle is revalidated before its catalog is read. The fixed component is
  then opened through `ReadVerifiedComponent`; only bytes read from the same
  proved regular-file handle whose size and SHA-256 match its manifest entry
  are decoded. Root/object identity drift, root/ancestor/file symlink/reparse,
  same-size replacement and digest mismatch prevent READY.
- Catalog projection is bound to expected bundle/catalog digests in the result.
- Managed projection is bound to `projectRevision`.
- No source path, YAML body, parser stack, runtime credential or secret-like
  value reaches diagnostics.
- Close clears only in-memory current project projections; there is no durable
  catalog state to clean up.

## 11. Implementation sequence

1. Add narrow `executionbundle.ReadVerifiedComponent`, including the
   platform-specific handle-relative root/object identity, regular-file,
   reparse/no-follow, same-handle read and exact-byte digest binding.
2. Extend private catalog decode structures and add lock-bound read operation
   to `projectlifecycle.Service` using the verified component bytes.
3. Add the bounded `ProjectCatalogView` types and deterministic projection.
4. Extend `ManagedProjectView` and `ReadManagedProjectView` with exact desired
   and host-placement readers plus the fixed per-document/aggregate limits.
5. Attach both projections to one `R0`/`R1`-bracketed Open observation, with
   whole-Open one-time retry, without changing remote Verify behavior.
6. Regenerate Wails bindings and update only affected frontend adapter/test
   models; do not add Topology interaction.
7. Run the focused F1 gates in section 12 and update F1 evidence. Do not begin
   F2 without a separate owner instruction.

## 12. QA plan

### 12.1 Required positive scenarios

- create metadata-only project from an exact verified bundle returns READY
  catalog and zero managed counts without creating inventory;
- reopen that empty project resolves the catalog by locks without relying on a
  persisted source ID;
- duplicate exact roots with one corrupted and one healthy copy return READY
  from the healthy copy; exact identity with no verified copy is INCOMPATIBLE;
  complete absence of exact identity is UNAVAILABLE;
- reopen a managed representative fixture returns servers, deployments,
  endpoint groups, Kafka/PostgreSQL member placements and BIND/
  Keepalived/dns-client/HAProxy host placements;
- roleless host-scoped placement remains roleless and no member ID appears;
- catalog mode projection emits correct placement kind for both forms;
- multiple services/modes have deterministic presentation order;
- Create/Open/current result uses zero Core, Execution Node and target calls;
- all project and bundle file digests are unchanged before and after reads.

### 12.2 Negative and boundary scenarios

- exact project bundle absent after cache replacement -> UNAVAILABLE while
  project open/direct managed data remain available;
- bundle manifest, catalog component or component digest changed -> not READY;
- root, intermediate or final-path replacement between initial `ValidateRoot`
  and component open, including same-size changed bytes, is rejected by opened-
  object identity/no-follow checks or exact-byte component verification;
- replacement after the final file object is opened cannot change the bytes
  read and decoded from that same handle;
- artifact lock, catalog lock, service set, definition version or definition
  digest mismatch -> INCOMPATIBLE;
- malformed consumed mode, role, placement or endpoint-group field;
- catalog over 8 MiB rejected before decode;
- duplicate/invalid identifiers and duplicate role entries;
- symlink/junction/reparse at bundle root, `catalog` ancestor, catalog file or
  managed project path;
- missing managed header, malformed desired root or malformed placement root;
- one owned placement entry expressing both member-scoped and host-scoped forms
  fails closed without catalog/service-based guessing;
- canonical revision changes during Open discard every projection and retry the
  whole Open once; a second change returns `PROJECT_CHANGED`/existing equivalent
  with no `App.current` update;
- owned document over 4 MiB, aggregate over 64 MiB, or collection/role count
  above the fixed limits returns one safe error and no partial projection;
- unknown configuration/extension fields are not exposed and do not cause
  local semantic interpretation;
- provider/VIP fields never appear in local managed view;
- no arbitrary directory search, network access or bundle fallback occurs.

### 12.3 Contract and regression scenarios

- `ServiceCatalog/v1alpha1`, service manifest and project lock fixtures remain
  reproducible and unchanged;
- existing metadata-only Create/Open behavior and first-save eligibility;
- existing server-only `ManagedProjectView` callers and E1–E6 tests;
- existing Project Verify snapshot and freshness behavior;
- generated Wails bindings and frontend TypeScript compilation;
- Project page counts for empty and managed projects;
- no project-edit contract or production Ansible file changes.

### 12.4 Required commands/environments

- focused Go tests for `internal/projectlifecycle`, `internal/installer` and the
  root Wails app;
- affected `go test -race` packages on RED OS when the platform/build allows;
- frontend test/lint/build when bindings or adapter types change;
- `wails build -nopackage -clean` because the bound result types change;
- catalog/schema reproducibility checks;
- secret-safe targeted audit and `git diff --check`.

Because F1 adds an exact-byte helper at the artifact/bundle trust boundary, its
implementation requires the repository's HIGH-RISK FULL DIFF architecture
review in addition to ordinary safety and QA gates.

No remote Core, target SSH, service apply/verify or deployment execution is
required. Windows is required for Wails build/binding and reparse-focused
regression; RED OS is required only for affected Go race portability evidence.

## 13. Overengineering check

Required mechanisms:

- one bounded catalog projection, because exposing the full service manifest
  would leak future H/runtime fields and invite React semantics;
- expansion of the existing managed view, because no-node reopen cannot use a
  Core snapshot;
- exact source matching, because using the current unrelated bundle would
  violate project lock identity.

Rejected mechanisms:

- catalog database, filesystem index, watcher, refresh daemon or persistence;
- generic repository/resolver framework beyond the existing lifecycle service;
- new remote protocol or Execution Node catalog call;
- full JSON Schema engine or Ansible loader in Go;
- raw catalog/YAML maps returned to React;
- second local topology snapshot or duplicate Server DTO;
- speculative mutation eligibility engine in F1;
- service-specific placement branches.

The simpler existing mechanisms are sufficient: validate configured bundle
roots, compare immutable locks, decode only consumed catalog fields, and extend
the existing owned-document reader. Existing path and integrity protections
are retained because they are safety requirements, not accidental complexity.

## 14. F1 DONE criteria

UI-01F1 is DONE only when:

1. an open project receives a deterministic catalog status bound to its exact
   artifact/catalog/service locks without remote calls;
2. READY exposes only the bounded catalog fields required by F and maps
   placement kind without service-specific branches;
3. an unavailable or incompatible catalog does not mutate or hide valid direct
   managed state;
4. managed reopen projects deployments, consumer endpoint groups and both
   canonical placement forms without Ansible precedence or derived semantics;
5. metadata-only project creation remains one-file-only;
6. production project/bundle digests remain unchanged by all F1 operations;
7. catalog bytes decoded by F1 come from the same safely opened regular-file
   object verified against the fixed manifest component, with platform-specific
   root/object identity and root/ancestor/file reparse rejection;
8. managed reads enforce the documented per-document, aggregate and collection
   limits without partial projection;
9. focused Go/frontend/Wails/reproducibility/safety gates and required FULL
   DIFF review pass;
10. every accepted `ProjectOpenResult` binds locks, catalog and managed view to
    one `R0 == R1` canonical revision, with whole-Open retry only;
11. architecture review has zero blocking findings, evidence is documented, one
   focused implementation commit exists and the worktree is clean.

F2 and all topology mutation remain NOT STARTED at F1 completion.

## 15. Implementation evidence

UI-01F1 was implemented against the approved plan baseline `9dd719b`.
`UI01F1-DIFF-001` and `UI01F1-DIFF-003` passed targeted review. The owner
authorized the final bounded correction for `UI01F1-DIFF-002`: the published
`genericEndpoint` marker is accepted only when absent or exactly `{}`; scalar,
sequence and nonempty-object forms fail with the existing safe catalog error.
No further architecture-review cycle was run or required for that exact
contract-compliance correction.

Focused Go tests, `go test ./...`, `go vet ./...`, RED OS catalog
reproducibility and `git diff --check` passed. F2 remains **NOT STARTED**.
