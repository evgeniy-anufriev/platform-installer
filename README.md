# Platform Installer V2

Platform Installer V2 is a clean architecture track built beside V1. V1 remains the working reference implementation and the source of verified requirements, edge cases and integration scenarios.

V2 starts with a standalone, offline-capable Ansible distribution. The desktop Installer is added only after the Ansible project contract and the first production service are stable.

```text
Portable Project
      |
      v
Standalone Ansible Core
validate -> plan -> apply -> verify
      ^                 |
      |                 v
Go adapter         structured result
      ^
      |
Visual UI editor
```

## Current status

`ARCH-01` is complete. `CORE-01` is in progress: published contracts, the
`platform.core` collection, a controller-only validation playbook, project
fixtures and the Kafka service-package/role skeleton now exist. No production
role, target mutation, backend or frontend has been implemented.

## Repository layout

```text
ansible-core/                    standalone Core collection and playbooks
  collections/.../platform/core/
    plugins/
    roles/                       generic Core roles are added here
contracts/                       published versioned schemas
services/
  kafka/
    ansible_collections/platform/kafka/
      roles/kafka_kraft/         independently usable service role
examples/                        portable valid/invalid Ansible projects
backend/                         deferred until the Core contract is stable
frontend/                        deferred until the backend contract is stable
```

Validate the self-contained Core fixture on a Linux Ansible controller:

```bash
cd ansible-core
ansible-playbook -i examples/valid/inventory/hosts.yml playbooks/validate.yml
```

The current decisions, contract outline and milestone gates are documented in:

- [Architecture](docs/architecture.md)
- [Ansible Core](docs/ansible-core.md)
- [Portable project contract](docs/project-contract.md)
- [Backend and UI boundaries](docs/backend-and-ui.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [V1 reference audit](docs/v1-reference-audit.md)
- [Open questions](docs/open-questions.md)
- [Roadmap](docs/roadmap.md)
- [CORE-01 implementation](docs/core-01.md)
- [Current state](CURRENT_STATE.md)

## Relationship to V1

V2 will selectively reuse verified behavior, tests and algorithms. It will not inherit V1 persistence schemas, Wails DTOs, page state or execution-specific domain models as architectural constraints.
