# V2 roadmap and milestone gates

The roadmap is dependency-based, not a calendar promise. A milestone is complete only when every “ready” criterion is demonstrated. Partial implementation does not unlock the next architectural layer.

## Phase A — Architecture baseline

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

### CORE-03: Runtime, events and security foundation

Deliverables:

- apply/verify lifecycle;
- runtime secret-provider contract;
- normalized callback events and result;
- cancellation and interruption semantics;
- offline artifact/trust verification;
- sanitized full diagnostics.

Ready when:

- apply executes only a matching fingerprinted plan;
- a wrong/missing credential fails safely without leakage;
- cancellation prevents later phases from starting;
- exact actionable errors and full sanitized diagnostics are available;
- a second no-change execution is measurable.

Not ready when:

- consumers parse human stdout as the primary protocol;
- secrets occur in commands, events or plan files;
- public repositories are used implicitly;
- apply reconstructs a different plan.

## Phase C — First production service

### SERVICE-01A: Kafka KRaft standalone

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

Not ready when:

- manual target repair is required;
- only the happy path is tested;
- the role needs Go-generated internal objects;
- the role chooses or moves placements itself.

## Phase D — Stable project contract

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

## Phase E — Go backend adapter

### BACKEND-01: Core process adapter

Deliverables:

- typed invocation of the published validate/plan/apply/verify playbooks and artifacts;
- normalized event streaming;
- execution-node transport abstraction;
- dedicated Linux execution-node production adapter and WSL2 development adapter boundary;
- cancellation, timeout and lost-process recovery;
- contract conformance tests against standalone Core.

Ready when:

- backend launches the same standard Core playbooks operators use directly;
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

Deliverables:

- project lifecycle;
- service catalog driven by Core manifests;
- multiple deployments per service type;
- explicit member placement and dependency editing;
- endpoint binding editor;
- validation projection.

Ready when:

- standalone, Patroni and multiple independent cluster scenarios are expressible;
- a customer can omit an available service entirely;
- no implicit Kafka/PostgreSQL instance is created;
- exported project matches the editor state and runs standalone.

Not ready when:

- React contains a parallel service/mode catalog;
- changing tabs loses desired state;
- raw internal IDs or translation keys appear in normal UI.

### UI-02: Installation workflow

Deliverables:

- readiness, plan, confirmation, execution and result views;
- execution-node configuration/preparation;
- certificate configuration and derived preview;
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

## Phase G — Expansion

### SERVICE-N: Additional production services

Each additional service is delivered as a service package plus fixtures and evidence. Adding it must not require changes to topology engine, backend execution branches or the base frontend catalog.

Ready when:

- catalog discovery makes the service available automatically;
- generic validation/plan/apply/result paths are reused;
- only genuinely specialized UI uses an optional extension component;
- standalone and Installer executions are equivalent.
