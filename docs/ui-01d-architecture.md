# UI-01D — архитектура first-write и общей edit/review session

Implementation status: **FINAL REVIEW**. Final evidence: [ui-01d.md](ui-01d.md).

Статус документа: архитектурный план, не разрешение на реализацию.
Revision binding: `UI-01D-ARCH-2026-09-05-EXECNODE-01`.

> **Owner supersession, 2026-09-15:** ADR-027 and
> [Save / Project Verify / DeploymentPlan](ui-save-verify-architecture.md)
> replace the target lifecycle described below. The original Core-backed
> Review/EditPlan, post-commit refresh and `COMMITTED_REFRESH_FAILED` sections
> remain implementation/compatibility history, not the architecture for new
> Save. New flow: `EditSession → local structural candidate/review → guarded
> Save`; optional Project Verify is separate; every execution still requires a
> fresh `BuildDeploymentPlan`. Save no longer requires READY or Core PASS.

Эта ревизия включает owner decisions `OWNER-UI-EXECNODE-01` через
`OWNER-UI-EXECNODE-09`, изменяет только application-context/navigation gates
и границы UI-01D/UI-01E/UI-02, и сверена с
`docs/ui-design-01-mockups.html` (сценарии A–F). Она не переносит в UI-01D
полный Servers/Execution Node panel, bootstrap, selection controls или
Installation execution implementation.

UI-01D established the backend-owned edit session, first managed write and
guarded transaction. ADR-027 now reuses those local mechanics for Save while
separating optional Core verification. It preserves read-only open/snapshot
из UI-01B и metadata-only creation из UI-01C. Полные редакторы серверов,
топологии, сертификатов и сервисов остаются в UI-01E–H.

## 1. Границы и инварианты

Каноническим desired state остаются portable native project files:

- `project.yml` владеет identity и lock provenance;
- `ansible.cfg`, `inventory/hosts.yml`, managed `group_vars` и managed
  `host_vars` являются фиксированными Installer-owned native documents;
- пользовательские YAML и generated `platform-state.yml` не становятся
  редакторским desired-state store.

Владельцы семантики не меняются:

```text
React/Wails
  только rendering и typed transport
        |
Go Installer backend
  project context, session, command bounds, ownership, path guards,
  candidate assembly, review/commit lifecycle и filesystem transaction
        |
fixed BuildProjectSnapshot request
        |
selected READY Execution Node
  target-free Core validation; no target contact
```

Go не копирует topology, catalog, PKI, service или Ansible precedence rules.
Core получает полный candidate и остаётся единственным владельцем
infrastructure semantics. SQLite, persistent draft, generic YAML API,
generic SSH API и второй desired-state store не добавляются.

## 2. Scope UI-01D

В milestone входят:

1. один backend-owned transient edit session на project context;
2. закрытый typed edit-command contract `v1alpha2`;
3. complete candidate assembly для existing и first-save managed project;
4. candidate-capable fixed `BuildProjectSnapshot` request с прежним
   `ProjectSnapshot/v1alpha1` response;
5. authoritative Review → EditPlan → guarded Commit/Discard;
6. first-write создания только разрешённых Installer-owned documents;
7. минимальный Review/Save UI shell и индикатор unsaved/review status;
8. RED OS и Windows safety acceptance для path, reparse, rollback и recovery.

UI-01D не включает:

- полные формы Servers, Topology, Certificates и Services;
- target probe, install/apply, execution progress и UI-02 event stream;
- target credential transport и runtime secret lease из UI-01E/UI-02;
- export/import/template slots;
- crash-persistent drafts;
- adoption или переписывание внешнего inventory/YAML;
- произвольные document/path/map commands.

Для D допустим narrow contract fixture/client, который доказывает один
first-write intent без создания полноценных E–H форм.

## 3. Backend components

Новые ответственности добавляются в существующий `internal/installer.Backend`
и его bounded stores. Нового application subsystem или daemon нет.

### 3.1 Project context

`OpenProject` уже определяет canonical root, classification и base revision.
Edit session принимает только открытый `projectContextId` и повторно проверяет
его resolved root. Context не является вторым desired-state хранилищем.

### 3.2 EditSessionStore

Добавляется in-memory store, связанный с project context:

```text
EditSession
  sessionId: 32 lowercase hex
  projectContextId
  resolvedProjectRootIdentity
  baseProjectRevision
  ordered intents[]
  createdAt / lastActivity / expiresAt
  state: EDITING | REVIEWED | COMMITTING | DISCARDED | EXPIRED
  activePlanId?: 32 lowercase hex
```

Ограничения из UI-01A обязательны: один active session на project, максимум
8 process-wide sessions, 1,024 intents, 4 MiB encoded command bodies и
30 минут idle lifetime. Process exit удаляет draft. Session state не
переживает restart и не является desired state.

`AppendEditCommand` всегда инвалидирует `activePlanId`. После любого нового
intent старый plan нельзя commit-ить, даже если его TTL ещё не истёк.

### 3.3 CandidateBuilder

CandidateBuilder строит один полный candidate из canonical source и ordered
intents. Он не вызывает Core для частичных YAML-фрагментов.

Его обязанности:

- проверить session, base revision и command `v1alpha2` shape;
- классифицировать managed/unknown/user-owned documents;
- применить semantic intents только к допустимым managed documents;
- синтезировать отсутствующие first-save documents по фиксированным шаблонам;
- reject path escape, absolute path, duplicate/case collision, symlink,
  hardlink, device/FIFO/socket, alternate stream и reparse point;
- проверить все `SecretRef`/`CredentialRef` значения по runtime reference
  grammar, не получая secret material;
- создать bounded candidate archive только из разрешённого набора файлов;
- вернуть before/after document states и deterministic digests.

Unknown files сохраняются в source project, но не копируются в Core candidate.
User-owned files могут читаться Core для полной семантической проверки, но не
перезаписываются Installer-ом.

## 4. Contracts

UI-01D публикует additive closed schemas:

- `contracts/project-edit/v1alpha2/schema.json` — closed `oneOf` commands;
- the same schema family contains `EditSession/v1alpha1`, `EditPlan/v1alpha2`
  and `EditCommitResult/v1alpha2` DTOs;
- `contracts/project-snapshot-request/v1alpha1/schema.json` — closed candidate
  proof request carried only by the existing fixed snapshot operation.

`project-edit/v1alpha1` остаётся compatibility input для backend readers, но
не экспортируется новым Wails UI. В v1alpha2 нет arbitrary `document`, `path`,
raw YAML, generic map escape или JSON merge patch. Entity update bodies —
complete typed replacements.

### 4.1 Session operations

```text
StartEditSession(projectContextId, baseProjectRevision)
AppendEditCommand(sessionId, command)
ReviewEditSession(sessionId)
CommitEditPlan(planId)
DiscardEditSession(sessionId)
```

`ReviewEditSession` и `CommitEditPlan` используют один plan identity. Один plan
может быть consumed только один раз. `Discard` удаляет только transient session,
candidate и plan state.

### 4.2 ExecutionContext projection

UI-01D не вводит новый persisted или wire `ExecutionContext` contract и не
дублирует existing Execution Node selection/lifecycle contract. На уровне
application state он потребляет следующую typed projection существующего
launch-time binding; UI-01E позднее материализует её через существующие
EXEC-01A operations:

```text
ExecutionContext/v1alpha1
  selection: existing explicit | AUTO_LOCAL | AUTO_FIRST_SERVER | none
  selectedNodeId?: application-local node identity
  state: NOT_CONFIGURED | CHECKING | NOT_PREPARED | READY | UNAVAILABLE |
         INCOMPATIBLE | UPDATE_REQUIRED | ERROR
  capabilityFingerprint?: opaque digest
  checkedAt?: timestamp
```

The mapping to the existing Execution Node service is fixed: `UNREACHABLE` →
`UNAVAILABLE`, `UNPREPARED`/`PREPARATION_REQUIRED` → `NOT_PREPARED`, `BROKEN` →
`ERROR`; `READY`, `UPDATE_REQUIRED` and `INCOMPATIBLE` retain their meaning.
The selection may be restored only as a local candidate after application
restart; the state returns to `CHECKING`/`UNAVAILABLE` until a fresh capability
handshake proves `READY`. Node removal, invalidation and replacement are
explicit transitions. No stale state silently becomes READY and no replacement
is inferred from list order.

The context lifetime is application-local and may be indexed by the local
project identity, but it is never serialized into project files or exported.
UI-01D consumes the typed gate and keeps its transient draft when the context
becomes unavailable. UI-01E owns selection, persistence of this local context,
handshake, preparation and invalidation; it does not introduce a second
desired-state store.

### 4.3 DocumentChange preconditions

Для first-write v1alpha2 заменяет старую модель "оба digest всегда есть":

```text
logicalPath: fixed allow-list path
before: { state: ABSENT }
     | { state: PRESENT, digest: sha256:... }
after:  { state: ABSENT }
     | { state: PRESENT, digest: sha256:... }
```

`ABSENT → PRESENT` — create, `PRESENT → PRESENT` — replace, `PRESENT →
ABSENT` — delete. `ABSENT → ABSENT` запрещён. Commit повторно проверяет
каждый before state под writer lock.

## 5. Lifecycle

```text
OPEN
  |
  +--> StartEditSession --> EDITING
                            |
                            +--> AppendEditCommand --> EDITING
                            |       (invalidates old plan)
                            |
                            +--> ReviewEditSession
                                  |
                   +--------------+--------------+
                   |                             |
             REVIEW_BLOCKED                 REVIEW_READY
                   |                             |
             retain draft                 COMMITTING
                                                 |
                              +------------------+------------------+
                              |                                     |
                           SAVED / NO_CHANGE                 SAVE_FAILED
                              |                                     |
                          new OPEN revision                  retain draft
```

### 5.0 Concurrency and cancellation

The bounded in-memory session store serializes append/review/commit state, and
the Wails application serializes its exported edit calls. Review marks the
session busy; commit first atomically verifies the latest reviewed plan and
marks the session `COMMITTING`. A competing mutation receives an explicit busy
or current-plan error. Project switch and close require explicit discard while
a session exists. Remote calls have bounded contexts; UI-01D intentionally does
not add a second generation/cancellation subsystem. Commit is one-shot after
success, while a blocked readiness or writer result retains the reviewed plan
for an explicit retry. The project writer lock remains independently bounded.

### 5.1 Start

Backend проверяет, что project context открыт, root identity разрешается без
symlink/reparse escape, а supplied base revision равен свежей canonical
revision. Session создаётся только в memory.

### 5.2 Append

Go проверяет closed command shape, ID grammar, bounds и fixed operation
allow-list. Client-side hints могут улучшать UX, но не становятся proof.
Append не пишет canonical bytes и не обращается к target.

### 5.3 Review

1. Read canonical documents and collect raw-byte revision/digests.
2. Revalidate managed-project ownership conjunction.
3. Apply all intents in order to one complete candidate.
4. Generate required first-save native documents where `ABSENT` is allowed.
5. Stage bounded archive in private transient runtime area.
6. Compute archive, lock, candidate and document digests.
7. Send one fixed `BuildProjectSnapshot` request to selected READY Execution
   Node.
8. Core validates the complete candidate target-free and returns the existing
   `ProjectSnapshot/v1alpha1` or bounded `Finding/v1alpha1`.
9. Verify the requested semantic intents are effective in the returned
   snapshot; if Core shadows them, return `EDIT_SHADOWED`.
10. Store opaque `EditPlan/v1alpha2` with expiry, before states, after states,
    semantic changes, impacts, snapshot fingerprint and bounded review diff.

Review statuses are `READY`, `BLOCKED` or `NO_CHANGE`. No `PASS` is produced
from local form validation or stale cached snapshot.

### 5.4 Commit

1. Resolve and verify project root, runtime root, transaction root and every
   affected ancestor under the project writer lock.
2. Recover any interrupted prior transaction.
3. Recollect canonical revision and all affected before digests/absence markers.
4. If any precondition differs, return `PROJECT_CHANGED` or
   `DOCUMENT_CHANGED`; write zero bytes.
5. Journal all creates/replacements/deletes, including backup and temporary
   paths, with protected permissions/ACLs.
6. Atomically publish every document or restore the original bytes on failure.
7. Mark the transaction committed and remove only its own recovery material.
8. Rebuild a fresh authoritative snapshot. If bytes are committed but refresh
   fails, return `COMMITTED_REFRESH_FAILED`, never a false rollback result.
9. Consume the plan exactly once and return the new project revision.

The existing transaction mechanics are reusable, but not unchanged: first-save
requires create-aware `ABSENT/PRESENT` preconditions, create-aware rollback,
collision blocking and fixed-path enforcement. Existing v1alpha1 behavior stays
compatibility-only until these semantics are proven.

## 6. First-write ownership

The exact conjunction is required:

- valid managed-project marker;
- valid project/lock envelope;
- `EMPTY_MANAGED_PROJECT` or previously committed managed project;
- matching base revision;
- planned path absent, or existing file has exact managed header and Core
  `INSTALLER_OWNED` classification;
- safe path ancestry and no canonical collision.

The first save may create only:

```text
ansible.cfg
inventory/hosts.yml
inventory/group_vars/all/platform-installer.yml
inventory/host_vars/<valid-host-id>/platform-installer.yml  (as needed)
```

`project.yml` is not changed by normal first save. No implicit localhost,
credentials, target username, password, key, host-key data, repository path,
Python path or service runtime is emitted. Empty `platform_targets` is not
committed as a configured first save; Core must accept a complete candidate.

Existing external `ansible.cfg`, inventory, group_vars or host_vars are never
adopted by a prompt or overwritten by the marker alone. Any ownership conflict
blocks the whole transaction and preserves every byte.

## 7. Remote candidate boundary

UI-01B's `BuildProjectSnapshot` operation name and `ProjectSnapshot/v1alpha1`
response remain the authority. UI-01D does not add a second generic operation.
Candidate proof is a separately negotiated request payload, carried by the
existing `execution-runtime/v1alpha1` envelope:

```text
apiVersion = platform.installer/project-snapshot-request/v1alpha1
kind       = BuildProjectSnapshotRequest
outer operation = BuildProjectSnapshot
```

The receiver rejects a missing/unknown `apiVersion` or `kind`; presence of the
closed `snapshotRequest` is the unambiguous candidate discriminator, so no
strategy/plugin or boolean mutation flag is introduced. The READY capability
handshake must advertise `BuildProjectSnapshot` and
`projectSnapshotRequestVersions:
[platform.installer/project-snapshot-request/v1alpha1]`. If it does not,
review stops with `PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED` before candidate
bytes are sent. This is a
versioned compatibility gate for mixed release deployments, not a second
operation.

The candidate request carries:

```text
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
```

The receiver verifies archive digest, regular-file/path limits, fixed logical
path allow-list, lock binding and safe extraction into a new private directory.
It invokes target-free Core only, removes only request-owned staging on success
and failure (a request-id/archive-digest-bound owner marker distinguishes
snapshot staging from lifecycle runs; a failed ownership claim never authorizes
cleanup), and
does not accept command, argv, playbook path or generic SSH parameters. Target
hosts are never contacted.

This is an additive candidate mode of the fixed operation, not reuse of the
UI-01B existing-project request unchanged. The existing `ProjectSnapshot` DTO
is reused; no second snapshot response is introduced. Unknown request versions
and unsupported candidate capability are hard failures, with no silent fallback.

## 8. Safety and failure policy

- Windows checks `FILE_ATTRIBUTE_REPARSE_POINT`; POSIX checks equivalent
  symlink/reparse conditions. `os.Lstat` alone is insufficient evidence on
  Windows.
- Root, `.runtime`, transaction directory, managed parents and targets are
  rechecked under lock immediately before preparation, replacement and
  recovery.
- Private runtime artifacts use protected ACLs. New canonical directories and
  files receive the canonical parent ACL with inheritance enabled; replacement
  and rollback preserve an existing canonical DACL.
- Candidate limits are 4,096 files, 4 MiB per file, 64 MiB uncompressed total,
  32 MiB archive and 512 UTF-8 bytes per normalized path.
- Secret values never enter commands, candidate, journal, diff, snapshot,
  events or logs. Only validated opaque `runtime:` references are allowed.
- Failure before commit leaves canonical bytes unchanged and retains the
  session for correction. Transaction failure restores original bytes or
  returns `ROLLBACK_FAILED` and blocks further writes.
- Crash recovery is idempotent and removes only transaction-owned material.
  A rollback output identity is journaled before replacement, so same-content
  external substitutions are not accepted as completed recovery.

Bounded findings include `CORE_VALIDATION_UNAVAILABLE`,
`CORE_VALIDATION_BLOCKED`, `WRITE_OWNERSHIP_REQUIRED`, `PATH_UNSAFE`,
`PROJECT_CHANGED`, `DOCUMENT_CHANGED`, `PLAN_EXPIRED`, `EDIT_SHADOWED`,
`PROJECT_LOCKED`, `SECRET_REFERENCE_INVALID`, `WRITE_FAILED`,
`ROLLBACK_FAILED` and `COMMITTED_REFRESH_FAILED`.

## 9. UI shell

UI-01D adds only the shared review/save shell:

- unsaved indicator bound to backend session state;
- `Review` action with loading/progress and bounded findings;
- review result showing semantic changes, affected documents and Core findings;
- `Save` enabled only for a current `READY` plan;
- `Discard` and explicit close/switch confirmation;
- draft retained after blocked review/commit;
- execution-state advisory: `ACTIVE_EXECUTION_USES_PREVIOUS_REVISION` only for
  an observed active run; without a known run ID UI-01D renders
  `ACTIVE_EXECUTION_STATE_UNKNOWN` and makes only the conditional immutable
  previous-revision statement.

Navigation never writes. React does not parse YAML, read `.runtime` events,
construct revision/digest semantics or decide ownership. A project switch or
close requires discard or return to editing. No UI-01D control starts an
installation or contacts a target.

## 10. Acceptance gates

### Core/remote

- real RED OS selected READY Execution Node;
- candidate request/response contract validation;
- fixed archive/path/lock digest verification;
- target-free Core validation under `sudo unshare -n`;
- project-local `ansible.cfg` proof after clearing ambient configuration:
  `env -u ANSIBLE_CONFIG ansible-config dump --only-changed`,
  `env -u ANSIBLE_CONFIG ansible-inventory -i inventory/hosts.yml --list`,
  and the fixed target-free Core operation from the candidate root;
- capability negotiation rejects a node without candidate mode and a mixed
  old/new release acceptance proves no silent downgrade;
- candidate staging cleanup on success, reject and transport failure;
- target contact sentinel proves zero target contact.

### Writer/session

- first save creates exact native documents from empty managed project;
- canonical bytes unchanged before commit;
- external/unknown files byte-preserved;
- absent-path collision blocks whole transaction;
- append after review invalidates old plan;
- append/review/discard are serialized by the bounded session store and a
  review marks the session busy; the Wails application serializes its exported
  edit calls. Project switch/close returns an explicit conflict while a
  session exists and requires explicit discard; it does not invent a second
  cancellation lifecycle;
- stale revision/document digest blocks without writes;
- expired and duplicate plan are blocked;
- disk failure rollback and crash recovery are idempotent;
- repeat with no semantic change returns `NO_CHANGE`;
- session limits, discard, project switch and close behavior pass.

### Security/portability

- Windows root/reparse/ACL tests;
- POSIX/RED OS symlink and mode tests;
- plaintext/disguised `SecretRef` rejection;
- no secrets in plan, candidate, journal, event or diagnostic output;
- `git diff --check`, JSON schema/catalog reproducibility and affected Go
  tests/race/vet/frontend gates.

UI-01D is complete only after Core-contract and safety reviews report zero
blocking findings and real first-write acceptance passes. It does not change
`CURRENT_STATE.md` to DONE before those gates.

## 11. Implementation order

1. Freeze v1alpha2/session/plan/result/request schemas and regenerate/check
   catalog/schema inputs.
2. Add bounded session store and lifecycle methods; test expiry, limits and
   plan invalidation without writes.
3. Add candidate builder, ownership/path/secret guards and absent-aware
   document changes.
4. Extend the fixed BuildProjectSnapshot candidate transport and receiver
   validation; prove cleanup and no target contact.
5. Harden and integrate create-aware transaction/recovery behavior.
6. Add minimal Wails bindings and Review/Save/Discard shell plus fixture client.
7. Run RED OS acceptance, Windows safety tests, affected regressions and
   architecture/safety reviews before owner approval or commit.

## 12. Execution Node application context and navigation gates

Execution Node selection, readiness, bootstrap and capability state are
Installer application/runtime context. They are never portable desired state
and never enter `project.yml`, `inventory/hosts.yml`, group_vars or host_vars
as an Installer-only role. A project reopened on another workstation may use a
different Execution Node.

The global application shell shows the selected Execution Node status on every
project page. The status reuses the existing execution/capability semantics:
`NOT_CONFIGURED`, `CHECKING`, `NOT_PREPARED`, `READY`, `UNAVAILABLE`,
`INCOMPATIBLE`/`UPDATE_REQUIRED` and `ERROR`. React renders this application
state; it does not invent a second readiness model. Clicking the status opens
Servers → the persistent Execution Node panel.

The Servers page has two independent regions:

```text
ServersPage
  scrollable project target-server list
  persistent bottom Execution Node panel
```

The panel is not an ordinary server row and is not an overlay. With zero
servers it remains visible and explains that the node is not configured. With
many servers only the target-server list scrolls.

Default selection is deterministic and one-time:

1. existing explicit user selection;
2. supported local Linux Installer, when eligible;
3. first eligible project server, selected once;
4. `NOT_CONFIGURED`.

Sorting, filtering, adding a server or changing table order never silently
recomputes a selection. Removing or invalidating a selected node does not
silently migrate to another host. The UI warns before removal, then requires
explicit replacement. `AUTO_LOCAL`, `AUTO_FIRST_SERVER` and `USER_SELECTED`
may be presentation metadata only; no new persistence is introduced without an
application-state contract.

Before any READY Execution Node exists, Project and Servers remain available;
Services, Topology, Certificates and Installation remain visible but locked
with an explanation. This is an application UX gate, not a Core semantic.

If a previously prepared node becomes temporarily unavailable, the current
configuration page and transient draft remain visible. The application blocks
only remote operations that require Core:

- optional Project Verify;
- `BuildDeploymentPlan`;
- installation/execution.

It does not discard the session, hide the page, block structural Review/Save or
report false validation. No local Linux shortcut bypasses the Execution Node
interface for optional Verify or mandatory planning.

Installation does not prepare the environment. Selection, host-key trust,
bootstrap, runtime activation/update and readiness preparation belong to
Servers and the existing EXEC-01A application lifecycle. Installation consumes
only:

```text
ExecutionNode = READY
AND saved canonical project
AND no unsaved session changes
THEN fresh BuildDeploymentPlan for the current revision/runtime
AND explicit approval of that plan
```

Only then may UI-02 expose DeploymentPlan → approval → StartExecution →
progress → Result. Installation may show a readiness prerequisite summary, but
must not contain an Execution Node setup card.

### 12.1 Owner decisions

- `OWNER-UI-EXECNODE-01`: global Execution Node status is visible on every
  project page and links to Servers.
- `OWNER-UI-EXECNODE-02`: Servers has a persistent bottom Execution Node panel;
  the target-server list scrolls independently.
- `OWNER-UI-EXECNODE-03`: selection priority is explicit user choice, eligible
  local Linux, first eligible project server once, then `NOT_CONFIGURED`.
- `OWNER-UI-EXECNODE-04`: selection is not continuously recomputed from list
  ordering, sorting, filtering or later additions.
- `OWNER-UI-EXECNODE-05`: selection/readiness/bootstrap are not portable
  desired state.
- `OWNER-UI-EXECNODE-06`: before first READY, only Project and Servers are
  available; other navigation remains visible but locked.
- `OWNER-UI-EXECNODE-07` is narrowed by ADR-027: temporary node loss retains
  configuration UI/draft and does not block local Save; it blocks Verify and
  remote planning/execution.
- `OWNER-UI-EXECNODE-08`: preparation belongs to Servers/application
  lifecycle, not Installation.
- `OWNER-UI-EXECNODE-09` is clarified by ADR-027: Installation execution
  requires READY plus a fresh approved DeploymentPlan for the saved revision;
  prior optional Project Verify is not required.

### 12.2 Milestone impact

UI-01D implemented the historical gate/context contract. ADR-027 removes
readiness from new local Save while retaining session outage behavior. It does not build
the full Servers panel, candidate-selection controls or bootstrap UI.

UI-01E owns target-server CRUD, the persistent Execution Node panel, automatic
candidate selection, explicit replacement, check/prepare controls and removal
or ineligibility handling. It reuses EXEC-01A contracts and does not recreate
bootstrap semantics in React.

UI-02 Installation owns deployment lifecycle only. It consumes a READY node
and current saved revision, builds a fresh authoritative DeploymentPlan and
requires approval before StartExecution; it does not select, prepare, activate
or update the Execution Node.

## 13. Mockup and acceptance references

The design mockup must show: zero servers with a bottom `NOT_CONFIGURED` panel;
one server with selected-automatically `NOT_PREPARED` and Check/Prepare/Change;
many servers with an independently scrolling list; global `READY`; temporary
unavailable warning with configuration page retained; and Installation with
only a readiness prerequisite summary. Values shown in the mockup are examples,
not Core rules.
