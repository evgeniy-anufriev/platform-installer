# Current state

## Phase

Architecture and contract design.

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

## Not implemented

- Contract schemas.
- Ansible collection, roles, plugins or playbooks.
- Production services.
- Go backend.
- Persistence.
- Desktop or web UI.

## Next gate

Begin `CORE-01 Repository and Contract Skeleton` from `docs/roadmap.md` only after an explicit implementation request.
