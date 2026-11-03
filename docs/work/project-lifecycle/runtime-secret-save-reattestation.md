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
