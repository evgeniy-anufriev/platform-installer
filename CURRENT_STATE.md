# Current state

## Application config and server type foundation (2026-09-14)

`OWNER-APP-CONFIG-01/02` is implemented. Repository development configuration
is the versioned `config/application.yml`; it currently declares `infra`,
`app` and `db`. New Installer sessions emit additive
`project-edit/v1alpha3`, whose `CreateServer` requires one grammar-valid type;
absence from the local configured list is warning-only.
Published v1alpha2 remains unchanged and both versions use the same Go
`EditCommand` model.

Canonical projects store only the grammar-valid ID as optional-on-legacy-read
`platform_host.type`. Core projects it through the existing
`ProjectSnapshot.hosts` object. Missing legacy and locally unknown valid types
are preserved without backfill; unknown configured types produce only a
nonblocking Installer diagnostic and do not alter Core status, validation or
fingerprint. Type has no service, topology, placement, Execution Node or source
selection semantics. UI-01E1 through UI-01E6 and UI-01F1 through UI-01F3 are
DONE; UI-01F4, UI-01F5 and UI-01F6 are DONE. UI-01F overall is DONE; UI-NET-01 is DONE (evidence: `docs/ui-net-01.md`), UI-01G1 through UI-01G4 are DONE (evidence: `docs/ui-01g1.md`, `docs/ui-01g2.md`, `docs/ui-01g3.md`, `docs/ui-01g4.md`), UI-01G overall is DONE, and UI-01H overall is DONE (evidence: `docs/ui-01h4.md`); UI-01I is NEXT.

## UI-01 implementation status (2026-09-07)

UI-01A through UI-01D are DONE. UI-01D was accepted by the owner without a
final revision-bound review. UI-01 overall remains NOT DONE; UI-01E1 through
UI-01E6 and UI-01F1 through UI-01F6 are DONE; UI-01F overall is DONE and UI-NET-01 is DONE while UI-01G overall and UI-01H overall are DONE; UI-01I is NEXT. UI-01B adds only the Wails/React read-only
shell and fixed `BuildProjectSnapshot` protocol operation; it adds no writer,
edit/session, candidate, save or apply path.

ADR-027 is implemented pre-UI-01E5 without changing milestone statuses. New
Installer sessions use local structural review and the existing guarded writer;
Save requires no Execution Node/Core call and returns a locally projected saved
revision. Reopen without a node reads only directly Installer-owned canonical
server fields. Explicit Project Verify runs the existing target-free
`BuildProjectSnapshot` operation, binds derived in-memory evidence to the saved
revision/attested active-runtime identity, and never mutates project files. A semantic Save
makes the new revision `UNVERIFIED`. Fresh `BuildDeploymentPlan` remains mandatory
before execution. UI-01E5 is DONE: readiness/preparation and navigation gating
use only the startup trusted binding, with explicit Prepare confirmation and
fresh post-Prepare Verify evidence. UI-01E6 is DONE: real Wails creation,
READY/navigation acceptance, target-free Core proof and RED OS regression
passed without service or target mutation; see `docs/ui-01e6.md`.

The 2026-09-05 accepted freeze is `docs/ui-01a-contract-freeze.md`; toolchain, mockup
reconciliation, reviews and QA are recorded in the adjacent `ui-01a-*`
documents. It fixed the one-file empty project (`project.yml` only), exact lock
provenance, first-save ownership, then-current complete-candidate Core proof,
project-edit v1alpha2 evolution, missing server/topology/PKI commands, and
runtime-only session credentials. ADR-027 supersedes only its Core-before-Save
requirement; its ownership and transaction protections remain. Historical
Core-contract and safety reviews reported 0 blocking findings.

The implementation sequence remains `docs/ui-01.md` (UI-01B through UI-01J).
Every milestone requires pre-start and acceptance mockup/contract checks.
Editor order is Servers → Topology → Certificates (PKI intent) → Service
settings. UI-02 execution/task-stream UI and target secret lease transport
remain separate.

## EXEC-OBS-01 completion (2026-09-05)

EXEC-OBS-01A through 01D are DONE. Managed Ansible task events use the existing
ExecutionEvent contract and authoritative Execution Node journal. Go
RunObserver provides pagination, replay, bounded typed subscriptions and the
derived Installer-side `.runtime/executions/<runId>/events.jsonl` mirror.
CLI `-command execution-watch -run-id <id>` prints the exact node/run/path,
follows until terminal and detaches on Ctrl+C without cancelling execution.

Real three-node Kafka runs `installer-1788591717613836600` (11m56s) and
`installer-1788592474776987100` (9m07s) both completed SUCCEEDED with PKI apply,
Kafka apply/verify, repeat changed=0, and 1,723 events each. Local mirror,
typed subscriber and remote stream matched. Live client/CLI restart and
Get-Content -Wait were proven. Real no_log/failure/degradation tests, Core,
Kafka/PKI, Go/race/vet, reproducibility, offline validation and secret audits
passed; both reviews have 0 blocking findings. See `docs/exec-obs-01.md` for
exact commands, test counts, durations and performance measurement limits.

UI-01A is the completed documentation freeze. UI-01B is DONE: its native
Windows Wails shell opens an existing project read-only through a READY
Execution Node and Core's fixed target-free ProjectSnapshot operation. UI-01C is
DONE: metadata-only local creation publishes one managed `project.yml`, and
empty-project reopen remains local without a Core snapshot. UI-01D is DONE by
owner acceptance without final revision-bound review: the Go-owned bounded
transient session, negotiated remote complete-candidate Core proof, guarded
first write and narrow Wails review/save shell passed Windows and RED OS
acceptance. UI-01E1 is DONE: new sessions use v1alpha4 server CRUD intents;
Core projects desired hostname, normalized SSH port and generic host references;
the staged Core-backed review/commit lifecycle is retained as historical
acceptance evidence, while ADR-027 defines the new local Save target. UI-01E2
Servers UI, UI-01E3 shared runtime session credentials, UI-01E4 Execution Node selection, UI-01E5 readiness/preparation and UI-01E6 cross-platform acceptance are DONE. UI-01F1 is DONE: lock-bound catalog and managed local topology reads passed. UI-01F2 is DONE: additive v1alpha5 topology intents, both placement forms, the final-state reducer and existing guarded local Save/reopen path passed Windows and RED OS gates with zero blocking review findings. UI-01F3 is DONE: the catalog-driven deployment editor, shared structural draft, local Review/Save and node-free reopen passed Windows and regression gates. UI-01F4 is DONE: shared member- and host-scoped placement editors use the existing session/review/local Save lifecycle; deterministic Wails frontend acceptance covers Save/reopen/clear without Core, Execution Node or target contact. UI-01F5 is DONE: Entry points reuses the five v1alpha5 endpoint intents; strict typed/bounded Go projection keeps raw Core endpoint/provider maps out of React, and INVALID exposes findings only. UI-01F6 is DONE: built Windows desktop, deterministic web-view, RED OS target-free/race and reproducibility acceptance passed. UI-01F overall is DONE; evidence is `docs/ui-01f6.md`. UI-NET-01 is DONE: v1alpha6 provider intent, guarded Save/reopen, Entry points editor and Core-preview freshness passed Windows/RED OS acceptance; evidence is `docs/ui-net-01.md`. UI-01G overall is DONE (evidence: `docs/ui-01g4.md`); UI-01H1 is DONE (evidence: `docs/ui-01h1.md`) and UI-01H2 is DONE (evidence: `docs/ui-01h2.md`); UI-01H3 is NEXT.

Status correction (2026-09-21): UI-01H overall is DONE; evidence is
`docs/ui-01h4.md`. UI-01I is NEXT. This supersedes the preceding historical
H3-next sentence.

## Phase

CORE-07, CORE-06, EXEC-01, SERVICE-01A through SERVICE-01D centralized
acceptance and the focused generic Kafka role lifecycle refactor are complete.
Ansible-native desired-state ownership and deterministic managed Kafka/PKI
projection are proven through the standalone execution path without requiring
`project.yml`.

SERVICE-02A is DONE. Named Kafka listeners, service-wide TLS profile
consumption, PKI-01 read-only verify reconstruction and SSL consumer
prerequisites are accepted through the standalone Ansible path.

NET-01 is DONE. Endpoint groups own one client-facing DNS domain and wildcard
intent; an endpoint-capable deployment assigns its group directly and Core
derives a read-only deterministic FQDN projection. Keepalived provider
deployments own virtual addresses; transport ports and routing remain deferred
to a future HAProxy milestone.

NET-02 is DONE. One host-scoped Keepalived deployment owns one unicast VRRP
instance, VRID, endpoint-group reference and one-or-more virtual addresses.
Three-node RED OS acceptance proved all-or-none VIP ownership, automatic
failover, rejoin without failback and idempotent apply/verify.

NET-03 is DONE. Authoritative BIND primary-secondary DNS derives canonical
host, endpoint and wildcard records from the Ansible-native desired state.
Three-node RED OS acceptance proved complete candidate/activation barriers,
native zone transfer, exact-once fingerprint/serial lifecycle, primary outage
continuity, recovery and idempotent verify/repeat apply.

NET-03.1 is DONE. The separate host-scoped dns-client package derives split
DNS inputs from one logical BIND deployment reference. Three-node RED OS
acceptance proved systemd-resolved route-only DNS, safe resolv.conf ownership,
normal resolver redundancy and post-recovery idempotence.

NET-04 is DONE. Host-scoped HAProxy provides HTTPS `public` routing on `*:443`,
deployment and opt-in host endpoints, normalized Host routing, and package-owned
stats backends. Three-node RED OS acceptance proved TLS endpoint verification,
runtime multi-node pooling, non-VIP-owner HAProxy failure isolation, recovery,
and idempotent verify/repeat apply.

NET-04.1 is DONE. Opt-in Keepalived HAProxy tracking uses a root-owned bounded
admin-socket helper and cluster-wide candidate/active barriers. Three-node RED
OS acceptance proved owner failure causes atomic configured-VIP migration,
natural recovery without failback, non-owner failure isolation, and idempotent
verify/repeat apply.

NET-04.2 is DONE. Successful source lifecycles run one read-only,
deduplicated integration projection, then full-model BIND before HAProxy even
when the source is already `changed=0`. Three-node acceptance proved provider
drift repair, desired-state-only add/remove, serial `4 → 5`, clean repeats,
shared PKI stability and final Keepalived health/idempotence.

UI-BE-01 is DONE. The accepted Installer boundary is a versioned query,
semantic-command and execution facade over the same canonical Ansible project.
ProjectSnapshot and other rich UI models are derived and read-only; normal
writes require EditPlan review, project/document revision checks and an
Ansible-native writer boundary. Arbitrary existing projects remain read-only
by default, while Installer-owned standard Ansible files are the recommended
write target. No production Go/Wails/React code, YAML writer or second
desired-state store was added.

UI-BE-02 is DONE. The controller-only `ProjectSnapshot/v1alpha1` query opens
the same standard Ansible project with Ansible-resolved inventory variables
and composes deterministic catalog, topology, configuration, endpoint, DNS,
HAProxy, PKI, validation and readiness views without target contact or writes.
Raw-byte project/document revisions, honest physical provenance, partial
results and secret exclusion are accepted against a three-host six-service
fixture, including offline RED OS execution.

UI-BE-03 is DONE. The Go Installer backend accepts a bounded semantic
`EditCommand`, produces an opaque reviewable `EditPlan`, proves staged native
Ansible documents through the authoritative controller-only ProjectSnapshot,
and commits only Installer-owned documents with revision/digest checks and a
journaled rollback-capable transaction. Go owns edit/session/transaction
semantics; Python/Ansible retains project loading, precedence and all
infrastructure authority. No Wails/React, apply/runtime execution, events or
second desired-state store was added.

DEVX-01 is DONE. The repository now has scoped Go/Core engineering rules,
repository-local Codex Skills for backend, adapter, writer and QA work,
documented implementer/reviewer prompt templates and a standardized final QA
workflow. Future Wails remains a thin deferred transport concern.

EXEC-01A is DONE. A trusted Linux acquisition environment builds the exact
Python/Ansible runtime closure, Go verifies and atomically publishes the
immutable bundle, and Prepare transfers, stages, proves and activates it
without requiring Python or Platform Core on Windows. Repeated Prepare returns
`READY` with `Changed:false`.

The production service entrypoint now performs one target repository probe per
requirement, calls the single existing resolver, supplies an ephemeral
target-filtered `ResolvedArtifactSource` projection to Ansible and stops before
transport when any result is `BLOCKED`. Real RED OS acceptance proved Kafka
`NOT_FOUND -> OFFLINE_BUNDLE -> artifact_delivery -> SHA-256 -> apply/verify`
with repeat `changed=0`, and three-node Keepalived
`AVAILABLE_COMPATIBLE -> REPOSITORY -> apply/verify` with repeat `changed=0`
and no artifact delivery. A separate shared-gate test proved a blocked source
cannot reach a mutation sentinel.

Operational offline bundles use only the current project-root
`bundle/<digest>/` cache entry; replacement prunes the prior local digest.
Kafka and future service payloads exist only inside a verified bundle
under `runtime/artifacts/<service>/`; `.runtime/` remains the runtime-only DEV
input and QA state.

UI-BE-04A is DONE. The actual execution implementation and published
plan/event/result contracts were audited without adding production execution
code. `docs/ui-be-04.md` freezes Core ownership of deterministic
`DeploymentPlan`, private `ExecutionManifest`, ordering and trusted execution
semantics; EXEC-01A remains the source-resolution and delivery foundation.
Future execution uses only fixed semantic Execution Node operations, a detached
Core controller, durable non-PID-only ownership, bounded journal/event replay,
reconnect, cancellation and one mutating run per project. The synchronous
Kafka/Keepalived `ExecuteService` is retained only for EXEC-01A regression.

UI-BE-04B is DONE. Core now builds the authoritative target-free public
`DeploymentPlan/v1alpha2` from its own ProjectSnapshot/validation graph and
the same full service catalog, with a private Core-only ExecutionManifest bound
to the identical plan fingerprint. `project.yml.metadata.id` is required for
Installer-managed mutation; a fallback path identity returns
`PROJECT_IDENTITY_REQUIRED` and no executable manifest. Artifact requirements,
not repository/bundle source selection, are planned. The immutable runtime
release digest is semantic; `runtime/current`, timestamps, paths, facts and
secrets are not.

UI-BE-04C is DONE. The Execution Node exposes fixed semantic lifecycle
operations, stages private digest-bound manifests, dispatches only Core-owned
trusted operation identities, and runs them through a detached transient
systemd controller. Durable journal/event replay, reconnect, exactly-once
terminal results, whole-cgroup cancellation, interrupted recovery,
foreign-unit safety and bounded retention passed RED OS acceptance. UI-BE-04D
is DONE. Go now owns only public plan approval and session lifecycle over the
typed Execution Node protocol. UI-BE-04E is DONE: the production-shaped UI
lifecycle completed two serial Kafka runs successfully under an explicit
30-minute test timeout, and the direct Kafka regression proved repeat apply
`changed=0, failed=0`. UI-BE-04 overall is DONE; documentation-only UI-01A is
DONE and UI-01B remains separately gated.

## Established direction

- V2 is an independent Git repository next to V1.
- Ansible Core is the first deliverable and must operate without Installer.
- Standard inventory, `group_vars`, `host_vars` and role defaults are the
  canonical user-owned desired-state source.
- Topology remains a first-class part of desired state.
- Service deployments, placements, direct endpoint-group assignments and certificate scopes are explicit.
- Go backend and UI are deferred until the standalone contract is proven by a production service.
- Standard `ansible-playbook` with normal inventory, `group_vars` and `host_vars` is the initial standalone interface.
- Kafka KRaft is split into single-node `SERVICE-01A`, same-host distributed
  `SERVICE-01B` and real multi-host distributed `SERVICE-01C`.
- Execution Node is a selectable logical role and may be the local Installer,
  a project target or an external Linux host; dedicated host and
  local/target-host execution are supported profiles; WSL2 is development-only.
- Initial placement is explicit only.
- Role defaults remain the canonical default source for standalone Ansible;
  schema `default` values are not semantic defaults.
- Service packages declare explicit logical-setting to role-variable mappings;
  generic Core does not infer names.
- `ResolvedTopology` and `ResolvedServiceConfiguration` are derived,
  read-only projections and never persistent sources of truth.
- Unknown Ansible variables outside service mappings remain opaque,
  pass-through values with physical origin metadata.
- Production Kafka SERVICE-01A is implemented as a standalone service package;
  Kafka-specific playbooks remain inside `services/kafka`.
- The production Kafka role is topology-profile agnostic after input
  normalization; SERVICE-01A/01B/01C names are fixture and acceptance concerns,
  not role lifecycle branches.
- `platform_desired_state` in ordinary Ansible variables owns logical
  deployment intent; inventory `platform_deployments` owns physical member
  placement, roles and member configuration.
- `platform_generated_state` is machine-owned and limited to generated
  identities, fingerprints, locks and metadata. `project.yml.desiredState` and
  legacy `platform_project` are bounded compatibility readers, not new-writer
  targets or required Ansible user input.
- Managed service projections are runtime-only. Kafka continues to consume its
  public manual `platform_kafka_instances` input in standalone mode.
- QA state invariant: stable PKI identities and fingerprints persist, while PKI
  materialization plans remain derived; every independent Ansible execution
  reconstructs those plans through read-only resolution.
- TLS-capable service apply playbooks run a service-scoped `pki-apply` stage
  before service mutation. It selects only that service type's effective
  `tlsProfile` consumers; an empty selection is a PKI no-op. The standalone
  Core PKI playbook remains intentionally project-wide.
- Kafka `clientPort` and `controllerPort` remain bounded PLAINTEXT compatibility
  inputs. SERVICE-02A introduces Kafka-package-owned named listeners; their
  default model supplies PLAINTEXT and SSL endpoints, while SASL remains out of
  scope. A Kafka deployment/member selects one `tlsProfile` for all of its SSL
  listeners; no listener owns a separate certificate profile.
- EndpointGroup owns only a client-facing domain/wildcard namespace.
  `ResolvedServiceEndpoints` is derived-only, DNS-only and is not persisted to
  generated state. A provider deployment owns virtual addresses; PKI adds them
  to SAN only through `includeEndpointVip`. Kafka has no generic NET-01
  endpoint.
- DNS logical content fingerprint and serial are machine-owned generated state.
  Each apply materializes them once, then provides the same runtime projection
  to all BIND role tasks.  Primary zones are Ansible-managed; secondary zones
  arrive only through native BIND transfer.
- DNS clients are a separate host-scoped service package. `dnsServerRef` is
  the sole logical client-to-BIND link; server addresses and managed route
  domains are derived at runtime and NET-03.1 has no generated state.
- HAProxy publication is a typed relationship from a target service deployment
  to one HAProxy deployment. Its reusable backend settings are normalized after
  layered merge; deployment and explicit `hostEndpoint: true` routes share the
  existing DNS/VIP namespace. Keepalived HAProxy tracking is explicit and
  opt-in per Keepalived deployment; a referenced HAProxy deployment must share
  its endpoint group and placement.

## Implemented

- Repository initialized.
- Architecture documentation skeleton created.
- Owner decisions OQ-001 through OQ-007 incorporated; `ARCH-01` is complete.
- Published alpha schemas for project parts, catalog, service manifest, findings,
  validation, plan, event, result and resolved service configuration.
- Standard `platform.core` validation playbook and controller-side module.
- Pure deterministic topology resolver producing canonical `ResolvedTopology`
  and a topology fingerprint from only used service-definition digests.
- Explicit placement/reference resolution with stable ordering and structured
  placement diagnostics; `host_vars` are not resolver inputs.
- Versioned `ResolvedServiceConfiguration/v1alpha1` contract.
- Deterministic deployment-level configuration resolver combining literal role
  defaults with `serviceDeployments[*].configuration` overrides.
- Deployment/member scoped configuration with
  `ROLE_DEFAULT -> DEPLOYMENT_OVERRIDE -> MEMBER_OVERRIDE` precedence and
  `VariableContext(deploymentId, memberId, hostId)` projections.
- Non-literal Ansible/Jinja defaults are represented as `DEFERRED`; exact
  static references resolve deterministically, with `UNRESOLVED` and `CYCLIC`
  findings where applicable.
- Explicit service-package configuration mappings and Kafka role defaults.
- Canonical service-manifest metadata for managed and advanced settings, with
  generated tracked configuration schemas and defaults conformance checks.
- Structured findings for unsupported member-scoped settings.
- Opaque/pass-through variables retain physical origin and redact secret-like
  values without becoming managed settings; their deterministic fingerprint is
  separate from managed configuration fingerprints.
- Independent deterministic member projections and configuration fingerprints.
- Portable valid/invalid fixtures, including Kafka and PostgreSQL topology cases.
- Kafka 4.3.1 single-node combined broker/controller role with offline artifact,
  Java 21 prerequisite, KRaft storage initialization, configuration and
  systemd apply/verify playbooks.
- Generic Kafka member lifecycle with a legacy single-member compatibility
  adapter, deterministic full/local/controller/broker member sets, controller-
  only quorum projections, role-aware listener requirements, host-scoped
  listener/path collision validation, host-once preparation and deterministic
  application of zero or more local logical members.
- Explicit mutually exclusive dynamic/static quorum modes, stable dynamic
  controller directory IDs and role-derived `process.roles`; broker-only,
  controller-only and combined internal members are no longer prohibited by
  production role assumptions.
- SERVICE-01C real three-host fixture for `192.168.56.101` through `.103`,
  dynamic KRaft quorum, with centralized Kafka acceptance completed.
- EXEC-01 execution selection contract with separate candidate eligibility and
  post-preparation readiness, generic execution-environment preparation,
  target bootstrap, local self-target transport and runtime credential boundary.
- EXEC-01 execution identity hardening: persistent runtime SSH identity and
  known-hosts state outside per-run QA workspaces, idempotent preparation and
  generic ensure-access composition for self-target and remote targets.
- CORE-06 canonical state selection with bounded legacy `platform_project`
  compatibility, inventory-owned member normalization and blocking duplicate,
  unknown-deployment and conflicting-source diagnostics.
- Deterministic Kafka runtime projection containing effective member identity,
  roles, node IDs, quorum, addresses and target paths, with a separate
  `runtimeProjectionFingerprint` over final service-relevant values.
- Kafka identity discovery and pure generate/recover/validate decisions,
  transaction-safe project/inventory persistence, disk reload and second
  validation before any Kafka mutation. Verify remains read-only.
- CORE-07 Ansible-native canonical state selection, optional project metadata,
  inventory-owned member composition and isolated generated-state schema.
  Managed Kafka identity materialization writes only
  `platform-state.yml`, reloads from disk and validates again before service
  mutation; unrelated inventory/group/host variables remain byte-preserved.
- CORE-07A authoring safety baseline: managed Kafka apply validates desired
  state before identity discovery/materialization; Kafka managed configuration
  is closed while explicit `advancedConfig` remains the controlled native
  property namespace. `hash_behaviour = merge` remains required Ansible policy.
- Managed PKI request resolution now consumes the same Ansible-native topology
  without requiring `project.yml`; standalone manual Kafka and PKI inputs remain
  supported public contracts.
- Explicit deployment-scoped Kafka clean-install and separately acknowledged
  administrative/QA host reset operations; neither is an automatic reconcile
  or identity-mismatch fallback.
- PKI-01 standalone foundation: canonical MANAGED certificate authority,
  certificate and TLS profiles; topology-derived HOST/MEMBER/DEPLOYMENT
  requests; Execution Node PEM and dedicated PKCS12 materialization; atomic
  target deployment; read-only verification; deterministic request and
  materialization fingerprints. Changed initialized identity is blocked with
  `CERTIFICATE_REISSUE_REQUIRED`.
- PKI explicit leaf reissue: `pki-reissue.yml` requires a non-empty runtime
  selection of exact request IDs. Ordinary apply still blocks changed request
  identity; the explicit operation preserves prior request material in
  protected Execution Node state, rekeys and reissues selected leaves, supports
  marker-based recovery and keeps CA identity changes blocked.
- NET-01 endpoint foundation: the rejected `endpointBindings` alpha entity was
  removed; endpoint-capable service deployments select one endpoint group;
  PostgreSQL opts in through its service manifest; pure resolution yields a
  deterministic FQDN projection and feeds PKI-01 SAN derivation without
  generated-state writes, target contact or certificate lifecycle changes.
- NET-02 Keepalived: host-scoped inventory priority, one deployment per VRRP
  election domain, deployment-owned multi-VIP addresses, native candidate
  validation and read-only all-or-none ownership verification. Three RED OS
  nodes proved failover/rejoin/no-failback; NET-04.1 later adds an explicit
  opt-in HAProxy `vrrp_script`/`track_script` dependency.
- NET-03 BIND: deterministic authoritative primary-secondary DNS with complete
  candidate and activation barriers, native secondary transfer, read-only
  verification and a generated fingerprint/serial lifecycle.  The bounded
  native configuration surface is `advancedConfig.options.minimal-responses`.
- NET-03.1 DNS client: systemd-resolved is selected whenever its unit exists;
  otherwise NetworkManager is considered only with a proven split-DNS backend.
  The role owns a resolved drop-in only, never replaces `/etc/resolv.conf`, and
  blocks unsafe ownership or global-DNS fallback.
- NET-04 HAProxy: complete candidate/activation barriers preserve the exact
  validated graph. The package provides fixed HTTPS `public` routing and
  local TLS stats backends, reloads on active-graph or TLS-bundle changes, and
  treats candidate workspace assembly as ephemeral rather than desired-state
  change.
- NET-04.1 Keepalived HAProxy tracking: the package playbook owns explicit
  prepare, activate and reconcile phases. Barrier A requires every native
  candidate validation; Barrier B requires exact candidate-to-active SHA-256
  equality and every native active validation before any reload. The helper is
  root-owned `0750`, checks active HAProxy plus its local admin socket, and has
  no `weight`; tracking failure makes the local VRRP participant ineligible.

## Completed

- POSTGRES-01 is DONE. PostgreSQL standalone and pg_auto_failover runtime
  acceptance passed, including TLS, automatic failover, natural rejoin,
  post-rejoin verify and repeat apply with `changed=0` and `failed=0` on all
  participating hosts.
- NET-03 is DONE. Three-node BIND acceptance proved host, endpoint and
  wildcard authoritative answers, native secondary transfer, exact-once serial
  increment on logical zone change, service continuity during primary outage,
  recovery, and post-recovery `changed=0 failed=0` verify/repeat apply.
- NET-03.1 is DONE. Three-node DNS-client acceptance proved the derived
  primary-plus-secondary route-only server list, normal system resolution of
  host/endpoint/wildcard records, unrelated resolution preservation, fallback
  with one remaining BIND server, recovery and `changed=0 failed=0`.

## Validation evidence

- RED OS controller VM: targeted CORE-04 suite - 15 tests passed.
- RED OS controller VM: `python3 -m unittest discover -s ansible-core/tests` -
  43 tests passed.
- RED OS controller VM: `python3 ansible-core/tools/build_fixture_catalog.py
  --check` - fixture catalog reproducibility passed.
- RED OS controller VM: Ansible validation smoke passed with `changed=0`,
  `failed=0`, and validation status `PASS` on `localhost` only.
- RED OS controller VM: privileged `unshare -n` offline check passed.
- RED OS controller VM: Kafka 4.3.1 apply and verify passed; repeat apply and
  verify passed with `changed=0` and no storage re-format.
- RED OS controller VM: offline apply through `sudo unshare -n` passed with
  `changed=0`.
- RED OS controller VM: CORE-05 contract/resolver suite, full Core regression,
  generated-schema check, catalog check and offline `unshare -n` check passed.
- RED OS controller VM: Kafka SERVICE-01A apply, verify and repeat apply passed
  with `changed=0` after the metadata migration.
- No temporary remote QA workspace or artifact copy remained after QA.
- EXEC-01 centralized RED OS acceptance: node1 as local Execution Node and
  target, node2/node3 as SSH targets; Phase A preparation, Phase B bootstrap,
  key-based ping, elevated unified playbook and repeat bootstrap all passed.
- EXEC-01 regression: 60 Core tests and 4 contract tests passed; preparation,
  bootstrap and centralized connectivity playbooks passed syntax-check; unified
  PLAY RECAP contained node1, node2 and node3 with `changed=0`.
- EXEC-01 hardening focused validation: 14 focused identity/persistence tests,
  full Core (90) and Kafka contract (16) suites passed; repeated preparation
  and centralized ensure-access passed on RED OS with node1/node2/node3 recap
  and `changed=0`. Persistent key permissions were verified as `0600` private,
  `0644` public and `0600` known-hosts.
- Centralized SERVICE-01C acceptance through node1 Execution Node passed:
  apply/repeat/verify all returned `failed=0`; repeat and verify returned
  `changed=0` for node1, node2 and node3. Stopping node3 preserved a passing
  node1/node2 quorum verify; full verify reported node3 failed; recovery and
  final verify returned all three members healthy.
- Centralized SERVICE-01A replay passed after completing its fixture inputs:
  apply, repeat and verify passed; repeat and verify returned `changed=0`.
- SERVICE-01B focused diagnosis: a fresh canonical dynamic same-host run and a
  separate `127.0.0.1` endpoint experiment both formed a three-voter quorum;
  apply/repeat/verify passed after all controller listeners were ready. The
  earlier verify failure was an immediate post-start convergence race, not a
  dynamic-quorum, identity, storage-format or endpoint incompatibility.
- Focused Kafka lifecycle refactor regression on RED OS / Ansible Core 2.18.15:
  9 Kafka contract tests and 60 Core tests passed; fixture catalog check and
  SERVICE-01A/01B/01C apply/verify syntax checks passed.
- Final real lifecycle replay passed through the centralized Execution Node:
  SERVICE-01A repeat/verify, SERVICE-01B repeat/verify and SERVICE-01C
  repeat/verify all returned `changed=0`, `failed=0`. With node3 stopped,
  node1/node2 quorum verify passed while full desired-state verify failed on
  node3; node3 recovery and final three-host verify returned `changed=0`,
  `failed=0`. Runtime QA SSH key material was removed from node2/node3.
- Centralized SERVICE-01D acceptance through node1 Execution Node passed:
  split broker/controller deployment applied and verified with six members;
  repeat apply and final verify returned `changed=0`, `failed=0`. Broker stop
  preserved controller quorum and produced the expected degraded full-state
  verification; broker recovery restored all members. Controller stop likewise
  preserved the two-controller quorum, and controller recovery restored the
  full healthy state. Readiness polling closed the bounded post-start race.
- SERVICE-01D runner lifecycle evidence is persisted under the Execution Node
  QA directory. The runner records PID/stage/status, rejects a live duplicate,
  converts an orphaned `RUNNING` state to `STALE`, and records terminal PASS or
  FAILED states without secrets.
- CORE-06 RED OS regression passed: 90 Core tests, 20 Kafka tests, 14 focused
  Kafka cleanup/contract tests and 7 privileged offline tests. Catalog and
  configuration schemas were reproducible; apply/reset syntax and diff checks
  passed.
- CORE-06 centralized FAST acceptance passed for SERVICE-01A, SERVICE-01B,
  SERVICE-01C and SERVICE-01D: apply and verify passed, and repeat apply plus
  verify returned `changed=0`. Standalone manual Kafka input remained valid.
- PKI-01 RED OS acceptance: topology-derived managed PKI apply created a
  managed CA, PEM and dedicated PKCS12 key/trust stores on node1; target verify
  and repeat apply returned `changed=0`. A changed standalone request was
  blocked with `CERTIFICATE_REISSUE_REQUIRED` before certificate mutation.
- CORE-07 RED OS regression: 104 Core tests and 22 Kafka tests passed; generated
  configuration schemas and catalog are reproducible; Core, Kafka and PKI
  syntax checks passed; privileged network-isolated validation passed with
  `localhost changed=0` and no target contact.
- CORE-07 centralized Kafka FAST acceptance passed for SERVICE-01A through
  SERVICE-01D with managed `project.yml` deliberately absent. Every apply and
  verify passed; every repeat apply returned `changed=0` on all participating
  hosts. Failure/recovery scenarios were not repeated.
- CORE-07 managed PKI no-project acceptance passed. Apply, repeat apply and
  verify returned `failed=0`; repeat apply and verify returned `changed=0`.
- CORE-07A focused RED OS validation: Core suite (107), Kafka contract suite
  (22), managed-configuration tests and catalog reproducibility passed.
- SERVICE-02A focused RED OS validation: 11 focused listener/PKI tests,
  generated configuration schema and fixture catalog reproducibility, and
  Kafka apply syntax check passed. The isolated fixture bound PLAINTEXT, SSL
  and controller listeners and completed an SSL handshake with CA verification.
- SERVICE-02A FAST regression completed on RED OS with deterministic
  profile-lifetime roots: SERVICE-01A, 01B, 01C and 01D initial apply passed;
  separate verify returned `changed=0 failed=0`; repeat apply returned
  `changed=0 failed=0` for every profile. Core suite (113) and Kafka focused
  suite (22) passed, catalog and syntax checks were reproducible, and
  `sudo unshare -n true` passed. The regression also fixed the real SSL
  handshake EOF/timeout defect and split KRaft broker/controller listener
  projection contract without changing identity or PKI lifecycle semantics.
- NET-03.1 RED OS acceptance: systemd-resolved apply configured the derived
  `~scada.local` route on node1/node2/node3; separate verify, repeat apply,
  primary failure, one-secondary-remaining failure, recovery, post-recovery
  verify and post-recovery apply all passed. Core (137), focused service
  contracts (63), generated catalog/schema, target-free validation and
  privileged offline checks passed.
- NET-04 RED OS acceptance: Barrier A/B and candidate-to-active graph equality
  passed on node1/node2/node3. TLS hostname verification passed for deployment
  and all configured host endpoints; normalized Host with and without `:443`
  selected the same backend and unknown Host returned `503`. Runtime socket
  counters proved all three pooled HAProxy participants served requests. A
  non-VIP-owner HAProxy stop returned `503` only for its host endpoint while
  pooled and other host endpoints remained healthy; recovery restored all.
  Separate verify, repeat apply, post-recovery verify and post-recovery repeat
  apply all returned `changed=0 failed=0` on localhost and every target.
  An explicit selected leaf reissue added the endpoint wildcard SAN, deployed
  it to all HAProxy participants and returned to a clean ordinary repeat apply.
- NET-04.1 RED OS acceptance: opt-in tracking candidate and active barriers
  passed on all three nodes with exact per-node candidate/active checksums.
  Stopping HAProxy on the semantic owner produced helper failure and VRRP
  FAULT, then moved all configured VIPs to one healthy backup while the
  deployment endpoint remained available. Recovery returned the former owner
  to BACKUP without failback. A non-owner HAProxy failure became FAULT without
  moving the VIP. Final Keepalived/HAProxy verify and repeat apply returned
  `changed=0 failed=0` on localhost and all targets.

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles.
- Production services beyond the accepted service slices.
- Production UI editor beyond the accepted UI-01B read-only, UI-01C
  metadata-only creation and UI-01D first-write/review slices.
- Generic backend/project persistence beyond the scoped Kafka identity
  transaction primitive.
- UI-01E4 Execution Node panel, later UI editor slices and UI-02 transport.
- Stateful listener-transition workflows; these remain deferred.
- Imported/external CA materialization, JKS, mTLS, global JVM cacerts,
  renewal and rotation.

## Next gate

CORE-01 through CORE-07, CORE-07A, PKI-01, SERVICE-01A through SERVICE-01D,
EXEC-01, the generic Kafka role lifecycle refactor, SERVICE-02A,
UI-DESIGN-01, UI-BE-01, UI-BE-02 and UI-BE-03 are complete. UI-BE-03 adds the
bounded safe writer but no Wails/React, UI persistence, execution or second
desired-state model.

POSTGRES-01, NET-01, NET-02, NET-03, NET-03.1, NET-04, NET-04.1, UI-BE-03,
DEVX-01, EXEC-01A, UI-BE-04B, UI-BE-04C, UI-BE-04D and UI-BE-04E are DONE.
UI-BE-04 overall, EXEC-OBS-01, documentation-only UI-01A, UI-01B, UI-01C and
UI-01D are DONE. UI-01D was owner-accepted without final revision-bound
review. UI-01E is decomposed into E1-E6; UI-01E1 server CRUD integration is
DONE; UI-01E2 through UI-01E6 and UI-01F1 through UI-01F6 are DONE. UI-01F
overall is DONE; UI-NET-01 is DONE, UI-01G overall and UI-01H overall are DONE, UI-01I is NEXT,
and UI-01 overall remains not done.
