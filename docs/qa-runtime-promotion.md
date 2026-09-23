# Resumable QA runtime promotion

`cmd/qa-runtime-promote` is a DEV/QA-only helper for a test project whose
immutable runtime release must change between acceptance cycles. It is not a
UI operation, does not choose a latest release, and is not used by normal
Execution Node preparation.

The caller supplies the project root, its exact expected artifact/catalog lock
pair, one trusted Execution Node, and either a runtime input plus new bundle
version or an explicit already-published digest. The helper performs:

```text
build on trusted acquisition node
→ durable pre-publication checkpoint with the verified new digest
→ verify and immutable publish
→ durable runtime-only checkpoint
→ supported prepare/activation
→ project-wide CAS update of artifactLock + catalogLock
→ reopen against the exact verified bundle
→ remove checkpoint
```

The checkpoint is under `.runtime/qa/runtime-promotions/`, contains only
paths, immutable digests and its stage, and is never canonical project state.
The pre-publication checkpoint also closes the short interruption window after
the cache has published and pruned the previous local release but before a
post-publication write can finish. A rerun resolves only that recorded digest;
if it was not published, it rebuilds and requires the same digest. It never
selects an arbitrary cache entry. A caller may instead provide
`-published-digest` for recovery of a release published before this helper was
introduced.

If project locks no longer equal either the supplied old pair or the exact new
pair, the helper stops without modifying the project. It uses the existing
`UpdateRuntimeLockSet` atomic transaction; ordinary project writers remain
unable to change runtime locks.
