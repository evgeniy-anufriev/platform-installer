# Platform Installer V2 — Agent Instructions

Platform Installer V2 is designed from the outside in:

`Standalone Ansible Core -> stable portable project contract -> Go adapter/orchestrator -> UI editor`.

The V1 repository at `../platform-installer` is a reference and requirements source. Do not copy V1 packages or models wholesale.

## Current phase

`CURRENT_STATE.md` is the authoritative dynamic source for milestone and
project status. Read it before beginning milestone work and require an explicit
owner request for the next gated milestone. This file contains durable
engineering and process instructions, not a second copied milestone ledger.

Preserve the established standalone Ansible Core contracts, Ansible-native
desired-state ownership, managed Kafka/PKI projections and execution-node
boundaries. Treat resolved topology, configuration, runtime projections,
plans, facts and results as derived state.

## Boundaries

- Ansible Core must validate, plan, apply and verify a project without Go, Wails, SQLite or the UI.
- Ansible Core and its Python runtime execute only on the selected Execution Node. The workstation may orchestrate with Go, use SSH/SCP, verify a returned bundle and publish its immutable cache, but is not a Core/Python execution environment.
- The portable project is the canonical desired state.
- Resolved execution groups/variables, runtime workspaces, facts, plans and results are derived state. Operator-authored inventory is desired project input.
- Ansible roles consume ordinary documented variables and remain usable with manual inventory.
- Go may orchestrate Ansible Core but must not reimplement service or topology rules.
- Go owns Installer application semantics: edit/session lifecycle, review plans,
  coordination and filesystem transactions. Python/Ansible owns infrastructure
  semantics and must not become the owner of Installer UI lifecycle.
- Local Save proves only structural/write safety through the guarded managed
  writer and does not require Core or an Execution Node. Optional Project
  Verify evaluates the exact last saved revision through target-free Core.
- Project Verify never authorizes execution. Every execution requires a fresh
  authoritative `BuildDeploymentPlan` for the current saved revision/runtime,
  approval, and `StartExecution` bound to that plan.
- Go must not recreate Ansible precedence or service/Core rules. Future Wails is
  a thin transport over the same Go backend.
- Installation source selection is one node-scoped policy: a compatible
  artifact from that node's configured approved repository wins; otherwise a
  compatible artifact in the immutable offline bundle is used; otherwise the
  operation is blocked. DEV may explicitly acquire required closure into a new
  bundle version; PROD never mutates the distributed bundle.
- React/Wails owns rendering and transport only: it must not parse Ansible YAML
  or calculate topology, FQDN/VIP/provider, validation or service semantics.
- Core owns derived `ProjectSnapshot`, endpoint/provider/PKI and deployment
  semantics. Python must not own Installer edit/session/process/UI lifecycle.
- No second desired-state persistence exists: SQLite may index runtime state but
  never becomes `config_json` authority; generated state is machine-owned only.
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
- Before each UI milestone (including its backend sub-milestones), review
  `docs/ui-design-01-mockups.html`, `docs/ui-design-01.md` and the milestone plan.
  Record the relevant screens/flows and any contract discrepancies before coding;
  resolve material discrepancies with the owner instead of silently diverging.
  Repeat the mockup check at acceptance. Demo values/statuses are not Core rules.
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
- `architecture-reviewer` (`.codex/agents/architecture-reviewer.toml`) is an
  independent read-only advisor to the owner, not an autonomous approval or
  convergence authority. For an architecture-sensitive plan, run one FULL
  PLAN review before presenting the plan to the owner. APPROVE goes to owner
  approval; APPROVE_WITH_CHANGES may receive obvious bounded nonblocking
  corrections and then goes to the owner without an automatic full re-review;
  BLOCK stops automatic work and returns the finding IDs, evidence, impact,
  smallest corrections and implementer recommendation to the owner. Never
  redesign and repeatedly review until APPROVE. A further full PLAN review
  requires an explicit owner request, except that one new review may follow a
  materially changed owner-approved architecture revision.
- Architecture DIFF review is risk-based. HIGH-RISK changes require one FULL
  DIFF review: canonical-state ownership, filesystem transactions/first save,
  migration, secret or credential persistence/security boundaries, Execution
  Node or process lifecycle/cancel/recovery, artifact/bundle trust or source
  authority, Vault/container-runtime architecture, a new persistence layer, or
  public/versioned contract architecture. MEDIUM-RISK changes normally rely on
  the PLAN review and need DIFF review only when the approved plan requires it,
  implementation changes architecture materially, or the owner requests it;
  examples include typed CRUD on the existing lifecycle, server model
  extensions, service editor integration and topology UI on existing
  contracts. LOW-RISK layout/labels/display fields, application-config value
  additions, CLI formatting, documentation, straightforward tests and bounded
  fixes within an approved contract normally require no architecture review.
- Per architecture review gate, the maximum automatic budget is one initial
  FULL review plus at most one TARGETED_RECHECK of owner-approved corrected
  blocker IDs. The recheck inspects only those findings and the immediately
  affected boundary. If it still BLOCKS, stop and return to the owner; there is
  no third automatic cycle. Nonblocking findings never trigger an automatic
  rerun. Any review beyond this budget requires explicit owner authorization.
- A material architecture change is narrowly limited to a change in canonical
  state ownership, persistence, public/versioned contract semantics,
  Core/Go/UI ownership, execution or resolver/source-selection authority,
  secret/security boundary, transaction/rollback model, daemon/lifecycle
  subsystem, or owner-approved architectural scope. Tests, names, error text,
  missing bounds/cleanup, negative tests, finding corrections that preserve the
  approved architecture, documentation synchronization and behavior-preserving
  local refactors do not automatically invalidate the whole review. If
  uncertain, report that uncertainty to the owner instead of starting another
  full review.
- Mandatory overengineering review remains. It is blocking only with evidence
  of a concrete unnecessary mechanism, a viable simpler existing/standard
  alternative satisfying the current requirement, and material maintenance,
  contract or safety cost. A merely aesthetic preference is nonblocking.
  Architecture review never replaces owner authorization or applicable
  Core-contract, safety and QA gates. Supply a facts-only envelope with mode,
  FULL/TARGETED_RECHECK context, exact revision identity, scope/non-goals,
  owner decisions, contracts and available evidence; never supply an expected
  verdict or self-review conclusion. If the custom role cannot be loaded, give
  the same full instructions to an independent read-only subagent and disclose
  the fallback. Self-review never counts. If no independent reviewer is
  available, report the review as unavailable/pending.
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
- `vendor/**` is third-party/generated dependency content. Do not recursively
  enumerate, grep/search, review, summarize, inspect or edit `vendor/**` in
  ordinary repository passes. Repository-wide searches MUST explicitly exclude
  it, for example: `rg <pattern> -g '!vendor/**'`. Do not run recursive
  `Get-ChildItem` or `find` through `vendor/**` without a narrow reason.
  Build and test tools may use `vendor/**` automatically. A single known file
  under `vendor/**` MAY be read only when the user explicitly requests
  dependency-source research or a concrete build/runtime failure requires that
  narrow inspection; even then, never perform a full recursive vendor scan.
  Exclude `vendor/**` from architecture, security, TODO, secret and
  code-quality scans.
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

`CURRENT_STATE.md` is the dynamic milestone source of truth; this instruction
file must not copy its current DONE/NEXT ledger. PostgreSQL behavior must not
be inferred from the completed PKI-01 foundation; its role must consume
explicit PKI materialization plans at runtime.

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
- A fresh install target must not build the bundle that bootstraps its own Python/Core. DEV acquisition/build runs on a trusted acquisition environment with an existing Python/Core runtime; the selected install Execution Node only receives and activates the verified result.
- Missing `python`, `py`, `pytest` or `ansible-playbook` on Windows is not by itself a reason to mark tests `NOT TESTED` when the RED OS QA environment is available.
- Execute Python/Ansible tests on the RED OS VM through the existing test connection.
- Use local Windows execution only for checks supported there, such as Git, diff and static-file checks.
- Do not install Python/Ansible on Windows merely to run Core QA unless explicitly requested.
- Test commands must use the current working-tree version, not a stale remote copy.
- Transfer only required repository content to a temporary remote test workspace.
- Clean temporary remote test workspaces after QA unless preservation is explicitly required for debugging.
- Use `scripts/qa-sync.ps1` for Windows to RED OS source transfer. It uses
  `scp -r` to copy only `ansible-core`, `services`, `examples`, `contracts` and
  the repository application `config`
  into a unique `/var/tmp/platform-installer-qa-*` workspace, verifies the
  source tree, and must be cleaned with the same helper after QA. Do not use
  tar streaming, `tar | ssh tar`, or ad-hoc archive pipelines. Transfer
  failures are QA infrastructure failures, not product failures.
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

The local cache retains only the current immutable offline bundle under
`bundle/<digest>/`; publishing a replacement prunes the prior local digest.
Its service payloads live inside the verified
bundle at `runtime/artifacts/<service>/`. A DEV import source is runtime-only
input under `.runtime/artifacts/<service>/`, never a second subtree of
`bundle/`.

They are local test inputs and must not be committed.

## Desktop build process cleanup

When a required Wails rebuild is blocked because the repository's own
`build/bin/platform-installer-ui.exe` is still running, first identify the
exact process image path. If it is that exact build output, Codex MAY stop only
that process to release the binary lock and continue the requested rebuild.
Never use this rule to stop another application, a differently located binary,
or an uncertain process.

Do not search Downloads/Desktop or download artifacts automatically during QA
or production execution when the expected artifact is missing. Report the
missing expected path instead. A separately authorized DEV acquisition may
download and verify an official artifact into `.runtime/artifacts/`, then
publish it into a new immutable bundle; production roles and production
execution must use only approved local artifacts, repositories or payloads and
must never download from the Internet.
