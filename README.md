# Platform Installer V2

Standalone Ansible Core -> portable project contract -> Go adapter/orchestrator -> UI editor.
The standard Ansible project is canonical desired state. Core owns infrastructure
semantics on the selected Execution Node; Go owns Installer lifecycle and guarded
filesystem transactions. React uses the shared backend interface for Wails and
Browser transports.

## Start here

- [Agent instructions](AGENTS.md): mandatory boundaries and procedure routing.
- [Current state](CURRENT_STATE.md): current status, blockers and authorized steps.
- [Task index](docs/agent-index.md): recurring-task contracts, code and checks.
- [Administrator guide](docs/guides/installer-engineer-guide.md): operator workflows.
- [Architecture](docs/architecture.md), [project contract](docs/project-contract.md),
  [Core](docs/ansible-core.md), [ADRs](docs/architecture-decisions.md) and
  [roadmap](docs/roadmap.md): read the sections relevant to the task.

## Repository layout

| Path | Purpose |
| --- | --- |
| `ansible-core/` | Standalone Core collection, fixed execution protocol, tools and playbooks |
| `services/` | Versioned manifests, schemas, standalone roles/playbooks and service tests |
| `contracts/` | Published versioned schemas and contract tests |
| `examples/` | Representative portable Ansible projects and generated catalog fixture |
| `internal/` | Go adapter, project lifecycle, guarded writer, execution and runtime secrets |
| Root `app*.go`, `installation_*.go`, `browser*.go` | Application and transport bindings |
| `frontend/src/` | React pages and shared `ProjectBackend`; Wails/Browser transports |
| `config/` | Versioned application configuration |
| `scripts/` | Bounded QA, source transfer and export helpers |
| `docs/` | Contracts, plans, evidence, conditional agent procedures and historical snapshots |

Core/Python acceptance runs on the configured RED OS environment from current
sources; see [QA procedure](docs/agent-procedures/qa.md). Windows orchestrates
the runtime and supports Go/frontend/document checks. Local runtime/secrets,
projects and bundles are not source inputs to ordinary repository searches.

V1 at `../platform-installer` remains a reference and is unchanged unless
explicitly requested. Historical milestone prose is evidence; current status
is maintained only in `CURRENT_STATE.md`.
