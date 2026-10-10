# V2 roadmap and milestone gates

The roadmap is dependency-based, not a calendar promise. A milestone is complete only when every “ready” criterion is demonstrated. Partial implementation does not unlock the next architectural layer.

## Phase A — Architecture baseline

Application libraries follow the separate [implementation plan](application-libraries/implementation-plan.md):
A1 standalone schemas/read-only Ansible+Core resolution, then rendering/image
delivery/provider hooks and execution integration, then Go and UI. Infrastructure
installation without library selection remains supported. A1 does not authorize A2
or real container/provider mutation; active status is recorded only in CURRENT_STATE.

### ARCH-01: Repository and boundaries

Deliverables:

- independent V2 repository;
- canonical architecture, project contract and decision log;
- explicit V1 reuse/reject policy;
- risk and deferred-decision list.

Ready when:

- Ansible/Core, backend and UI responsibilities have no intentional overlap;
- topology and standalone operation are represented;
- no application code has been introduced before contract approval;
- owner approves the baseline.

Not ready when:

- Go or React is still required to produce runnable Ansible input;
- topology is represented only as inventory;
- service definitions are owned by more than one layer.

## Phase B — Standalone Ansible Core foundation

### CORE-01: Repository and contract skeleton

Status: DONE. Contract documents, standard playbook validation, the offline
Draft 2020-12 schema engine, service-package skeletons and fixture conformance
execution are implemented and tested.

Deliverables:

- Ansible collection/package layout;
- monorepo dependency boundaries and independently packageable Core/service-role targets;
- draft JSON/YAML schemas for project, service manifest, plan, event and result;
- standard Ansible project layout and documented `ansible-playbook` invocations;
- example projects for zero, one and multiple deployments;
- schema validation tests.

Ready when:

- a project can be validated on Linux without Go/UI;
- validation runs through standard `ansible-playbook` with normal inventory, `group_vars` and `host_vars`;
- invalid references and modes produce structured diagnostics;
- no plaintext-secret field exists in schemas;
- format and exit-code behavior are documented;
- Core validation/tests run without backend or frontend source dependencies.

Not ready when:

- validation depends on Installer DTOs;
- service lists or modes are hard-coded in a client;
- schema errors require reading a Python/Ansible traceback;
- a proprietary launcher is required.

### CORE-02: Deterministic topology resolution

Status: DONE. The topology-only slice was implemented and validated on the
RED OS controller in an offline network namespace.

Deliverables:

- deterministic project resolver over inventory, `group_vars` and `host_vars`;
- explicit placement and dependency resolution;
- endpoint and certificate-scope resolution;
- canonical plan fingerprint;
- golden fixtures and property/invariant tests.

Delivered in this milestone:

- pure resolver output limited to canonical `ResolvedTopology`;
- explicit placement and generic reference validation reused from CORE-01;
- stable ordering and topology fingerprint using only used service-definition
  digests;
- no dependency DAG, endpoints, certificates, runtime role variables or
  deployment plan.

Ready when:

- identical inputs produce byte-stable logical output and fingerprint;
- two deployments of the same service remain isolated;
- a service type absent from the project produces no role invocation;
- conflicts block planning with precise diagnostics;
- resolved execution groups/runtime variables are disposable and reproducible.

Not ready when:

- roles choose hidden placements;
- service instance IDs become endpoint DNS names implicitly;
- output ordering changes between runs;
- generated files must be manually edited.

### CORE-03: Deterministic service configuration resolution

The first CORE-03 slice is intentionally limited to resolving logical
deployment configuration. It does not start execution lifecycle work.

Deliverables:

- versioned logical-setting to ordinary role-variable mapping in service packages;
- canonical role defaults loaded from service-role `defaults/main.yml`;
- deployment-level defaults plus portable project override resolution;
- explicit `DEFERRED` state for non-literal Ansible/Jinja defaults;
- canonical `ResolvedServiceConfiguration` projection and fingerprint;
- precise blocking finding for unsupported member configuration;
- deterministic configuration fixtures and standalone role-conformance boundary.

Ready when:

- identical defaults, overrides and package inputs produce byte-stable output;
- placement changes affect topology fingerprint but not configuration fingerprint;
- no derived configuration is persisted as desired state;
- Core does not evaluate Ansible/Jinja variables or emit role runtime variables;
- manual inventory, group_vars and role defaults remain a valid standalone role input.

Not ready when:

- member/host precedence is inferred;
- generic Core guesses logical-to-role-variable names;
- schema defaults and role defaults are both treated as canonical.

### CORE-04: Scoped configuration and variable context

Status: DONE. Scoped configuration, variable contexts, opaque pass-through
preservation, deterministic references and independent member projections were
implemented and validated on the RED OS QA VM.

CORE-04 adds deployment/member configuration scopes while preserving host vars
as physical-host context and preserving standalone Ansible as the runtime
authority. Service mappings declare allowed scopes. Derived output retains
independent member projections for multiple members on one host, exact static
reference states, source metadata and deterministic fingerprints.

The milestone does not implement a Jinja interpreter, facts, lookups, runtime
role-variable generation, plan/apply/verify, or production services.

### CORE-05: Canonical service metadata and variable preservation

Status: DONE. Service packages now author canonical managed/advanced setting
metadata in `service.yml`; tracked `configuration.schema.json` files are
deterministically generated and checked for reproducibility. Role defaults
remain standalone Ansible's canonical default/Jinja source.

CORE-05 preserves unknown group and host variables as opaque pass-through
values with physical origin. Managed configuration and opaque input have
separate deterministic fingerprints, and an explicit future mapping promotes
an existing opaque role variable without rewriting its stored value.

## Phase C — First production service

### SERVICE-01A: Kafka KRaft standalone

Status: DONE. Kafka 4.3.1 single-node KRaft apply and verify were implemented
inside the Kafka service package and validated on RED OS with offline artifact,
idempotent storage initialization and `changed=0` repeat execution.

Deliverables:

- Kafka KRaft single-node service package and role;
- supported target matrix marked as test targets, not certification claims;
- offline package acquisition, Java, configuration and systemd management;
- minimal endpoint/TLS hooks required by the agreed slice;
- service health and KRaft verification;
- acceptance fixture set.

Ready when:

- clean single-node installation succeeds through standard `ansible-playbook`;
- a second run has no avoidable changes;
- failure and verification results are structured and actionable;
- unsupported features are explicit;
- integration hosts and offline artifacts are available.

Not ready when:

- the role is only defaults/schema/set_fact;
- the target requires manual repair;
- the slice silently claims unsupported security/listener features.

### SERVICE-01B: Kafka KRaft distributed

Status: DONE for same-host multi-member deployment and SERVICE-01C real
multi-host extension.

Deliverables:

- controller/broker/combined member roles and explicit placements;
- stable node identities and deterministic quorum configuration;
- multiple independent Kafka deployments;
- distributed verification and failure evidence;
- RED OS and ALT Linux integration evidence where environments are available;
- failure, retry and idempotency tests.

Ready when:

- clean distributed installation succeeds from standalone Core;
- second run has no avoidable changes;
- configuration changes converge predictably;
- failure is actionable and resumable;
- secrets and host keys remain protected;
- service health, membership and quorum are verified, not assumed.

### EXEC-01: Execution Node and target bootstrap

Status: DONE. This milestone establishes selectable execution-node
semantics, separates candidate eligibility from post-preparation readiness,
and provides generic preparation/bootstrap phases. The selected Execution Node
may be local, a project target, or external; a dedicated host is optional.

Ready when:

- local Installer, target-host and external-host selections are contractually
  representable;
- Phase A prepares the selected execution environment;
- Phase B bootstraps remote targets from that Execution Node;
- a self-target skips password bootstrap and uses explicit local transport;
- runtime credentials are never persisted or logged;
- one standard Ansible invocation produces a unified multi-host recap.

Hardening follow-up: persistent execution identity state is kept outside
ephemeral QA workspaces; repeated preparation reuses the identity and the
generic `ensure-execution-access.yml` entrypoint composes preparation, target
bootstrap and centralized elevation verification. Explicit rotation or
execution-environment destruction remains the identity removal path.

### SERVICE-01C: Kafka KRaft real multi-host deployment

Status: DONE. Centralized EXEC-01 acceptance was applied through one Execution
Node invocation.

Deliverables:

- explicit `node1`/`node2`/`node3` member fixture with shared cluster state;
- dynamic quorum bootstrap using `controller.quorum.bootstrap.servers` and
  full `--initial-controllers` formatting input;
- repeat apply and verify idempotency, quorum-preserving one-node failure and
  member recovery acceptance;
- static quorum remains a compatibility contract/unit/fixture path using
  `controller.quorum.voters`, without fallback between modes.

Ready when:

- real three-host apply, repeat apply and verify pass;
- two remaining controllers verify quorum while one member is stopped;
- the stopped member is diagnosed as degraded/failed and returns healthy after
  restart;
- no TLS/SASL, placement automation or generic endpoint model is introduced.

Not ready when:

- manual target repair is required;
- only the happy path is tested;
- the role needs Go-generated internal objects;
- the role chooses or moves placements itself.

### SERVICE-01D: Kafka split broker/controller deployment

Status: DONE. The generic Kafka lifecycle accepts split broker-only and
controller-only members without topology-profile branches. Centralized
acceptance uses node1 as the selectable Execution Node and node1/node2/node3 as
the three physical targets.

Acceptance evidence:

- six Kafka members applied and verified with dynamic controller quorum;
- repeat apply and final verify returned `changed=0`, `failed=0`;
- broker and controller stop/recovery scenarios preserved quorum and restored
  the complete healthy deployment;
- bounded systemd readiness polling prevents immediate post-start verify races;
- the resumable runner persists stage, PID, terminal status and log directory,
  detects orphaned `RUNNING` state as `STALE`, and prevents live duplicates.

Static quorum remains an explicit compatibility mode covered by contract and
fixture tests; no automatic fallback is introduced. CORE-06 remains separate
and is not started by this milestone.

## Phase D — Stable project contract

### CORE-06: Canonical project state and runtime projection

Status: DONE under its original contract. Deployment-level desired state was
canonical in `project.yml.desiredState`; physical member ownership and
placement were inventory-owned. CORE-07 supersedes the desired-state ownership
boundary while preserving CORE-06 projections and compatibility readers.
Managed Kafka projects normalized inputs into the existing
runtime-only standalone role contract and records a deterministic
`runtimeProjectionFingerprint` from final service-relevant values.

Kafka deployment/member identities are discovered, generated or recovered
before first mutation, transactionally persisted to project plus inventory,
reloaded and validated before runtime projection. Verify remains read-only.
The bounded legacy `platform_project` adapter and manual standalone
`platform_kafka_instances` input remain compatible without becoming additional
canonical stores. Centralized EXEC-01 fast acceptance for SERVICE-01A through
SERVICE-01D passed with repeat apply and verify at `changed=0`.

### PKI-01: Certificate and Java-store materialization

Status: IMPLEMENTED. PKI-01 adds topology-derived managed certificate requests
with default HOST scope, MANAGED CA materialization on the Execution Node, PEM
and dedicated PKCS12 deployment to targets, and read-only verification.
Certificate/private-key/password values remain runtime state; canonical
projects retain only intent and secret references. Ordinary reconcile blocks
changed request or authority identity with `CERTIFICATE_REISSUE_REQUIRED`.
An explicit selected leaf reissue preserves prior request material in protected
Execution Node state; authority rotation remains deferred.

Kafka TLS, JKS, mTLS, imported/external CA, renewal and rotation remain
explicitly deferred to later milestones.

### CORE-07: Ansible-native canonical desired state

Status: DONE. Standard inventory, `group_vars`, `host_vars` and role defaults
are canonical user-owned desired state. `platform_desired_state` declares
logical deployments; inventory `platform_deployments` declares members and
placement. Machine-owned identities, fingerprints and locks are isolated in
`platform_generated_state`. Managed Kafka and PKI work without `project.yml`;
legacy project inputs and standalone role variables remain bounded
compatibility paths. The Installer must edit these same files and invoke the
same standalone playbooks.

### CONTRACT-01: V2 contract release candidate

Deliverables:

- versioned schemas and compatibility policy;
- catalog/artifact lock format;
- migration rules;
- import/export round-trip fixtures;
- contract conformance suite.

Ready when:

- first production service no longer requires ad hoc contract exceptions;
- examples round-trip without semantic loss;
- declared unknown extensions survive semantic YAML round trips;
- older supported project versions have deterministic migration or explicit rejection;
- Core versions declare compatible contract ranges.

Not ready when:

- changing UI needs changes to the canonical schema;
- generated state is stored as desired configuration;
- service upgrades are not reproducible.

### SERVICE-02A: Kafka named listeners and SSL consumer prerequisites

Status: DONE. Kafka now uses explicit named `PLAINTEXT`, `SSL` and
role-appropriate `CONTROLLER` listeners with one service-wide TLS profile.
Legacy `clientPort` and `controllerPort` settings were removed. Kafka consumes
PKI-01 materialization read-only and copies required material into its
Kafka-owned directory without persisting passwords.

RED OS FAST acceptance passed for SERVICE-01A through SERVICE-01D with
profile-lifetime isolation: initial apply, separate verify and repeat apply
all passed; verify and repeat returned `changed=0 failed=0`. Core (113), Kafka
(22), catalog, syntax, offline and diff gates passed.

### UI-DESIGN-01: Installer interaction architecture

Status: DONE. This documentation/design milestone defines Platform Installer
as a visual editor and orchestrator for the same Ansible-native project used by
standalone operators. It adds no Wails/React production code, persistence
model, Core topology model or UI-owned desired state.

Deliverables:

- vertical global navigation with Installation as the project home and
  Topology as a separate page;
- generic deployment/member/host topology UX with service-specific editors;
- schema-driven service, PKI, findings, execution and source-value UX;
- Ansible-file ownership, optimistic save and external-change design;
- YAML/Jinja preservation boundaries, SecretRef and generated-state rules;
- static conceptual mockups.

### POSTGRES-01: PostgreSQL standalone and pg_auto_failover

Status: DONE. PostgreSQL standalone and two-data-member
pg_auto_failover deployments use include-based dynamic configuration,
topology-scoped TLS/HBA policy and runtime-only credentials. RED OS acceptance
proved initial apply, separate verify, repeat apply, TLS enforcement,
automatic failover, data preservation, natural rejoin and post-rejoin
idempotence. Final focused/Core, generated-artifact, syntax, offline and
security audits passed.

Production UI-01 remains dependent on a minimal backend read/write, run and
revision boundary; React or Wails must not assume those responsibilities.

### NET-01: Endpoint Groups and Resolved Service Endpoints

Status: DONE. NET-01 establishes the Ansible-native endpoint group contract,
direct `serviceDeployment.endpointGroup` assignment, and read-only FQDN
resolution. It deliberately excludes transport ports and all routing semantics;
those belong to a future HAProxy milestone. PostgreSQL is the first opt-in package, Kafka
remains outside generic endpoint semantics, and PKI-01 consumes the projection
only according to existing SAN policy.

### NET-02: Keepalived / VRRP / Stable VIP Ownership

Status: DONE. One host-scoped Keepalived deployment owns one VRRP instance,
one VRID, one endpoint group reference and one-or-more virtual addresses.
Three-node RED OS acceptance proved native validation, all-or-none multi-VIP
ownership, automatic failover, natural rejoin with `nopreempt`, and repeat
apply/verify idempotence. The NET-02 baseline has no active HAProxy dependency;
NET-04.1 later adds explicit opt-in `vrrp_script`/`track_script` semantics.

### NET-03: Authoritative BIND DNS

Status: DONE. NET-03 derives deterministic project-host, endpoint and wildcard
DNS records, and maintains machine-owned per-zone fingerprint/serial state.
Three-node RED OS acceptance proved complete candidate and active barriers,
native primary-to-secondary BIND transfer, authoritative responses from all
nodes, exact-once serial increment on a logical zone change, primary outage
continuity, natural primary restoration, and post-recovery verify/repeat
idempotence.  DNS routing and HAProxy are deliberately deferred.

### NET-03.1: DNS Client / Split DNS Runtime Adapters

Status: DONE. A separate host-scoped `dns-client` package consumes one logical
`dnsServerRef` and derives its primary-plus-secondary addresses and route-only
zone from the existing Core DNS projection.  Three-node RED OS acceptance
proved systemd-resolved split DNS, safe resolv.conf ownership, normal resolver
host/endpoint/wildcard lookups, unrelated DNS preservation, primary and
single-remaining-server fallback, recovery, and idempotent apply/verify.
NetworkManager fallback has focused coverage and blocks safely unless a
supported per-domain DNS backend is present.

### NET-04: HAProxy

Status: DONE. The host-scoped HAProxy package provides fixed HTTPS `public`
routing on `*:443`, deployment and explicit host endpoints, normalized Host
routing and package-owned TLS stats backends. Three-node RED OS acceptance
proved candidate/activation barriers, hostname-verified TLS, real pooled
multi-node backend use, non-VIP-owner failure isolation, recovery, and clean
verify/repeat apply.

### NET-04.1: Keepalived HAProxy health tracking

Status: DONE. Opt-in Keepalived tracking references one colocated HAProxy
deployment and renders a root-owned bounded admin-socket readiness helper with
one `vrrp_script` and `track_script`, without weight. A cluster-wide candidate
and active-validation barrier prevents any service reconcile until every
participant has validated the exact SHA-256-matched configuration. Three-node
RED OS acceptance proved owner failure causes atomic configured-VIP migration,
endpoint continuity, natural backup recovery without failback, non-owner
failure isolation, and clean final verify/repeat apply.

## Phase E — Go backend adapter

### NET-04.2: Service-driven provider reconciliation

Status: DONE. A successful service lifecycle invokes one deterministic,
read-only provider projection; BIND reconciles before HAProxy from complete
canonical desired state. Acceptance proved deduplication, full-model drift
repair, desired-state add/remove cleanup, serial `4 → 5`, clean repeats and
shared-PKI stability.

Owner-authorized ENDPOINT-HAPROXY-PLACEMENT-01 replaces explicit provider
selection with endpoint → Keepalived placements → same-group HAProxy host
intersection, using existing source-owned integration and full reconcile.
Package backend defaults and overrides remain Core-owned. Missing placement
is an error with skipped integration, not a run failure. Source implementation
and acceptance status are tracked in CURRENT_STATE and the
[narrow implementation plan](endpoint-haproxy-placement-plan.md); earlier
NET-04.2 acceptance does not prove this changed selection.

### UI-BE-01: Installer UI / backend boundary

Status: DONE. The versioned query/semantic-command/execution boundary is
defined in `docs/ui-be-01.md`. UI read models remain derived projections over
the same canonical Ansible project. Normal writes use reviewed EditPlans,
optimistic project/document revisions and a safe Ansible-native writer;
arbitrary existing projects are read-only by default and Installer-owned
standard Ansible files are the preferred write target. No production backend,
UI, YAML writer or speculative contract family was added.

Recommended gated sequence:

- UI-BE-02: DONE — read-only ProjectSnapshot and controller query adapter;
- UI-BE-03: DONE — safe Ansible-native writer and EditPlan/commit boundary;
- DEVX-01: DONE — Go/Core scoped guidance, Codex Skills, reviewer templates and reusable QA workflow;
- EXEC-01A: DONE — bootstrap a READY Execution Node before Platform Core exists, with node-scoped repository-first/offline-bundle fallback;
- UI-BE-04A: DONE — actual execution audit and boundary freeze;
- UI-BE-04B: DONE — target-free Core DeploymentPlan and private ExecutionManifest;
- UI-BE-04C: DONE — fixed Execution Node runtime protocol and durable lifecycle;
- UI-BE-04D: DONE — Go ExecutionService, approval, sessions and reconnect;
- UI-BE-04E: DONE — production Kafka E2E and final regression;
- UI-BE-04 overall: DONE — validation, plan, execution and events;
- UI-01: production Wails/React UI over those accepted contracts.

### UI-BE-02: Read-only ProjectSnapshot

Status: DONE. `platform.core.project_snapshot` and the standalone
`project-snapshot.yml` entrypoint compose a versioned deterministic read model
from the Ansible-loaded project without writes or target contact. The accepted
contract includes separate raw-byte project/document revisions and catalog/Core
versions, six-service catalog and deployment views, effective configuration
with honest provenance, heterogeneous topology, endpoint/provider/DNS/HAProxy
relations, shared PKI identities, partial validation and static readiness.
Offline RED OS acceptance and the architecture review have zero blockers.
UI-BE-03, DEVX-01 and EXEC-01A are complete. UI-BE-04A is DONE and
UI-BE-04B, UI-BE-04C, UI-BE-04D and UI-BE-04E are DONE. UI-BE-04 overall is
complete; later UI milestones remain separately gated.

### UI-BE-04A: Execution architecture audit

Status: DONE. `docs/ui-be-04.md` records the actual EXEC-01A reuse matrix and
freezes Core ownership of deterministic deployment planning, private execution
manifests and trusted ordering. The future Execution Node API is a fixed
semantic protocol with detached controller ownership, bounded journal/events,
replay, reconnect, cancel and recovery. The current synchronous Kafka and
Keepalived `ExecuteService` remains only an EXEC-01A regression path. No
production planning, runtime protocol, session or frontend code was added.

### UI-BE-04B: Core deployment planning

Status: DONE. Core builds a deterministic public `DeploymentPlan/v1alpha2`
and private execution manifest from the target-free validated project graph,
full catalog and immutable runtime-release identity. Project identity is
canonical `project.yml.metadata.id`; a path fallback is blocked for
Installer-managed mutation. Source selection remains EXEC-01A execution-time
behavior. Core planning passed normal and network-isolated RED OS acceptance.

UI-BE-04C, UI-BE-04D and UI-BE-04E are complete. UI-BE-04 overall is DONE.

### UI-BE-04C: Execution Node runtime protocol

Status: DONE. The activated runtime now exposes only fixed semantic operations
and runs trusted Core-owned manifest operations through a detached transient
systemd controller. Run journals are private, digest-bound, replayable and
bounded; ownership includes run, project, plan, manifest, release and unit
identity. RED OS acceptance proved disconnect/reconnect, exactly-one terminal
results, whole-control-group cancellation, interrupted recovery, foreign-unit
safety and retention. UI-BE-04E completed production Kafka E2E and final
regression; UI-BE-04 overall is DONE.

### EXEC-OBS-01: Ansible task observability and Installer-side event mirror

Status: DONE (2026-09-05). Internal gates 01A through 01D implement the managed
callback, safe shared journal writer, controller integration, paginated
GetEvents, complete typed event model, RunObserver and CLI watch. The remote
journal stays authoritative; local files are runtime-only mirrors and future
UI consumes typed subscriptions.

Two production Kafka lifecycle runs completed SUCCEEDED, with PKI/apply/verify,
repeat changed=0, 1,713 task events per run and identical remote/subscriber/local
streams. Live reconnect and CLI restart, real no_log/failure/degradation,
Core/service/race/offline/security gates passed; reviews have 0 blocking
findings. Commands and counts: `docs/exec-obs-01.md`.

UI-01A, UI-01B and UI-01C are DONE. UI-01B provides the production Wails/React
read-only existing-project shell and its one fixed target-free Core snapshot
operation. UI-01C adds local metadata-only project creation and empty-project
reopen; UI-01D implementation/acceptance is complete and owner-accepted
without final revision-bound review. The separately authorized application
config/server-type foundation adds a versioned local type catalog and additive
`CreateServer` v1alpha3 contract without starting full server CRUD. UI-01E is
decomposed into E1 server CRUD integration, E2 Servers UI, E3 shared runtime
credentials, E4 Execution Node selection panel, E5 readiness/navigation gating
and E6 final Windows/RED OS acceptance. UI-01E1 is DONE: v1alpha4 server CRUD
intents use the existing edit/session/guarded-transaction lifecycle, Core projects desired
hostname/normalized port and generic references, and focused Windows/RED OS
gates passed. UI-01E2 through UI-01E6 and UI-01F1 through UI-01F6 are DONE;
UI-01F overall is DONE. F6 evidence is recorded in `docs/ui-01f6.md`.

ADR-027 changes the target architecture without changing milestone statuses:
new Save is local structural persistence; Project Verify is optional derived
preflight on READY; every execution still requires fresh BuildDeploymentPlan.

### DEVX-01: Codex engineering harness

Status: DONE. Repository-local Skills now guide Go backend work, Go-to-Core
adapter changes, safe project-writer changes and milestone QA. Scoped
instructions preserve the `internal/` application boundary and `ansible-core/`
infrastructure boundary. Implementer/reviewer roles are documented prompt
templates because this repository has no executable role-definition mechanism.
Wails/React guidance is intentionally deferred until concrete UI contracts
exist.

### BACKEND-01: Core process adapter

Status: SUPERSEDED by the explicit UI-BE-04B through UI-BE-04E gates. This
heading remains as historical roadmap context; `docs/ui-be-04.md` is the
accepted execution boundary.

Deliverables:

- typed semantic invocation of published validate/plan/execution operations and artifacts;
- normalized event streaming;
- trusted Linux Execution Node transport;
- cancellation, timeout and lost-process recovery;
- contract conformance tests against standalone Core.

Ready when:

- backend invokes fixed Core semantic operations and service packages remain
  independently usable through standard Ansible entrypoints;
- it contains no service-specific topology rules;
- active and interrupted runs are recovered correctly;
- execution mechanisms can be replaced behind one port.

Not ready when:

- backend rebuilds inventory independently;
- a service requires a new backend execution branch;
- WSL2 appears in domain models.

### BACKEND-02: Project, secrets, runs and audit

Deliverables:

- transactional project lifecycle;
- portable import/export;
- runtime credential broker;
- persisted run/result metadata and sanitized log references;
- UI-oriented read models.

Ready when:

- deleting one project cannot affect unrelated/global data;
- plaintext secrets never enter persistence;
- project export runs standalone;
- concurrency and stale-plan gates are enforced server-side.

Not ready when:

- SQLite becomes a second desired-state schema;
- UI must coordinate multi-call transactional mutations.

## Phase F — UI visual editor

### UI-01: Project, hosts and topology editor

Implementation breakdown: [UI-01A–UI-01J](ui-01.md). Contracts → shell
→ empty project → first-write/review → servers → topology → PKI profiles →
service settings → portable export → native acceptance. Every milestone starts
with a mockup/contract check. Each stage requires an explicit owner start.

UI-01A is DONE (documentation only): [contract preflight](ui-01a.md),
[accepted freeze](ui-01a-contract-freeze.md), [reviews](ui-01a-review.md) and
[QA](ui-01a-qa.md). Empty-project, first-write/inventory ownership, typed
command, selected Execution Node validation and frontend toolchain decisions are
closed. UI-01B is DONE: native folder selection, a verified immutable runtime,
READY Execution Node handshake and Core-authoritative read-only snapshot were
accepted without canonical-project mutation. UI-01C is DONE: local
metadata-only creation, no-replace publication and empty-project reopen were
accepted without Core/Execution Node contact. UI-01D implementation and
acceptance are complete: the bounded transient session, complete-candidate
remote Core proof, guarded first write and narrow Windows review/save shell
passed its executable gates and was owner-accepted without final
revision-bound review. The application config/server-type foundation is
independent of UI-01E and does not advance its implementation. UI-01E1 through UI-01E4 are DONE;
the pre-E5 ADR-027 Save/Verify separation is implemented without advancing E5.
UI-01E5 is DONE: the application-owned trusted Execution Node binding now
supports read-only readiness, explicit-confirmation preparation and fresh
post-Prepare Verify, while candidates remain transport-free. UI-01E6 is DONE;
UI-01F1 through UI-01F6 are DONE; UI-01F overall is DONE. UI-NET-01 is DONE:
provider tuples are edited through v1alpha6, the existing guarded local
Save/reopen lifecycle and the Topology → Entry points UI. Its Core-derived
preview never infers PKI/SAN impact locally; see `docs/ui-net-01.md`.
UI-01G1 is DONE: additive v1alpha7 PKI intents, direct bounded managed-state
reopen, generic final-state references and guarded local Save passed Go and
RED OS gates; see `docs/ui-01g1.md`. UI-01G2 is DONE: the Certificates page
uses the shared draft and typed intents with no local PKI derivation; see
`docs/ui-01g2.md`. UI-01G3 is DONE: revision/node/runtime-bound Core PKI
evidence is projected to Certificates without local SAN/VIP calculation; see
`docs/ui-01g3.md`. UI-01G4 is DONE: Windows/RED OS target-free acceptance,
race gates and hygiene passed; see `docs/ui-01g4.md`. UI-01G overall is DONE.
UI-01H1 is DONE: v1alpha8 safe configuration intents, bounded catalog and
managed projections, local Save/reopen and descriptor-driven TLS reference
integrity passed; see `docs/ui-01h1.md`. UI-01H2 is DONE: the one Services
list/detail route, Topology hand-off and descriptor-gated deployment forms use
the existing shared edit lifecycle without Core or target changes; see
`docs/ui-01h2.md`. UI-01H3 is DONE: member-scoped configuration and trusted
TLS-profile selection use the shared v1alpha8 session and contextual
Certificates return without Core or target changes; see `docs/ui-01h3.md`.
UI-01H4 is DONE: Windows desktop, RED OS target-free/race and regression gates
passed with no target contact; see `docs/ui-01h4.md`. UI-01H overall is DONE.
UI-01I is DONE: guarded portable export/reopen, Windows/Wails and RED OS
target-free evidence, plus the one permitted DIFF targeted recheck, passed with
zero blocking findings; see `docs/ui-01i.md`. UI-01J is DONE: final native,
RED OS, Core-contract and safety acceptance passed; see `docs/ui-01j.md`.
UI-01 overall is DONE. UI-02 remains separately authorized work.

Owner-authorized export display-name refinement uses the export directory name
for the copied optional manifest's `metadata.name`, retaining source and ID.
Output digests and original source revision remain separate; see
[plan](project-export-display-name-plan.md) and CURRENT_STATE for its acceptance.

Accepted design input: [metadata-only project creation and progressive
editing](ui-project-creation-design.md). The HTML remains a prototype; frozen
backend requirements must be implemented and proven in their owning milestones.

Deliverables:

- project lifecycle;
- service catalog driven by Core manifests;
- multiple deployments per service type;
- explicit member placement and dependency editing;
- endpoint group and deployment-assignment editor;
- validation projection.

Ready when:

- standalone PostgreSQL, the accepted pg_auto_failover baseline and multiple
  independent cluster scenarios are expressible;
- a customer can omit an available service entirely;
- no implicit Kafka/PostgreSQL instance is created;
- exported project matches the editor state and runs standalone.

Not ready when:

- React contains a parallel service/mode catalog;
- changing tabs loses desired state;
- raw internal IDs or translation keys appear in normal UI.

### UI-02: Installation workflow

Local pages: Summary → Plan → Execution → Result. Execution Node selection and
preparation are owned by the Servers/application lifecycle and existing EXEC-01A
contracts; Installation consumes a READY node and a saved current revision,
then always builds a fresh authoritative DeploymentPlan. Prior optional Project
Verify is displayed separately and never bypasses planning. Plan shows Core
actions/dependencies and target hosts; Result shows observed per-action outcomes
and verify for a specific run, without rerunning verification on view.

The approved pre-implementation protocol design is
[UI-02 architecture](ui-02-architecture.md). Credentialed Start requires the
future closed `StartExecution/v1alpha2` and
`ExecutionCapabilities/v1alpha2` contracts; legacy v1alpha1 remains valid for
planning/readiness but cannot authorize credentialed Start.

UI-02A is DONE: it reconciles the Installation mockup, exposes a closed local
read-only state and shows Summary, Plan, Execution and Result without a plan,
Core call, node/target contact, secret or Start path. UI-02B is NEXT and alone
may create and approve a fresh plan.

UI-02B is DONE: the Installer invokes the existing target-free Core planning
operation through `ExecutionService`, projects a bounded plan, and accepts
only the exact acknowledgements for its saved revision/runtime binding. It has
no Start, cancellation, secret or target-contact path. UI-02C is DONE: its
single `ExecutionService` Start path uses v1alpha2, while the node owns the
durable attempt-to-run binding, lease attachment and authoritative run ID
before controller launch. UI-02D is DONE: the App composes the runtime-only
credential broker with `ExecutionService`, uses closed Wails event/result DTOs
and bounded generation-bound observer subscriptions, and separates explicit
cancel from navigation/unsubscribe. Focused Windows and RED OS race gates and
the permitted targeted architecture recheck passed. UI-02E is DONE: the
immutable QA runtime completed two production-shaped one-host/three-member
Kafka cycles through the generic lifecycle, both `SUCCEEDED`, with repeat
apply `changed=0`; see
[UI-02E completion evidence](ui-02e-pki-runtime-secret-transport.md#8-completion-evidence).
UI-02F is DONE: bounded Core-derived service-secret descriptors,
session-only descriptor-bound values and v1alpha3 runtime transport are
complete. UI-02 overall is DONE.

Deliverables:

- readiness, plan, confirmation, execution and result views;
- certificate configuration and derived preview;
- readiness prerequisite summary linked to Servers, without node preparation;
- structured progress, cancellation and diagnostics;
- offline help.

Ready when:

- UI survives navigation and restores backend-owned active state;
- raw Ansible events are normalized before presentation;
- blocked/action-required/warning semantics are distinct;
- complete workflow uses only stable backend/Core contracts.

Not ready when:

- frontend parses callback text;
- UI can mutate without an approved plan;
- passwords or internal URIs are rendered.

## Post-UI-02 service installation acceptance

SERVICE-INSTALL-09 [ClickHouse](service-install-09-clickhouse-architecture.md)
with standalone 1/1 (no Keeper), paired server+Keeper HA 3/1 and 3/3,
TLS-only enabled protocols and HTTPS endpoint. The corrected PLAN passed its
single targeted recheck with zero blockers. The all-services one-plan final
acceptance was later reassigned to SERVICE-INSTALL-11. Earlier
references to SI09 as the final eight-service test below are historical snapshots.
As of 2026-09-29 SI09 has partial acceptance, not DONE: direct 1/1, 3/1 and
3/3 service cycles, strict repeat and the ClickHouse HTTPS endpoint pass, but
the real React/Wails cumulative run ended FAILED at HAProxy apply. The bounded
HAProxy TLS-probe correction passed direct QA; the owner declined another full
plan run. A terminal real-bridge PASS remains a future SI09 gate, not inferred
from direct Ansible evidence. SERVICE-INSTALL-10 is now
[Docker rootless + Compose](service-docker-rootless-architecture.md), with
autonomous RED OS and real nonvisual React/Wails -> Go -> Execution Node
initial/repeat terminal SUCCEEDED, repeat `changed=0`, mutual-TLS API, Compose
and LXC systemd stop/start/reboot proof. Full regression gates passed; SI10 is
DONE (2026-10-01). SI11 all-services single-plan acceptance is NOT STARTED.

Owner-revised first SI11 stage, `S11-00 — Installer-free QA baseline`:
on the dedicated node1/node2/node3 VMs remove confirmed Installer,
Execution Node and QA-installed service units, configuration, data, packages
and temporary workspaces. Do not restore VM snapshots or reinstall the OS;
do not claim the result is a provably fresh OS. Preserve OS access/bootstrap
baseline (network, SSH technical account and approved repositories), and
never delete unknown or shared system data merely to satisfy a checklist.
Scope, pre-clean inventory, phased actions and final absence checks are in
the [S11-00 cleanup record](service-install-11-cleanup.md). S11-00 is DONE
(2026-10-01); the all-services run has not begun.

Owner acceptance rule for SI11 after the verified `S11-00` cleanup:
the complete installation scenario MUST be driven only through the real
Wails/React interface, as a user would operate it. UI automation may click,
type and use the native dialogs, but must not call Wails-bound Go methods
directly, override React handlers/bindings or native dialogs, or invoke
Go/Ansible/Core operations through QA scripts, CLI or a test-only bridge.
Project open/edit, Secrets, fresh plan, approval, Start, progress and terminal
result must all be reached and observed in the interface. Read-only logs may
corroborate evidence but cannot drive the scenario or replace UI observation.
If any required operation is unavailable in the UI, SI11 is BLOCKED until that
product path works; a direct backend call is not an acceptable workaround.
Ordinary unit/regression gates remain separate and cannot substitute for this
end-to-end acceptance.
The staged [SI11 React/Wails UI test cases](service-install-11-ui-test-cases.md)
cover implemented controls on every page, state transitions and negative
boundaries before the uninterrupted all-services run. The owner's mention of
project deletion was an example of a sequence, not an added UI requirement.

After SI09 functional acceptance, plan `EXEC-PLAN-SCOPE-01` separately; it is
NOT STARTED. The current `BuildDeploymentPlan` emits apply/verify actions for
every saved deployment. A future fresh, authoritative scoped plan must be able
to apply a selected deployment and reconcile only endpoint providers affected
by its changed endpoint relation, generically for every service. BIND and
HAProxy retain their full canonical-model `reconcile.yml` behavior so manual
drift is corrected; scope selection must not turn this into an unsafe
backend-file-only write. Unrelated deployments, such as unchanged Keepalived
and Vault, must not be reapplied. This needs its own contract/architecture and
acceptance before implementation; SI09 must not silently change existing
execution-plan semantics.

Latest SI08-F status (2026-09-29): the fresh 3-host Keepalived/BIND/HAProxy/
Vault endpoint project and strict repeat are technically DONE through real
React/Wails → Go → Execution Node. Both full runs SUCCEEDED; repeat had
`changed=0`. DNS serial migration was explicit and evidence-bound, and
authenticated Vault KV remained reachable through DNS/VIP after leader
step-down and loss/restoration of the active Vault member. Full Core,
service, frontend/Wails, RED OS race and secret gates passed.
[SI08-F evidence](service-install-08f-vault-endpoint-ha.md). SI09 all-services
one-plan acceptance has not started. SI08-F source and QA are recorded in
focused commits; see `CURRENT_STATE.md` for the current milestone gate.

Latest SI08-E status (2026-09-28): Vault 1/1, HA 3/1 and HA 3/3 technical
acceptance is DONE, including real React/Wails lifecycle, strict `changed=0`
repeats, failover, explicit unseal, persistent KV marker and the full RED OS
race gate. [SI08-E evidence](service-install-08e.md). SI09 (all services in
one plan) has not started and requires a separate owner request. Earlier
shared-worktree changes still prevent a clean-repository claim; consult
`CURRENT_STATE.md` before treating the broader release as finalized.

Historical pre-SI08-E status snapshot: SERVICE-INSTALL-01 Keepalived DONE (2026-09-23); SERVICE-INSTALL-02
BIND DONE (2026-09-23); SERVICE-INSTALL-03 dns-client DONE (2026-09-23);
SERVICE-INSTALL-04 HAProxy DONE (2026-09-23); SERVICE-INSTALL-05 Kafka DONE
(2026-09-23); SERVICE-INSTALL-06 PostgreSQL/pg_auto_failover DONE (2026-09-24);
SERVICE-INSTALL-07 Redis standalone and Sentinel HA (three members on one host
by default, with three-host placement also required) is NEXT; SERVICE-INSTALL-08 is Vault,
with SI08-A contract foundation DONE, SI08-B DONE, SI08-C implementation and
QA PASS (commit pending), SI08-D implementation/correction QA PASS in the shared
worktree (DIFF-06 resolved by owner-authorized exact correction; no new review),
and SI08-E NOT STARTED. SERVICE-INSTALL-09
is the final one-plan acceptance for eight services. Redis implementation is in progress;
target acceptance has not started.
For SERVICE-INSTALL-07, the service Secrets dialog accepts bounded values
against the verified local catalog without a readiness check. The installation
flow obtains fresh Core requirements and a deployment plan before Start;
Execution Node readiness is an installation prerequisite, not a repeated
service-editor action. Passwords remain session-only.
The completed UI-02E one-host Kafka evidence remains historical evidence.
Milestones and individual acceptance criteria:
[SERVICE-INSTALL-01…07](service-install-acceptance.md).

The sequence uses one Git-ignored cumulative Installer-managed QA project:
01 created it, 02–08 open and extend its exact saved revision, and 09 builds
the final single plan from that same project. A milestone may remove only the
old attributable runtime installation of its own service; it must not replace
the cumulative project or discard accepted preceding services. Redis standalone
is additionally accepted in a separate isolated QA project; Redis Sentinel HA
is the sole Redis deployment added to the cumulative project, because the
current Redis contract admits at most one Redis deployment per project.

Order: 01 Keepalived → 02 BIND → 03 dns-client → 04 HAProxy → 05 Kafka
(replace the isolated one-target QA deployment with a three-target deployment)
→ 06 PostgreSQL/pg_auto_failover → 07 Redis standalone and Sentinel HA (3/1 and 3/3) with mandatory TLS
→ 08 Vault (1/1, 3/1, 3/3) → 09 all eight services from one shared plan.
SI08-A evidence: [contract foundation](service-install-08a.md).
SERVICE-INSTALL-07 architecture:
[Redis/Sentinel](service-install-07-redis-sentinel-architecture.md).
Before each service installation, identify and remove only its attributable
old QA installation through a proven narrow cleanup path. Record exact targets
and check ports, paths, unit names and neighboring deployment state first.
Core determines dependency ordering and permitted parallelism inside a plan;
one plan does not require simultaneous launch of every service.

Every installation uses `CreatePlan -> ApprovePlan -> Start`, reaches an
authoritative `SUCCEEDED` result with apply/verify PASS, and is repeated through
a fresh plan to prove `changed=0`. Record run IDs, actual placement, observed
service health, relevant PKI/network integration, and secret-safe events/results.
For Kafka, verify cluster membership/quorum and TLS on all three target hosts.
For the final shared plan, verify cross-service dependencies and integrations.
Record before/after evidence that unrelated QA deployments were not changed.
The final shared-plan test starts only after the individual service tests pass.

SERVICE-INSTALL-06 accepted an isolated three-host PostgreSQL
`pg_auto_failover` deployment: node1 monitor, node2 and node3 database
members. The first Go-managed lifecycle run
`installer-45943379628ebee4a28716d85b571916` completed `SUCCEEDED` in 17m45s
with 65 changes; the fresh repeat
`installer-4fcc0cd5afc8689509aea2e2a49935e6` completed `SUCCEEDED` in 17m9s
with `changed=0`. PKI apply, PostgreSQL apply and verify passed in both cycles.

## Phase G — Expansion

### BROWSER-REMOTE-01/02 — Linux backend с браузерной рабочей станции (dev HTTP; HTTPS в v1.0)

Один пользователь открывает React UI на своей рабочей станции, а Go backend
работает на Linux Execution Node и доступен по настроенному `host:port`.
Wails остаётся альтернативной тонкой оболочкой над теми же Go-методами.
HTTP remote разрешён только для dev с явным флагом
`-browser-allow-insecure-dev-http`; credentials и содержимое runtime-secret
файлов в HTTP-канале не защищены от наблюдения/изменения. Не использовать с
production-системами или данными. В v1.0 необходимо реализовать HTTPS и
подтвердить защиту трафика. Firewall, аутентификация и Keycloak остаются за
рамками Installer.
Проектные пути вводятся как пути Linux-узла, файл зашифрованного runtime
секрета выбирается на компьютере браузера и передаётся только в одну typed
операцию. План и потоки: [BROWSER-REMOTE](browser-mode-remote-plan.md).

Dev HTTP сам по себе не является production-приёмкой. В v1.0 приёмка должна
включать HTTPS origins, негативную проверку недоверенных origins,
доказательство защищённой передачи credentials/secret uploads, а также
browser путь open/save/export и полный typed API flow.

### RUNTIME-BUNDLE-UX-01 — упростить обновление runtime bundle (будущий)

Убрать повторяющуюся ручную цепочку «собрать bundle → опубликовать в активный
локальный кэш → обновить `artifactLock` проекта → заново открыть проект →
подготовить Execution Node». Проверенный immutable bundle должен проходить
понятный пользователю штатный путь с явным состоянием каждого шага и точной
диагностикой несовпадения digest/catalog/binding. Не выбирать `latest`
автоматически, не ослаблять проверку bundle и не менять `artifactLock` через
обычный ProjectWriter. Отдельно проверить восстановление после прерывания
публикации и работу с уже открытым проектом. Это отдельный milestone после
SI11, а не обход текущей проверки доверия.

### UI-UX-01 — production-ready аудит дизайна интерфейса (будущий, неблокирующий)

После функциональной приёмки SI11 провести отдельный неблокирующий аудит.
Накопленные предложения и конкретные кейсы: [UI-UX-01](ui-ux-01-proposals.md).

### RUN-ATTACH-01 — повторное подключение к активному запуску после перезапуска Installer (будущий)

Если окно или процесс Installer закрылись, а detached run продолжает работу,
повторное открытие того же проекта должно обнаружить сохранённую запись
незавершённого запуска и предложить подключиться к нему по его Installer ID
(run ID). Пользователь повторно подтверждает SSH-доступ и доверие к узлу по
штатному проверенному пути; выбирать Execution Node заново вручную не требуется,
если локальная запись однозначно связывает проект, run и узел.

Подключение проверяет идентичность проекта, run и Execution Node, восстанавливает
статус и поток событий из авторитетного журнала с последней подтверждённой
позиции и показывает терминальный результат. Оно не создаёт новый план и не
отправляет повторный Start. После завершения должны быть доступны ожидающие
защищённые выходные файлы, включая bootstrap-выходы Vault. Доступ ограничен
этой парой «проект + run + узел»; SSH-учётные данные не сохраняются. В плане
milestone определить, достаточно ли существующей повторной SSH-авторизации и
host-key проверки или нужен короткоживущий одноразовый токен подключения;
долгоживущий bearer-токен не хранить.

Приёмка: закрыть приложение во время активного detached run, открыть тот же
проект, подключиться к указанному Installer ID, получить пропущенные события,
увидеть актуальный прогресс и terminal status без повторного запуска. Отдельно
проверить истёкшие учётные данные, недоступный узел, несовпадение run/project
identity и восстановление доставки Vault outputs.

### UI-LOGS-01 — страница «Логи» (будущий, не начат)

Реализовать сейчас отключённый раздел навигации как отдельную страницу истории
выполнений: список доступных run ID, безопасные статусы и результаты и **весь
доступный подробный поток событий** выбранного запуска в исходном порядке,
включая события задач Ansible и привязку к host там, где она есть. Вкладки
«Выполнение» и «Результат» на странице «Установка» предназначены для основных
этапов, прогресса и итога, а не заменяют полный журнал. Источник страницы
«Логи» — авторитетные run journal/result через закрытую безопасную проекцию,
не ограниченный буфер текущего React-сеанса; длинный поток читать частями без
молчаливого отсечения, а предел хранения или потерю событий показывать явно.
В тот же подробный журнал включить значимые структурированные события
оркестрации Installer/Go (например, открытие/Save/Verify проекта, связь с
Execution Node, планирование, Start/Cancel и получение результата), если их
можно надёжно привязать к соответствующей операции или run. Показывать
источник события и сохранять порядок внутри каждого источника; не выдавать
локальные Go debug-логи за
авторитетные события выполнения и не дублировать одно действие дважды.
Корреляцию и хранение Go-событий определить в плане milestone, не создавать
ради этого вторую модель проекта.
Предусмотреть понятные пустое/недоступное состояния. Не создавать вторую базу
желаемого состояния и не выводить секреты, сырые учётные данные или
неотфильтрованный Ansible output. До реализации кнопка «Логи» остаётся
отключённой; точный UX и контракт чтения истории определить в плане milestone
перед разработкой. Это не блокирует текущие SI11-тесты реализованного
интерфейса.
Решение владельца для текущей реализации: «Журналы» показывают только события
текущего запуска Installer в памяти текущего процесса; после нового запуска
Installer журнал пуст. В интерфейсе поток выводится страницами по 512 строк,
все поля события доступны как скрываемые колонки. Это решение сужает исходный
исторический scope ниже; лимит Core/Go повышен до 16 384 событий для покрытия
сценария на 10 000.

При подготовке UI-LOGS-01 посмотреть на пользовательские сценарии и подачу
журналов в Platform Installer V1 как на источник удачных UX-идей. Не переносить
оттуда пакеты, модели или контракты без отдельного анализа границ V2; сейчас
репозиторий V1 для этой заметки не исследовался.

### Deferred feature: dependency-aware parallel installation

After the sequential all-services acceptance, consider bounded parallel
execution within one approved deployment plan. Complete the shared
infrastructure layer first: Keepalived, BIND, dns-client and the HAProxy
configuration that does not depend on application backends. Then run
independent application deployments, such as Kafka, Redis and Vault,
concurrently. A backend or other operation that consumes an application
endpoint waits for that provider's apply/verify result; for example, the
Vault-backed HAProxy configuration cannot be finalized before Vault is ready.

Core's declared `dependsOn` edges remain the ordering authority. The future
controller scheduler must also serialize conflicting operations on the same
target (package manager, shared files, service reloads), retain one
authoritative run/journal and bounded task-event stream, and preserve
failure/cancel/secret-output semantics. Start with a small concurrency limit
and prove both speedup and unchanged apply/verify/repeat results. This is a
later feature, not part of the current sequential service acceptance.

### SERVICE-N: Additional production services

Each additional service is delivered as a service package plus fixtures and evidence. Adding it must not require changes to topology engine, backend execution branches or the base frontend catalog.

Ready when:

- catalog discovery makes the service available automatically;
- generic validation/plan/apply/result paths are reused;
- only genuinely specialized UI uses an optional extension component;
- standalone and Installer executions are equivalent.

## SERVER-INFORMATION-CHECK-01

Owner-requested unified read-only server check: confirm SSH key, direct Go informational connection, agreed host fields in the lower card region and independent Проверен status. Execution Node information works before Core; installation readiness remains separate. See [plan](server-information-check-plan.md) and ADR-031. This does not authorize a new full-service installation or target mutation.

## EXECUTION-NODE-PASSWORD-AUTH-01

Owner-authorized password authentication for the common Execution Node SSH/SCP transport, alongside PEM, with unchanged explicit host-key trust and plan approval. Active-run authorization survives ordinary session expiry only for the exact run. See [plan](execution-node-password-auth-plan.md), ADR-032 and current acceptance status in CURRENT_STATE.
