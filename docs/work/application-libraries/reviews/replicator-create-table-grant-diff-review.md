# Replicator CREATE TABLE — FULL DIFF

2026-10-18. Independent architecture-reviewer: **APPROVE**, zero findings and zero blocking findings.

Base: `83f89e316a0ba267a39379f001289fdb1e929f19`.
Normalized scoped diff SHA-256: `ae4f0e3c4d52ad7a60504f1338a1026bbf93f50e88b5a210b4d4819992d69542`.

Scope: Core `normalize_clickhouse_grants`, ClickHouse `application_sql.py`,
their two provider test files, project/Core contracts and kafka-ch-replicator
defaults. Other accumulated SDKU changes are excluded.

CREATE TABLE is supported consistently through normalization, desired/current
grant comparison, GRANT/REVOKE SQL and read-only CHECK GRANT. Existing account
and database UUID/marker custody, same-library database boundaries, foreign
grants/roles/grant-option/partial-revoke conflicts and existing-account
nonmutating policy remain. No additional runtime, lock, store or abstraction.
The SDK ClickHouse health disable is explicitly owner-approved; TLS,
multi-host JDBC and Docker/HTTP health remain.

Reviewer independently inspected source, orchestration and diff identity; no
target contacts or tests were performed by the reviewer. Parent-run RED OS
evidence: Core18 PASS; provider7 PASS197.655s, including isolated native
standalone and three-server cluster, CREATE TABLE/check/repeat/revoke. The
earlier missing-collection-path QA failure is retained separately in the
[journal](../evidence/sdku-sequential-applications-journal.md).

Review does not establish real three-host application acceptance. That gate
uses a new approved plan on the validated/published runtime23 with skip_verify.
