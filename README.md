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

Architecture baseline only. No application or Ansible implementation has been started.

The current decisions, contract outline and milestone gates are documented in:

- [Architecture](docs/architecture.md)
- [Ansible Core](docs/ansible-core.md)
- [Portable project contract](docs/project-contract.md)
- [Backend and UI boundaries](docs/backend-and-ui.md)
- [Architecture decisions](docs/architecture-decisions.md)
- [V1 reference audit](docs/v1-reference-audit.md)
- [Open questions](docs/open-questions.md)
- [Roadmap](docs/roadmap.md)
- [Current state](CURRENT_STATE.md)

## Relationship to V1

V2 will selectively reuse verified behavior, tests and algorithms. It will not inherit V1 persistence schemas, Wails DTOs, page state or execution-specific domain models as architectural constraints.
