# Platform Installer V2 architecture

## Objective

V2 is a portable infrastructure product whose primary executable component is a standalone Ansible Core. The Installer is an optional editor and orchestrator of the same project that operators can validate and deploy without the GUI.

The architecture optimizes for:

- offline and protected networks;
- RED OS and ALT Linux targets;
- explicit topology and deterministic placement;
- multiple independent deployments of the same service type;
- reproducible plans and executions;
- runtime-only secrets;
- smaller, local change surfaces;
- replaceable execution mechanisms.

## System boundary

```text
┌───────────────────────────────────────────────────────────────┐
│ Portable Project Bundle                                       │
│ desired project + pinned catalog + artifact lock              │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────┐
│ Standalone Ansible Core                                       │
│ schema validation | topology compiler | inventory projection  │
│ plan | roles | verification | events/results                  │
└──────────────────────────────┬────────────────────────────────┘
                               │ SSH/become
                         target Linux hosts

Optional clients of the same boundary:

┌──────────────────────────┐       ┌────────────────────────────┐
│ Go adapter/orchestrator  │<─────>│ UI visual project editor   │
│ runs Core, stores runs   │       │ edits desired state only   │
└──────────────────────────┘       └────────────────────────────┘
```

`Ansible Core` means the independently distributable automation product, not only upstream `ansible-core`. It may contain an Ansible collection, roles, playbooks, inventory/validation plugins, schemas, callbacks and a small standalone launcher. It must not depend on Go or the Installer database.

## Three layers

### 1. Ansible layer

Owns:

- portable project schema and semantic validation;
- versioned service package catalog;
- topology resolution and deterministic Ansible projection;
- target preparation and service convergence;
- package source policy and offline artifacts;
- apply-time safety assertions;
- target verification;
- normalized events and execution result contract;
- standalone CLI/command contract.

It does not own GUI state, SQLite identities, Wails DTOs or desktop lifecycle.

### 2. Installer backend

Added after Core stabilization. It owns:

- project file lifecycle and transactional local persistence;
- invocation of the published Ansible Core contract;
- execution-node transport and workspace synchronization;
- runtime credential resolution;
- concurrency, cancellation and recovery;
- audit and full sanitized logs;
- read models optimized for UI.

It must not reproduce service validation, topology rules, inventory construction or role defaults.

### 3. UI

Added after the backend adapter. It owns:

- visual editing of hosts, service deployments, placements and endpoints;
- service catalog presentation from manifests;
- schema-driven configuration forms with optional specialized editors;
- validation, plan, progress and result projections;
- diagnostics and offline help.

It must not own a hard-coded service catalog, compute inventory, resolve TLS identities or interpret raw Ansible output.

## Canonical data flow

```text
Desired Project
    -> structural and semantic validation
    -> discovered facts snapshot (separate input)
    -> resolved immutable plan
    -> explicit confirmation/fingerprint check
    -> generated ephemeral workspace
    -> Ansible execution
    -> verification
    -> structured result + sanitized diagnostics
```

Each arrow has a versioned contract. Later layers consume these contracts rather than constructing alternate models.

## Topology remains central

Topology is not reduced to inventory. The project explicitly models:

- hosts and operator-selected addresses;
- named service deployments;
- service mode;
- members and their placement on hosts;
- member roles;
- dependencies between deployments;
- endpoint groups and endpoint bindings;
- network and certificate policies.

Examples supported by the same model:

- one standalone PostgreSQL deployment;
- one three-node Patroni deployment;
- two independent `pg_auto_failover` deployments;
- no PostgreSQL deployment at all.

Ansible inventory is a deterministic derived projection. Roles apply the resolved topology; they do not silently choose placement.

## Distribution model

The standalone distribution is a digest-locked offline bundle containing:

- Ansible collection and roles;
- service manifests and schemas;
- playbooks and callbacks;
- supported Python/collection dependencies or an explicit prerequisite contract;
- artifact manifest and signatures/trust metadata;
- examples and operator documentation.

The precise production execution packaging—dedicated node, container or another Linux environment—is an adapter decision and does not affect project or role contracts.

## Security invariants

- Plaintext secrets are runtime-only.
- Project data contains opaque secret references or required-secret declarations.
- Generated secret files use restrictive permissions and guaranteed cleanup.
- SSH host keys are verified independently for execution node and targets.
- Plans are immutable and fingerprinted before mutation.
- Public Internet repositories are never enabled implicitly.
- Package resolution is `INSTALLED -> configured REPOSITORY -> verified PAYLOAD -> BLOCKED`.
- Passwordless sudo is not required and sudoers is never changed implicitly.

## Compatibility

Supported combinations are compatibility data populated by integration evidence. The design must not invent certified RED OS, ALT Linux, Ansible, Python, Java, container-runtime or LXC versions.

## V1 reuse policy

Reuse after review:

- verified requirements and security invariants;
- RED OS/ALT Linux discovery knowledge;
- SSH host-key and secret-redaction test cases;
- event normalization concepts;
- offline manifest/trust concepts;
- topology, endpoint and TLS edge cases;
- idempotency and integration scenarios.

Reimplement behind V2 contracts:

- topology compilation;
- project validation;
- execution orchestration;
- portable export/import;
- persistence projections;
- UI page state.

Do not carry forward:

- duplicated frontend service catalogs;
- implicit default/demo instances;
- raw internal identifiers in normal UI;
- derived plans persisted as editable desired state;
- per-page business models;
- Go-only inventory semantics;
- service rules duplicated across Go, React and YAML.
