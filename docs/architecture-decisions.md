# Architecture decisions

## ADR-001: V2 is a separate repository

Status: Accepted.

V2 is developed in `platform-installer-v2`. V1 remains an operational reference and is not used as a source dependency.

Reason: the new contract order must not be constrained by V1 persistence, UI or execution models.

## ADR-002: Ansible Core precedes backend and UI

Status: Accepted.

The first executable product is standalone Ansible Core. Go backend work starts only after one production service proves the lifecycle and project contract.

## ADR-003: Portable Ansible project is the canonical desired state

Status: Accepted.

Standard Ansible inventory, `group_vars`, `host_vars` and role defaults are the
canonical user-owned desired state. Backend databases and frontend stores are
projections/caches. They cannot introduce desired-state concepts absent from
those ordinary Ansible inputs. `project.yml` is optional compatibility and
machine metadata, never a required user-authored desired-state document.

## ADR-004: Topology is explicit and first-class

Status: Accepted.

Service deployment, mode, members, roles, placements, dependencies and direct
`serviceDeployment.endpointGroup` assignments are explicit Ansible variables.
Resolved execution groups and runtime variables are derived. Endpoint groups
own client-facing domain/wildcard intent; provider deployments own virtual
addresses. Resolved FQDN identity and runtime ownership are read-only
projections, never generated desired state.

## ADR-005: Service catalog belongs to versioned service packages

Status: Accepted.

React may render and enhance the catalog but does not manually redefine supported service types, modes, fields or constraints.

## ADR-006: Roles remain conventionally usable

Status: Accepted.

Roles accept documented normal Ansible variables. The project resolver is one producer of resolved role variables, not a mandatory Installer-specific runtime inside every role.

## ADR-007: Derived state is immutable and disposable

Status: Accepted.

Facts, plans, resolved execution topology, generated runtime variables and results are fingerprinted outputs. They are never silently merged back into desired state. Operator-authored inventory and variable files remain desired project input.

## ADR-008: Secrets are references in desired state

Status: Accepted.

Plaintext secret values exist only in the execution boundary and are never included in project files, plans, events or ordinary diagnostics.

## ADR-009: Execution mechanism is replaceable

Status: Accepted.

The Execution Node is a selectable logical role, not a mandatory dedicated
server. Supported choices include an eligible local Linux Installer, an
eligible project target, and an external Linux host. WSL2 is a development
adapter; container and other future mechanisms may implement the same Core
invocation contract. None appear in service topology or service manifests.

## ADR-010: Compatibility is evidence-backed data

Status: Accepted.

Certified OS/runtime/service combinations are populated by integration tests. Architecture documents do not invent supported RED OS or ALT Linux versions.

## ADR-011: Kafka KRaft is the first production service

Status: Accepted.

Delivery is split into `SERVICE-01A` standalone/single-node KRaft and `SERVICE-01B` distributed KRaft. SERVICE-01A proves installation, offline artifacts, Java, configuration, systemd, basic endpoint/TLS hooks, verification and idempotency without attempting every security or listener feature. PostgreSQL modes remain contract fixtures.

## ADR-012: Standard Ansible is the standalone interface

Status: Accepted.

Initial Core operations are invoked with standard `ansible-playbook` and normal inventory, `group_vars` and `host_vars`. A proprietary launcher is neither required nor planned. A convenience CLI may be added later as an optional client only when real operational use cases justify it.

## ADR-013: Automatic placement

Status: Accepted for initial V2.

Only explicit placement is supported initially. Future automatic placement must return a deterministic, explainable proposed project patch and requires operator acceptance before changing desired state.

## ADR-014: Execution Node is a selectable logical role

Status: Accepted.

Execution Node selection is an execution concern separate from service
topology. `AUTO`, `EXPLICIT_TARGET`, `LOCAL_INSTALLER` and
`EXTERNAL_EXECUTION_HOST` are supported contract concepts. A selected target
may also be the Execution Node; in that case explicit local Ansible transport
may be used and self-target bootstrap is skipped. WSL2 remains a development
adapter and no selection is written into service manifests.

## ADR-015: Project mode and direct-role mode coexist

Status: Accepted.

The portable project resolver provides the platform workflow, while every production role remains callable with manual inventory and ordinary role variables. This prevents service automation from becoming dependent on the project editor or resolver.

## ADR-016: Project files, not SQLite, own desired state

Status: Accepted.

The future backend may index and revision projects in SQLite, but the managed Ansible project directory remains authoritative. SQLite owns discovered, execution, audit and local-environment state.

## ADR-017: Certificate profile and scope are distinct

Status: Accepted.

A profile defines issuance, key and SAN policy. A scope explicitly defines one aggregation boundary and its topology/endpoint sources. Certificates are never implicitly created per service member.

## ADR-018: Semantic YAML round trips

Status: Accepted.

Project import/export preserves semantics and declared unknown extensions. Byte-identical formatting and comments are not guaranteed, and V2 will not introduce a complex YAML AST editor without demonstrated need.

## ADR-019: One boundary-enforced monorepo

Status: Accepted.

Ansible Core, service packages, published contracts, backend and frontend start in one repository with explicit dependency rules. Core and roles remain independently testable, distributable and usable without Installer.

## ADR-020: Installer writes use reviewed Ansible-native edit plans

Status: Transaction/ownership controls remain accepted; Core-approved Save
authorization is superseded by ADR-027 for new Installer sessions.

Go is the Installer application backend. It owns semantic edit commands,
in-memory review-plan lifecycle, concurrency guards and filesystem
transactions. Python/Ansible remains the infrastructure authority: it loads
standard inventory and variables, applies its normal precedence, and builds
the authoritative validation and ProjectSnapshot projections. Go does not
reimplement those Core semantics.

The Installer opens supported standard Ansible projects without converting
them to another desired-state model. Arbitrary existing projects are read-only
by default. The bounded writable layout uses explicitly Installer-owned
ordinary Ansible documents: `group_vars/all/platform-installer.yml` owns
`platform_desired_state`, while `host_vars/<host>/platform-installer.yml` owns
each host's `platform_deployments`. Existing human-owned files and subtrees
are not mutated without a separate adoption decision.

A semantic command produces a bounded local structural preview by staging only
owned documents. Optional Core Project Verify is separate from Save. Commit
rechecks the raw-byte project revision and affected document digests
under a project writer lock. It journals exact old bytes, performs synced
atomic replacements, rolls back a failed multi-document write and recovers an
interrupted journal before a later commit. The terminal state is either the
entire original document set or the entire approved set. The frontend never
saves a rewritten ProjectSnapshot, and SQLite never stores an independently
editable desired-state copy.

## ADR-021: Pre-Core bootstrap uses a verified offline runtime bundle

Status: Accepted for EXEC-01A.

An Execution Node may not have Python, Ansible or Platform Core when selected.
Go therefore owns the narrowly scoped pre-Core bootstrap lifecycle: explicit
SSH host-key trust, inspect, bundle acquisition/transfer, staged activation and
READY classification. It must not infer project, catalog, topology or service
semantics.

Core and Python execute only on the selected Execution Node. The workstation is
limited to Go orchestration, SSH/SCP, verification of a returned bundle and
atomic publication into the immutable local cache. A fresh install target
cannot build the bundle that is required to install its own Python/Core; an
explicit DEV acquisition therefore uses a trusted acquisition environment
that already has the builder runtime, while the install target remains a
consumer of the verified result.

The runtime distribution is a separately usable versioned directory beside the
Installer. Its manifest declares compatibility identity and SHA-256 for every
component. Go validates that manifest and its root-contained regular files
before transfer. A local package closure may be explicitly acquired from a
trusted Execution Node's configured repositories, with per-file verification,
then atomically published into the local offline bundle. Preparation itself
never downloads packages or enables repositories.

After activation, Core owns the first capability handshake and all later
infrastructure lifecycle. The active runtime changes only after staged
verification; an interrupted or failed update leaves the prior runtime intact.
## ADR-022: Unified repository-first offline-bundle fallback

Installation resolves each requirement against the configured approved
repository of the actual install node first, then against the compatible
content in the Installer's single logical offline bundle. If neither source
can satisfy the required compatibility, the operation is blocked. The
repository result of an Execution Node is never reused for a managed target.

DEV may explicitly acquire an exact dependency closure from an approved
repository through a trusted Linux acquisition environment and publish a new
immutable bundle atomically. PROD may consume repositories, but never mutates
the distributed bundle or acquires into it. The same source selection semantics
apply to Execution Node preparation and service package installation; only the
acquisition capability differs.

## ADR-023: Core plans and a fixed Execution Node controller own execution semantics

Status: Accepted by UI-BE-04A; implementation is gated by UI-BE-04B through
UI-BE-04E.

Platform Core owns the public deterministic `DeploymentPlan`, its semantic
fingerprint, action ordering and the private trusted `ExecutionManifest`.
Service packages retain their apply/verify/reconcile lifecycle semantics and
declare the trusted package entrypoints consumed by Core. Go owns application
review, one-shot approval, session coordination, replay/reconnect and semantic
cancel requests, but never derives the private manifest, selects a playbook or
reimplements service/provider ordering.

Planning is controller-only and target-contact-free. It declares artifact
requirements but does not probe repositories or select `REPOSITORY` versus
`OFFLINE_BUNDLE`; the existing EXEC-01A target probe, resolver,
RuntimeProjection and Ansible gates remain the execution-time authority.

Execution uses a fixed versioned machine protocol and one fixed Core controller
started in a detached transient systemd unit. The caller cannot submit shell,
argv, playbook paths or arbitrary commands. Durable ownership binds run,
project, plan, private manifest, controller journal and unit identities; a PID
alone is insufficient. Disconnect does not cancel a run. The Execution Node
enforces one active mutating run per project and owns bounded journal, event
replay, terminal-result, cancellation and interrupted-run recovery semantics.

## ADR-024: Managed empty projects and complete-candidate first save

Status: Accepted by UI-01A.

Creating a project publishes only a schema-valid `project.yml`. It contains a
generated stable identity, display name, desired-state contract, complete
catalog/artifact locks from one verified local immutable bundle, and the
lifecycle-immutable `platform.installer/managed-project: v1alpha1` consent
label. It creates no
inventory, variable files, implicit hosts or service deployments. The marker
distinguishes an intentionally empty managed project from an incomplete
external project; empty lifecycle status itself is derived and not persisted.

For this UI creation profile, artifact lock digest is the verified SHA-256 of
the bundle `manifest.yaml`, catalog lock digest is that manifest's catalog
digest, and service locks come from the matching catalog. The UI submits only
an opaque verified compatibility-source handle. This mapping is versioned as
`ProjectCompatibilitySource/v1alpha1`; it does not settle general CONTRACT-01
migration rules.

The first save builds one complete temporary candidate containing fixed
Installer-owned `ansible.cfg`, `inventory/hosts.yml`, managed group_vars and
only required managed host_vars. Core validates the whole candidate with normal
Ansible loading before an EditPlan can be committed. Planning changes zero
canonical bytes. Commit rechecks project revision, existing document digests,
planned absence, path ownership and symlink/reparse safety, then publishes all
documents through the journaled atomic transaction.

The fixed inventory has every declared server in `all.hosts` and
`platform_targets`, no implicit localhost, and no runtime user or credential.
The fixed project configuration selects that inventory and preserves the
required merge, host-key-checking and interpreter policies without embedding
workstation/runtime paths or privilege-escalation policy.

Whole-file ownership of inventory and ansible.cfg is granted only by the
managed-project marker and only when those paths do not already exist.
Arbitrary/external projects remain read-only for inventory; adoption is a
separate future decision. Unknown files and user-owned YAML are preserved.

First save uses `project-edit/v1alpha2`, whose document preconditions represent
both PRESENT+digest and ABSENT explicitly and whose path allow-list includes
only the fixed managed project files. Project lifecycle, edit sessions and
remote snapshot request are separately versioned typed application contracts;
none exposes raw YAML, paths to Core, shell or generic SSH.

Editor navigation and transient drafts do not require a current execution run,
repository probe, RuntimeProjection or target facts. Per ADR-027, local
structural Review/Save uses the guarded writer without Python/Core or an
Execution Node. Optional Project Verify and fresh DeploymentPlan construction
remain target-free Core operations on READY. Runtime credentials remain outside
canonical project state. Execution progress reaches future React only through
typed Go/RunObserver subscriptions.

UI mutation remains disabled until the writer has OS-specific Windows reparse
checks, safe runtime journal/recovery paths, bounded canonical-only candidate
archives and strict runtime secret-reference values. Target credentials use one
write-only, expiring session lease shared across targets; transporting its
secret to an Execution Node is a separate fixed runtime operation and is never
part of project save.

## ADR-025: Execution Node is global application context

Status: Accepted by the UI architecture update, 2026-09-05.

Execution Node selection, readiness, capability, bootstrap and activation are
Installer application/runtime context. They are not portable desired state and
must not be written to `project.yml`, `inventory/hosts.yml`, `group_vars` or
`host_vars` as an Installer-only role. A project may be opened on another
workstation and use another Execution Node. Supported local Linux still uses
the same Execution Node semantic interface; it is not a workstation bypass.

The global shell shows the current Execution Node state on every project page.
Servers owns a persistent bottom Execution Node panel, while the ordinary
target-server list scrolls independently. Selection is deterministic: explicit
user choice, eligible local Linux, first eligible project server once, then
`NOT_CONFIGURED`. Later sorting, filtering, additions or removal do not silently
switch a previously selected node; replacement is explicit.

Before the first READY node, currently implemented Project and Servers remain
available. Future editor availability is milestone-gated, not a prerequisite
for local Save. Temporary loss retains the current page and transient session;
it blocks Project Verify and remote planning/execution, but not structural
Review/Save. It does not discard draft state or claim validation success.

Servers/application lifecycle owns selection, host-key trust, bootstrap,
runtime preparation and activation through EXEC-01A. Installation owns only
the deployment lifecycle. Prior Project Verify is optional; every execution
still requires READY, saved canonical state, no unsaved changes and a fresh
authoritative DeploymentPlan for the same revision/runtime.

## ADR-026: Application config owns selectable server types

Status: Accepted as `OWNER-APP-CONFIG-01` and `OWNER-APP-CONFIG-02`,
2026-09-14.

Installer uses one versioned `config/application.yml` contract for bounded
application/product behavior. It is not portable infrastructure desired state
and cannot contain service defaults, topology, PKI, placement, credentials,
target addresses, Execution Node policy or source-selection rules.

Every server newly created by Installer has one stable type ID. The canonical
ID is stored as `platform_host.type`; localized display labels and the
selectable list remain in application configuration. Portable validation uses
grammar only, so a valid type unknown to the current workstation remains
readable and unchanged. Such a mismatch is a nonblocking Installer diagnostic
and never changes Core snapshot status, validation or fingerprint.

`project-edit/v1alpha2` remains immutable. Additive
`project-edit/v1alpha3` requires `CreateServer.type`; both versions normalize
into the same Go `EditCommand` model, and new Installer sessions emit v1alpha3.
Missing or invalid AppConfig blocks only AppConfig-dependent creation and does
not block read-only Core interpretation of existing projects. Production
embedding, override and distribution policy is a separate future decision.

## ADR-027: Save, Project Verify and DeploymentPlan are separate operations

Status: Accepted by `OWNER-UI-SAVE-VERIFY-01` through
`OWNER-UI-SAVE-VERIFY-06`, 2026-09-15.

Save is a local Go application operation over the existing typed EditSession,
bounded managed candidate and guarded filesystem transaction. It proves
structural/write safety only and requires neither Core nor an Execution Node.
A saved canonical project may therefore be `UNVERIFIED`, `INVALID` or `STALE`
without preventing later editing or Save. Verification evidence is derived
runtime state, never portable desired state.

Project Verify is an optional target-free Core preflight for the exact last
saved canonical revision on a READY Execution Node. It never saves an unsaved
overlay or mutates project files. E5 may automatically check readiness and may
prepare only after explicit confirmation.

Fresh `BuildDeploymentPlan` remains the mandatory execution gate for the exact
current saved revision/runtime. Prior Project Verify never permits direct
`StartExecution`, and Installation may request a fresh plan regardless of the
optional verification badge. See
[the binding owner-change architecture](ui-save-verify-architecture.md).
