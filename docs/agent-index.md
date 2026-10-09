# Agent task index

Navigation only. Current status/authorization lives in [CURRENT_STATE](../CURRENT_STATE.md).
Start with [AGENTS](../AGENTS.md) and current state; load only the applicable row
and mandatory procedures. Check scoped instructions explicitly when starting at
the repository root. Paths and symbols below are entrypoints, not a whole-repo map.

## Recurring tasks

User application libraries: start with [the documentation folder](application-libraries/README.md)
and choose its architecture/configuration/execution/secrets/UI document for the question.
These are discussion drafts, not implemented contracts or milestone authorization.

| Task | Contract / required reading | Code entrypoints | Verification |
| --- | --- | --- | --- |
| UI layout, labels, dialogs | [UI design](ui-design-01.md), [mockup](ui-design-01-mockups.html): shared rules and affected screen; relevant milestone plan | [App.tsx](../frontend/src/App.tsx), affected page (`ServicesPage`, `ServersPage`, `TopologyPage`, `CertificatesPage`, `InstallationPage`, `UtilityPages`), relevant CSS | Affected frontend tests/typecheck/lint/build as applicable; real flow acceptance follows [QA](agent-procedures/qa.md). Visual PASS requires visual inspection. |
| React bindings / Browser transport | [Backend/UI boundaries](backend-and-ui.md), relevant ADR and [browser plan](browser-mode-local-plan.md) | [backend.ts](../frontend/src/backend.ts): `ProjectBackend`; [browser_backend.ts](../frontend/src/browser_backend.ts); corresponding method in [app.go](../app.go) or [browser_rpc.go](../browser_rpc.go) | Affected transport/frontend/Go checks; real Wails acceptance for affected application flows. |
| Save, Review, reopen, transactions | [Project contract](project-contract.md), ADR-027 in [ADRs](architecture-decisions.md), relevant lifecycle plan; [internal rules](../internal/AGENTS.md) | [app.go](../app.go): `ReviewStructuralEditSession`, `CommitStructuralEditPlan`; [lifecycle.go](../internal/projectlifecycle/lifecycle.go); [transaction.go](../internal/installer/transaction.go) | Focused ownership/revision/rollback/path tests, Go gates and real Save/reopen flow; Save remains node-free. |
| Project Verify / Core adapter | [Core](ansible-core.md), [UI-BE-02](ui-be-02.md), ADR-027; [internal](../internal/AGENTS.md) and [Core rules](../ansible-core/AGENTS.md) | [app.go](../app.go): `VerifyProject`; `internal/coreadapter/`; [execution_protocol.py](../ansible-core/tools/execution_protocol.py) | Revision/runtime binding, target-free and offline checks; Core tests on RED OS via [QA](agent-procedures/qa.md). |
| Plan, approval, Start, cancellation, observation | [UI-BE-04](ui-be-04.md), [UI-02 architecture](ui-02-architecture.md), relevant plan and [review](agent-procedures/review.md) for risk classification | [installation_plan.go](../installation_plan.go): `CreateInstallationPlan`, `ApproveInstallationPlan`; [installation_execution.go](../installation_execution.go): `StartApprovedInstallation`, `CancelInstallationRun`; [execution_service.go](../internal/executionnode/execution_service.go); Core execution protocol | Affected Go/Core lifecycle checks and real fresh-plan -> approval -> Start -> terminal evidence. See [QA](agent-procedures/qa.md); mocks/direct harnesses are supplementary. |
| Service role, settings, endpoints, PKI | [Core](ansible-core.md), [project contract](project-contract.md), service architecture/acceptance document; relevant ADR; [Core rules](../ansible-core/AGENTS.md) | `services/<service>/service.yml`, `configuration.schema.json`, `playbooks/`, collection role and `tests/`; Core `plugins/module_utils/` symbol for the projection | Service-focused contracts/syntax/standalone/real UI gates via [QA](agent-procedures/qa.md). Follow runtime projection across apply/verify/diagnostics. |
| Generated catalog / configuration schema | Relevant service manifest and published schema contract | [build_fixture_catalog.py](../ansible-core/tools/build_fixture_catalog.py), [build_service_configuration_schema.py](../ansible-core/tools/build_service_configuration_schema.py) | Reproducibility checks on RED OS from current sources; inspect generators first. |
| Bundle, rebind, Execution Node preparation | [Runtime bundle procedure](agent-procedures/runtime-bundle.md), [QA](agent-procedures/qa.md), [rebind plan](runtime-bundle-project-rebind-plan.md) | [runtime_bundle_rebind.go](../runtime_bundle_rebind.go), root `execution_node_*.go`, `internal/executionnode/`, bundle CLI | Strict trust, exact digest/publication, current READY binding; no manual cache copy or install-node acquisition build. |
| SI11 full visible-UI cycle | [SI11 procedure](agent-procedures/si11.md), [UI cases](service-install-11-ui-test-cases.md), [journal](service-install-11-test-journal.md), applicable active plan | Real Wails/React controls and native dialogs; bounded preparation seam is separate | UI cases' stricter user-flow acceptance; record revision/run/terminal evidence; new naming acceptance remains separate. |

## Selecting bounded excerpts

For UI design, use the heading matching the screen plus Shared typography/dialog
rhythm, Shared visual language, Findings/plans/execution and ownership sections
when they affect the task. In HTML locate the matching `section` ID, shared style
and event handling; do not dump all screens or assume one long line is small.

For code, find the symbol in the known file/module with `rg -n`, then read its
body and immediate callers/contracts. Expand if an ownership or cross-screen
dependency is unresolved. A row is a route, not permission to skip gates.

## Historical evidence

- [SI11 checkpoints](history/si11-state-20261008.md): old runs, resets and editor evidence.
- [Vault/SI08 checkpoints](history/vault-state-20261008.md): Vault implementation/review/HA evidence.
- [Workflow checkpoints](history/workflow-state-20261008.md): ordering, active-run credentials, Browser and rebind.
- [Earlier milestone checkpoints](history/milestones-state-20261008.md): accepted baseline and dated ledger.

Read a specific historical section only to resolve an evidence question.
Historical NEXT/NOT STARTED/host/digest statements are not live facts.
Keep this index small; add routes only for demonstrated recurring tasks.
Update a route when its entrypoint moves. Do not duplicate status ledgers here.
