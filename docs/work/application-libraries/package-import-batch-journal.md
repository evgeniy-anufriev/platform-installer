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
