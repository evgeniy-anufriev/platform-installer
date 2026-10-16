# SECRETS-ACCESS — independent TARGETED_RECHECK

2026-10-16. Verdict: **APPROVE**, zero unresolved blockers. Independent read-only
architecture-reviewer reused from FULL DIFF; parent transcribed this report.
One owner-approved targeted recheck used, limited to SEC-D01/D02 and directly
affected boundaries. No tests/target contacts/file edits by reviewer.

HEAD adc491da19f44802389a3aa5eb127081522c3ed7. Manifest
`.runtime/qa/application-design/secrets-access-recheck-identity.json`, SHA256
`2F5AE86AFF78A0D3CAC9DEF095B437F01FC3320C316DDAF47E8254C208907679`.
Every listed file hash matched at start/end; validity CURRENT for this identity.

## SEC-D01 — OWNER_ACCEPTED

Owner explicitly rejected ownership prohibition. PostgreSQL preserves operator-
assigned object ownership and a self creator role; corresponding owner ACL/default
ACL is not removed. Default ACL uses acldefault baseline. Safe notice
APPLICATION_PROVIDER_OWNER_AUTHORITY_PRESERVED and UI explanation prevent claiming
that DML revoke removes owner authority. Foreign ownership/membership/admin guards
remain. Positive native coverage includes schema/table/sequence/self-creator,
access removal and unchanged repeat. This is changed authority policy, not proof
that ordinary REVOKE restricts the owner.

## SEC-D02 — RESOLVED

managed_grant_delta limits revoke to direct SELECT/INSERT on same-library managed
DBs. Custody/all-node UUID+marker checks precede changes. Foreign DBs, unsupported
rights, role membership and column/partial/grant-option remain conflicts. Deleted
access DBs stay in job scope. The existing native batch/ON CLUSTER path executes
revoke; per-node final grant deltas must be empty before witness publication.
Tests cover two DBs, reduction, last-access deletion, actual deny, neighbor
preservation and foreign-assignment refusal. No unconditional REVOKE/guard removal.

## Minimalism / limits

No unnecessary mechanism found: existing witness/locks/batch/job projection,
no DTO, grant ledger, persistence, daemon, polling or concurrency. Canonical docs
and owner amendment inspected. Evidence at review was PG owner65.554s PASS and
CH standalone PASS; cluster/runtime/Vault/Agent/cleanup were still pending.
Review approval is not the final QA verdict. No further automatic review required.
