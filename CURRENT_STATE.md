# Current state

## Phase

CORE-03 - deterministic service configuration resolution.

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
- Non-literal Ansible/Jinja defaults are represented as `DEFERRED`; Core does
  not implement an Ansible/Jinja variable engine.
- Explicit service-package configuration mappings and Kafka role defaults.
- `MEMBER_CONFIGURATION_UNSUPPORTED` blocking findings with deployment/member
  identity and exact paths.
- Configuration fingerprint independent of actual member placement.
- Portable valid/invalid fixtures, including Kafka and PostgreSQL topology cases.
- Kafka service collection and explicit `roles/kafka_kraft` skeleton; production
  tasks are intentionally absent.

## Validation evidence

- RED OS controller VM: `python3 -m unittest discover -s tests -p 'test_*.py'` -
  34 tests passed.
- RED OS controller VM: `python3 ansible-core/tools/build_fixture_catalog.py
  --check` - fixture catalog reproducibility passed.
- No production Kafka installation or target mutation was performed.

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Member/host-specific configuration precedence.
- Generic Core mutation roles and production Kafka role tasks.
- Production services.
- Go backend.
- Persistence.
- Desktop or web UI.

## Next gate

CORE-01, CORE-02 and CORE-03 are complete. The next gate is `SERVICE-01A`
Kafka KRaft standalone installation and verification. It must be requested
explicitly before production service tasks begin.
