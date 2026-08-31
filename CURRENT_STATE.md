# Current state

## Phase

EXEC-01 and SERVICE-01C centralized acceptance are complete. SERVICE-01B
dynamic same-host quorum is proven; its apply post-start readiness gate remains
the focused follow-up.

## Established direction

- V2 is an independent Git repository next to V1.
- Ansible Core is the first deliverable and must operate without Installer.
- The portable project contract is the single desired-state source.
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
- Kafka SERVICE-01B/01C distributed combined broker/controller role with
  explicit dynamic/static quorum mode, stable member directory IDs, full-cluster
  bootstrap projection and host-local member mutation.
- SERVICE-01C real three-host fixture for `192.168.56.101` through `.103`,
  dynamic KRaft quorum, with centralized Kafka acceptance completed.
- EXEC-01 execution selection contract with separate candidate eligibility and
  post-preparation readiness, generic execution-environment preparation,
  target bootstrap, local self-target transport and runtime credential boundary.

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

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles.
- SERVICE-01B apply lacks an explicit post-start quorum-readiness gate; direct
  verify can race Kafka's normal initial controller convergence.
- Production services beyond the accepted service slices.
- Go backend.
- Persistence.
- Desktop or web UI.

## Next gate

CORE-01 through CORE-05, SERVICE-01A, EXEC-01 and SERVICE-01C are complete.
The next gate is an explicit SERVICE-01B post-start readiness gate and replay;
dynamic quorum remains required and no fallback or storage change is authorized.
