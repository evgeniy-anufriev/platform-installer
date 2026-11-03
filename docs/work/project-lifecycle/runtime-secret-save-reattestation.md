# Runtime secret reattestation after project Save

Owner request, 2026-11-03: project changes must not reset previously entered
secrets. Reported symptom: Installation Plan shows
`RUNTIME_SECRET_DESCRIPTORS_STALE` during application image preparation.

## Cause and correction

Successful structural Save already keeps project-bound pending secret values
and their original expiry while revoking attached values and descriptor proof.
Registry inputs can also be saved from authored library sources before any
Core descriptor discovery. Image preparation previously required cached proof
without requesting its replacement, so both paths could fail before planning.

The image preparation credential callback now obtains fresh descriptors through
the existing Execution Node Core operation when its current-revision evidence
is absent or stale. The existing broker reattests retained inputs. Exact project,
revision, node, runtime, registry purpose, hosts and library scope checks still
precede returning the selected registry values. Current evidence is reused.
Core failures and expired/missing inputs still block preparation.

No secret persistence, TTL renewal, broker contract or Core rules are added.
Save remains local; discovery happens only when requesting the plan. Plan
approval and Start gates remain unchanged. This corrects the accepted behavior
in `docs/backend-and-ui.md`, rather than introducing a new lifecycle.

UI/design check: `docs/design/ui-design-01.md` (2026-11-02 registry refinement),
Installation mockup and `docs/work/ui-backend/ui-be-04.md` retain session input
and fresh-plan ownership. The observed prerequisite failure conflicts with that
flow. No React rendering or interaction changes are part of this correction.

## Validation

- Focused Go tests PASS: image preparation, registry saved-source authorization,
  Save retention and application input reattestation.
- New regression cases cover first discovery, Save invalidation, stale revision,
  a changed Core reference mapped from the same source, missing new source,
  foreign library scope, discovery failure and expiry. Successful repeats reuse
  current proof and return only registry inputs.
- `go vet ./...`: PASS.
- Full `go test ./...`: PASS (including desktop, executionnode, installer and
  runtimesecret packages; Go's existing cache was used where applicable).
- Independent FULL DIFF review: APPROVE, zero findings/blockers. Reviewer
  inspected both implementation files against base
  `20c9a17486fddb71c4a80e108eb45c4345354386`; reviewed diff SHA-256:
  `6550e0b5a7210f958c902324cdafc0158e0ffe73c657cc0b01e972adc26c0a24`.
  No unnecessary abstractions, duplicate contracts or scope expansion found.
  Review does not replace the outstanding real UI acceptance gate.
- Real React/Wails acceptance: BLOCKED/unavailable. The standard
  `node scripts/qa-wails-bridge.cjs` preflight failed with
  `QA_WAILS_BRIDGE_PREFLIGHT_FAILED`; no `platform-installer-ui.exe` process was
  present. No actual UI flow, visual PASS, bundle publication, installation or
  Start is claimed or performed.

Implementation base: `20c9a17486fddb71c4a80e108eb45c4345354386`.
Unrelated working-tree changes are excluded from this correction.

## Start credential callback correction (2026-11-03)

Owner subsequently reported `TARGET_CREDENTIAL_REQUIRED` after successful plan
preparation and server checks, and requested its correction. Start rebuilds the
authoritative plan, including image preparation, but its context did not carry
the image preparation credential provider used by Create Plan. The transport
therefore stopped before the broker could supply any already-entered values.

Start now registers that same provider. Because the rebuild runs outside
`editMu`, the callback acquires the mutex and checks the captured operation's
generation, root, project, plan, binding, runtime and requested project/revision
before delegating to the existing scoped credential preparation. It introduces
no storage or wire change. The error now has an explicit SSH preparation message
instead of the generic project-open fallback. UI interaction remains unchanged.

Validation on base `02b1fd59023c186c17c243963d4a44eb557dc5fe`:

- Focused Start regression PASS: actual Go Start -> ExecutionService authoritative
  rebuild -> OpenSSH image preparation, using a synthetic command runner.
  Existing SSH credentials, both registry values and approved target key reach
  preparation. The runner deliberately stops before execution dispatch.
- Changed generation, foreign revision/library, missing credential session and
  missing target trust block preparation. Error-message regression PASS.
- Full `go test ./...` and `go vet ./...`: PASS.
- Windows Wails production build PASS using `-s -skipbindings -m -nosyncgomod`:
  backend rebuilt with existing frontend assets; no frontend rebuild claimed.
  Output: `build/bin/platform-installer-ui.exe`.
- Race checks unavailable with this toolchain's `CGO_ENABLED=0`.
- FULL DIFF review was started, then interrupted at the owner's explicit request
  not to invoke review. No review verdict or approval is claimed for this fix.
- Standard real Wails bridge preflight still failed; real React/Wails acceptance
  remains unavailable/blocking. No real Start, installation, target change or
  visual acceptance was performed.

## Planning and node-operation failures retain SSH (2026-11-03)

Owner reproduced: missing registry password -> planning error -> enter password
-> next planning attempt asks to check Execution Node -> recheck loses secrets.
Owner additionally required that operation errors never reset SSH.

Cause: any deployment-plan error unconditionally invalidated a dynamic node
binding. This removed its approved SSH pin, readiness and runtime secret inputs.
The missing registry password was incorrectly treated as loss of node trust.
The same invalidation appeared in inspection/preparation/Verify error branches.

Correction: failed planning revalidates the existing binding guards rather than
deleting the binding. Node inspection, preparation planning, preparation and
post-preparation inspection, and Project Verify inspection now return their
errors without erasing SSH identity/pin or session secrets. Failed inspection
marks readiness UNREACHABLE; failed preparation marks it NOT_PREPARED. A retry
can use the same connection. Actual identity/endpoint/pin changes remain guarded.

Validation from base `ef754291`:

- Dynamic-binding regression: missing password -> exact registry error -> save
  registry input -> successful plan. A second case repeats same-key approval and
  CheckExecutionNode before planning. Both preserve Vault typed inputs, PKCS#12
  password and an unrelated application password. Image preparation receives
  only the scoped registry value.
- Changed endpoint, tampered pin and cleared/expired session still block reuse
  through the existing guards.
- Five operational failure cases (Check, preparation plan, Prepare,
  post-Prepare Check, Verify inspection) preserve SSH credential generation,
  binding, approved pin file and existing session secrets. A subsequent Check
  succeeds without reentering SSH data or reapproving the key.
- Focused tests, full `go test ./...` and `go vet ./...`: PASS (existing Go cache
  used where applicable).
- Windows Wails backend rebuild PASS with existing frontend assets using
  `wails build -s -skipbindings -m -nosyncgomod -nocolour`.
- No review invoked, per owner instruction. Real React/Wails acceptance remains
  unperformed; no real installation or Start was initiated.

## Password SSH: protocol stderr can masquerade as node unavailability (2026-11-03)

Owner clarified a separate sequence: Check Execution Node -> Prepare -> check
other servers -> fill session secrets -> prepare plan returns
`EXECUTION_NODE_UNAVAILABLE`; another node check makes the next plan work.
SSH uses a password, elapsed time is a few minutes. The isolated installation's
logs and runtime are not accessible, so its exact cause is not established.
This code differs from READY_REQUIRED/BINDING_REQUIRED and does not itself
prove that the application's readiness or SSH credential has been reset.

Code investigation found that `osRunner.RunBounded` combined stdout and stderr.
The runtime protocol uses it for the release path, active-state metadata and
JSON response. A successful SSH/PAM/sudo notice on stderr therefore makes the
release path invalid and produces precisely `EXECUTION_NODE_UNAVAILABLE`.
A native subprocess regression with separate pipes reproduces the failure
with the original runner, without a network error or readiness change.

Correction reuses `RunSeparatedBounded` for bounded protocol output. Only stdout
is parsed; stderr is independently bounded to 16384 bytes and discarded. Exit
failures and overflow in either stream still block the operation. The subprocess
overflow checks also exposed inherited `bytes.Buffer.ReadFrom` bypassing
`boundedOutput.Write` during os/exec's io.Copy. A narrow ReadFrom override now
routes copies through the existing bounded Write. No credential TTL, host-key
guard, readiness, plan approval, retry, process lifecycle or contract changed.
The design check agrees with Servers' independent readiness/observation model;
no UI/design discrepancy or architecture change is introduced. This is a bounded
fix within the approved transport contract; no independent review was invoked.

Validation on base `1aefccef`:

- New runtime protocol test: actual native child processes emit valid release,
  active-state and JSON stdout plus synthetic private stderr; original runner
  FAILS with EXECUTION_NODE_UNAVAILABLE, corrected runner PASS.
- Native subprocess nonzero exit, stdout overflow and stderr overflow all remain
  rejected; private stderr canary is absent from returned stdout. Existing
  bounded-output retention test PASS.
- Full `go test ./...` and `go vet ./...` PASS on Windows. Race unavailable with
  CGO_ENABLED=0; no concurrency mechanism was changed.
- `wails build -s -skipbindings -m -nosyncgomod -nocolour` PASS, existing frontend
  assets, output `build/bin/platform-installer-ui.exe`.
- `node scripts/qa-wails-bridge.cjs`: QA_WAILS_BRIDGE_PREFLIGHT_FAILED. Real
  React/Wails password-SSH acceptance remains unavailable/blocking; no password
  from the isolated system was requested or used, no real Start was initiated.
  This fixes a reproduced failure mode, not proof of the isolated-system cause.
