# Previous run reconnection evidence

Date: 2026-10-13. Source base: `f8c5f468874f8d3a6f902f15acaaae9e71bf0b8c`.
Owner authorized minimal implementation, then clarified existing controls/Cancel
must remain available, and requested application/bundle rebuild for personal QA.

## Checks

- `go test ./...`: PASS.
- `go vet ./...`: PASS.
- Focused recovery Go tests: PASS, including identity/token rejection,
  terminal race, renewal and unconfirmed Cancel retry.
- App handler suite: 73 PASS, including Attach/subscription/ordinary Cancel
  without another Start.
- Frontend typecheck, lint and production build: PASS.
- Debug Wails QA binary built successfully. No installation was started for QA.
- Windows race detector unavailable: no configured C compiler was found.

## Review

Initial FULL PLAN: APPROVE_WITH_CHANGES, zero blockers. Its observe-only Cancel
restriction was superseded by the owner's explicit correction.
Revised FULL PLAN: APPROVE_WITH_CHANGES, zero blockers. Existing
ExecutionService.Reconnect is reused rather than adding a second cancel path.
FULL DIFF: BLOCK on RR-D01. Unconfirmed cancellation could be bypassed by
previous-run inspection or bundle rebind terminal publication. The owner
explicitly authorized the correction and one TARGETED_RECHECK. The correction
guards Choose/Confirm, inspection, reattach and detached cancellation retry.
Regression covers Cancel error → Choose/Confirm → credential renewal → inspect
→ reattach → ordinary Cancel retry; the local record remains RUNNING until stop
is confirmed. Focused recovery/rebind suites PASS after the correction.
TARGETED_RECHECK: APPROVE; RR-D01 RESOLVED; zero remaining blockers. See
[review record](../reviews/run-reconnect-review.md). Full Go tests/vet rerun PASS.
App and InstallationPage suites: 97 PASS; frontend typecheck/lint/build PASS.

## Rebuilt deliverables

Production Wails binary: `build/bin/platform-installer-ui.exe`, rebuilt 2026-10-13.
The same production bridge is retained; AttachOrphanRun is generated in main.App
bindings and explicitly registered in the browser transport.

Bundle: `run-reconnect-20261013-01`, built from the current working tree on trusted
node2 using retained approved runtime inputs, without acquisition/downloads.
Platforms: RED OS 7.3 and 8.0.3, x86_64. Standard validator passed for all 1,109
manifest components. Digest:
`sha256:59b0d1aa0b6c9570fa2242985fc73ba54bc41bdd875de679dce1084a8fce19d3`.
The standard publisher returned the same digest in active `cache/`. Source copy:
`.runtime/qa/run-reconnect-20261013-01/bundle/`. Previous active bundle is preserved
and verified in `.runtime/qa/run-reconnect-previous-bundle-20261013/bundle/`.
The temporary node2 build workspace was cleaned with qa-sync.

## Acceptance

Real React/Wails close/reopen/attach/control acceptance is pending owner QA.
No real-run IDs or target PASS are claimed for this change.
