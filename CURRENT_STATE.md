# Current state

## Phase

CORE-02 — deterministic explicit topology and placement resolution.

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

## Implemented

- Repository initialized.
- Architecture documentation skeleton created.
- Owner decisions OQ-001 through OQ-007 incorporated; `ARCH-01` is complete.
- Published alpha schemas for project parts, catalog, service manifest, findings,
  validation, plan, event and result.
- Standard `platform.core` validation playbook and controller-side module.
- Pure deterministic topology resolver producing canonical `ResolvedTopology`
  and a topology fingerprint from only used service-definition digests.
- Explicit placement/reference resolution with stable ordering and structured
  placement diagnostics; `host_vars` are not resolver inputs.
- Portable valid/invalid fixtures, including Kafka and PostgreSQL topology cases.
- Kafka service collection and explicit `roles/kafka_kraft` skeleton; production
  tasks are intentionally absent.

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles and production Kafka role tasks.
- Production services.
- Go backend.
- Persistence.
- Desktop or web UI.

## Next gate

CORE-01 and CORE-02 are complete. The next gate is CORE-03 runtime, events and
security foundation; it must be requested explicitly before implementation
begins.
