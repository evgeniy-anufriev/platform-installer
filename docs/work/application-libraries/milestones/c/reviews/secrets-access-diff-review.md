# SECRETS-ACCESS — independent FULL DIFF

2026-10-16. Verdict: **BLOCK**, independent architecture-reviewer, two blocking
findings. Reviewer was read-only; report transcribed by parent. No reviewer
tests/target contacts. One FULL review used; no recheck performed.

HEAD adc491da19f44802389a3aa5eb127081522c3ed7. All18 file hashes from
`.runtime/qa/application-design/secrets-access-review-identity.json` matched
at start/end. Manifest SHA256:
`C6AC739A7530B0C4B8B3B6D655CECAEAA117E95BFBE64D93535D7C54F73483BB`.
Unrelated earlier dirty UI changes were outside review scope.

## SEC-D01 — BLOCKING / OPEN

`database_access.sql.j2:25` accepts a schema/relation owner with any same-library
account marker, including the grantee itself. Existing preflight rejects DB
ownership/membership, not schema/table ownership. Ordinary REVOKE cannot remove
implicit owner DDL/grant authority. A self-referential additionalCreatorRoles
also permits this for future objects.

Smallest correction: reject target_oid ownership of user schemas and supported
relations, reject target account in creator roles. Keep current guards; never
REASSIGN/DROP OWNED. Native negatives for schema/table/sequence and self-creator
must prove conflict without changing ownership/ACL/data.

## SEC-D02 — BLOCKING / OPEN

`ApplicationAccountAccess.tsx:169` promises removed CH rights will be revoked.
`services/clickhouse/.../plugins/modules/application_scope.py:116` instead fails
with CLICKHOUSE_APPLICATION_GRANTS_DRIFT for observed rights outside desired.
This pre-existing limitation is newly exposed as supported CRUD by this UI.

Owner choices:
1. Reduce scope: disable CH removal/reduction and accurately document it. This
   does not fulfill original full CRUD acceptance.
2. Implement bounded managed-CH grant ownership/reconciliation with existing
   witness, native batching and cluster checks. Revoke only calculated grants
   in the approved owned scope. Preserve membership/grant-option/partial-column/
   foreign-ownership failures; do not simply remove GRANTS_DRIFT or revoke all.

Choice2 requires explicit owner acceptance of CH policy; the PG ACL policy is
not implicitly applicable to CH. Test one account/two DBs, INSERT reduction,
one/last-row deletion, Verify, unchanged repeat, actual permissions, neighbor
isolation and cluster propagation.

## SEC-D03 — nonblocking / OPEN

Synchronize approved-plan status and canonical contract/capability/creator-role
documentation before closure; distinguish current Core extension from historical
UI-only acceptance in CURRENT_STATE.

## Minimalism and gate

Zero blocking overengineering findings. databaseAccess expresses the concrete
multi-DB requirement; SQL uses current sessions/locks/quoting/markers, policy
filter keeps Ansible precedence, UI uses current writer/dirty/lease. No new DTO,
state store, ACL ledger, daemon, event triggers, polling or concurrency.

Reported native/core/frontend evidence is implementer evidence, not independent
reproduction. Full regression and runtime/Vault/Agent end-to-end acceptance were
unfinished at review. Validity CURRENT for manifest. Stop automatic changes and
return SEC-D01/D02 to owner; an owner-approved TARGETED_RECHECK may inspect only
these findings and directly affected boundaries after permitted corrections.
