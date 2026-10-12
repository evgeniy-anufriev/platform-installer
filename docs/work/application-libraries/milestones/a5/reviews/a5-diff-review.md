# A5 — independent FULL DIFF review

Date: 2026-10-11. Verdict: **BLOCK**. Independent reviewer:
`/root/a5_full_diff_review`, role `architecture-reviewer`.

## Reviewed identity

- Branch: `codex/application-libraries`.
- Base HEAD: `054668d36fdaab14d9012dba8f45337bbd5cbd04`.
- Uncommitted source manifest: `.runtime/qa/a5-full-diff-source.sha256`.
- Manifest SHA256: `ea490d48dcea6792d0ee19cae73170e42e2225c9bc4532f6fb3c832d7376f2c2`.
- All 95 file hashes matched. Prior unrelated A2 documentation/hunks excluded.
- Scope: Redis/Sentinel ACL, ClickHouse resources/accounts/grants, shared
  projections, protected credentials, Verify, catalog/schema and QA probe.
- No Go/UI, endpoint implementation, commit or master synchronization.

Source was frozen during review. This report and subsequent status-only updates
record the verdict; they do not change the reviewed implementation.

## Findings

### A5-D01 — BLOCKING, targeted recheck pending: partial-member failure/retry

Evidence: mandatory plan matrix at `a5-technical-plan.md:461`; ClickHouse
`plugins/modules/application_scope.py:78` and Redis provider
`tasks/account_scope.yml` implement multi-member boundaries. Successful native
tests, concurrency, wrong-password and foreign-account denial do not prove
behavior after a partially successful fan-out. Implementer confirmed no native
partial-member failure/recovery scenario has been run.

Impact: aggregate failure and the barrier before Vault credential publication
remain unproved after partial mutation.

Owner authorized a targeted recheck. Added native Redis member fan-out recovery
and ClickHouse three-server fail-closed/retry cases. The final run passed the
Redis ACL suite (2 tests) and ClickHouse provider suite (3 tests). Redis member
one retains its witness through member-two authentication failure; after
correcting the invocation credential, member two applies and repeats are
unchanged. ClickHouse blocks a foreign same-name account on one HA member before
the following publication-marker task; removal of the isolated fixture permits
the application account to be created across all members. See
`../evidence/a5-test-journal.md`, “Owner-approved D01/D02 targeted acceptance”. Independent
targeted review result is pending.

### A5-D02 — BLOCKING, targeted recheck pending: two libraries/two Docker hosts

Evidence: mandatory plan matrix at `a5-technical-plan.md:460`. Unit tests
`test_application_providers.py:37` and `:95` prove placement deduplication and
name collision rejection. Full A5 pipeline used one Docker host. Separate
ClickHouse HA and prior A4 multi-host evidence do not prove the combined A5
library-isolation flow.

Impact: the full approved A5 acceptance matrix cannot be claimed complete.

Owner authorized a targeted recheck. Added a Core projection scenario with two
libraries, two Docker placements on different hosts, separate Redis deployment
scopes and exactly one logical account hook per library. Added a native Redis
case proving installation of the second library preserves the first account
and witness. Both focused test suites passed. See the journal section above;
independent targeted review result is pending.

### A5-D03 — NON_BLOCKING, CLOSED: Redis existing ACL profile documented/tested

Evidence: Redis `plugins/module_utils/application_acl.py:185–193` accepts a
narrow canonical ACL profile. Additional permissions/categories or broader key
patterns cause `GRANTS_DRIFT`, even when requested operations would be allowed.
The native existing-account test uses an exactly matching profile.

The supported canonical profile and fail-closed behavior are documented in the
A5 technical plan. A native negative test confirms that a broader existing
account using `+@all`/`~*` is rejected and not adopted. No category/glob
interpreter was added.

### A5-C02 — NON_BLOCKING, OPEN: production Keeper queue policy proof

Tests show no plaintext password in the native queue and no submitted
password/verifier in checked server logs. They do not prove production queue
access/retention policy. Keep protected existing Keeper infrastructure an
explicit prerequisite; no new subsystem is required.

A5-C01 remains **OWNER_ACCEPTED**. Historical PLAN BLOCK is preserved;
pending-operation markers, task correlation and special ambiguity retry gates
remain excluded by owner decision.

## Architecture and overengineering assessment

No confirmed architectural violation or secret leak was found in the inspected
code. No blocking overengineering findings: shared member projections avoid
allocation duplication; native service modules maintain a single lock/check/
mutation/persistence boundary using standard locks, temporary files and native
clients. No new DTO registry, persistence layer, lifecycle framework or
premature Go/UI/Kafka-SASL scope was introduced.

Reviewer independently inspected contracts, instructions, relevant changes and
tests, and checked revision identity. QA was supplied by the implementer and
the journal; reviewer did not run target operations or extract runtime secrets.

## Disposition

The original FULL DIFF verdict remains BLOCK. The owner authorized corrections
and one TARGETED_RECHECK for A5-D01/D02.

## Owner-approved TARGETED_RECHECK

**Verdict: APPROVE — A5-D01 and A5-D02 resolved.** Independent reviewer:
`/root/a5_d01_d02_targeted_recheck`. Scope was limited to these findings and
the immediately affected boundaries.

- Verified source manifest: `.runtime/qa/a5-targeted-recheck-source.sha256`,
  SHA256 `87eadc687df307b1f2debf58c0d539aa2762d3b5e757f24441cfb2519f14d0cd`;
  all 96 hashes matched.
- D01 resolved: native Redis member error/retry preserves the completed member
  and witness; the second member can finish, and the publication marker is
  withheld until the required members pass. Native ClickHouse three-server
  test confirms a foreign same-name account blocks before the next publication
  task; after removing the isolated fixture, ON CLUSTER apply and unchanged
  repeat pass.
- D02 resolved: two libraries, two Docker placement host IDs, separate Redis
  provider scopes and one logical account hook per library are covered by Core
  projection. Native Redis confirms adding the second library preserves the
  first account and witness.
- No overengineering was found in the corrections. The reviewer independently
  checked the manifest but relied on the implementer's journal for QA results;
  the reviewer did not run the tests.

The FULL verdict above remains the historical initial result; its two blocking
findings are resolved by this approved recheck. No further FULL or targeted
review is authorized by this result. A5 implementation, current-scope QA and
the allowed review gate are complete. C02 remains a documented nonblocking
Keeper infrastructure policy limitation. No commit or master synchronization
performed.
