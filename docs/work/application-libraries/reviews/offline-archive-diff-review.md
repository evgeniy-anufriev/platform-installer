# Offline archive deduplication — independent FULL DIFF

2026-10-21. Independent read-only architecture-reviewer verdict:
**APPROVE_WITH_CHANGES**, unresolved BLOCKING: **0**.

Base HEAD: `9cee05b2fe3eabf4279a6cfed3d0e41a87e8ad16`.
Four-file review snapshot:
`sha256:8c6442f9abeafde70f03bb5910b288a71bb4197de6c51bcd6216be62c998caa3`.
Identity is SHA256 of UTF-8 LF-joined `<relative path> <lowercase SHA256>` rows,
in order:

1. `ansible-core/playbooks/application-libraries-preflight.yml`
2. `ansible-core/playbooks/tasks/application-libraries-offline-archives.yml`
3. `ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/preflight.yml`
4. `ansible-core/tests/qa_application_offline_archives.py`

Older dirty Kafka/Vault optimizations excluded. Owner authorized deduplicated
archive verification and full alarm-view SDKU/CSPA plan with
`skipInfrastructureVerify=true`. Reviewer did not edit source, run tests or
contact targets. Snapshot hashes were independently rechecked unchanged.

## Findings

**OAR-D01 — NON_BLOCKING, OPEN**, native test file around line63. Extracted-barrier
tests prove deduplication and integrity failures, but do not instrument the exact
number of real filter calls or run the production play sequence with a later
mutation sentinel. A future wiring/recomputation regression could escape these
tests. Current unique-record loop and production import order directly establish
the intended behavior. Recommendation: add a call counter, a corrupted-archive
mutation sentinel and a direct-role immediate-check assertion. Source change or
another architecture review is not required for this nonblocking recommendation.

## Reviewer conclusions

- Existing manifest digest, component lock, size/SHA256 and symlink checks reused.
- Barrier follows all target preflight and precedes Vault/provider mutation stages.
- Only actually selected OFFLINE_BUNDLE rows are checked; repository-selected
  fallback bytes remain untouched.
- Full records determine uniqueness, so different paths/locks are not merged.
- Target archive copy still receives its own SHA256/size check before Docker load.
- Direct role preflight retains immediate verification by default.
- No persistent cache, new DTO, lifecycle or unnecessary abstraction introduced.
- Supported `--limit` calls must include localhost, as already required by the
  pre-existing resolver; no new limiter workaround is recommended.

Reviewer received node2 current-source QA:28 tests/61.387s, OK(one existing skip):
native6 PASS, runtime21 PASS/one skip. Syntax was pending in the report; parent
subsequently completed Apply syntax check PASS. git diff --check PASS.
Review does not establish changed-runtime performance or real application
acceptance. Those require the separately owner-authorized standard plan.

Validity CURRENT for the exact reviewed source snapshot. Changes to stage order,
archive selection, integrity filter or direct-role mode invalidate the affected
conclusion. Documentation and recommended test additions alone do not.
