# Current state

## Phase

CORE-04 - scoped configuration and variable context.

## Established direction

- V2 is an independent Git repository next to V1.
- Ansible Core is the first deliverable and must operate without Installer.
- The portable project contract is the single desired-state source.
- Topology remains a first-class part of desired state.
- Service deployments, placements, endpoint bindings and certificate scopes are explicit.
- Go backend and UI are deferred until the standalone contract is proven by a production service.
- Standard `ansible-playbook` with normal inventory, `group_vars` and `host_vars` is the initial standalone interface.
- Kafka KRaft is split into single-node `SERVICE-01A` and distributed `SERVICE-01B`.
- Dedicated Linux execution node is the production baseline; WSL2 is development-only.
- Initial placement is explicit only.
- Role defaults remain the canonical default source for standalone Ansible;
  schema `default` values are not semantic defaults.
- Service packages declare explicit logical-setting to role-variable mappings;
  generic Core does not infer names.
- `ResolvedTopology` and `ResolvedServiceConfiguration` are derived,
  read-only projections and never persistent sources of truth.
- Unknown Ansible variables outside service mappings remain opaque,
  pass-through values with physical origin metadata.

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
- Structured findings for unsupported member-scoped settings.
- Opaque/pass-through variables retain physical origin and redact secret-like
  values without becoming managed settings.
- Independent deterministic member projections and configuration fingerprints.
- Portable valid/invalid fixtures, including Kafka and PostgreSQL topology cases.
- Kafka service collection and explicit `roles/kafka_kraft` skeleton; production
  tasks are intentionally absent.

## Validation evidence

- RED OS controller VM: targeted CORE-04 suite - 15 tests passed.
- RED OS controller VM: `python3 -m unittest discover -s ansible-core/tests` -
  43 tests passed.
- RED OS controller VM: `python3 ansible-core/tools/build_fixture_catalog.py
  --check` - fixture catalog reproducibility passed.
- RED OS controller VM: Ansible validation smoke passed with `changed=0`,
  `failed=0`, and validation status `PASS` on `localhost` only.
- RED OS controller VM: privileged `unshare -n` offline check passed.
- No production Kafka installation or target mutation was performed; temporary
  remote QA workspace and validation artifact were removed.

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles and production Kafka role tasks.
- Production services.
- Go backend.
- Persistence.
- Desktop or web UI.

## Next gate

CORE-01, CORE-02, CORE-03 and CORE-04 are complete. The next gate is `SERVICE-01A`
Kafka KRaft standalone installation and verification. It must be requested
explicitly before production service tasks begin.
