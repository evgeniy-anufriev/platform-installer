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

## Implemented

- Repository initialized.
- Architecture documentation skeleton created.

## Not implemented

- Contract schemas.
- Ansible collection, roles, plugins or playbooks.
- Production services.
- Go backend.
- Persistence.
- Desktop or web UI.

## Next gate

Approve the Architecture Baseline and begin `CORE-01 Repository and Contract Skeleton` from `docs/roadmap.md`.
