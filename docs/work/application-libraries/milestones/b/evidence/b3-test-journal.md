# B3 shared lifecycle evidence

Owner authorized B3 on2026-10-14. Base9935b8e4 (B2 plus automatic portable-source
refresh), branch codex/application-libraries-b3. No commit/push authorized.

## Scope and design check

Read approved B technical plan section11/12/13, canonical execution contract,
internal rules, review/QA procedure and installer-go-backend skill. UI design
shared ownership/findings and Installation mockup examined. Mockup still has
one mixed-flow fresh-plan button; explicit mode/verification summary is the
already recorded B-plan discrepancy. B3 is backend contract/lifecycle only;
B4 real transport/bridge acceptance and C visual changes are not claimed.

## Implementation

Existing ExecutionService builder/plan store gains explicit mode routing through
B1 ModePlanBuilder. Retained mode/source map/order repeat before Start; no legacy
fallback. Existing approval/trust/typed lease/Start/Cancel/reconnect reused.
Fresh executable revision/identity/fingerprint checks occur before dispatch.
Infrastructure observation is defensively cloned; local cache remains UNKNOWN
on read and is never consulted for approval/Start. Actual Core phases/actions
and source infra run IDs remain separate from current library run state.

New tests cover all three supported modes, exact repeated request/cloning,
unsupported runtime, stale/blocked/mismatched fresh responses before lease,
unknown Start attempt reuse, ordinary Cancel, target trust before typed lease,
mode presentation and ordinary approval, account-independent UNKNOWN cache,
cache-write failure warning and common pre-dispatch PENDING rollback. Existing
legacy lifecycle/reconnect/cancel tests remain required. No Core/service mutation.

Focused Windows B3 tests PASS. Final Windows full tests/vet/build and browser-tag desktop suite PASS.
Final native/race/offline and FULL DIFF evidence follows below. No real Wails/React acceptance or overall B-stage completion
claimed. Prior unrelated Linux installer/contracts regression failures remain
in B2 journal; not hidden by new skips or changed assertions.


## Final QA and independent review

Windows: go test ./..., go vet ./..., go build ./... and
`go test -tags browser ./internal/desktop` PASS against final source. Focused
seven B3 test functions PASS (mode/failure subcases included).

RED OS current-tree Go adapter/executionnode complete suites PASS; desktop
selection B3|Installation|Reconnect|Recovered|InfrastructureVerification|
LocalRunRecord|RestoreLocalRun PASS. The same lifecycle selection with -race
on executionnode/desktop PASS, no reported races. B3 executionnode/desktop in
`sudo -n unshare -n` network namespace with GOTOOLCHAIN=local/GOPROXY=off/
GOSUMDB=off PASS. No downloads or target service mutations.

Initial full Linux desktop suite FAILED on unchanged
TestExpiredPasswordCannotDestroyActiveRunTransport at line34:
EXECUTION_NODE_UI_WINDOWS_REQUIRED from existing non-Windows binding guard.
Test and guard unchanged from base; this is outside B3 mode code. No skip/guard
weakening introduced. Safe full failure log preserved; no full Linux desktop
regression PASS claimed. Previous broader B2 baseline failures remain separate.

[Independent FULL review](../reviews/b3-diff-review.md): APPROVE, blocking0,
nonblocking0, mandatory overengineering findings0. Frozen nine-file identity
9bfa3a118b633b5e4bfc424f36c2c217796d8ee642eddc1ed17c603d10138432 unchanged.
No automatic recheck needed. B3 COMPLETE for approved backend lifecycle/
presentation scope. B4 production bindings/React/Wails real bridge acceptance
and C visual screen work remain separate and were not started. This does not
complete the whole B milestone. No commit/push performed.

Five safe native logs copied locally to .runtime/qa/b3/evidence, hashes matched
remote originals: adapter c1bf76620c43dce0c8a8d5d7343231c2524b765fdb984946f2f32e1b29e4b248;
focused893e48857ffd1097ce68c4a59aad1499c2a8ba25cbc250fd33b80f1956fecafe;
full failureb60b62d38e5ea6891ccf25c05af08cfa718fe4b74c17075b51e5c4556b684e86;
offline0e74c4348d27527a590e6665dca43f596274742463a19c7f5ccdae7ed23218c6;
race57a97543bc3cab87732a63813d4471e2ddce4a206214793d74e543f71b8f3c8e.
Temporary source workspace2cbe3952103c43acac8072801598d2f5 removed with qa-sync
following evidence copy. No owned Go test processes remained at completion.


## Publication authorization

Owner requested B3 commit and master synchronization. Reviewed identity verified
unchanged; only intended B3 files are included. Fetch confirmed master, B3 base
and origin/master have no divergence. Normal fast-forward integration/push only;
commit identity is recorded in Git history. No additional milestone authorized.
