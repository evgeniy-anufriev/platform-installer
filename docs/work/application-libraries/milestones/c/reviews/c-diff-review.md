# C FULL DIFF review — BLOCK

2026-10-15. Independent architecture-reviewer `c_plan_review`.
Base `a7260c6f7cbe3f41dcdf8dd996234ec529e33caa`.
27-file identity `89a9932b22e2fb89d1dfb3204b53820d0c60569027c47e32b45fc6e9f3821c7d`.
Plan SHA256 `cb5a6c4fdda5c951bf04516d1ad52a6941b91f31d30a622ce9317913b2d687b7`.
Reviewer independently checked all file hashes twice; zero mismatches.

## Findings and disposition

- **C-D01 BLOCKING OPEN:** ApplicationSecretInputs filters by libraryId, while
  SetDeploymentRuntimeSecretValues with empty serviceDeployment derives requirements
  from all evidence.applicationInputs. Broker requires exact identifiers/counts
  before merge. Two libraries with distinct refs therefore cause
  RUNTIME_SECRET_INPUT_INVALID. The new mocked save test does not exercise this
  backend boundary. Locations: ApplicationSecretInputs.tsx:40–48,83–89;
  ApplicationsPage.tsx:941–949; internal/desktop/app.go:773–798;
  internal/runtimesecret/broker.go:346–348,1132–1150.
  Minimal options: reuse the full application input dialog with explicit shared
  scope, or narrowly extend the existing input contract with library identity and
  derive that library's exact requirements from trusted evidence on the backend.
  Never accept arbitrary client requirements or weaken Broker exact-set guards.
  Required tests: real desktop/Broker two-library saves preserving previous inputs,
  shared ref, stale revision/fingerprint, unknown library/foreign ref, then actual
  React/Wails acceptance. Owner disposition pending; no correction applied.
- **C-D02 NON_BLOCKING OPEN:** successful library Create hides the form without
  clearing its create dirty marker, leaving Review disabled/LOCAL_FORM_UNSAVED.
  Clear only that marker after accepted Create; failed Create must preserve input.
  Locations: ApplicationsPage.tsx:393,403,421,438–442,1035; App.tsx:1615–1621.
- **C-D03 NON_BLOCKING OPEN:** native discard/cancel navigation differs from the
  planned three choices “В черновик / Отбросить / Остаться”. No silent loss found.
  Either owner accepts the bounded two-choice flow with explicit per-field staging,
  or use an existing small dialog; no generic batch-save framework is justified.
  Locations: plan §4; ApplicationsPage.tsx:142–154; App.tsx:360–374.

## Boundary and complexity assessment

No new desired-state store, resolver, Start path, infrastructure Apply, daemon or
parallelism found. Amendment reuses CAS/session guards; import reuses captured
preview bytes, PlanStore and normal structural commit. Authored package reads stay
bounded and revision-checked. No blocking overengineering findings. Typed credential
source validation remains intact. Reviewer did not run tests or inspect secret values.

Reported parent checks: final Windows Go full PASS, frontend182 PASS/focused10 PASS,
unchanged Core native17 PASS; earlier native Go12 PASS is not final-tree evidence.
Actual React/Wails/target/visual acceptance and provider→Vault→Agent proof remain open.

**One unresolved blocker. Review CURRENT for frozen identity only.** Automatic
implementation stopped under review.md. Further correction and one targeted recheck
require owner disposition; this report is not an approval of a later snapshot.
