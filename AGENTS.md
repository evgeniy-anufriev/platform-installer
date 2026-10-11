# Platform Installer V2 — Agent Instructions

Build outside in: Standalone Ansible Core -> portable project contract -> Go adapter/orchestrator -> UI editor.
V1 at `../platform-installer` is a reference only; do not copy its packages/models wholesale or change it without an explicit request.
`CURRENT_STATE.md` is the sole current milestone/status source. A next gated milestone requires an explicit owner request.

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

## Change discipline and mandatory procedures

- Keep the local `master` branch synchronized with GitHub repository [`evgeniy-anufriev/platform-installer`](https://github.com/evgeniy-anufriev/platform-installer), using `origin/master` as its upstream. Before working on `master`, fetch and inspect whether either side has commits the other lacks; integrate remote changes without rewriting history. After authorized changes are committed and validated on `master`, push them with a normal fast-forward push. Never force-push; preserve uncommitted work and resolve divergent history explicitly.
- Read the relevant canonical contract before editing; prefer one contract over parallel DTOs.
- Before a UI milestone, including backend sub-milestones, check the relevant screens/flows in [mockups](docs/ui-design-01-mockups.html), [UI design](docs/ui-design-01.md), and its milestone plan. Read shared interaction/ownership rules plus affected screens; expand for cross-screen impact. Record discrepancies before coding, resolve material discrepancies with the owner, and repeat the relevant check at acceptance. Demo values/statuses are not Core rules.
- Prefer built-in Ansible tasks/filters and a small explicit sequence. Add abstractions only where built-ins cannot safely meet the requirement and reuse/complexity justifies the contract.
- Roles may hardcode product invariants, never effective configuration. Endpoints, listeners, protocols, paths, identities and security policy come from the resolved runtime projection shared by apply, verify and diagnostics.
- PostgreSQL must consume explicit runtime PKI materialization plans; do not infer its behavior from PKI-01 completion.
- Update architecture decisions and roadmap when a boundary changes.
- Before architecture-sensitive planning or risk classification/review, read [review procedure](docs/agent-procedures/review.md). HIGH-RISK DIFF requires independent FULL review; LOW-RISK documentation/layout normally does not. Preserve the one FULL plus at most one owner-approved TARGETED_RECHECK budget, BLOCK stop, and owner approval. Self-review never counts.
- Before Core/service QA or real WebView testing, read [QA procedure](docs/agent-procedures/qa.md), including its environment, PEM/session, trust, transfer and cleanup prerequisites.
- Before SI11 UI preparation or acceptance, also read [SI11 procedure](docs/agent-procedures/si11.md), its linked test cases and current journal. Preparation does not authorize Approve/Start or prove installation acceptance.
- Before artifact acquisition, bundle build/validation/publication/rebind/activation, or bundle-dependent UI QA, read [runtime bundle procedure](docs/agent-procedures/runtime-bundle.md).
- Before stopping a process for a blocked Wails rebuild, read the exact-image restriction in the QA procedure; never stop an uncertain or unrelated process.
- Use focused subagents for independent review, implementation or QA when requested. Main agent runs affected tests; milestone regression/offline/OS QA follows the applicable QA delegation rules without implying permission for unrelated agents.

## Secrets, execution and acceptance gates

- Runtime credentials/private keys belong only under `.runtime/secrets/` or the established runtime identity mechanism; never commit them, copy values to docs/skills/fixtures/source, or print them. Load only at runtime and redact command/error output. Missing credentials are a clear prerequisite failure.
- Acceptance for every service and affected application flow MUST exercise actual React handlers/bindings against real Wails Go methods and, where relevant, supported Execution Node Core/Ansible. Use the existing bounded automation seam; never add a production bypass, arbitrary command bridge or test-only save/start path.
- Direct Go harnesses and mocked frontend tests are supplementary. Record flow, saved revision, run IDs, terminal results and safe event/output evidence. An unavailable real bridge is blocking, never replaced by mocks. Visual inspection is separate; report PASS only if performed.
- SI11's full user-flow acceptance follows its stricter visible-UI test cases; the separately bounded preparation seam is not acceptance evidence.
- Run Python/Ansible Core tests on the configured RED OS VM from the current working tree. Do not install Python/Ansible on Windows for QA without an explicit request, use stale remote sources, or modify targets during read-only tests. ALT QA is required only for ALT-specific behavior or an explicit request.
- For established EXEC-01 QA use `platform-automation`, its persistent SSH identity, `IdentitiesOnly=yes` and `sudo -n`; no admin/password sudo fallback. See QA procedure for the exact connection and bootstrap-only policy recovery.
- Fresh install targets must not build their own bootstrap runtime. Use the trusted existing-runtime acquisition environment; SI11 bundle builds use node2, independently of node1 installation selection.
- Publish updated verified bundles with the standard publisher into active `cache/` before dependent UI flows; locked/published digests must match. Preserve needed prior bundles before replacement; never manually copy into cache or delete the legacy fallback as a rename.
- Do not search Downloads/Desktop or automatically download missing artifacts during QA/production. Report the expected missing path. Only separately authorized DEV acquisition may download/verify official artifacts; production never downloads from the Internet or mutates the distributed bundle.

## Context efficiency and navigation

- Start with these instructions and compact `CURRENT_STATE.md`. Reuse already loaded identical current instructions; reread if the file changed, the checkout changed, or completeness is uncertain. Confirm status freshness before gated work.
- Use [task index](docs/agent-index.md) for recurring tasks; read only relevant contracts/procedures and scoped `internal/AGENTS.md` or `ansible-core/AGENTS.md` when working in those layers. Root-launched sessions must not assume nested instructions were automatically loaded.
- Search known modules/symbols first, then expand as needed. Read bounded function/section excerpts, not whole large source files. Limit output at the command source; avoid truncation that forces repeated reads.
- `vendor/**` is third-party/generated: never recursively enumerate/search/review/edit it in ordinary passes. Repository-wide searches MUST explicitly exclude it (`rg <pattern> -g '!vendor/**'`), including architecture/security/TODO/secret scans. Only an explicit dependency-source request or a concrete failure permits one known file; build/test tools may consume vendor normally.
- Skip `ansible-core/**/_vendor/**`, generated/runtime output and V1 by default. Vendored tests/benchmarks require dependency validation/maintenance scope; V1 reading requires relevant reference behavior.
- Use representative fixtures. Inspect generated source manifests/generators first; `examples/catalog/service-catalog.yml` is intentionally tracked and generated by `ansible-core/tools/build_fixture_catalog.py` from service manifests.
- Never dump the repository or complete successful logs. Report concise evidence and relevant failures; broaden/repeat checks only for new changes, failures, unresolved risk or required gates.
- Historical snapshots under `docs/history/` are loaded only for a specific evidence question. They are not current statuses, authorizations or another desired-state store.
- Update existing state entries rather than prepending run narratives. Put detailed evidence in the relevant journal and link it; preserve exact IDs/revisions there. Indexes/procedures must not acquire DONE/NEXT ledgers.

## Canonical documents

- [Architecture](docs/architecture.md): layer/security boundaries.
- [Ansible Core](docs/ansible-core.md): standalone runtime and role contracts.
- [Project contract](docs/project-contract.md): portable desired state and ownership.
- [Architecture decisions](docs/architecture-decisions.md): relevant ADRs.
- [Roadmap](docs/roadmap.md): milestone requirements/sequence; historical status prose does not override current state.
- [Current state](CURRENT_STATE.md): active status, blockers, owner decisions and next authorized steps.
