# Application package batch import

2026-11-02, owner-requested change. After the Wails launch rejection below,
the owner explicitly requested committing the completed change. This authorizes
publication without claiming real Wails acceptance.

Page-level application import captures all packages below a selected
`application-packages` directory in one existing structural plan/transaction.
Single application import is placed in the instance screen and bound to the
declared application ref. Library import remains a single version directory.
Core, deployment creation, execution and runtime bundles are unchanged.

Validation completed:

- Focused Go import tests pass, including empty/invalid/conflicting batch
  rejection, preview without writes and source changes after preview.
- Real repository packages: SZI, SDKU and CSPA library import/commit followed by
  complete corresponding application directory import/commit pass in isolated
  native Go test projects. This is supplementary evidence, not Wails acceptance.
- React component/page tests: 28 pass. TypeScript/Vite production build passes.
- A separate dev Wails executable was built in
  `.runtime/qa/package-batch-import/installer-import.exe`.

Real Wails acceptance is BLOCKED: automatic approval review rejected both
the configured QA-node launch and the reduced launch without SSH arguments.
The stated reason was only `blocked by policy`. No Wails process was started,
no UI import acceptance, deployment plan or installation was performed.
The temporary Vite server was stopped. Existing project/service data and
unrelated working-tree changes were preserved.

## Import diagnostics follow-up — 2026-11-02

The supported `wails dev` runner subsequently started successfully. The earlier
direct executable launch rejection remains historical, not a current blocker.
Owner's 36-file SZI layout was reproduced by omitting external Keycloak
providers/themes from a private copy of the repository packages. Real React
import handlers called real Wails Go review methods: missing `themes.tar.gz`
returned BLOCKED with the old generic diagnostic. Adding only that archive
returned READY with 37 documents. No installation or structural Save was run.

The diagnostics fix preserves validation/limits, publishes a Russian reason and
logical package/file path through the existing finding, and does not publish
file contents or raw YAML parser messages. Generic import form explanations were
removed at the owner's request.

Final-source Wails checks: missing archive returns APPLICATION_PACKAGE_INVALID,
field `application-packages/keycloak/1.0.0/assets/themes.tar.gz`, with the Russian
reason that a file declared in `files` is absent. Repaired source returns READY,
37 documents; structural plan `d38a4b63fff55d0b688f19d38f8108f4`, base revision
`sha256:ed631f43ba7e4f245a3e1f977c77bd01fb9ab3aaee6d1e8ec32460acc627c439`.
Both reviews were discarded through the UI; project bytes unchanged. UI screenshot
was visually inspected and shows the concrete Russian finding. No execution
plan/run IDs exist for these review-only tests. Safe results/screenshots are in
`.runtime/qa/import-reproduce/review-diagnostic-*.json` and
`.runtime/qa/import-reproduce/diagnostic-missing.png`.

Validation: `go test ./...`, final affected installer/desktop packages, focused
import/export tests and `go vet ./...` PASS. Three import React tests and the
TypeScript/Vite production build PASS. Native regressions cover missing/unlisted
files, forbidden paths, defaults version mismatch, unchanged blocked project
revision and content redaction.
