# Current state

## Phase

CORE-07, CORE-06, EXEC-01, SERVICE-01A through SERVICE-01D centralized
acceptance and the focused generic Kafka role lifecycle refactor are complete.
Ansible-native desired-state ownership and deterministic managed Kafka/PKI
projection are proven through the standalone execution path without requiring
`project.yml`.

## Established direction

- V2 is an independent Git repository next to V1.
- Ansible Core is the first deliverable and must operate without Installer.
- Standard inventory, `group_vars`, `host_vars` and role defaults are the
  canonical user-owned desired-state source.
- Topology remains a first-class part of desired state.
- Service deployments, placements, endpoint bindings and certificate scopes are explicit.
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
- Kafka `clientPort` and `controllerPort` remain simplified PLAINTEXT
  compatibility settings for SERVICE-01A through SERVICE-01D. Their projection
  is Kafka package responsibility, not a Generic Core endpoint contract;
  multi-listener TLS/SASL modeling is explicitly deferred.

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

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles.
- Production services beyond the accepted service slices.
- Go backend.
- Generic backend/project persistence beyond the scoped Kafka identity
  transaction primitive.
- Desktop or web UI.
- Generic Kafka listener/endpoint modeling and stateful transition workflows.
- Kafka TLS consumption of PKI-01 material.

## Next gate

CORE-01 through CORE-07, PKI-01, SERVICE-01A through SERVICE-01D, EXEC-01 and
the generic Kafka role lifecycle refactor are complete. SERVICE-02A (Kafka
named listeners and SSL consumption) remains gated by an explicit owner
request.
