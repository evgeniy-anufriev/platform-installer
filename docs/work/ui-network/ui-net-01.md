# UI-NET-01 — Provider and virtual-address editor evidence

UI-NET-01 is complete. It adds the provider side of the existing canonical
endpoint model to **Topology → Entry points** without adding a local resolver,
PKI workflow, target operation or second persistence path.

## Delivered boundary

- Immutable `project-edit/v1alpha6` carries one complete
  `ReconcileEndpointProvider` tuple or an explicit `ClearEndpointProvider`.
- The existing EditSession, final-state reducer and guarded local writer own
  local Save/reopen. Reconcile requires an exact READY provider-capable catalog;
  Clear remains catalog-independent structural cleanup.
- The Wails Entry points screen uses only typed intents. It renders eligible
  providers, direct-owned legacy states, bounded VIP rows, draft state and the
  existing Core endpoint preview.
- Provider drafts mark preview stale with the neutral local statement that
  configuration changed. React and Go do not infer PKI/SAN effects. Current
  FQDN/VIP data is explicitly labelled as Core evidence; INVALID has findings
  only, without an authoritative preview.

## Acceptance evidence

- Windows: `wails build -nopackage -clean` built
  `build/bin/platform-installer-ui.exe`; the launched desktop shell exposed the
  Wails project/open UI and navigation. No project was opened or mutated.
- Frontend: lint, production build and 41 tests passed, including typed
  provider reconcile, catalog-unavailable Clear and neutral stale-preview UI.
- Go: `go test ./...` and `go vet ./...` passed.
- RED OS: in a fresh `scripts/qa-sync.ps1 -IncludeGo` workspace,
  `CGO_ENABLED=1 go test -race ./internal/installer ./internal/coreadapter`
  passed. Core regression passed: 244 tests, 4 skipped. Fixture catalog and
  service configuration schemas were reproducible; catalog digest was
  `sha256:e87acc790d389a67ea90da7b785562018cd3450181fa00f4dfa2b38fe9eaeccf`.
- RED OS target-free `project_snapshot_acceptance.yml` passed on `localhost`
  with `changed=0`, `failed=0`; its deliberate invalid-root case returned the
  expected `PROJECT_SNAPSHOT_INPUT_INVALID` finding. No inventory target was
  contacted.
- The temporary RED OS workspace was removed and its absence confirmed.
- The bounded full DIFF review and its owner-authorized targeted recheck for
  UI-NET-01B had zero remaining blocking findings. No new architecture boundary
  was introduced by the C/D presentation work.
- Changed-file secret audit found no secret assignment/value. `git diff --check`
  passed.

UI-01G Certificates is next. UI-NET-01 itself does not issue, reissue,
materialize or apply certificates.
