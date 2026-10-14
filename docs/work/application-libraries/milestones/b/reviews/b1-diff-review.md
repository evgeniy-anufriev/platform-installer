# B1 — independent FULL DIFF review

2026-10-14. Independent read-only `architecture-reviewer`, agent
`/root/b1_diff_review`. **APPROVE_WITH_CHANGES**, **0 BLOCKING**.

## Identity and scope

Base `12aa076a3dd96716e929cba3a63365bfa4140a8d`.
All 11 files in `.runtime/qa/b1/diff-identity.txt` checked; no hash mismatch.
Manifest SHA256:
`4c39e4e50f88c7edcc7330811f7406e15396cfbb02941dfa63652217e6c3e559`.
Approved B plan SHA256:
`a831e85165db407e1300e74f848e0e678a2f281702b21b6b4647230b37b2bce2`.

Scope: typed application snapshot, image requirements, B0 mode request and
summary decoding, local observational cache and shared atomic writer.
B2–B4, Wails/UI and infrastructure execution excluded.

## B1-D01 — NON_BLOCKING / OPEN in reviewed revision

`internal/executionnode/application_image.go:35` and
`internal/executionnode/infrastructure_verification_test.go:103`.
Decoder validates `imageId` and `localReference` formats independently and accepts
different digests. Positive test uses `aaa…` and `bbb…`. Existing Core
`application_runtime.image_requirement()` derives the reference from the same
image ID and rejects a mismatch.

Impact: inconsistent response could enter presentation. No admission bypass:
Core still owns delivery/Start and Go does not execute this read model.
Smallest correction: consistent positive fixture, negative mismatch case and
digest equality check. No resolver/DTO addition. Focused test is sufficient;
another architecture review is not required for this correction.

## Overengineering

Reviewer found zero unnecessary abstractions, duplicate DTO/contracts,
excessive persistence, premature scope or speculative mechanisms.

`buildDeploymentPlanRequest` and `writeLocalOperationalRecord` remove duplicate
staging/atomic publication sequences. Open product-specific JSON avoids moving
provider/configuration semantics into Go. Separate bounded JSON is required by
plan §5.1 because last-run must not erase infrastructure observations; no new
database/catalog/desired-state store exists.

B1 cache primitives are intentionally for later B3 consumption. Absence of
lifecycle refresh/Wails bindings is not incomplete B1. No generic CRUD, new
goroutine, plugin framework, second Compose resolver or arbitrary selector.
Only missed simpler mechanism is the local equality check in B1-D01.

## Evidence and limitations

Reviewer read root/scoped instructions, review procedure, current state,
approved plan, affected Go source/tests, canonical B0 schemas and actual Core
application/image projection, ownership/Installation UX rules and mockup.

Confirmed by code: cache availability always UNKNOWN; prior PASS never becomes
admission; SSH user excluded, host identity/bundle retained; corrupt/missing
cache never becomes PASS; modes negotiated without FULL fallback; existing
staging/protocol/manifest binding reused; last-run v1 format unchanged; no
secrets/stdout/runtime credentials in the new cache.

Parent reported focused/full Go tests, vet, build and diff check PASS. Reviewer
did not run tests or visit targets. No real UI acceptance performed or claimed;
it remains a later gate.

Review valid for the recorded identity. Changes to admission, protocol,
persistence security or lifecycle require separate classification. The obvious
B1-D01 correction and status synchronization do not invalidate this review.
Next action: present B1 result/limits to owner; later milestones not authorized.

## Author correction after review

B1-D01 corrected with equality against the image-derived local reference,
consistent positive fixture and mismatched-digest negative case. Focused
`go test ./internal/executionnode` and `go vet ./internal/executionnode` PASS.
This is author-verified correction, not an independent recheck or new verdict.
Original reviewer finding and identity retained above. No automatic re-review.
