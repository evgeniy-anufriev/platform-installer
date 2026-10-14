# B1 — Go read models, adapter and local observation

2026-10-14. Owner authorized B1 implementation after B0 synchronization.
Branch `codex/application-libraries-b1`; base
`12aa076a3dd96716e929cba3a63365bfa4140a8d` (B0 plus generated portable refresh).

## Scope and boundaries

Approved [B plan](../b-technical-plan.md), sections 5.1 and 9.
Core remains the resolver and admission authority. No new Core operation,
schema, desired-state store, provider selector or Compose converter was added.
No B2 writer, B3 execution lifecycle, UI/bindings, infrastructure rerun, commit
or push is included in this implementation authorization.

UI design/matching Installation mockup checked before implementation: status
presentation is Core-owned; unavailable observations must remain unknown;
fresh plan/approval/Start remain separate. B1 adds no screen or action. No
material discrepancy requires a change to the agreed UI flow in this stage.

## Implementation

- `coreadapter.Snapshot` retains the versioned application projection with typed
  libraries, instances, placements and origins; open product-specific parameters,
  provider descriptors and resources remain Core-provided JSON. Version/ID/count
  and response-size checks reject invalid application snapshots.
- `OpenSSHTransport.ReadApplicationLibraries` reuses `BuildProjectSnapshot`.
  `BuildDeploymentPlanForMode` negotiates B0 capabilities before staging and sends
  v1alpha4 with a fixed mode and runtime-source choices, never secret values.
  Legacy ordered plans and new mode plans share the same staging, decoding and
  manifest binding helper. An unsupported/mismatched mode never falls back to full.
- Plan decoding retains the typed infrastructure summary and application image
  requirements separately from service/RPM requirements. Missing/stale reason
  codes remain unchanged. Closed summary/image values reject unexpected fields.
- A separate bounded JSON observation uses the existing canonical project key,
  root checks, private temporary file, atomic replace and directory sync. The
  existing v1 last-run record remains unchanged. Cache binding excludes SSH user
  and includes node address/port/host-key identity and bundle digest.
- Cached display always reports current availability `UNKNOWN`; previous result
  and observation timestamp are informational. Publication/read helpers are B1
  backend primitives for B3 consumption, not new Wails bindings or Start paths.
  Cache write failure is returned separately and cannot alter a remote result.

## Verification

- Focused `go test ./internal/coreadapter ./internal/executionnode ./internal/desktop`
  PASS on the final frozen source.
- `go test ./...` PASS; `go vet ./...` PASS; `git diff --check` PASS.
- New checks cover typed application projection, unsupported versions/IDs,
  response size, closed evidence, mode negotiation/no fallback, fixed protocol
  request and wrong-mode response, image/RPM separation, corrupt/oversized cache,
  project relocation/node/bundle mismatch, account-independent observation,
  UNKNOWN availability, v1 last-run preservation, symlink refusal when supported,
  and a real filesystem write failure.
- An initial compile check caught misuse of the existing singleton-array helper;
  corrected with a fixed three-mode check. The first new capability test omitted
  required envelope fields; fixture corrected to match the closed contract. Both
  failures were superseded by the passing focused and full checks above.
- No Core/service source changed; no target mutation or installation performed.
  Real UI flow acceptance is not claimed; production integration is B4.

## Review gate

Mandatory HIGH-RISK FULL DIFF review requested for the persistence/contract boundary.
Source identity manifest `.runtime/qa/b1/diff-identity.txt` SHA256
`4c39e4e50f88c7edcc7330811f7406e15396cfbb02941dfa63652217e6c3e559`.
Independent [FULL DIFF](../reviews/b1-diff-review.md) returned
APPROVE_WITH_CHANGES, zero blockers. One nonblocking B1-D01 identity-consistency
check corrected: `localReference` must match the image digest; positive fixture
made consistent and negative mismatch added. Focused executionnode tests and vet
PASS after correction. No repeated architecture review was required/requested.
The initial broad text replacement also touched an unrelated test closure and
was caught by compilation; that incidental edit was removed before focused PASS.
Final correction affects only image decoder and its test, retaining all existing
checks. Full Go regression/build above applies to reviewed source; final bounded
delta has its own focused PASS. No additional Core/target acceptance claimed.
Final 11-file identity manifest `.runtime/qa/b1/final-identity.txt` SHA256
`9575b7aa32450d56e1a421fcc4f091e24d74cfe354511e0461779e01b9475263`.

## Owner-authorized commit and synchronization

Owner requested B1 commit and master synchronization on 2026-10-14.
Final 11-file identity rechecked unchanged; full `go test ./...` and
`go vet ./...` rerun PASS after B1-D01 correction. Bounded secret-pattern and
staged diff checks PASS. Only B1 source/tests and evidence/current-state files
included; runtime files excluded. No next milestone implementation authorized.
