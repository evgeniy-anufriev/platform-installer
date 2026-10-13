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
│ schema validation | topology resolver | execution projection  │
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

`Ansible Core` means the independently distributable automation product, not only upstream `ansible-core`. It may contain an Ansible collection, roles, standard playbooks, validation modules/plugins, schemas and callbacks. Its initial public interface is standard `ansible-playbook`; it has no required proprietary launcher and does not depend on Go or the Installer database.

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
- standard `ansible-playbook` invocation contract.

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
    -> target-free resolved immutable plan
    -> explicit confirmation/fingerprint check
    -> execution-time observations and artifact source resolution
    -> generated ephemeral workspace
    -> Ansible execution
    -> verification
    -> structured result + sanitized diagnostics
```

Each arrow has a versioned contract. Later layers consume these contracts rather
than constructing alternate models. Discovered facts and runtime observations
remain separate timestamped state; they are not inputs to the deterministic
deployment plan.

## Topology remains central

Topology is not reduced to inventory. The project explicitly models:

- hosts and operator-selected addresses;
- named service deployments;
- service mode;
- members and their placement on hosts;
- member roles;
- dependencies between deployments;
- endpoint groups and direct deployment endpoint assignments;
- network and certificate policies.

Examples supported by the same model:

- one standalone PostgreSQL deployment;
- one three-node Patroni deployment;
- two independent `pg_auto_failover` deployments;
- no PostgreSQL deployment at all.

The portable project initially uses normal Ansible inventory, `group_vars` and `host_vars` as desired input. Service topology remains explicit data rather than being inferred from ad hoc group membership. Core deterministically resolves execution groups and runtime role variables from that input. Roles apply the selected placement; they do not silently choose it.

CORE-07 fixes those standard Ansible inputs and role defaults as the canonical
user-owned desired state. The Installer edits the same files; it does not own a
parallel service model. Generated identities, fingerprints and locks are kept
in schema-constrained machine state, while `project.yml` is optional
compatibility/metadata and is not required for standalone operation.

## Distribution model

The standalone distribution is a digest-locked offline bundle containing:

- Ansible collection and roles;
- service manifests and schemas;
- playbooks and callbacks;
- supported Python/collection dependencies or an explicit prerequisite contract;
- artifact manifest and signatures/trust metadata;
- examples and operator documentation.

Owner clarification (2026-10-13, EMPTY-PACKAGES-BOOTSTRAP-01): DNF may update
already installed dependencies while installing missing runtime prerequisites.
When all prerequisites are installed, preparation performs no package transaction.
Actual React/Wails Prepare/READY acceptance is outside this implementation stage;
its absence does not constitute verified application-flow acceptance.

The explicit runtime prerequisite contract also supports an empty RPM payload:
Linux build-host os-release or explicit platform metadata declares compatibility.
Selected-node preparation consumes installed prerequisites first, then supplied
verified RPMs, and installs prerequisites absent from both through the existing
configured approved DNF repositories (ADR-021, EMPTY-PACKAGES-BOOTSTRAP-01).
Such a bundle requires repository access on an unprovisioned node; service
artifact closure requirements are unchanged.

The execution node is a selectable logical execution role. It may be the
supported local Linux Installer environment, an eligible project target, or an
external Linux host. A dedicated Linux host is one supported topology, not a
requirement; WSL2 remains a development adapter. Container or other future
execution mechanisms remain adapter choices and do not affect project or role
contracts. The monorepo boundary keeps Core and service roles independently
packageable and testable despite sharing one source repository with the later
backend and frontend.

## Security invariants

Execution detail observability is implemented by EXEC-OBS-01. The managed
Ansible callback produces safe task events through the same authoritative
Execution Node journal writer. Paginated GetEvents feeds Go RunObserver,
which writes a derived local runtime mirror and delivers typed subscriptions.
Future UI uses those subscriptions. Task-detail degradation and local mirror
failure do not change deployment outcomes; critical lifecycle integrity
retains its fail-closed policy. See [EXEC-OBS-01](work/execution/exec-obs-01.md).

- Plaintext secrets are runtime-only.
- Project data contains opaque secret references or required-secret declarations.
- Generated secret files use restrictive permissions and guaranteed cleanup.
- SSH host keys are verified independently for execution node and targets.
- Plans are immutable and fingerprinted before mutation.
- Public Internet repositories are never enabled implicitly.
- Package resolution is `INSTALLED -> configured REPOSITORY -> verified PAYLOAD -> BLOCKED`.
- Passwordless sudo is not required and sudoers is never changed implicitly.

Execution access has separate lifetimes from QA workspaces. A prepared
Execution Node stores its managed SSH identity under a persistent runtime
state root, outside per-run QA workspaces, with restrictive permissions. The
workspace, logs and temporary inventory overlays remain ephemeral. Before a
managed run, the generic EXEC-01 access gate may prepare or reuse that
identity, reconcile its public key on remote targets, and verify elevation;
service playbooks do not implement SSH recovery.

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

### Informational server SSH exception

Owner-approved SERVER-INFORMATION-CHECK-01 permits the Go workstation to contact a saved target or Execution Node directly for host-key confirmation and bounded read-only system information. This exception does not execute Core/Python/Ansible, mutate infrastructure, resolve Ansible inventory precedence or authorize installation. The address/port are those of the saved server card. The owner-approved explicit key confirmation supplies the same exact pin to existing installation target trust through the Execution Node. Installation rejects a changed key or endpoint and still requires fresh plan approval. Facts are session-only observations; see [plan](work/server-information/server-information-check-plan.md).

Execution Node SSH authentication supports session passwords and PEM using the same pinned OpenSSH/SCP transport. Passwords stay in broker memory; a command-owned ASKPASS capability supplies one helper response. A retained password after lease expiry is available only for the exact active Start/run, never ordinary checks or another Start. See ADR-032 and [password plan](work/execution-node-password-auth/execution-node-password-auth-plan.md).
