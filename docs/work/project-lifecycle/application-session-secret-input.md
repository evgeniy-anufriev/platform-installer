# Application and library connection session input

Owner request, 2026-11-03: application secrets must be editable before Project
Verify using the service-secret lifecycle; provided library connections must
also show whether their session secret has been entered. Owner prohibited
independent review and explicitly requested real Wails verification.

## Change

The previous UI required a current verified snapshot for both enabled fields
and resolved source references. Saving required current Core descriptor proof.
The editor now inventories saved package/application source declarations and
stores input in the existing project-bound pending Broker, just like local
service input. Local discovery/save/presence requires neither Verify nor SSH.
The shared Broker owns bounds, expiry, cleanup and target-attachment separation.

The application-specific adapter lives in the existing
`internal/desktop/application_secret_descriptors.go`; there is no standalone
`pending_application_secrets.go` script or second lifecycle/store. Local keys
include library, slot and opaque authored reference. Before attachment, existing
Core runtime-attested snapshot fields and descriptors supply the actual resolved
source and authorized requirement/library scope. Go never renders templates.
Changes to the saved source do not silently reuse a prior field's value.

Library connection headings now show the same presence badge as application
credential accounts. Values stay in the session, outside structural commands,
project documents, diagnostics and public API results. The editor blocks only
unsaved source changes, active operations and missing field declarations.

UI/design check: shared secret-input ownership and the instance Secrets/library
Connections views in `docs/design/ui-design-01.md` and the mockup were checked.
The owner supersedes the former verified-snapshot prerequisite; the design and
backend contract record the new local input rule. Apply/plan approval gates are
unchanged. No new milestone, installation or Start was undertaken.

## Real React/Wails evidence

Live Wails Go backend at loopback port 34143 with current source and Vite 5179.
Bounded isolated component test mounted actual `ApplicationsPage` with managed
state returned by actual `App.OpenProject` and production backend functions.
No backend response, Core projection, input handler or credential save was
mocked. Whole-App navigation admission was outside this component test.

QA project:
`.runtime/qa/application-pending-wails-20261103/project`.
Saved revision:
`sha256:e1abd54ad88190edf9e0bdfe005682ff53f9b3c033b71d612d523ca33cd620c2`.
Initial verification `UNVERIFIED`, SSH session `MISSING`.

- Instance: enter synthetic value, replace it, leave/reenter Secrets — PASS.
- Provided library connection: initial «Секрет не задан», enter value, then
  «Секрет задан», leave/reenter Connections with status retained — PASS.
- Actual `SetDeploymentRuntimeSecretValues` calls completed; local
  `GetPendingApplicationRuntimeSecretDescriptors` confirmed presence — PASS.
- Project file hashes unchanged; public result contains no submitted value.
- Generated screenshots inspected: account and connection presence badges are
  readable; password inputs are cleared after submission. Visual PASS for these
  two views, not whole-App navigation or installation.
- No real plan, approval, execution run, Start or target change. No remote Core
  execution was needed for this local input flow; subsequent projection/promotion
  is covered by Go tests, not claimed as new live Core acceptance.

Safe local evidence: `evidence.json`, `check.cjs`,
`application-secret-before-verify.png`, `library-connection-secret-missing.png`
and `library-connection-secret-status.png` under the same QA directory. Synthetic
QA source/project artifacts retained for reproducibility. Agent-started Wails
and Vite processes were stopped after testing.

## Other validation

- Full `go test ./...` and `go vet ./...`: PASS. Added local input refusal,
  template-to-Core projection, changed-source/stale-proof and provider mapping
  tests passed in the final focused selection. Broker presence/expiry coverage
  confirms reads do not renew input lifetime or cross project boundaries.
- Frontend affected tests: PASS; full run 371 PASS / 2 FAIL in 28 files. Both
  failures are in unchanged `InstallationPage.b4.test.tsx`: old text assertions
  for infrastructure Verify and changed scope no longer match unchanged
  `InstallationPage.tsx`. They are not marked passed or modified by this work.
- Frontend typecheck, lint, production build: PASS; existing large-chunk warning.
- Windows Wails production build: PASS with updated frontend assets and bindings.
- No independent review invoked, per owner instruction.
