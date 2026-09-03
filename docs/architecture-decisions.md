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

Status: Accepted by UI-BE-01; implemented by UI-BE-03.

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

A semantic command produces an opaque, reviewable EditPlan by staging only
owned documents and proving its effective result with Core ProjectSnapshot.
Commit rechecks the raw-byte project revision and affected document digests
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
