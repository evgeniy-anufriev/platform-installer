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

Project import/export preserves semantics and declared unknown extensions. Owner-approved export naming updates only the copied optional `project.yml` metadata.name to the export directory name, retaining the project ID and untouched source; preview describes the renamed output while source revision guards stay original. Byte-identical formatting and comments are not guaranteed, and V2 will not introduce a complex YAML AST editor without demonstrated need.

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
then atomically published into the local offline bundle.

Owner-approved EMPTY-PACKAGES-BOOTSTRAP-01 (2026-10-13) permits a runtime bundle
with empty packages. The builder discovers compatibility from populated payload
directories, explicit `--platform OS:VERSION:ARCH`, or Linux `/etc/os-release`
plus `uname -m`. Preparation uses installed runtime prerequisites first, then
verified bundle RPMs. Only prerequisites absent from both may be obtained with
DNF from the node's existing configured approved repositories; it never adds or
enables repositories or substitutes a download after corrupt/incomplete offline
input. This is a fixed pre-Core runtime exception, not a service source-policy
change. A package-empty bundle is repository-dependent for an unprovisioned node.
Owner clarification (2026-10-13, EMPTY-PACKAGES-BOOTSTRAP-01): DNF may update
already installed dependencies while installing missing runtime prerequisites.
When all prerequisites are installed, preparation performs no package transaction.
Actual React/Wails Prepare/READY acceptance is outside this implementation stage;
its absence does not constitute verified application-flow acceptance.

Bootstrap is a fixed manifest-bound shell resource executed from root-owned,
reverified content before Python/Ansible. Bootstrap and activation are separate
SSH phases; cancellation cannot dispatch activation after interrupted bootstrap.
Node-scoped flock and immutable same-digest release reuse protect concurrent
preparations. Failed capabilities preserve the prior release/current/active
metadata; OS package installation may remain after a later preparation failure.

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
[the binding owner-change architecture](work/ui-lifecycle/ui-save-verify-architecture.md).

## ADR-028: Remote browser access uses the environment network boundary

Status: Accepted by the owner for BROWSER-REMOTE-01/02, 2026-10-06.

The Linux Go application may serve the existing React UI over an explicitly
configured `host:port` so one operator workstation can use it remotely. The
deployment environment must restrict that listener to the browser workstation
and localhost on the Linux host; all other sources are denied. The environment
team owns the rule and its evidence. The Installer does not provide
authentication, TLS, reverse-proxy, Keycloak or firewall management in this
milestone. The later deployment is expected to place the service behind a
443/TLS load balancer with Keycloak.

This is a one-workstation browser transport over the existing Go `App`, not a
multi-user service or a new application authority. React uses the same typed
backend interface for browser and Wails transports. Project paths supplied by
the browser refer to the Linux host and remain subject to existing Go path and
transaction checks. An encrypted runtime-secret file selected on the browser
workstation is submitted in memory to its single typed import operation; the
file name is not sent and plaintext secret values remain runtime-only.

### ADR-029: Remote Browser HTTP is dev-only until v1.0 HTTPS

Status: Accepted by the owner, 2026-10-06; restricts ADR-028 until the v1.0
security work is complete.

The current remote Linux Browser transport uses plain HTTP while carrying
credentials and encrypted runtime-secret file bytes. Source-IP restrictions do
not protect those values in transit. Remote Linux Browser HTTP is allowed only
in development with explicit `-browser-allow-insecure-dev-http` opt-in; it is
not accepted for production systems or data. HTTPS, explicit external HTTPS
origin handling, and negative origin/transport tests are scheduled for v1.0.
Local Windows Browser mode and Wails mode are unaffected.

## ADR-030: BIND point updates retain removed endpoints until explicit reconcile

Status: Accepted by the owner for Execution Order 01, 2026-10-07.

Base BIND Apply owns project hosts, SOA and only endpoint-group wildcard
records whose existing `address.wildcard` setting is `true`. A source service
with an endpoint may idempotently publish only its exact DNS record; this path
does not delete a record when the endpoint is later removed or unlinked. Such
records remain until an operator explicitly runs the existing full BIND
`reconcile.yml`, which retains its complete-model deletion behavior and stays
opt-in.

The managed primary uses BIND `update-policy local;` instead of
`allow-update { none; };` for the managed zone. The generated host-local key is
root-readable only. The update task sends only the resolved zone and exact
source owner, but the local key itself is zone-wide authority, not a per-source
ACL; this is an explicitly accepted host-local privileged boundary. Key bytes
must not appear in events or task output.

Before full reconciliation replaces a dynamically updated zone, it synchronizes
the BIND journal and uses the SOA serial actually served by the primary as the
lower bound for a validly newer candidate serial. A machine-runtime per-zone
recovery marker remains until the role proves the zone authoritative and
writable after thaw/recovery. Ansible cleanup attempts thaw on post-freeze
failure, and the next BIND operation recovers any marked zone before normal
work. The marker is runtime recovery data, not project desired state or a
second persistence database. Standalone Ansible retains the same behavior.

## ADR-031: Go performs bounded informational server checks

Accepted by owner 2026-10-08. A single Servers action confirms the current SSH host key and reads hostname, OS/version, architecture, CPU count, RAM and server time directly from the saved host using Go. The same information is available on the Execution Node before Core preparation. Current SSH password or PEM session, isolated pinned OpenSSH, bounded output/time and revision/identity revalidation are required. One explicit fingerprint confirmation supplies the same pinned key for informational SSH and existing installation target trust; a second confirmation is unnecessary. Changed keys or effective endpoints block installation. Trust and facts do not approve execution plans or change desired inventory. Existing Execution Node readiness runs separately after an informational check and cannot erase successfully collected facts. No generic command bridge or fact persistence is introduced. See [implementation plan](work/server-information/server-information-check-plan.md).

## ADR-032: Execution Node supports session SSH passwords

Owner-approved 2026-10-08. Password and PEM use the existing OpenSSH SSH/SCP transport and exact confirmed host-key pin. Password is broker-owned memory, supplied through standard ASKPASS using early helper dispatch in the current executable and a command-owned one-use loopback capability. No password argv/environment/file, new credential DTO or desired-state store is introduced. Only a matching STARTING plan/RUNNING run may use a retained password after ordinary lease expiry; new operations require a live lease. Copies are wiped on callback return and hold release. PEM file/digest guards remain. See [plan](work/execution-node-password-auth/execution-node-password-auth-plan.md); broader preparation/Start acceptance remains separately gated.

## ADR-033: Endpoint placement selects HAProxy providers

Owner-approved 2026-10-09. Core derives HAProxy destinations through the
service endpointGroup, matching Keepalived endpointGroupRef placements, and
same-group HAProxy placements on those hosts. All matching provider/host pairs
participate; neither full VIP coverage nor a unique provider is required.
Legacy haproxy.deploymentRef is read-compatible and ignored for selection;
haproxy.backend remains an override over package-owned defaults. Source Apply
depends on the selected base providers, whose normal Apply already preserves
source backends without resolving future services. Missing placement produces
a safe FAILED diagnostic followed by SKIPPED integration without terminating
the run. Runtime errors of selected providers remain fail-stop. Existing
publication, archives and explicit full reconciliation are reused. Partial
hooks do not discover previous excluded hosts after move/delete; no durable
target store or new transaction guarantee is introduced. See the
[narrow plan](work/endpoint-placement/endpoint-haproxy-placement-plan.md).

## ADR-034: Application libraries use an additive Ansible-only resolve boundary

A8 extends this decision with one mixed execution manifest/run and the existing
sequential fail-fast controller. Application Apply is a final suffix after all
infrastructure Verify operations; no scheduler or separate approval is added.
Digest-bound runtime source metadata distinguishes operator Vault input from
bootstrap output of this run/provider. Application inputs depending on bootstrap
are materialized after the barrier from existing protected Execution Node files.
No new storage or desired-state source is introduced. The new closed manifest
and request/capability versions are opt-in; Go/UI remain separate milestones.

Owner authorized A1 implementation on 2026-10-10. Application/library packages
remain local versioned portable inputs, not another catalog or persistence layer.
Package metadata declares a bounded exact file closure; defaults stay in ordinary
role files. Only validated defaults load on the Execution Node. Ansible composes
application defaults, recipe slot overrides, instance overrides and allowed host
overrides using its built-ins. Core checks derived identities, connections,
credential descriptors and package revisions without another precedence engine.
Connection selectors default by serviceType inside each library; Kafka requires
an explicit named client listener. Infrastructure-only behavior stays unchanged.
Read-only library snapshots use v2alpha1; current execution refuses them until A7.
No provider mutations, Agent rendering, image delivery or Go/UI work is part of A1.
Provider allocation unavailable in existing read-only projections is fail-closed,
never inferred from a manifest port. See [A1 plan](work/application-libraries/milestones/a1/a1-technical-plan.md)
and [evidence](work/application-libraries/milestones/a1/evidence/a1-test-journal.md).

A2 extends the same boundary with explicit standalone materialization/Apply/Verify,
native Compose and typed image descriptors inside the existing artifact lock.
Repository selection stays node-scoped; controller verification reads only a
target-selected fallback archive and completes across placements before writes.
Image startup references derive from full image IDs, preventing different library
images from retagging one shared mutable name without a daemon-wide registry or
new identity store. Config-digest labels provide interruption recovery with native
Compose recreate. Infrastructure-only planning and the A7 execution guard remain.
See [A2 plan](work/application-libraries/milestones/a2/a2-technical-plan.md) and
[DIFF review](work/application-libraries/milestones/a2/reviews/a2-diff-review.md); these do not authorize
later provider, Go or UI stages.

## ADR-035: Managed PKI authorities enter the target OS trust store

For each resolved PKI authority selected for a target, `platform.core.pki_deploy`
installs its public CA certificate under `/etc/pki/ca-trust/source/anchors/` and
runs `update-ca-trust`. The anchor filename is derived from separate hashes of
the project and authority identities, allowing distinct projects and authorities
to coexist. Installed anchors are intentionally retained, including when an
authority is no longer selected by the project. Refresh runs on each PKI
deployment, making a retry recover when the prior `update-ca-trust` command failed
after file changes. This is system-wide trust on the target and complements service-local
certificate copies; it does not change certificate issuance, service endpoints,
or desired project data. The implementation targets the supported RED OS
trust-store layout.

## ADR-036: Service data directories remain package-owned settings

Kafka and PostgreSQL expose `dataDirectory`; Redis, ClickHouse and Vault expose
deployment `dataRoot` and member `dataDirectory`. The existing schema-driven
Services editor presents these declarations as bounded text fields. The
default data path on each target host is `/var/lib/<deploymentId>`. When
members of one deployment share a host, their default paths gain member-ID
subdirectories. An explicit member directory is an exact path. Core places
member overrides in the existing member list, while role defaults remain
Ansible-owned. Before target mutation, roles reject unsafe absolute paths,
linked, foreign or writable ancestors and local path collisions. Changing a
path never moves existing data; migration is a separate operator procedure.
Runtime-only member paths and facts remain derived state.

Owner decision (2026-10-11): changing a data path on an already installed
deployment is not guarded by this UI change. For PostgreSQL, Kafka and
ClickHouse, a subsequent apply can initialize a new empty directory and
reconfigure the service to use it while the old data remains at the former
path. Operators must migrate existing data separately before applying a path
change. Redis retains its existing directory consistency check. Adding Vault
and changing defaults can likewise select a new empty data directory on a
reapply unless the operator migrates existing data first.

## ADR-038: Broker-bound Kafka Schema Registry

Schema Registry is a component of the selected Kafka deployment, derived for each
broker member, including combined members. Controller-only hosts are excluded.
The canonical service package declares settings and a pinned conditional artifact;
the existing source gate retains node-scoped acquisition authority. Core and the
role share a pure projection. No placement or desired-state persistence is added.
Member-only port overrides stay in canonical member inputs rather than becoming
host-wide role variables. See the [implementation contract](work/kafka-schema-registry/implementation.md).

## ADR-037: Portable service data root and target resource prefix

The portable project carries `platform_data_root_directory` and
`platform_name_prefix` as ordinary Ansible variables beside its desired state.
Installer Review/Save edits the same managed document. The service data root
defaults to `/var/lib` and supplies service data paths only; explicit
deployment/member paths retain precedence. Application data remains in the
application account home, and Installer execution workspaces and cache are
outside this setting.

For a configured non-default service data root, the existing managed data path
guard creates or repairs that one directory as the current SSH technical user
(`ansible_user`) with mode `0755`. Service data directories below it remain
owned by their service accounts. Verify checks the root owner and mode without
changing them. The system-wide `/var/lib` default remains root-owned and is
never chowned.

An empty name prefix adds nothing to service-owned target resource names.
A nonempty validated prefix is prepended where service resources are created
and checked. Installer PKI paths and application runtime names retain their
existing names. It does not rename internal
contract keys, collection names or Installer runtime identity paths. The
owner will remove old deployments before rollout; the Installer does not
migrate or remove old resources when the prefix changes.

## ADR-039: Core owns reusable infrastructure Verify evidence

Owner-approved B plan, 2026-10-14. The fixed library-only execution scope may
reuse successful Verify operations covering all enabled infrastructure deployments
of one resolved infrastructure model. Core derives the model and validates source
journals on the selected Execution Node. A bounded operational index in existing
execution state references those journals; it is not portable desired state.

Infrastructure mutation starts a new evidence generation once per run. A terminal
FAILED run can contribute completed Verify operations without changing its outcome.
Verify-only uses the same planner/approval/controller lifecycle and never falls back
to Apply. Library-only requires a fresh plan, approval and revalidation under the
existing project active-run admission lock, with exact approved SSH keys.
Loss or corruption of evidence blocks reuse. Historical Verify is not continuous
health monitoring; normal provider guards remain in force.

Go may persist a local operational projection analogous to run records; it cannot
authorize reuse or compute infrastructure equivalence. React renders the Core
decision. Existing A8 same-run barrier, secret custody and standalone Ansible paths
are preserved. New request/capability/plan/manifest versions isolate the extension.
See [technical plan B](work/application-libraries/milestones/b/b-technical-plan.md)
and [execution contract](contracts/execution-planning-and-events.md#b0-cross-run-infrastructure-verification).

Owner amendment, 2026-10-14: if compatible saved Verify evidence is absent or stale,
the same approved library-only plan includes fixed infrastructure Verify operations
before library Apply/Verify. It has no infrastructure Apply, separate plan or second
approval. Core stops the run before libraries on Verify failure/cancel and publishes
successful verification through the existing evidence generation.

## ADR-040: Library edits and package import reuse the local managed writer

Owner-approved B2 scope, 2026-10-14. Library edits mutate only existing
Installer-owned inventory/group_vars/host_vars through structural Review/Save.
Ansible remains the desired-state resolver; local Save does not imply semantic
validity, effective values or execution admission. Derived identities are not
persisted in place of authored package references and overrides.

Package import captures reviewed data-only manifest closure through existing
handle-bound reads, derives a new immutable version directory and uses the same
PlanStore and revision-guarded recoverable transaction. Imported package bytes
remain ordinary portable sources without managed-header normalization; existing
versions/user-owned documents are not adopted or overwritten. Local revision and
fixed-root project export include this closure, never operational caches/secrets.
No second catalog, YAML adoption framework or execution mechanism is introduced.
See [B2 writer contract](contracts/application-library-writer.md).


### B2 owner amendment - 2026-10-14

D01/D02: user-defined environment, parameters and package files accept arbitrary
parameter names and assignments, including PASSWORD. Do not infer credentials
from names or assignment text. Explicit Installer credential source descriptors
and runtime private-key custody remain separate. D03: reject overlapping
parent/child edit writes while retaining independent slot edits. Reuse existing
writer and Core validators; no new secret classification framework.


## ADR-041: B3 modes reuse the existing installation lifecycle

Owner authorized B3 from the approved B plan on2026-10-14. Explicit mode Build
uses the existing B1 transport and ExecutionService plan store; approval,
credential/trust staging, PENDING start intent, uncertain response recovery,
Cancel and reconnect are shared. Mode/source policy metadata is retained in the
in-memory plan record solely to repeat the same fresh Build before Start. No
second desired-state store, infrastructure resolver or execution API is added.

Core remains owner of all infrastructure equivalence, evidence and Start admission.
Local infrastructure observations are display-only UNKNOWN on reload. Backend
presentation exposes mode and actual Core verification/operation output without
synthetic infrastructure success. Legacy CreateInstallationPlan remains compatible;
production transport/UI integration and real bridge acceptance belong to B4.

## ADR-042: Apply performance reuses transport and scoped endpoint publication

Owner approved P2 on2026-10-15. Ansible keeps execution/domain ownership. Standard
pipelining and operation-private OpenSSH control sockets reduce repeated transport
setup; runtime lease/trust and confirmed-stop semantics are unchanged. Socket
custody is ephemeral derived state, not a new credential store or session registry.
Existing source resolvers and HAProxy candidate/archive/activation tasks accept a
selected source set; BIND keeps local authenticated dynamic update grouped by zone.
Singleton role inputs remain compatible. Every backend and public endpoint retains
its original sequential checks. No distributed rollback, scheduler, workers, health
cache, new public DTO or UI performance controls are introduced. See the
[P2 plan](work/application-libraries/apply-performance-plan.md) for safety and QA gates.

## ADR-043: Application database access reuses provider authority

Owner approved the Secrets access plan on2026-10-16 and authorized SEC-D02
reconciliation while rejecting SEC-D01 as an ownership prohibition. Ordinary
project accounts remain canonical. Core atomically selects legacy or database
grant policy after the existing Ansible combine; credentials and runtime lease
are unchanged. PostgreSQL uses batch GRANT and database-wide default privileges
for declared creator roles. Operator-assigned object ownership is permitted and
is not represented as a revocable DML grant. No ownership transfer is inferred.
ClickHouse's existing UUID/marker witness bounds direct SELECT/INSERT REVOKE to
the managed account and its managed library databases, retaining foreign/role/
grant-option/partial/column conflicts and the existing ON CLUSTER execution.
No grant ledger, daemon, event trigger, new DTO/store or parallelism is introduced.
Acceptance is tracked only in CURRENT_STATE and the access journal.
