# PROJECT-VERIFY-PASSWORD-FIX-01

2026-10-08. Owner reports global Verify transitions Checking -> Unverified and Projects explains READY required while node is Checked: Prepared. Existing Core result/status contract remains authoritative; no successful result may be fabricated from node readiness.

## Diagnosed code defects

Project archive staging calls Identity.IdentityFile directly. desktopIdentity rejects empty PEM path in password mode, despite supported shared identityFile wrapper. Other missed direct resolver calls exist in runtime projection and legacy service transfer, outside this Verify correction. On node1, /var/tmp/platform-installer/execution-plan belongs to platform-automation (0700); admin cannot write its parent. Snapshot/plan staging therefore cannot work for the new password account. Transport failures mapped to EXECUTION_NODE_UNAVAILABLE become misleading READY_REQUIRED; backend UNVERIFIED with error is rendered as plain Unverified in global header.

## Bounded correction proposal

Use existing password/PEM-aware identityFile in project archive staging only; retain strict host pin and same auth providers. Legacy ExecuteService and runtime projection remain outside this verified correction. For ordinary snapshot/plan archive uploads, claim fresh /var/tmp/platform-installer-project-<runID> as current SSH user, ordinary exclusive mkdir0700 under verified root-owned sticky real /var/tmp. Upload, digest-check and existing sudo extraction stay the same. Cleanup only follows acquired ownership, retains context scope and targets that exact generated path. No privileged ownership changes or reuse/repair of previous user's folders. Candidate snapshot uploads keep their existing private Core-mediated staging contract and guarded namespace; do not change Python/Core to solve this ordinary Verify defect.

Report archive claim/upload/extraction failures as a stable Go PROJECT_TRANSFER_FAILED error instead of readiness failure. Other actual node readiness prerequisites retain existing codes. UI projects backend UNVERIFIED+error as Verification unavailable; global status opens Projects for the existing localized detailed error. Canonical persisted desired state and backend verification evidence are unchanged. Preserve valid VERIFIED/INVALID/STALE and default never-checked labels; catch binding promise rejection with a safe visible failure without printing raw errors.

## Gates

Architecture-sensitive filesystem/transport correction: independent scoped FULL PLAN, then focused FULL DIFF for this new defect. Existing review budgets for completed password support are not reopened. Unit tests password staging without PEM, fresh top-level claim, failure ownership/cleanup, PEM/candidate regressions, header Verify -> unavailable -> reason and genuine success. Affected Go test/vet and frontend tests/build/lint. Real React/Wails Verify required against the existing current bundle/Exec node and entered credentials, read-only target-free Core only; no full installation/Start/rebind/publication/account/sudoers change. Missing credentials/bridge remains an explicit acceptance gap. Detailed evidence in SI11 journal; current state stays in CURRENT_STATE.

## Implementation and owner evidence

Independent FULL PLAN APPROVE_WITH_CHANGES, no blockers. PV-P01: cleanup uses the acquired exact path and purpose, only after successful claim, with bounded context preserving operation scope. PV-P02: resolver fix limited to project archive staging; no claimed legacy ExecuteService password support. PV-P03: typed PROJECT_TRANSFER_FAILED remains separate from READY prerequisites; canonical UNVERIFIED/error is projected as UNAVAILABLE only for rendering.

2026-10-08 owner real UI confirmation after correction: «Проверка выполнилась. Я проверил». This confirms the reported Verify flow now completes on the prepared node. Exact terminal VERIFIED/INVALID response, revision and run ID were not supplied; no full installation/Start acceptance is inferred. Agent did not operate this particular user flow. Source adds focused password/no-PEM, claimed namespace cleanup and safe unavailable/header navigation tests. FULL DIFF pending.
## Independent FULL DIFF — APPROVE

2026-10-08, base 2ea2e8a9718744383bd88f55e6e2af1bda4d1e14; manifest SHA256 D06B44C9A3EEF2592A924FF0031DC61631D9963303210EDE225918CEC4D88739. Independent reviewer checked all six source hashes, code/guard/test changes and Core candidate boundary. PV-P01/PV-P02/PV-P03 RESOLVED; zero new findings, zero unresolved blockers, no overengineering findings. Owner confirmation accepted as evidence that the reported UI Verify flow completes, with exact result/revision/run limitations retained above. Reviewer did not operate the UI or run reported tests. No repeat review required for unchanged scope.