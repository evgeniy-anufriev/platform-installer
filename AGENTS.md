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

## Context Efficiency

- Always start with `AGENTS.md` and `CURRENT_STATE.md`.
- Read only architecture and contract documentation relevant to the task.
- Prefer targeted searches and symbols before opening full files.
- Do not inspect `ansible-core/**/_vendor/**` by default; inspect vendored tests
  or benchmarks only for dependency validation or vendor maintenance.
- Do not read all fixtures when one representative fixture and targeted search
  are sufficient. Do not inspect V1 unless its reference behavior is required.
- For generated artifacts, inspect source manifests and generators first.
- Do not perform repository-wide source dumps or paste complete successful logs;
  surface only relevant failure excerpts.
- Main Agent runs affected tests and uses representative fixtures. Delegate
  milestone-level regression, clean/offline and OS-specific checks to QA/Test.

`examples/catalog/service-catalog.yml` is generated, intentionally tracked and
reproducible. Its source of truth is the catalog manifests plus
`ansible-core/tools/build_fixture_catalog.py`.

## Test Credentials

Local integration-test credentials may exist under `.runtime/secrets/`.

- Never commit them.
- Never copy secret values into docs, Skills, fixtures or source.
- Never print secret values in logs or reports.
- Load them only at runtime.
- Redact them from command and error output.
- Missing credentials must produce a clear test prerequisite failure.

## Test Execution Environment

The Windows development workstation is not the canonical runtime for Python/Ansible Core tests.

- Prefer the configured RED OS test VM when Python or Ansible is unavailable locally.
- Missing `python`, `py`, `pytest` or `ansible-playbook` on Windows is not by itself a reason to mark tests `NOT TESTED` when the RED OS QA environment is available.
- Execute Python/Ansible tests on the RED OS VM through the existing test connection.
- Use local Windows execution only for checks supported there, such as Git, diff and static-file checks.
- Do not install Python/Ansible on Windows merely to run Core QA unless explicitly requested.
- Test commands must use the current working-tree version, not a stale remote copy.
- Transfer only required repository content to a temporary remote test workspace.
- Clean temporary remote test workspaces after QA unless preservation is explicitly required for debugging.
- Never modify target hosts during read-only Core tests.
- RED OS is the primary current Core QA environment.
- ALT Linux validation is required only for ALT-specific milestone behavior or when explicitly requested.
