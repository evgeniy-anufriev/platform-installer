# UI-01E1 — Server model / CRUD integration architecture

Status: **DONE** (2026-09-14). This document defines the backend and contract
integration for server CRUD. UI-01E2 owns the production Servers page and its
Add/Edit/Delete dialogs.

> **Owner supersession, 2026-09-15:** ADR-027 and
> [Save / Project Verify / DeploymentPlan](../ui-lifecycle/ui-save-verify-architecture.md)
> replace every statement below that makes target-free Core Review/PASS or a
> READY Execution Node a prerequisite for Save. Server fields, v1alpha4 typed
> intents, final-state reducer, source ownership, revision/digest guards and the
> generic reference contract remain unchanged. Core-backed candidate proof is
> historical acceptance evidence, not new Save authorization.

## 1. Goal

Make server creation, partial update and deletion work for an existing
Installer-managed project through the revised UI-01D lifecycle:

```text
saved/local managed server view
        ↓
typed project-edit/v1alpha4 intent
        ↓
EditSessionStore
        ↓
Installer local structural candidate/review
        ↓
existing revision/digest-guarded CommitEditPlan transaction
        ↓
canonical saved revision (`UNVERIFIED` or `STALE`)
        ↓ optional
target-free Project Verify on READY
```

There is no `SaveServer`, direct YAML mutation, UI-owned project model or
second desired-state store.

## 2. Position in UI-01E

The owner-approved UI-01E decomposition is:

1. UI-01E1 — Server model / CRUD integration;
2. UI-01E2 — Servers page + Add/Edit/Delete;
3. UI-01E3 — shared runtime session credentials;
4. UI-01E4 — Execution Node bottom panel + auto-selection;
5. UI-01E5 — readiness/preparation + navigation gating;
6. UI-01E6 — Windows/RED OS acceptance + regressions.

UI-01E1 supplies the backend behavior consumed by E2. It does not pull E2-E6
forward.

## 3. Closed architecture decisions

The four blocking architecture findings are resolved as follows:

| Decision | Resolution |
| --- | --- |
| UI01E1-ARCH-001 | Command history and authoritative proof are separated. Commands reduce in order, but review derives one final-state expectation per affected host and proves only that final state. |
| UI01E1-ARCH-002 | `project-edit/v1alpha2` remains behaviorally compatible. Completeness requirements for legacy hosts apply only to new v1alpha4 sessions. |
| UI01E1-ARCH-003 | `ansiblePort` has an exact normalized integer contract, range, default, invalid-value behavior, precedence semantics and fingerprint rules defined below. |
| UI01E1-ARCH-004 | `desiredHostname` is canonical desired state. An additive `project-edit/v1alpha4` carries it; v1alpha2 and v1alpha3 remain immutable. E1 edits and projects it, minimally updates the existing UI-01D first-save form to supply it, while E5 owns applying it to target hosts. |

Four additional contract clarifications are part of the final decision:

- omitted `sshPort`, explicit `sshPort: 22` and `clearSSHPort: true` are three
  distinct intents;
- `DeleteServer` consumes only a generic Core reference contract;
- canonical `server.type` participates in project/snapshot identity, while
  membership of that value in local AppConfig does not;
- `UpdateServer` is a deliberately closed semantic field update, not a generic
  patch mechanism.

The earlier overengineering review found no blocking abstraction. The single
managed-inventory helper remains justified; no parallel server DTO, store,
lifecycle or generic YAML framework is introduced.

## 4. Design and mockup reconciliation

This plan was checked against `docs/design/ui-design-01-mockups.html`,
`docs/design/ui-design-01.md`, `docs/work/ui-01/ui-01.md`, the UI-01A contract freeze and the
accepted UI-01D implementation.

E1 models the desired fields represented by the Servers screen and dialog:

- immutable inventory host ID;
- required server type for newly created servers;
- required desired hostname for newly created servers;
- address;
- effective SSH port.

`desiredHostname` is the hostname that server preparation will install on the
target. E1 persists and projects the intent but never contacts a target; the
idempotent hostname preparation behavior belongs to E5.

The later UI must keep desired and observed state distinct. Observed hostname,
operating system, architecture, CPU, RAM, reachability and readiness are not
canonical CRUD fields. Per-server SSH username and authentication method are
also excluded because credentials are shared runtime session input owned by
E3 and are never persisted in the portable project.

For E2, the modal action remains labelled **Сохранить**. Its tooltip explains:
«Сохранить изменение в черновик. Файлы проекта будут изменены только после
проверки и общего сохранения проекта». This is a UI decision, not a second save
mechanism: the action appends a typed intent and canonical files change only
through Review → Commit.

The existing narrow UI-01D first-save form is the only frontend compatibility
change in E1: it gains required `desiredHostname` input and emits it through
v1alpha4 `CreateServer`. This keeps the accepted first-save path usable when
new sessions switch to v1alpha4; it is not the production Servers editor.

The following mockup elements remain deferred:

- rendered Servers table and dialogs — E2;
- shared session credential input — E3;
- facts, reachability and connection checks — E3/E5;
- persistent Execution Node panel and auto-selection — E4;
- preparation, readiness and navigation gating — E5.

## 5. Ownership

| Concern | Authority |
| --- | --- |
| Server identity | inventory host ID in the portable project |
| Address and SSH port | ordinary effective Ansible variables projected by Core |
| Server type | `platform_host.type` in the portable project |
| Desired hostname | `platform_host.desiredHostname` in the portable project |
| Type choices and labels | versioned local application config |
| Edit/session/review/transaction lifecycle | Go Installer backend |
| Local structural/write safety | Go managed-project writer |
| Ansible precedence and infrastructure validity | optional Project Verify and mandatory fresh DeploymentPlan through Core |
| Non-cascading delete/source ownership guard | Go managed-project writer |
| Rendering and form state | React in E2 |
| Credentials, host-key trust, facts and readiness | runtime state in E3-E5 |
| Applying desired hostname to a target | idempotent preparation workflow in E5 |

The portable Ansible project remains canonical desired state. Local
application configuration is never copied into the project. Server type is
descriptive metadata only and cannot select services, placement, an Execution
Node or an artifact source.

## 6. Additive edit contract v1alpha4

The published contracts remain immutable:

- `project-edit/v1alpha2` is compatibility-only and retains its original
  decoding and update behavior;
- `project-edit/v1alpha3` remains unchanged and retains required `type` on
  `CreateServer`;
- E1 introduces additive `platform.installer/edit-command/v1alpha4`;
- new Installer edit sessions emit v1alpha4 only;
- all three versions normalize into the same internal Go `EditCommand` and
  server reducer. No version-specific Server DTO is added.

v1alpha4 operations are:

```text
CreateServer:
  hostId + type + desiredHostname + address + optional sshPort

UpdateServer:
  hostId + at least one of
  type / desiredHostname / address / sshPort / clearSSHPort

DeleteServer:
  hostId
```

`UpdateServer` is a closed semantic patch over exactly `type`,
`desiredHostname`, `address` and SSH-port intent. Field omission means
“preserve the current canonical value”. JSON `null`, arbitrary object keys,
JSON Pointer/path operations, nested map merging and generic JSON Merge Patch
semantics are not supported. Removal is available only through an explicitly
declared semantic command field such as `clearSSHPort: true`. The closed schema
and `unevaluatedProperties: false` enforce this boundary.

`EditCommand` gains only the optional internal `DesiredHostname` field needed
by the shared reducer. Existing `EditSession`, `EditPlan`, `EditCommitResult`,
session limits and command limits remain unchanged.

For a v1alpha4 update of a legacy host, any missing required current-session
metadata (`type` or `desiredHostname`) must be supplied before review. This
does not apply retroactively to v1alpha2/v1alpha3 commands and does not mutate
a project merely because it was opened. A grammar-valid type absent from the
current local application config remains a non-blocking Installer diagnostic.

## 7. Additive Core host projection

The server read model remains `ProjectSnapshot.hosts[hostId]`; no `ServerDTO`
or local repository is added. E1 extends the existing host object with
`desiredHostname` and normalized `ansiblePort`:

```json
{
  "hosts": {
    "node1": {
      "ansibleHost": "192.168.56.101",
      "ansiblePort": 22,
      "type": "infra",
      "desiredHostname": "node1.example.internal"
    }
  }
}
```

Projection rules:

- Core derives values from loaded Ansible variables. Go and React never merge
  inventory, group_vars or host_vars.
- `ansiblePort` is a JSON integer in the inclusive range 1..65535.
- An absent effective `ansible_port` projects as integer `22`.
- An Ansible integer or canonical decimal string in range normalizes to the
  same JSON integer. Booleans are not integers for this contract.
- A present non-decimal, unresolved, boolean or out-of-range value produces
  structured blocking Core finding `HOST_TRANSPORT_PORT_INVALID`; the
  snapshot is not `PASS` and no edit plan can be created.
- Legacy missing `platform_host.type` or
  `platform_host.desiredHostname` remains readable and is not backfilled on
  open.
- `desiredHostname` uses the existing canonical host desired-vars grammar and
  is optional only for legacy read compatibility.
- Canonical `platform_host.type` is included in the host projection and
  therefore affects `projectRevision` and `snapshotFingerprint` when its
  project value changes.
- Whether that canonical type ID is present in the workstation's local
  AppConfig affects only the Installer diagnostic
  `UNKNOWN_CONFIGURED_SERVER_TYPE`. Adding/removing/relabeling an AppConfig
  entry does not alter project bytes, Core status, Core validation,
  `projectRevision` or `snapshotFingerprint`.

Fingerprint and clear-port rules are explicit:

- absent `ansible_port` and explicit `ansible_port: 22` produce the same
  effective `hosts[*].ansiblePort` value;
- their source bytes differ, so `projectRevision` differs;
- because `snapshotFingerprint` includes the complete canonical snapshot,
  including `projectRevision`, it also differs;
- `clearSSHPort: true` removes only the Installer-owned inline host override;
  it does not promise port 22 because a higher-precedence source may provide a
  different effective value;
- after clear, Core projects the actual effective port. Source removal is
  proven against the staged managed document and effective behavior is proven
  against the final Core snapshot;
- setting `sshPort` requires the final Core value to equal the requested
  integer. A higher-precedence value that shadows it yields `EDIT_SHADOWED`.

The three SSH-port command states are intentionally different:

| Intent | Managed inventory write | Final proof |
| --- | --- | --- |
| `sshPort` omitted | Create writes no inline `ansible_port`; Update preserves the existing inline key or absence unchanged. | No explicit requested-port assertion; Core reports the inherited/default effective port. |
| `sshPort: 22` | Write an explicit inline integer `ansible_port: 22`; do not canonicalize it to absence. | Core effective port must be exactly 22 or review fails with `EDIT_SHADOWED`. |
| `clearSSHPort: true` | Update only: remove the Installer-owned inline `ansible_port` key. | Prove source-key absence, then accept the effective inherited/default Core value, which is not necessarily 22. |

`sshPort` and `clearSSHPort` are mutually exclusive, and
`clearSSHPort` is not valid for `CreateServer`. This field-presence distinction
must survive JSON decoding; a zero-value Go integer is not used to infer
whether `sshPort` was supplied.

No username, password, private-key path, host-key trust, facts or readiness
are added to `ProjectSnapshot.hosts` by E1.

## 8. Managed inventory adapter

E1 adds one small internal adapter around the existing managed YAML loader. It
operates only on a marked Installer-owned `inventory/hosts.yml` and exposes
the two owned maps required by the frozen layout:

```text
all.hosts
all.children.platform_targets.hosts
```

Every managed server must occur exactly once in both maps. The adapter:

- uses `safeProjectPath` and `parseManagedYAML`;
- rejects missing or wrongly shaped owned roots instead of silently repairing
  them;
- retains unrelated keys in the fully owned document while deterministic YAML
  serialization normalizes formatting;
- never adopts or rewrites unmarked/user-owned inventory;
- never reads service rules or calculates resolved topology;
- stages every change before a canonical write.

Host identity is immutable. Rename is not modeled as delete plus create and is
outside UI-01.

## 9. CRUD semantics

### CreateServer

The reducer rejects an ID already present in either managed map, adds the host
to both maps, and writes `ansible_host`, `platform_host.type` and
`platform_host.desiredHostname`. It writes `ansible_port` whenever `sshPort`
is explicitly present, including explicit value 22; omission writes no inline
port key.

### UpdateServer

Only explicitly supplied closed properties change. Omitted address, port,
type and desired hostname are preserved. Explicit `sshPort`, omitted
`sshPort`, and `clearSSHPort` follow the table in section 7. Current-session
completeness for a legacy host follows section 6; older command contracts keep
their compatibility behavior.

An unknown but grammar-valid type is preserved when omitted and remains a
non-blocking Installer diagnostic. Desired hostname is desired state only;
changing it does not run preparation.

### DeleteServer

Deletion removes only the server identity from `all.hosts` and
`platform_targets`. It never cascades to a service deployment, member,
endpoint, certificate or another server.

`DeleteServer` queries a generic authoritative reference contract by target
identity `{targetKind: "host", targetId: hostId}`. Core returns zero or more
safe generic records containing reference kind, source identity and canonical
field path. Go knows only that a non-empty result means the target is in use;
it emits stable `REFERENCE_IN_USE` and may show those safe generic records in
review. Go must not enumerate Kafka, PostgreSQL, PKI, endpoint, placement or
any other service-specific reference rules. New service packages extend Core
reference discovery without a Go change.

The Go managed-project writer remains authoritative only for ownership, safe
path and non-cascading mutation mechanics. Core owns generic reference
discovery and validates the complete remaining candidate. The source guard
must run against the evolving staged candidate so references created or
removed earlier in the same session are observed.

A non-empty Installer-owned host placement document is never silently
deleted. A managed host-vars document is considered inert only when it has the
expected ownership marker and contains no semantic managed values or
references after normalization; such a file may remain. User-owned host_vars
are preserved. E1 does not expand the hardened transaction engine with file
deletion solely for cosmetic cleanup.

Deleting the final server is not prohibited by Go. Core decides whether the
full resulting candidate is valid.

## 10. Ordered session and final-state proof

Commands reduce in session order against one evolving in-memory candidate.
Existence and duplicate checks therefore observe earlier commands in the same
session. Semantic command history is retained for review summaries, but it is
not used as a list of intermediate states that the final snapshot must satisfy.

After all commands are reduced, the backend derives exactly one final-state
expectation for each affected host from the final staged candidate:

- `exists=false`; or
- `exists=true` with final address, type, desired hostname, explicit-port
  source state and effective-port expectation as applicable.

Core and source proof evaluate that final expectation once. Required sequence
semantics are:

- Create → Update: allowed; prove the final merged server;
- repeated Update of one field: last explicit value wins;
- Update of different fields: changes merge;
- Create → Delete: net-zero candidate bytes, therefore `NO_CHANGE` and no
  commit plan;
- Delete → Create with the same ID: blocked as
  `SERVER_RECREATE_IN_SESSION_UNSUPPORTED` to avoid hidden replacement and
  reference ambiguity;
- Update after Delete and duplicate Create remain blocked.

The bounded Batch used by `ReviewEditSession` remains. Appending after review
invalidates the previous opaque plan exactly as in UI-01D. E1 adds no undo
history, draft persistence or client-side reducer.

## 11. Revised local Save and optional proof

For every non-empty candidate diff:

1. read the current managed source view and verify `baseProjectRevision`;
2. reduce typed commands into one bounded local candidate;
3. validate structural shape, ownership, paths and document before states;
4. produce a local affected-document preview;
5. commit only through the existing journaled transaction;
6. return the new canonical revision as `UNVERIFIED` or `STALE`.

Optional Project Verify later asks Core to validate exactly that saved revision.
Before execution, fresh `BuildDeploymentPlan` remains mandatory regardless of
the optional Verify result. Historical E1 Core candidate acceptance below
proves the old implementation, not a prerequisite for the revised Save.

Impact reporting follows actual semantics:

- create/delete/address/port changes report `SERVER_INVENTORY_CHANGED`;
- type-only changes report `SERVER_METADATA_CHANGED`;
- desired-hostname changes report `SERVER_PREPARATION_CHANGED`;
- `TOPOLOGY_CHANGED` is reported only when the authoritative snapshot diff
  shows an actual topology change;
- existing endpoint, PKI or configuration impacts are added only when their
  derived projections actually change.

No apply, bootstrap, hostname change, connectivity check or target contact is
triggered by server CRUD.

## 12. Failure behavior

E1 preserves or adds stable blocked outcomes for:

- invalid, duplicate or missing server identity;
- missing v1alpha4 type or desired hostname when required;
- invalid address, desired hostname or SSH port;
- `HOST_TRANSPORT_PORT_INVALID` from Core projection;
- create of an existing host;
- update/delete of an absent host;
- same-session delete/recreate;
- server reference warning/optional Verify invalid result from generic records;
- inconsistent managed inventory membership;
- unmarked or user-owned inventory;
- stale project revision, expired session/plan and superseded review;
- local candidate structural failure; optional Project Verify findings are
  separate and never undo Save;
- transaction conflict, unsafe path, symlink/reparse point or recovery failure.

Errors and plans contain no credentials. Unknown configured type is a warning,
not a blocked outcome.

## 13. Implementation slices

1. Add immutable v1alpha4 schema, decoder compatibility matrix and focused
   v1alpha2/v1alpha3 immutability tests.
2. Extend Core host projection with deterministic `desiredHostname` and
   `ansiblePort`, including default, normalization, invalid-value and
   fingerprint tests, and expose generic host-reference discovery needed by
   safe deletion.
3. Add the narrow managed-inventory helper and ordered server reducer under
   `internal/installer`.
4. Integrate all operations into `applyCommand` and final-state
   `proveSnapshot`, retaining the existing plan store, staging and transaction
   code.
5. Permit exactly the server operations at the existing Wails
   `AppendEditCommand` boundary and generate application-config diagnostics
   for explicit or preserved unknown types.
6. Add required `desiredHostname` to the existing narrow UI-01D first-save form
   and its v1alpha4 command mapping. Do not add the Servers page.
7. Add focused backend/session/Wails tests and a frontend regression proving
   first save reaches local structural Review → Save with required hostname.
8. Synchronize milestone evidence only after executable acceptance passes.

## 14. Acceptance

UI-01E1 is complete only when automated tests prove:

- v1alpha2 and v1alpha3 schemas and behavior remain unchanged;
- new sessions emit v1alpha4 and CreateServer requires type and desired
  hostname;
- the existing first-save form requires and sends desired hostname, and its
  local structural Review → Save flow remains functional before UI-01E2;
- create, partial update, type/desired-hostname replacement, port set/clear
  and delete;
- absent port, explicit 22, numeric string, invalid value, precedence shadow
  and clear-to-inherited-port behavior;
- omitted port, explicit port 22 and clear-port remain distinct through decode,
  staged source and final proof;
- projectRevision and snapshotFingerprint behavior for absent versus explicit
  port 22;
- changing canonical server type changes project/snapshot identity, while
  changing only local AppConfig membership or display label does not;
- duplicate create and absent update/delete are blocked;
- v1alpha4 legacy-host completion is enforced without v1alpha2 backfill;
- unknown valid type is preserved and warning-only;
- referenced-host deletion is blocked without cascade;
- DeleteServer uses generic Core reference records and has no service-specific
  reference knowledge in Go;
- UpdateServer rejects null, unknown fields and generic patch/path payloads;
- Create → Update, repeated Update, disjoint Update and Create → Delete have
  the exact semantics in section 10;
- Delete → Create is blocked with its stable code;
- review proves one final state per affected host, not every intermediate
  state;
- before Review and before Commit, canonical project digests are unchanged;
- Core validates the full staged candidate and proves host state;
- commit changes only the reviewed managed document and refreshes the snapshot;
- stale revision/plan, ownership and path-safety guards remain intact;
- unmarked inventory remains byte-identical;
- no target server is contacted during snapshot/review.

Required focused gates:

```text
go test ./internal/installer ./internal/coreadapter .
go test ./...
go vet ./...
frontend test
frontend lint
frontend build
RED OS Core host-projection and staged-candidate acceptance
catalog/schema reproducibility
secret audit
git diff --check
```

RED OS acceptance uses the current worktree in a temporary QA workspace,
remains target-free and proves cleanup. Full Windows UI interaction, shared
credentials, target preparation and end-to-end UI regressions belong to E2-E6.

### Historical implementation evidence (2026-09-14, before ADR-027)

- New sessions emit the deliberately server-CRUD-only
  `project-edit/v1alpha4`; v1alpha2/v1alpha3 tests remain compatible.
- The existing first-save compatibility form now requires desired hostname and
  reached the then-current Core-backed Review → Commit lifecycle; it is not a Servers
  page or a direct writer.
- Core projects `desiredHostname`, normalized `ansiblePort`, and generic host
  reference records. The Go reducer owns no service-specific delete rules.
- Local gates passed: focused Go tests, `go test ./...`, `go vet ./...`,
  frontend Vitest (7 tests), lint, production build, and
  `wails build -nopackage -clean`.
- A fresh RED OS QA workspace passed 242 Core tests (4 skipped), fixture-catalog
  and configuration-schema reproducibility, and
  `go test -race ./internal/installer ./internal/coreadapter`; the temporary
  workspace was removed. The checks are target-free.
- Added-line secret audit and `git diff --check` passed. Per owner direction,
  no additional reviewer loop was run for this milestone.

## 15. Non-goals

- production Servers page or Add/Edit/Delete dialogs beyond the narrow
  first-save compatibility form;
- per-host or shared credentials;
- SSH connection checks, facts or host-key trust;
- Execution Node selection, preparation, readiness or navigation gating;
- applying `desiredHostname` to a target before E5;
- server rename, delete/recreate replacement or bulk import;
- automatic legacy migration/backfill;
- topology/member editing or cascading delete;
- generic YAML adoption;
- service apply/verify or runtime execution;
- a new persistence layer, Server DTO or save mechanism.

## 16. Overengineering check

The design adds one additive command-contract version, two fields to the
existing Core host projection and one internal managed-inventory helper. It
reuses the current command model, session, candidate snapshot, plan store and
transaction lifecycle. File-deletion support, draft persistence, generic YAML
round-tripping, a server repository and a separate Wails CRUD API remain
unjustified and excluded.
