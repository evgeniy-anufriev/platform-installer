# ClickHouse library base tables — FULL DIFF review

2026-10-17. Independent read-only reviewer `/root/kafka_topics_plan_review`.
Reviewer returned the report; parent recorded it. Verdict: **BLOCK**, 2 open findings.

## Reviewed identity

Base `08a8395ec1862d50b16cd8b07348e06725c462f4`.
Plan SHA-256 `40daaea3cebc83204881d8465c960e324414d8ff7aa324f1eed34e6c295c51a5`.
Source fingerprint `f32a10f1b24e569339710669e9e31c67cf99dcfd74163b343211fad332fec18d`,
46 files, independently checked before and after review. Sorted changed tracked
and untracked source/plan paths; each line path + space + lowercase SHA256(file)
+ LF, then SHA256 UTF-8. Excludes CURRENT_STATE, evidence/reviews and generated
vendor/portable/dist. Source remained frozen through the verdict.

## CHBT-D01 — BLOCKING / OPEN

`services/clickhouse/ansible_collections/platform/clickhouse/plugins/modules/application_scope.py:157–161`:
the existing explicit-table grant preflight rejects a missing table with
CLICKHOUSE_APPLICATION_MIGRATION_REQUIRED before library resources can create it.
The new account-free tests do not cover this path. Existing DB/missing base table
with an explicit application grant therefore fails before CREATE.

Smallest correction: preflight may tolerate only missing tables actually declared
for creation in the corresponding database/current plan. Accounts and Verify must
still require actual existence; missing undeclared tables retain the rejection.
Add production-module regression for preflight → resources → accounts and a
negative undeclared-table case, using fake clients without server mutations.

## CHBT-D02 — BLOCKING / OPEN

`services/clickhouse/ansible_collections/platform/clickhouse/plugins/module_utils/application_sql.py:33–38,69–77`:
table_matches compares engine names but not ReplacingMergeTree arguments. An
existing ReplacingMergeTree(insert_ts), or corresponding Replicated variant,
can pass against the required no-version engine despite different deduplication
semantics.

Smallest correction: compare native engine arguments including absence of version
and is_deleted parameters through the existing metadata/normalization boundary;
no general SQL parser or ALTER. Test actual table_matches: no-version variants
match; versioned variants with all other metadata equal fail with drift.

## Overengineering and evidence

No concrete unnecessary abstractions, duplicated contracts/DTO, speculative
persistence, premature migrations/schema UI, or missed simpler standard mechanism
found. Standard Ansible combine/template are used. Existing protected native
client and DB witness custody are reused. Early DB witness publication addresses
retry after a table error without adding a store/lock.

Reviewer inspected source/schema/defaults/template/provider/projection/tests/docs
and read-only fingerprints. Reported Core/Go/frontend test PASS are implementer
results, not reviewer reruns. Real Wails resource selection remains incomplete
(selector timeout); it is not PASS. Real server CREATE/HA/repeat acceptance was
not run under the owner's prohibition and is not an additional blocker.

Review validity: CURRENT for the fingerprint above. Automatic corrections stopped.
Owner decision required on D01/D02. One owner-approved TARGETED_RECHECK is available
for those IDs and immediately affected code; no further FULL review was started.

## Owner disposition — 2026-10-17

The original independent BLOCK verdict above is retained as review evidence.
The owner clarified D01: application grants cover the entire selected database,
including existing and future objects. Source inspection confirms the existing
UI writes `tables: ["*"]`, and user_batch renders `GRANT ... ON <database>.*`.
The missing-table check applies only to explicitly named table grants, not this
database-wide path. D01 is therefore NOT APPLICABLE to the required flow; no
per-table preflight exception or grants widening is needed.

The owner explicitly REJECTED D02: the current engine-name/schema verification
is sufficient. Engine-argument verification is not added. This is an owner scope
decision, not an independent reviewer APPROVE or a claim that arguments match.

Neither finding now blocks the owner-approved scope. Production code is unchanged
by this disposition. Real Wails/Core acceptance remains incomplete; the prohibition
on application installation and server table mutations remains in force.

Subsequent evidence update (2026-10-17): owner-authorized real React/Wails/Core
plan-only QA completed, seven cases PASS; see ../evidence/clickhouse-base-tables-journal.md.
The earlier incomplete-UI statement describes the review-time state. Production
source unchanged; plan status/evidence updated after QA, no new review verdict.
