# V2 roadmap and milestone gates

Application libraries follow the [chapter plan](work/application-libraries/implementation-plan.md).
A8 integrates A1–A7 into one Core plan/run with all-infrastructure Verify before
library mutation. Its gate covers mixed success/repeat, failure/cancel, protected
same-run Vault token handoff and infrastructure-only compatibility. A9 remains
the full standalone acceptance; Go and UI follow afterward.

[B](work/application-libraries/milestones/b/b-technical-plan.md) starts with the
bounded B0 Core extension for cross-run infrastructure Verify evidence and explicit
library-only/Verify-only scopes. Its gate is node-authoritative full coverage,
stale-evidence/trust/concurrency protection and standalone RED OS acceptance.
B1–B4 then integrate the existing Go adapter/writer/lifecycle; C owns application UI.
Local status is operational evidence, never a second desired-state or Start authority.

Current status and authorization live only in [CURRENT_STATE](../CURRENT_STATE.md).
This document describes sequence, scope and exit criteria. Recorded implementation
checkpoints are retained in [history](history/roadmap-checkpoints-20261012.md).

The roadmap is dependency-based, not a calendar promise. A milestone is complete only when every “ready” criterion is demonstrated. Partial implementation does not unlock the next architectural layer.

## Phase A — Architecture baseline

Kafka Schema Registry follows its [component implementation contract](work/kafka-schema-registry/implementation.md).
Its exit gates include native broker placement, conditional artifact source selection,
protected TLS, read-only Verify, repeat changed=0, owned clear and real Installer lifecycle.

Application libraries follow the separate [implementation plan](work/application-libraries/implementation-plan.md):
A1 standalone schemas/read-only Ansible+Core resolution, then rendering/image
delivery/provider hooks and execution integration, then Go and UI. Infrastructure
installation without library selection remains supported. A1 does not authorize A2
or real container/provider mutation; active status is recorded only in CURRENT_STATE.

[A2](work/application-libraries/milestones/a2/a2-technical-plan.md) covers explicit standalone
rendering, pinned image delivery and rootless Compose Apply/Verify. Its exit gates
include multi-host registry/offline selection, clean repeat, interrupted activation,
image isolation and readiness. Provider/secret hooks and Installer execution
integration are separate stages; A2 does not unlock Go/UI by itself.

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#core-01-repository-and-contract-skeleton). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#core-02-deterministic-topology-resolution). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#core-04-scoped-configuration-and-variable-context). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

CORE-04 adds deployment/member configuration scopes while preserving host vars
as physical-host context and preserving standalone Ansible as the runtime
authority. Service mappings declare allowed scopes. Derived output retains
independent member projections for multiple members on one host, exact static
reference states, source metadata and deterministic fingerprints.

The milestone does not implement a Jinja interpreter, facts, lookups, runtime
role-variable generation, plan/apply/verify, or production services.

### CORE-05: Canonical service metadata and variable preservation

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#core-05-canonical-service-metadata-and-variable-preservation). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

CORE-05 preserves unknown group and host variables as opaque pass-through
values with physical origin. Managed configuration and opaque input have
separate deterministic fingerprints, and an explicit future mapping promotes
an existing opaque role variable without rewriting its stored value.

## Phase C — First production service

### SERVICE-01A: Kafka KRaft standalone

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#service-01a-kafka-kraft-standalone). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#service-01b-kafka-kraft-distributed). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

EMPTY-PACKAGES-BOOTSTRAP-01 adds an owner-approved fixed-runtime prerequisite
path: empty bundle payload with os-release/explicit platform identity, installed
packages first, then supplied RPMs, then configured approved DNF repositories
only when absent from both. Service source rules remain unchanged. See the
[plan](work/runtime-bundle/empty-packages-bootstrap-plan.md) and
[journal](work/runtime-bundle/empty-packages-bootstrap-journal.md); current
implementation/acceptance status belongs only to CURRENT_STATE.

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#exec-01-execution-node-and-target-bootstrap). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#service-01c-kafka-kraft-real-multi-host-deployment). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#service-01d-kafka-split-brokercontroller-deployment). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#core-06-canonical-project-state-and-runtime-projection). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Kafka deployment/member identities are discovered, generated or recovered
before first mutation, transactionally persisted to project plus inventory,
reloaded and validated before runtime projection. Verify remains read-only.
The bounded legacy `platform_project` adapter and manual standalone
`platform_kafka_instances` input remain compatible without becoming additional
canonical stores. Centralized EXEC-01 fast acceptance for SERVICE-01A through
SERVICE-01D passed with repeat apply and verify at `changed=0`.

### PKI-01: Certificate and Java-store materialization

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#pki-01-certificate-and-java-store-materialization). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Kafka TLS, JKS, mTLS, imported/external CA, renewal and rotation remain
explicitly deferred to later milestones.

### CORE-07: Ansible-native canonical desired state

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#core-07-ansible-native-canonical-desired-state). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#service-02a-kafka-named-listeners-and-ssl-consumer-prerequisites). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

RED OS FAST acceptance passed for SERVICE-01A through SERVICE-01D with
profile-lifetime isolation: initial apply, separate verify and repeat apply
all passed; verify and repeat returned `changed=0 failed=0`. Core (113), Kafka
(22), catalog, syntax, offline and diff gates passed.

### UI-DESIGN-01: Installer interaction architecture

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-design-01-installer-interaction-architecture). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Deliverables:

- vertical global navigation with Installation as the project home and
  Topology as a separate page;
- generic deployment/member/host topology UX with service-specific editors;
- schema-driven service, PKI, findings, execution and source-value UX;
- Ansible-file ownership, optimistic save and external-change design;
- YAML/Jinja preservation boundaries, SecretRef and generated-state rules;
- static conceptual mockups.

### POSTGRES-01: PostgreSQL standalone and pg_auto_failover

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#postgres-01-postgresql-standalone-and-pg_auto_failover). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Production UI-01 remains dependent on a minimal backend read/write, run and
revision boundary; React or Wails must not assume those responsibilities.

### NET-01: Endpoint Groups and Resolved Service Endpoints

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-01-endpoint-groups-and-resolved-service-endpoints). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### NET-02: Keepalived / VRRP / Stable VIP Ownership

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-02-keepalived--vrrp--stable-vip-ownership). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### NET-03: Authoritative BIND DNS

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-03-authoritative-bind-dns). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### NET-03.1: DNS Client / Split DNS Runtime Adapters

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-031-dns-client--split-dns-runtime-adapters). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### NET-04: HAProxy

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-04-haproxy). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### NET-04.1: Keepalived HAProxy health tracking

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-041-keepalived-haproxy-health-tracking). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

## Phase E — Go backend adapter

### NET-04.2: Service-driven provider reconciliation

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#net-042-service-driven-provider-reconciliation). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Owner-authorized ENDPOINT-HAPROXY-PLACEMENT-01 replaces explicit provider
selection with endpoint → Keepalived placements → same-group HAProxy host
intersection, using existing source-owned integration and full reconcile.
Package backend defaults and overrides remain Core-owned. Missing placement
is an error with skipped integration, not a run failure. Source implementation
and acceptance status are tracked in CURRENT_STATE and the
[narrow implementation plan](work/endpoint-placement/endpoint-haproxy-placement-plan.md); earlier
NET-04.2 acceptance does not prove this changed selection.

### UI-BE-01: Installer UI / backend boundary

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-be-01-installer-ui--backend-boundary). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Recommended gated sequence:

### UI-BE-02: Read-only ProjectSnapshot

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-be-02-read-only-projectsnapshot). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### UI-BE-04A: Execution architecture audit

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-be-04a-execution-architecture-audit). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### UI-BE-04B: Core deployment planning

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-be-04b-core-deployment-planning). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### UI-BE-04C: Execution Node runtime protocol

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-be-04c-execution-node-runtime-protocol). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### EXEC-OBS-01: Ansible task observability and Installer-side event mirror

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#exec-obs-01-ansible-task-observability-and-installer-side-event-mirror). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

ADR-027 changes the target architecture without changing milestone statuses:
new Save is local structural persistence; Project Verify is optional derived
preflight on READY; every execution still requires fresh BuildDeploymentPlan.

### DEVX-01: Codex engineering harness

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#devx-01-codex-engineering-harness). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

### BACKEND-01: Core process adapter

This original adapter outline is superseded by UI-BE-04B–E; see
[execution contract](contracts/execution-planning-and-events.md) and
[the recorded decision](history/roadmap-checkpoints-20261012.md#backend-01-core-process-adapter).

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

Implementation breakdown: [UI-01A–UI-01J](work/ui-01/ui-01.md). Contracts → shell
→ empty project → first-write/review → servers → topology → PKI profiles →
service settings → portable export → native acceptance. Every milestone starts
with a mockup/contract check. Each stage requires an explicit owner start.

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-01-project-hosts-and-topology-editor). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

Owner-authorized export display-name refinement uses the export directory name
for the copied optional manifest's `metadata.name`, retaining source and ID.
Output digests and original source revision remain separate; see
[plan](work/project-lifecycle/project-export-display-name-plan.md) and CURRENT_STATE for its acceptance.

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
[UI-02 architecture](work/ui-02/ui-02-architecture.md). Credentialed Start requires the
future closed `StartExecution/v1alpha2` and
`ExecutionCapabilities/v1alpha2` contracts; legacy v1alpha1 remains valid for
planning/readiness but cannot authorize credentialed Start.

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#ui-02-installation-workflow). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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

Historical checkpoint: [source record](history/roadmap-checkpoints-20261012.md#post-ui-02-service-installation-acceptance). Current status is in [CURRENT_STATE](../CURRENT_STATE.md).

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
The staged [SI11 React/Wails UI test cases](work/services/service-install-11-ui-test-cases.md)
cover implemented controls on every page, state transitions and negative
boundaries before the uninterrupted all-services run. The owner's mention of
project deletion was an example of a sequence, not an added UI requirement.

After SI09 functional acceptance, plan `EXEC-PLAN-SCOPE-01` separately.
A future fresh, authoritative scoped plan must be able
to apply a selected deployment and reconcile only endpoint providers affected
by its changed endpoint relation, generically for every service. BIND and
HAProxy retain their full canonical-model `reconcile.yml` behavior so manual
drift is corrected; scope selection must not turn this into an unsafe
backend-file-only write. Unrelated deployments, such as unchanged Keepalived
and Vault, must not be reapplied. This needs its own contract/architecture and
acceptance before implementation; SI09 must not silently change existing
execution-plan semantics.

The sequence uses one Git-ignored cumulative Installer-managed QA project:
01 created it, 02–08 open and extend its exact saved revision, and 09 builds
the final single plan from that same project. A milestone may remove only the
old attributable runtime installation of its own service; it must not replace
the cumulative project or discard accepted preceding services. Redis standalone
is additionally accepted in a separate isolated QA project; Redis Sentinel HA
is the sole Redis deployment added to the cumulative project, because the
current Redis contract admits at most one Redis deployment per project.

Every installation uses `CreatePlan -> ApprovePlan -> Start`, reaches an
authoritative `SUCCEEDED` result with apply/verify PASS, and is repeated through
a fresh plan to prove `changed=0`. Record run IDs, actual placement, observed
service health, relevant PKI/network integration, and secret-safe events/results.
For Kafka, verify cluster membership/quorum and TLS on all three target hosts.
For the final shared plan, verify cross-service dependencies and integrations.
Record before/after evidence that unrelated QA deployments were not changed.
The final shared-plan test starts only after the individual service tests pass.

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
операцию. План и потоки: [BROWSER-REMOTE](work/browser/browser-mode-remote-plan.md).

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
Накопленные предложения и конкретные кейсы: [UI-UX-01](design/ui-ux-01-proposals.md).

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

### DRAFT: подпрогресс текущей операции установки

Будущий scope, не часть текущего A9: показывать внутри общей операции библиотек
подтверждённый подпрогресс, например «запущено 12 из 30 контейнеров».
Core определяет общее число размещений из авторитетного плана и сообщает
завершённые размещения через существующий поток событий. UI только отображает
эти данные; не разбирает Ansible tasks и не опрашивает Docker самостоятельно.
Один экземпляр на двух хостах учитывается как два размещения.

Для общей шкалы рассмотреть вес операции по числу размещений: обычное действие
сохраняет вес 1, Apply/Verify приложений получают вес N. Доля завершённых
размещений двигает шкалу внутри операции. Общие хуки библиотеки и публикация
endpoint остаются частью Apply; полный вес подтверждается только успешным
завершением всей операции. Это доля выполненной работы, не оценка времени.

Сохранить существующие операции/плейбуки, approval binding, порядок и
failure/cancel semantics. Не добавлять пользовательские настройки весов,
дополнительные target-запросы или отдельный механизм установки. Перед
реализацией уточнить минимальный контракт plan/event, обработку повторных и
переставленных событий, восстановление счётчика и поведение при ошибке;
проверить обычный infra-only план и одну/несколько библиотек. Черновик не
авторизует реализацию и не меняет текущий расчёт процента.

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

Owner-requested unified read-only server check: confirm SSH key, direct Go informational connection, agreed host fields in the lower card region and independent Проверен status. Execution Node information works before Core; installation readiness remains separate. See [plan](work/server-information/server-information-check-plan.md) and ADR-031. This does not authorize a new full-service installation or target mutation.

## EXECUTION-NODE-PASSWORD-AUTH-01

Owner-authorized password authentication for the common Execution Node SSH/SCP transport, alongside PEM, with unchanged explicit host-key trust and plan approval. Active-run authorization survives ordinary session expiry only for the exact run. See [plan](work/execution-node-password-auth/execution-node-password-auth-plan.md), ADR-032 and current acceptance status in CURRENT_STATE.
