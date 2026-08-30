# Platform Installer V2 — Agent Instructions

Platform Installer V2 is designed from the outside in:

`Standalone Ansible Core -> stable portable project contract -> Go adapter/orchestrator -> UI editor`.

The V1 repository at `../platform-installer` is a reference and requirements source. Do not copy V1 packages or models wholesale.

## Current phase

The repository is implementing CORE-01. Only standalone Ansible Core,
published contracts, service-package skeletons, fixtures and their tests are
in scope. Do not begin CORE-02, a production service, backend or frontend
without the corresponding milestone request.

## Boundaries

- Ansible Core must validate, plan, apply and verify a project without Go, Wails, SQLite or the UI.
- The portable project is the canonical desired state.
- Resolved execution groups/variables, runtime workspaces, facts, plans and results are derived state. Operator-authored inventory is desired project input.
- Ansible roles consume ordinary documented variables and remain usable with manual inventory.
- Go may orchestrate Ansible Core but must not reimplement service or topology rules.
- UI is an editor and projection of the portable contract, not another source of truth.
- Service capabilities are declared by versioned service packages, not hard-coded into React.

## State separation

Always distinguish:

- desired state;
- discovered facts;
- resolved plan;
- observed execution result;
- runtime-only secrets.

Never persist plaintext secrets in project files, inventory, logs, events, audit or diagnostics.

## Change discipline

- Read the relevant canonical document before editing.
- Prefer one contract over parallel DTOs.
- Update decisions and roadmap when a boundary changes.
- Use focused subagents for independent architecture review, implementation or QA when requested.
- Keep V1 unchanged unless the user explicitly requests a V1 change.

## Canonical documents

- `docs/architecture.md`
- `docs/ansible-core.md`
- `docs/project-contract.md`
- `docs/architecture-decisions.md`
- `docs/roadmap.md`
- `CURRENT_STATE.md`
