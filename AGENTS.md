# Platform Installer V2 — Agent Instructions

Platform Installer V2 is designed from the outside in:

`Standalone Ansible Core -> stable portable project contract -> Go adapter/orchestrator -> UI editor`.

The V1 repository at `../platform-installer` is a reference and requirements source. Do not copy V1 packages or models wholesale.

## Current phase

CORE-01 through CORE-07A, PKI-01, EXEC-01 and SERVICE-01A through SERVICE-01D
are complete, including the focused generic Kafka role lifecycle refactor.
The next gated milestone is SERVICE-02A: Kafka named listeners and SSL
consumption. Do not begin SERVICE-02A, a new production service, backend or
frontend without the corresponding milestone request.

Until that request is made, preserve the established standalone Ansible Core
contracts, Ansible-native desired-state ownership, managed Kafka/PKI
projections and execution-node boundaries. Treat resolved topology,
configuration, runtime projections, plans, facts and results as derived state.

## Boundaries

- Ansible Core must validate, plan, apply and verify a project without Go, Wails, SQLite or the UI.
- The portable project is the canonical desired state.
- Resolved execution groups/variables, runtime workspaces, facts, plans and results are derived state. Operator-authored inventory is desired project input.
- Ansible roles consume ordinary documented variables and remain usable with manual inventory.
- Go may orchestrate Ansible Core but must not reimplement service or topology rules.
- UI is an editor and projection of the portable contract, not another source of truth.
- Service capabilities are declared by versioned service packages, not hard-coded into React.
- `project.yml` is optional compatibility metadata for the established
  Ansible-native path; inventory, `group_vars`, `host_vars`, role defaults and
  ordinary documented role variables remain authoritative as applicable.
- Managed Kafka and PKI projections are runtime-only; do not introduce a
  competing persistent desired-state model.

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
- Avoid overengineering: prefer built-in Ansible tasks, filters and a small
  explicit task sequence over custom Python modules/plugins. Introduce a new
  abstraction only when the built-ins cannot express the required behavior
  safely and the added contract is justified by reuse or complexity.
- Roles and tasks may contain hardcoded product invariants, but must not
  hardcode effective configuration. Dynamic endpoints, listener names,
  protocols, paths, identities and security policy must come from the resolved
  runtime projection shared by apply, verify and diagnostics.
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

The current next-gate decision is recorded in `CURRENT_STATE.md`: SERVICE-02A
remains explicitly gated by an owner request. Kafka TLS consumption must not
be inferred from the completed PKI-01 foundation.

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

### Established RED OS EXEC-01 connection

For the configured RED OS QA target at `192.168.56.101`, always connect as
`platform-automation` using the persistent execution identity
`.runtime/platform-exec-key-20260901` with `IdentitiesOnly=yes`. SSH key login
is the established transport. The target policy grants
`platform-automation ALL=(ALL) NOPASSWD: ALL`; use `sudo -n`/Ansible
`become: true` and do not use password-based sudo or the `admin` login for
EXEC-01 QA. Do not add or persist any credential values here. If the policy
is absent, diagnose or restore it only through the existing EXEC-01 bootstrap
mechanism.

## Local Test Artifacts

Local binary artifacts used for offline/integration QA live under:

`.runtime/artifacts/<service>/`

They are local test inputs and must not be committed.

Do not search Downloads/Desktop or download artifacts automatically during QA
or production execution when the expected artifact is missing. Report the
missing expected path instead. A separately authorized DEV acquisition may
download and verify an official artifact into this local cache; production
roles and production execution must use only approved local artifacts,
repositories or payloads and must never download from the Internet.
