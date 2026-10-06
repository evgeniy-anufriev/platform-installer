# UI-01A — frozen UI contracts and ownership

Status: ACCEPTED by UI-01A, 2026-09-05. This is an architecture contract, not
an implementation. Normative words MUST, MUST NOT and MAY constrain UI-01B+.

> **Normative owner supersession, 2026-09-15:** ADR-027 and
> [Save / Project Verify / DeploymentPlan](ui-save-verify-architecture.md)
> replace only the Core-before-Save and READY-before-Save requirements in this
> freeze. Typed commands, canonical ownership and transaction safety remain.
> New Save is local structural persistence; Project Verify is optional; fresh
> BuildDeploymentPlan remains mandatory before execution.

## 1. Screen / contract matrix

`AVAILABLE` means implemented in the current repository. `PLANNED` means an
accepted gap with an owning milestone. A document that merely describes a
future method does not make it available.

| Screen / action | Read source | Command API | Canonical owner | Derived state / validation | Save | Current implementation / gap |
| --- | --- | --- | --- | --- | --- | --- |
| Projects / create | Verified local bundle metadata; native folder picker | `CreateProject` application operation | `project.yml` owns identity and locks | Go validates request/path; contract validation validates manifest | Atomic publication of one file | PLANNED UI-01C; no method exists |
| Projects / open empty managed | Local structural classifier and `project.yml` metadata | `OpenProject` | Same file; recent list is operational only | No Core result is invented | Read-only | PLANNED UI-01B/C |
| Projects / open configured | Local classifier, then existing `ProjectSnapshot/v1alpha1` | `OpenProject`, `RefreshProject` | Native Ansible files | Core owns interpretation/findings | No write | Snapshot AVAILABLE; application methods and remote adapter PLANNED UI-01B/D |
| Servers / list | `ProjectSnapshot.hosts` | none | Inventory | Facts/readiness are separate observations | none | Read AVAILABLE; view composition PLANNED UI-01B/E |
| Servers / add-edit-remove | Saved/local managed view plus transient edit session | `CreateServer`, `UpdateServer`, `DeleteServer` | Installer-owned inventory for managed projects | Go validates structural safety; optional Verify/Core validates saved revision | Local structural review/commit | Commands and inventory writer PLANNED UI-01D/E |
| Session credentials | Secret broker availability only | `SetSessionCredential`, `ClearSessionCredential` | Runtime-only memory/provider | Go validates type/lifetime; never Core desired state | Never project save | PLANNED UI-01E |
| Topology / catalog | `ProjectSnapshot.serviceCatalog`, deployments, topology | Existing deployment commands | Service manifests own modes/rules; managed group_vars owns selected deployment | Core resolves and validates | Shared review/commit | Read and create/delete deployment AVAILABLE |
| Topology / members and placement | Snapshot topology/hosts | Existing placement commands; planned `ReconcileDeploymentPlacement` | Managed host_vars | Core validates roles/cardinality/references | Shared review/commit | Point operations AVAILABLE; whole-deployment reconcile PLANNED UI-01F |
| Topology / endpoint and HAProxy links | Snapshot endpoints/integrations | Existing endpoint-group and HAProxy operations | Managed group_vars | Core owns endpoint/provider/integration semantics | Shared review/commit | AVAILABLE for supported relations; no generic arbitrary dependency API |
| Certificates / desired profiles | Snapshot PKI plus desired origins | PKI CRUD commands in section 5 | Managed group_vars | Core validates references and derives consumers/SAN | Shared review/commit | Read AVAILABLE; commands PLANNED UI-01G |
| Certificates / material state | Runtime observation only | none in UI-01 | Execution Node generated/runtime state | PKI apply/verify owns result | Never editor save | UI-02; must not appear as desired-state PASS |
| Services / list | Snapshot deployments/catalog/effective configuration | Existing deployment/config commands | Managed group_vars | Catalog declares settings; Core validates/evaluates origin | Shared review/commit | AVAILABLE after common session is added |
| Services / PKI reference | Snapshot effective configuration and PKI identities | Existing `SetServiceConfigurationValue` / remove override for catalog-declared `tlsProfile` | Managed group_vars/host_vars according to allowed scope | Core validates profile existence/compatibility | Shared review/commit | AVAILABLE when service manifest exposes setting; UI PLANNED UI-01H |
| Settings / UI preferences | Local operational preferences | bounded preference update | Application-local store | Go only | Local atomic preference save | PLANNED; never portable desired state |
| Settings / validation binding | Stored node ID and non-secret transport references | select/clear binding | Application operational metadata | Inspection result is observed state | Local only | Node primitives AVAILABLE; editor binding service PLANNED UI-01B/D |
| Review/save | Saved/local managed view and transient session | Local structural preview, guarded commit/discard | Native Ansible files | Go proves structural/write safety; Core is optional Verify and mandatory fresh plan | One guarded transaction | ADR-027 target; old Core-backed PlanEdit remains compatibility history |
| Installation / plan | Existing `DeploymentPlan` | build/approve in UI-02 | Plan is derived and revision-bound | Core owns plan/manifest | No project write | Backend AVAILABLE; UI-02 |
| Installation / progress | `GetExecution`, typed RunObserver subscription | cancel only through lifecycle contract | Remote journal is observed authority | Execution lifecycle | No project write | Backend AVAILABLE; UI-02 |
| Installation / result | terminal run/result and per-action events | no verify-on-view | Observed result | Service verify entrypoint | No project write | Backend data AVAILABLE; UI-02 composition |
| Logs/history | Run index plus typed events/results | retention/export later | Operational state only | No desired-state inference | No project write | Partly AVAILABLE; UI-02 |

React receives generated Wails bindings over these application operations. It
never receives filesystem write primitives, generic SSH, raw YAML or a mutable
`ProjectSnapshot` round trip.

## 2. Empty project lifecycle

### 2.1 Canonical create set

Successful `CreateProject` publishes exactly one canonical file:

```text
<project>/
  project.yml
```

It MUST NOT create `ansible.cfg`, `inventory/`, `group_vars/`, `host_vars/`,
desired deployments, localhost, runtime workspace, facts, plans or secrets.

`project.yml` contains:

```yaml
apiVersion: platform.installer/v2alpha1
kind: PlatformProject
metadata:
  id: project-<16 lowercase cryptographic hex characters>
  name: <operator display name>
  labels:
    platform.installer/managed-project: v1alpha1
desiredStateContract: platform.installer/project-desired-state/v2alpha1
catalogLock: <complete lock from verified selected local bundle>
artifactLock: <lock from the same verified local bundle>
```

`desiredState` is absent. The marker is portable machine metadata, not desired
infrastructure state. It is explicit ownership consent that this Installer
lifecycle never mutates, not cryptographic provenance or a mutable lifecycle
status. Empty state is derived from marker + exact absence of
inventory/variable documents; no `state: EMPTY` field is persisted.

The lock pair MUST come from one locally verified immutable bundle/cache entry.
The full compatible service map is pinned at create so adding a deployment does
not silently mutate project compatibility metadata. The request selects a
verified bundle digest, not caller-supplied lock bodies. If no verified bundle
is available, creation is BLOCKED with `PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE`.
No Execution Node connection or repository probe is used.

For UI-created projects the v1alpha1 lock mapping is exact:

- `artifactLock.apiVersion` is `platform.installer/artifacts/v1alpha1`;
- `artifactLock.digest` equals `executionbundle.Verified.Digest`, currently the
  SHA-256 of the verified bundle's exact `manifest.yaml` bytes; that manifest
  commits to ordered component paths, sizes and SHA-256 values;
- `catalogLock.apiVersion` is `platform.installer/catalog/v1alpha1`;
- `catalogLock.digest` equals `Verified.Manifest.CatalogDigest`;
- `catalogLock.services` is derived from the catalog whose digest matches that
  manifest and contains every compatible definition ID/version/digest;
- `artifactLock.signatureEnvelope` is omitted until the selected verified
  bundle actually provides and validates that versioned evidence.

This is the accepted UI creation profile for the existing project lock schema,
not a general CONTRACT-01 migration rule. UI-01C exposes it as one
`ProjectCompatibilitySource/v1alpha1` returned by the trusted local bundle
verifier; React cannot submit any digest or service lock independently. The
remote snapshot request compares both persisted lock digests with the selected
READY Execution Node bundle before Core runs. A mismatch is
`PROJECT_COMPATIBILITY_BINDING_MISMATCH`, not a schema-only PASS.

The technical ID is generated independently of display name to avoid locale,
rename and collision rules. Display name remains user-facing. The destination
must not exist; its parent must exist and be writable. Backend creates a sibling
temporary directory and publishes with an OS no-replace primitive: Windows
`MoveFileEx` without `MOVEFILE_REPLACE_EXISTING`, Linux `renameat2` with
`RENAME_NOREPLACE`; an unsupported platform fails rather than emulating the
race-prone check/rename pair. It fsyncs where supported. All path ancestors are
checked for symlink/reparse-point escape. Cancel writes nothing; a failed
operation is not published to recent projects.

The operation removes its own unpublished sibling on failure after proving its
resolved identity. Startup cleanup may remove only a sibling carrying the exact
Installer create-transaction marker/ID, owned by the current account, still
unpublished and older than the bounded recovery threshold; it revalidates the
parent and target identities before recursive removal. An unrecognized sibling
is preserved and reported, never guessed to be an orphan.

### 2.2 Classification on open

| Inputs | Classification | UI behavior |
| --- | --- | --- |
| Valid manifest, managed marker, no other canonical files | `EMPTY_MANAGED_PROJECT` | Open locally; editing session available; status “not configured” |
| Valid manifest, managed marker, canonical inputs present | `MANAGED_PROJECT` | Request fresh Core snapshot before authoritative editing/save |
| Valid manifest without marker and inventory present | `EXTERNAL_PROJECT` | Core snapshot; write only existing explicitly managed documents |
| Manifest absent but supported inventory present | `ANSIBLE_PROJECT` | Core snapshot; project identity/run planning may remain blocked |
| Missing inventory without managed marker | `PROJECT_INPUT_INCOMPLETE` | Do not reinterpret as new project; safe open error/read-only diagnosis |
| Marker present but malformed/unknown canonical files exist | `MANAGED_PROJECT_INVALID` | Not empty; no save until safe finding is resolved |
| Invalid/unsupported manifest or unsafe path | `PROJECT_OPEN_BLOCKED` | No draft mutation; safe typed finding |

Local classification reads only bounded metadata and paths. Infrastructure
meaning is never inferred locally. Configured content is authoritative only
after Core returns a compatible snapshot.

### 2.3 Lifecycle

```text
ABSENT --CreateProject/atomic publish--> EMPTY_MANAGED_PROJECT
EMPTY_MANAGED_PROJECT --start session--> EDITING_UNSAVED
EDITING_UNSAVED --discard--------------> EMPTY_MANAGED_PROJECT
EDITING_UNSAVED --Core-blocked----------> EDITING_UNSAVED
EDITING_UNSAVED --review+commit---------> MANAGED_PROJECT
MANAGED_PROJECT --new session-----------> EDITING_UNSAVED
```

Process restart preserves only canonical states. An unsaved draft is lost after
an explicit close/discard decision; it is not restored as desired state.

## 3. First save and ownership freeze

The Core-before-commit flow in section 3.1 is historical UI-01D architecture
before ADR-027. The ownership matrix and transaction guards remain current;
new Save uses local structural candidate review as defined by ADR-027.

### 3.1 Complete candidate invariant

The backend builds one complete candidate from the current canonical project
and the ordered session intents. It transfers that candidate to the Core
validation boundary, asks for a fresh existing `ProjectSnapshot/v1alpha1`, and
exposes an opaque `EditPlan` only when the candidate is accepted. Per-document
schema checks are supplementary; they never replace whole-project validation.

Planning writes zero canonical bytes. Commit rechecks project revision and all
before digests under the project lock, then atomically commits every document.
Post-commit snapshot failure returns `COMMITTED_REFRESH_FAILED`; it never lies
that rollback occurred after bytes were safely committed.

### 3.2 First-save ownership matrix

| Document | Created | Owner | Mutation rule |
| --- | --- | --- | --- |
| `project.yml` | CreateProject | Project metadata/lock contract | Not changed by normal first save; lock updates require future explicit compatibility operation |
| `ansible.cfg` | First save | Whole-file Installer-owned only in marked managed projects | Fixed managed header and required Ansible settings; never overwrite external file |
| `inventory/hosts.yml` | First save | Whole-file Installer-owned only when marker grants v1alpha1 managed inventory | Deterministic full serialization; no rewrite/adoption for external projects |
| `inventory/group_vars/all/platform-installer.yml` | First save | Existing managed-header contract | Owns `platform_desired_state`; create only for marked project |
| `inventory/host_vars/<host>/platform-installer.yml` | First save/as needed | Existing managed-header contract | Owns `platform_deployments`; create only for a host with placement/override |
| User `platform.yml`, other group_vars/host_vars | Never implicitly | User-owned | Read through Core; UI remains read-only for those values |
| `platform-state.yml` | Never by editor | Generated read-only | Excluded from editor transaction |

The YAML files use the established managed comment. `ansible.cfg` uses the
separate exact configuration marker shown below; both are versioned ownership
conditions rather than guesses from a filename. The first save extension may
create missing fixed documents only when the immutable
managed-project marker is present. Existing path without the exact ownership
condition returns `WRITE_OWNERSHIP_REQUIRED`; no adoption prompt is implied.

The exact first-save ownership conjunction is: valid managed-project marker,
valid project/lock envelope, `EMPTY_MANAGED_PROJECT` or a previously committed
managed-project classification, matching base project revision, planned path
absent, safe path ancestry, and no unknown canonical collision. Reopening on a
different Installer does not require local hidden ownership state. Replacing an
existing file additionally requires that exact file's versioned managed header
and Core `INSTALLER_OWNED` classification; the project marker alone never grants
rewrite permission.

The first-save `ansible.cfg` template is exact and intentionally smaller than
the repository Core runtime configuration:

```ini
# Managed by Platform Installer.
# This is standard Ansible configuration; formatting may be normalized.
[defaults]
inventory = ./inventory/hosts.yml
retry_files_enabled = False
host_key_checking = True
interpreter_python = auto_silent
hash_behaviour = merge
```

It fixes the portable inventory source and the required merge policy, but does
not embed a repository checkout, collection path, Python path, privilege
escalation, target username, secret or workstation path. A service playbook or
execution runtime remains responsible for its own collection/runtime boundary.
UI-01D must test these exact bytes modulo the final newline.

The first-save inventory is also deterministic and contains no implicit
`localhost`:

```yaml
# Managed by Platform Installer.
# This is standard Ansible YAML; formatting may be normalized.
all:
  hosts:
    node1:
      ansible_host: 192.0.2.10
  children:
    platform_targets:
      hosts:
        node1: {}
```

Every declared server occurs once under `all.hosts` and once as an empty member
of `platform_targets`. `ansible_port` is emitted only when it differs from 22.
Placement remains in managed host_vars, not inline inventory. `ansible_user`,
private keys, passwords and host-key material are omitted: the Installer run
binds one runtime-only session identity to all target nodes, while a standalone
Ansible operator supplies equivalent transport settings through CLI/SSH
configuration. An empty `platform_targets` group is never committed as a
configured first save; Core must accept the complete candidate.

### 3.3 Revision, rollback and paths

- Base revision is the existing raw-byte project revision (initially manifest
  only). Candidate revision covers all new canonical files.
- Every existing affected file carries a before digest; a missing-before marker
  is explicit for planned creates and commit verifies it is still absent.
- Fixed logical paths are derived in Go. Host IDs pass the existing identifier
  grammar before they become path components.
- No symlink/reparse point is followed. Parent directories are checked again
  under lock before commit.
- Transaction journal records creates separately from replacements. Rollback
  removes only files created by this transaction and restores replaced bytes;
  it removes only transaction-created empty parent directories.
- Unknown files are preserved. A collision at a planned managed path blocks the
  entire transaction even if other candidate documents are valid.
- Crash recovery is idempotent and retains the existing journal/atomic-replace
  semantics. Secret values are rejected before staging and never enter journal.

### 3.4 Edit session

One backend-owned in-memory session is keyed by opaque ID and binds project ID,
canonical root, base revision and ordered semantic intents. It has bounded
commands/bytes, explicit expiry, review and discard. Page navigation changes no
canonical bytes. Wails/React may mirror form state for rendering, but backend
session is the authority for the review candidate. A project switch or close
must choose continue or discard. Process exit does not persist the draft.

`ReviewEditSession` compiles the session into one candidate; it does not rely on
the current 16-command `Batch` limit for a whole topology. Commit consumes the
opaque plan once. Any new edit invalidates the previous review plan.

### 3.5 Mandatory writer and candidate hardening

The current v1alpha1 writer does not yet satisfy the expanded first-save threat
model. UI-01D must close these defects before enabling any UI mutation:

- on Windows, reject every `FILE_ATTRIBUTE_REPARSE_POINT` on the project root,
  `.runtime`, transaction directories, managed parents and targets; POSIX keeps
  the equivalent no-symlink checks. `os.Lstat` alone is not accepted evidence;
- recheck the resolved project root identity and every ancestor under the
  writer lock immediately before preparation, replacement and recovery;
- validate `.runtime/project-writer.lock` and `.runtime/edit-transactions`
  through the same contained-path policy. Recovery never calls recursive
  removal until the resolved transaction directory is proven to be the exact
  child of that safe runtime root;
- new canonical files use mode `0644` on POSIX and inherited non-broadened ACLs
  on Windows. POSIX transaction journals/backups use `0600` files inside `0700`
  directories. On Windows the runtime, lock, journal and backup paths use a
  protected DACL limited to the current user, SYSTEM and Administrators; opened
  handles are checked against the resolved root identity before use. Existing
  document mode/ACL is preserved;
- the create transaction uses a sibling directory under the selected parent.
  Before publish it applies the same reparse/identity checks. After atomic
  rename succeeds, the project exists even if parent fsync, recent-project
  indexing or refresh fails; return `CREATED_REFRESH_FAILED` with project root
  and identity instead of deleting or reporting that nothing was created.

Remote/local staged candidates contain only regular canonical documents:
`project.yml`, `ansible.cfg`, `inventory/hosts.yml`, and `.yml`, `.yaml` or
`.json` files below `inventory/group_vars` and `inventory/host_vars`. Unknown
files elsewhere are preserved in the source project but not copied to Core.
Limits are 4,096 files, 4 MiB per file, 64 MiB uncompressed total, 32 MiB
archive bytes, and 512 UTF-8 bytes per normalized relative path. Absolute,
escaping, duplicate, case-colliding, alternate-stream, device, FIFO, socket,
symlink, hardlink and reparse entries block the whole proof. The receiver
extracts into a new `0700` directory, verifies count/size/digest while writing,
and deletes it after the request. Limits produce a bounded Finding, never a
partial snapshot.

Every field ending in `SecretRef` or `CredentialRef` must match
`^runtime:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` in Go and the owning Core/service
schema. References are opaque broker IDs and are never joined to a filesystem
path. A matching field name never exempts its value from validation. UI-01D adds
common rejection tests for plaintext/disguised values; service-specific schemas
must use the common reference definition before their setting is editable.

## 4. Editor / Core / Execution Node boundary

Editing is independent of repository probes, runtime projections, target facts
and active execution state. Core authority remains mandatory where semantics
are needed, and AGENTS.md still forbids local Python/Ansible on the workstation.

```text
React -> generated Wails binding -> Go project/edit service
                                     | local path/create/session lifecycle
                                     | canonical project bytes
                                     v
                             fixed ProjectSnapshot operation
                                     v
                    selected READY Linux validation runtime
                         (controller-only, no target contact)
```

The physical node MUST be the operator-selected READY Execution Node. The
editor consumes only its restricted `CoreValidationBinding`: node ID, trusted
transport reference and the node's immutable compatible runtime. It does not
call repository probe, source
resolution, RuntimeProjection, deployment planning or execution lifecycle.

The existing local `coreadapter.CommandAdapter` is retained for standalone RED
OS tests. UI-01B adds a second implementation over a fixed structured remote
`BuildProjectSnapshot` operation returning the same snapshot contract for an
existing project only. It is not a generic command/SSH API: the request carries
no command, candidate, owned-path classification or mutation intent; the node
uses an empty owned-path set and removes request staging after the response.
Diagnostics are bounded and safe. UI-01D alone adds candidates, ownership,
review, commit and rollback.

Behavior without a usable validation binding:

- create/open metadata and edit a known empty managed draft: allowed;
- navigate and retain an already loaded draft/snapshot: allowed with stale badge;
- refresh a configured project, produce authoritative review or commit: blocked
  with `CORE_VALIDATION_UNAVAILABLE`; draft retained;
- no result is labelled PASS and no cached snapshot proves a new commit.

Target session credentials are unrelated to Core validation. Their absence is
not an editor blocker. Missing credentials for the validation transport block
only refresh/review/commit that require remote Core.

The target credential contract is `SessionCredential/v1alpha1`. One active
project session has one technical username and exactly one authentication mode:
`SSH_PRIVATE_KEY` or `SSH_PASSWORD`. Wails submits the secret once to a
write-only Go `RuntimeSecretBroker`; the response contains only status metadata:
mode, availability and expiry. Its internal
`runtime:ssh-session-<32-hex>` reference is never exposed through Wails/React.
Query, review, logs and events never return the value or internal reference.
The lease expires one hour after it is set/replaced, on project
close/replacement or process exit, whichever comes first, and is applied to every target `Node` for that
project only by a future trusted Go transport. Execution Node credentials
remain a separate trusted binding.

The Installer never opens a direct workstation-to-target SSH path and never
materializes the target password or private key in a Windows file. Secret bytes
remain in the write-only process broker until streamed to the selected Execution
Node. Password/key authentication must not use argv, environment variables,
command-line interpolation or a persistent project file.

UI-01E implements local capture, replacement, expiry and non-disclosure only;
it performs no target probe. Before UI-02 target contact, the execution
transport must add a fixed `PutRuntimeSecretLease/v1alpha1` operation: secret
bytes travel on the already authenticated SSH stdin stream, are written on the
selected Execution Node as a run/session-bound `0600` lease outside project and
journal, and only its opaque reference enters Node/runtime projection. The
controller materializes the lease inside its Linux `0700` private runtime and
maps it to `ansible_password` or `ansible_private_key_file` through `0600`
private runtime state, suppresses it
from callback/events, and removes it on terminal, cancel, expiry and interrupted
run recovery. Until that fixed operation passes password/key/no-log/cleanup
tests, installation with that credential mode is BLOCKED, never silently
downgraded. This future UI-02 transport work does not block UI-01 editor save.

An active execution uses an immutable revision-bound copy. Editing and save MAY
continue; UI shows `ACTIVE_EXECUTION_USES_PREVIOUS_REVISION` as a warning. The
current run is never changed, restarted or cancelled. Starting another run
remains blocked by the existing active-run guard.

When reachable, the warning is based on authoritative `GetExecution`; a cached
run record is labelled stale and never used to claim terminal state. Save
remains allowed because it cannot mutate the immutable run, but starting a new
run always rechecks the existing active-run guard remotely.

If the Installer has lost the run ID and the current protocol cannot discover
it, the editor displays active state as `UNKNOWN`; it does not infer success or
failure. This affects only the warning. Remote `StartExecution` remains the
authoritative concurrency gate and must return the conflicting run identity
when one exists.

Future progress UI uses `ExecutionService`/typed RunObserver subscriptions via
Wails. React must not read `.runtime/executions/<runId>/events.jsonl`, parse
callback text, infer terminal result or treat observer disconnect as FAILED.

## 5. Semantic command freeze

All commands belong to Go application lifecycle and are validated structurally
there. Infrastructure validity and resolved effects remain Core-owned. Commands
mutate only fixed Installer-owned native documents through the common session,
staged snapshot, plan and commit path.

### 5.1 Servers / inventory — missing

| Command | Minimal intent | Documents | Policy and expected plan |
| --- | --- | --- | --- |
| `CreateServer` | `hostId`, `address`, optional `sshPort` | managed `inventory/hosts.yml` | Reject duplicate/invalid identity; plan shows host create and inventory digest |
| `UpdateServer` | `hostId`, changed address/port | same | Identity immutable; Core validates complete references; plan shows fields only |
| `DeleteServer` | `hostId` | inventory plus affected managed host_vars only when explicitly included in one reviewed reconcile | Block dangling placement by default; no cascading service deletion |

Technical username, password/key and host-key trust are session/runtime data,
not fields in these commands. A future explicit host rename is not delete+create
and is out of UI-01.

### 5.2 Topology — reuse plus one missing reconcile

Reuse current deployment, configuration, endpoint group, HAProxy and point
placement operations. Add:

| Command | Minimal intent | Documents | Policy and expected plan |
| --- | --- | --- | --- |
| `ReconcileDeploymentPlacement` | `deploymentId`, complete list of `{memberId, hostId, roles, configuration?}` for that deployment | only corresponding managed host_vars | Preserve other deployments and unknown files; Core validates mode/cardinality/distinct hosts; plan reports member add/move/remove |

This is canonical full-model reconcile for one deployment, not raw host_vars.
It solves cross-host member moves atomically and is not constrained by the
legacy 16-child Batch. Generic dependency editing is not invented: UI-01
supports existing endpoint-group and HAProxy relations. Any additional relation
requires catalog/Core contract evidence and a later versioned command.

### 5.3 Certificates / PKI — missing

The operations are `Create`, `Update`, `Delete` for each bounded entity:

- `CertificateAuthority` (`id`, `mode=MANAGED`, `commonName`, safe optional fields);
- `CertificateProfile` (`id`, `authorityRef`, `sanPolicy`, safe optional policy);
- `TLSProfile` (`id`, `certificateProfileRef`, optional scope,
  `storePasswordSecretRef` only);
- `CertificateScope` (`id`, profile/scope and bounded source references).

All affect only `platform_desired_state` in managed group_vars. Payload shapes
reuse the existing project desired-state schema definitions; they are not raw
YAML maps. Delete is blocked by Core when referenced. Expected `EditPlan`
contains semantic entity/property changes, document digest, `PKI_INPUT_CHANGED`,
Core findings and derived snapshot fingerprint. SAN, consumers, keys, passwords,
request/materialization plans and reissue decisions are never command input.

### 5.4 Services / deployments

Reuse `CreateServiceDeployment`, `DeleteServiceDeployment`,
`SetServiceConfigurationValue`, `RemoveServiceConfigurationOverride`,
`SetServiceEndpointGroup`, `ClearServiceEndpointGroup`,
`SetHAProxyIntegration`, `ClearHAProxyIntegration`, and the existing point
placement commands `AssignServiceToHost`, `RemoveServiceFromHost` and
`SetPlacementProperty`. For UI-01 implementation the
currently open `deployment` map must be replaced at the transport boundary by
bounded fields `deploymentId`, `serviceType`, `mode`; Core/catalog owns whether
the mode is valid. Existing Go internal representation MAY adapt these fields,
but Wails never exposes arbitrary maps as a service editor API.

No new command is needed for deployment-level `tlsProfile` when the manifest
declares it as a setting: use existing setting set/reset. Member-level override
uses a typed extension of placement property only if the catalog mapping permits
member scope. Multiple deployments are independent IDs; opening a catalog item
does not create an instance.

### 5.5 Versioned API evolution

UI-01 does not add the new operations to the closed
`platform.installer/edit-command/v1alpha1` enum. UI-01D introduces one additive
schema family at `contracts/project-edit/v1alpha2/schema.json` and the Go
constants `edit-command/v1alpha2`, `edit-session/v1alpha1`,
`edit-plan/v1alpha2` and `edit-commit-result/v1alpha2`. V1alpha1 remains readable
for compatibility but cannot represent first save; the UI uses v1alpha2 only.

V1alpha2 command bodies are a closed `oneOf` keyed by operation. The UI-visible
set is exact:

- `CreateServiceDeployment(deploymentId,serviceType,mode)`,
  `DeleteServiceDeployment(deploymentId)`;
- `SetServiceConfigurationValue(deploymentId,setting,value)` and
  `RemoveServiceConfigurationOverride(deploymentId,setting)`; `setting` must be
  a catalog property and `value` validates against that property's schema;
- `Create|Update|DeleteEndpointGroup`, with `endpointGroupId` and a complete
  desired-state endpoint-group body for create/update;
- `Set|ClearServiceEndpointGroup` and `Set|ClearHAProxyIntegration`, using only
  the source deployment and referenced entity/deployment IDs;
- `CreateServer(hostId,address,sshPort?)`,
  `UpdateServer(hostId,address?,sshPort?)`, `DeleteServer(hostId)`;
- `ReconcileDeploymentPlacement(deploymentId,members[])`, where each member is
  exactly `{memberId,hostId,roles[],configuration?}` and `configuration` is
  admitted only through catalog-declared member settings;
- `Create|Update|DeleteCertificateAuthority`,
  `Create|Update|DeleteCertificateProfile`,
  `Create|Update|DeleteTLSProfile`, and
  `Create|Update|DeleteCertificateScope`, each with `entityId` and a typed
  entity body for create/update that reuses the matching desired-state schema
  definition. Delete has no body.

Point placement operations from v1alpha1 remain backend compatibility input but
are not exported by Wails; the UI uses `ReconcileDeploymentPlacement`.
`value` exists only for one catalog-addressed service setting. There is no
generic `document`, YAML, path or arbitrary map escape. Entity update bodies are
complete replacements in the transient candidate, not JSON merge patches. Core
validates all cross-entity meaning.

`DocumentChange/v1alpha2` has this exact model:

```text
logicalPath: one of
  ansible.cfg
  inventory/hosts.yml
  inventory/group_vars/all/platform-installer.yml
  inventory/host_vars/<valid-host-id>/platform-installer.yml
before: { state: ABSENT } | { state: PRESENT, digest: sha256:... }
after:  { state: ABSENT } | { state: PRESENT, digest: sha256:... }
```

Exactly one digest is present iff that side is `PRESENT`; before and after may
not both be `ABSENT`. This represents create, replace and delete without an
invented digest. Plan and commit use the same document changes and fixed path
allow-list.

The application lifecycle contract is
`platform.installer/project-lifecycle/v1alpha1`; UI-01C publishes its closed
schema at `contracts/project-lifecycle/v1alpha1/schema.json`:

| Request/result | Exact caller-controlled fields | Result/authority |
| --- | --- | --- |
| `CreateProjectRequest` | absolute `projectRoot`, `displayName`, verified `compatibilitySourceId` | `ProjectOpenResult`; backend generates project ID and lock bodies |
| `OpenProjectRequest` | absolute `projectRoot` | classification, bounded metadata, revision, findings; snapshot only when Core proof exists |
| `RefreshProjectRequest` | open project context ID | fresh snapshot or typed unavailable/blocked finding |

`compatibilitySourceId` is an opaque local verifier handle, not a digest body.
Paths are never exposed to Core as target paths.

The edit-session operations are `StartEditSession(projectContextId,
baseProjectRevision)`, `AppendEditCommand(sessionId,command)`,
`ReviewEditSession(sessionId)`, `CommitEditPlan(planId)`, and
`DiscardEditSession(sessionId)`. Session and plan IDs are 32 lowercase hex
characters. One process permits one active session per project, at most eight
total sessions, 1,024 intents, 4 MiB of encoded command bodies and 30 minutes
idle lifetime. Exceeding a limit blocks the newest operation without changing
canonical bytes. Review emits `EditPlan/v1alpha2`; commit consumes it once.

Remote proof adds one fixed operation and reuses the existing response DTO:

```text
BuildProjectSnapshotRequest/v1alpha1
  requestId
  projectIdentity
  candidateProjectRevision
  projectArchiveDigest
  artifactLockDigest
  catalogLockDigest
  installerOwnedLogicalPaths[]
  projectContract = v2alpha1
  snapshotContract = v1alpha1
  editContract = v1alpha2

response: existing ProjectSnapshot/v1alpha1 or bounded Finding/v1alpha1
```

UI-01D publishes the closed request schema at
`contracts/project-snapshot-request/v1alpha1/schema.json`; it does not create a
second snapshot response.

The request travels only to the selected READY Execution Node through a fixed
protocol method. The controller verifies archive digest, safe extraction,
logical path allow-list, selected bundle digest and catalog digest, then invokes
the target-free Core snapshot entrypoint. It accepts no command, argv,
playbook path or generic SSH operation.

### 5.6 Snapshot provenance defect and gate

Current `ProjectSnapshot/v1alpha1` incorrectly reports every member override as
`inventory/hosts.yml` with `READ_ONLY`, including values that came from the
accepted managed host_vars document. This is a real backend contract defect,
not a reason for React to infer provenance.

Before UI-01F enables placement/member editing, Core must report the actual
origin under the same snapshot contract:

- managed `inventory/host_vars/<host>/platform-installer.yml` -> `HOST_VARS`,
  exact logical path, `EDITABLE`;
- inline `inventory/hosts.yml` -> `INVENTORY`, exact path, `READ_ONLY`;
- other user host_vars -> `HOST_VARS`, exact path, `READ_ONLY`;
- unresolved origin -> `UNKNOWN`, `READ_ONLY_UNRESOLVED`.

### Historical UI-01D remote acceptance before ADR-027

UI-01D was required to add the fixed remote snapshot operation and a standalone acceptance
test for the generated project-local `ansible.cfg`. On RED OS that test changes
to the exported project root, unsets `ANSIBLE_CONFIG`, asserts through
`ansible-config --version` that the active file is that root's `ansible.cfg`,
checks `ansible-config dump --only-changed` and `ansible-inventory --list`, then
runs the target-free Core validation under `sudo unshare -n`. It must prove the
configured inventory and merge policy without relying on the current adapter's
working directory or explicit `-i`. UI-01F owns the provenance bug fix and its
managed/user-owned/inline fixtures; the editor remains disabled for member
values until that evidence passes.

## 6. Negative-scenario ownership

| Scenario | UI precheck | Go command/lifecycle | Core | Save effect |
| --- | --- | --- | --- | --- |
| missing `metadata.id` | display safe field hint | classify invalid | contract finding | BLOCK |
| missing catalog/artifact locks | display compatibility error | Create/Open BLOCK | schema/compatibility | BLOCK |
| marked empty project, no inventory | show normal empty state | valid classification | not invoked until complete candidate | allowed to edit, not yet saved |
| malformed managed document structure | syntax-neutral error UI | structural reject; no repair/adoption | not required for Save | BLOCK Save |
| arbitrary user-owned YAML | read-only origin | ownership check | may read safely | BLOCK affected edit; preserve bytes |
| project/runtime path contains reparse point | safe path error | OS-specific path identity guard | not reached | BLOCK before stage/lock/recovery |
| candidate exceeds file/path/byte limits | bounded size error | candidate/archive guard | not reached | BLOCK; no partial snapshot |
| stale project revision | stale badge | revision guard | fresh snapshot if requested | BLOCK, retain draft |
| document digest mismatch | generic conflict | digest guard | none needed | BLOCK entire transaction |
| first Project Verify Core failure | show findings | keep saved project editable | authoritative | Save remains; mark `INVALID` |
| cross-file structurally safe but semantically invalid candidate | do not validate forms as final truth | save complete bounded candidate | optional Verify/fresh plan authoritative | Save remains; execution requires fresh successful plan |
| duplicate server identity | immediate hint | structural reject | confirms candidate | BLOCK |
| invalid topology reference | optional client hint | no semantic inference | optional Verify/fresh plan authoritative | Save may remain; no direct execution |
| missing deployment reference | display returned finding | no local service rule | optional Verify/fresh plan authoritative | Save may remain; no direct execution |
| missing PKI identity reference | optional selector warning | no fabricated identity | optional Verify/fresh plan authoritative | Save may remain; no direct execution |
| plaintext disguised as `*SecretRef` | generic reference error | strict `runtime:` reference grammar | schema confirms | BLOCK before staging |
| Execution Node unavailable | status banner; forms remain | local writer unaffected | Verify/plan unavailable | Save allowed; draft retained |
| target credentials absent | session status only on Servers | secret availability only | irrelevant to target-free validation | editor and E5 allowed; UI-02 target execution BLOCK |
| target credential mode lacks proven runtime materializer | session status only on Servers | keep lease local only | irrelevant to target-free validation | editor and E5 allowed; UI-02 target execution BLOCK |
| Execution Node transport credential absent | explicit Verify/plan warning | local writer unaffected | unavailable | Save allowed; Verify/plan blocked |
| execution active during edit/save | revision warning | allow edit/save; bind new revision | prior run remains plan-bound | allowed; active run unchanged |

Client-side validation improves forms only. It never turns an operation READY.

## 7. Implementation handoff

The attached start brief used an older B–H layout. The current owner-approved
sequence B–J is authoritative and retains every requested dependency:

| Milestone | Must exist before start | Contract delivered |
| --- | --- | --- |
| UI-01B | This freeze; selected toolchain; existing snapshot contract | Shell/navigation/project context, local classifier, read-only open and validation binding status |
| UI-01C | B project lifecycle shell; verified bundle metadata reader | Lifecycle v1alpha1, compatibility source mapping, exact one-file publish, reopen empty managed project |
| UI-01D | C marker/lifecycle; fixed remote request; v1alpha2 edit schema; path/candidate/secret-ref hardening | Common transient session, complete candidate, review, first-write transaction and standalone project-config proof |
| UI-01E | D session/transaction; runtime secret broker contract | Server CRUD over managed inventory and one write-only session credential for all servers; no target probe |
| UI-01F | E hosts; catalog snapshot; deployment/placement contracts; corrected member origin | Catalog instance creation, topology/member/placement reconcile and supported integrations |
| UI-01G | F topology; existing PKI schemas; D transaction | PKI authority/profile/TLS/scope commands and Core-derived previews |
| UI-01H | G profile identities; F deployments; schema-driven configuration | Service settings, origins/reset and PKI references; same editor from Topology |
| UI-01I | H saved project and explicit export policy | Full portable export/reopen; no template-slot import |
| UI-01J | B–I complete | Native end-to-end acceptance and UI-01 closure |

UI-01B must not implement create/write. UI-01C must not implement first save.
UI-01D may use narrow test intents before full editors. UI-01 execution/progress
screens remain placeholders; UI-BE-04 and EXEC-OBS-01 are consumed in UI-02.

## 8. Non-blocking limits

- External project inventory adoption and host rename are deferred.
- Template import/server slots are deferred; UI-01I exports saved full projects.

### Post-freeze additive server-type decision

`OWNER-APP-CONFIG-01/02` supersedes only the command-version detail above.
Published `project-edit/v1alpha2` remains unchanged and continues to represent
the historical `CreateServer(hostId,address,sshPort?)`. New Installer sessions
use additive `project-edit/v1alpha3`, whose same `CreateServer` command also
requires `type`. Both versions decode to the existing Go `EditCommand`; no
parallel server model is introduced. `platform_host.type` is optional on legacy
read, grammar-only in the portable schema, and required/configured-list checked
for new v1alpha3 creation by the Go application layer.
- Generic service dependency editing beyond accepted endpoint/HAProxy relations
  needs a future catalog/Core contract.
- Unsaved drafts are not crash-persistent.
- Editing without a validation node is possible, but authoritative refresh,
  review and save are unavailable.
- Cross-platform desktop architecture is preserved, but UI-01B first proves the
  Windows build; Linux/macOS packaging remains later platform acceptance.

None of these limits weakens canonical ownership or Core validation.
