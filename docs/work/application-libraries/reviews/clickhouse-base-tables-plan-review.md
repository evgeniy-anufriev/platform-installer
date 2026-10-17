# ClickHouse library base tables — FULL PLAN review

2026-10-17. Independent architecture reviewer `/root/kafka_topics_plan_review`.
Verdict: **APPROVE**, zero blocking or nonblocking findings. Reviewer operated
read-only and returned the report; parent recorded it here.

## Identity and scope

Plan `docs/work/application-libraries/clickhouse-base-tables-plan.md`, SHA-256
`152cab781d628d7c8ffaba07b93f3f4d77c6375732ba53c4dde8396fa27b74c6`,
rechecked after inspection. Source context HEAD
`08a8395ec1862d50b16cd8b07348e06725c462f4`.
Full plan reviewed: file-only contract/precedence, both image DDLs, engines,
Keeper identity, resource stages, existing DBs, Verify, compatibility and acceptance.
Authorization covers planning only, not implementation or target changes.

## Findings and architecture

No new finding IDs. The clarification "БД есть, таблиц ещё нет" is represented:
table creation is independent of database creation, including an explicitly
selected existing-mode database. This new child-resource behavior requires owner
approval and is not disguised as existing database reconciliation.

Both images were directly inspected. Columns/order/types/codecs/indexes/keys/
settings agree with the transcription. Engine path changes are explicitly proposed
adaptations. Keeper paths distinguish physical databases/tables, avoiding shared
replication identities and rename-sensitive database/table macros. Original
ReplacingMergeTree sorting and absence of a version argument are preserved.
The existing DB/account helper is unsuitable for camelCase columns; the plan
separates their rendering without expanding unrelated account policies.

Resource defaults remain distinct from application common defaults, with Ansible
merge/precedence. Package defaults/group_vars are desired state; projections/jobs/
fingerprints are derived. All selected SDKU ClickHouse databases are covered even
without account references; libraries without these defaults retain prior behavior.
Existing resource stages and protected application_scope retain credential custody
and current witness/lock boundaries. UI neither resolves topology nor edits DDL.
Standalone/HA come from the selected deployment. CREATE/read-back/Verify exclude
ALTER/DROP. All projected HA members are checked after distributed DDL propagation.

## Overengineering

Unnecessary abstractions, duplicate DTO/contracts, premature scope, speculative
persistence/lifecycle mechanisms and omitted simpler mechanisms: **0**.
Ordered specifications serve the two actual DDLs and file overrides. Existing
Ansible combine/Jinja/loops are appropriate; a small extension of the protected
native client avoids duplicating secret/client handling. No migration engine,
UI schema editor, table ownership registry, new Python executable/parser or lock.

## Evidence and limits

Reviewer read current status/procedure/contracts, resolver/provider paths,
application_scope/native SQL helper, writer and affected design rules. Images
were visually compared and technical assertions checked against official docs:
[replication](https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/replication),
[distributed DDL](https://clickhouse.com/docs/reference/statements/distributed-ddl),
[ReplacingMergeTree](https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/replacingmergetree).

No tests/server operations or secret reads. Screenshot setting support on pinned
ClickHouse, metadata normalization, HA propagation/retry and preservation during UI
Save remain implementation/QA gates, not demonstrated results.

Validity CURRENT. Material changes to authority, existing-mode child-table behavior,
engine/replication identity, mutation or credential execution need assessment of the
changed boundary. Next: owner approval, explicitly noting Keeper path adaptation.
No implementation or DDL execution before that approval.
