# ClickHouse library base tables — implementation plan

Status: implemented; Core/UI plan-only acceptance PASS on 2026-10-17.
Owner dispositions and native execution limits: see evidence/clickhouse-base-tables-journal.md.
Owner prohibits application installation and all server table mutations during this stage.
Base: master `08a8395e` (portable-source refresh of `80b21f18`).

## Owner request and scope

Create `records` and `alarm_message` in every ClickHouse database selected in a
library's common resources. The owner clarified: "БД есть, таблиц ещё нет";
there is no request to create tables outside a library binding. Existing database
presence must not skip table creation. There is no per-application opt-in or new
UI table selector. DDL structure is authored in library defaults and overridden
only in project files. Replication follows each selected ClickHouse deployment,
not the number of hosts in the entire project.

Preserve the screenshots' column names/case, order, types, codecs, indexes,
partition/primary/sorting/sampling keys and explicit settings. `default` in the
alarm screenshot is replaced by the selected resource database, not hard-coded.
No conversion to Distributed tables, TTL addition, version argument for
ReplacingMergeTree or change to sorting/deduplication semantics is planned.

## Existing implementation and change points

- `resolve_application_libraries/tasks/instance.yml` loads package defaults with
  Ansible and emits resolved library/application rows. Extend that existing row
  with resource defaults, using ordinary combine, recursive=true/list_merge=replace.
- `application_libraries.py` and `application_providers.py` publish target-free
  library projection and existing per-library ClickHouse jobs. Database rows gain
  their resolved table specifications, independently of account references or
  existing database presence. Preserve existing physical provider/database claim
  checks; identical shared definitions may be deduplicated, conflicting table
  definitions for one physical provider/database/table must fail before mutation.
- `application-libraries-provider-stage.yml` already runs resource batches before
  account grants, Vault publication and containers; reuse this stage. Existing
  verify stage remains read-only. Existing projects/packages without table defaults
  keep their current behavior; SDKU supplies the two defaults. Do not silently
  introduce SDKU tables into unrelated libraries that do not declare them.
- ClickHouse `application_provider/tasks/resources.yml` enters the existing
  `application_scope` module. That module owns native TLS credential custody,
  client cleanup, current object witness/lock and cluster checks. Keep these
  boundaries; do not build a second credential/SQL execution subsystem.

## File-only contract

Keep resource structure distinct from `platform_library_definition.defaults`,
whose existing meaning is common application ENV/configuration. Add a separate
field in the same `roles/library_<name>/defaults/main.yml`:

```yaml
platform_library_definition:
  resource_defaults:
    clickhouse:
      tables:
        records:
          engine: MergeTree
          columns:
            - {name: systemId, type: UInt32, codec: 'T64, LZ4'}
            # Remaining ordered columns are transcribed from 1.png below.
          indexes:
            - {name: idx_set_objectId, expression: objectId, type: 'set(1000)', granularity: 1}
          partition_by: "toDate(fromUnixTimestamp64Milli(toInt64(ts), 'UTC'))"
          primary_key: '(parameterId, objectId, systemId, attrId, ts)'
          order_by: '(parameterId, objectId, systemId, attrId, ts, ts2, invalid, quality, value, strValue)'
          sample_by: parameterId
          settings: {index_granularity: 8192, allow_nullable_key: 1}
        alarm_message:
          engine: ReplacingMergeTree
          columns:
            - {name: id, type: UUID}
            # Remaining ordered columns are transcribed from 2.png below.
          order_by: '(ts, ts2, id)'
          settings: {index_granularity: 8192}
```

This is an abbreviated shape example, not the complete SDKU defaults. Columns and
indexes use ordered lists, so dictionary sorting cannot reorder them. Type/codec/
key/index expressions and explicit settings remain operator-authored file data;
this is a table specification, not a general SQL-script migration executor.
Do not add product settings allowlists; ClickHouse validates supported syntax and
settings. Escape identifiers/literals correctly and preserve camelCase columns;
the current database/account identifier helper must not rename or reject columns.

Override the same resource subtree on the library deployment in group_vars:

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      resource_defaults:
        clickhouse:
          tables:
            records:
              settings:
                index_granularity: 4096
```

Precedence: package resource_defaults < library deployment resource_defaults.
Use normal Ansible recursive combine, replacing lists. Omitting an override restores
the package value; it does not remove the two required tables. No application/slot
or host-specific table overrides: replicas of one table share one desired schema.
An explicitly empty override map does not disable base-table creation.

Extend the canonical library/deployment schemas and package capability metadata
for this field. Include resolved definitions in snapshot/plan fingerprints; a file
edit invalidates old Verify/plans through existing project revision rules. Older
Core schemas/package capabilities must reject unsupported table declarations,
not silently skip them. No new desired-state store, protocol for arbitrary SQL,
ownership registry, lock or production Python script.

## Engine and replication identity

| Selected deployment mode | records | alarm_message |
| --- | --- | --- |
| standalone | MergeTree | ReplacingMergeTree |
| raft-ha | ReplicatedMergeTree | ReplicatedReplacingMergeTree |

The current raft-ha package is one shard / three replicas and already projects
cluster `default`, Keeper and `{shard}`/`{replica}` macros. Use that resolved
context; do not discover a different effective mode or construct ports/hosts in
Go/UI. In HA issue one CREATE ON CLUSTER through an initiating provider member
and verify the result on every projected member. Standalone needs no Keeper.

Keeper paths must distinguish physical databases and tables. The screenshot's
`/clickhouse/tables/{shard}/alarm_message` cannot be copied literally for several
databases: they would share a replication identity. Propose one derived path:
`/clickhouse/tables/<projectId>/<deploymentId>/{shard}/<database>/<table>`,
with the same path on the table's replicas and distinct `{replica}` values.
Render database/table identity as concrete escaped path segments, not rename-sensitive
database/table macros. This is the intentional adaptation of screenshot engine
arguments; column/key/settings semantics remain unchanged. Existing tables are
never automatically reattached, converted or moved to this path.

## Resource execution and existing databases

1. Target-free planning resolves the table set for each selected
   `kind: clickhouse.database` resource, including mode=existing. Show the resource
   action through normal execution planning; no additional table editor or DDL
   viewer in UI. Planning/import/review do not execute DDL.
2. Preflight reads database/table metadata for all projected members, verifies
   target topology/credentials and detects conflicting existing table structure
   before provider writes. A missing table is valid for Apply, not for Verify.
3. Run existing database creation/ownership handling first. For an already present
   selected database, proceed to table checks; do not keep table creation inside
   the `database missing` condition. A managed database's existing ownership guard
   remains; an existing-mode database is not adopted, altered, replaced or deleted.
   Creating the requested child tables there is explicitly part of this new
   library contract, independent of database object ownership.
4. Create each missing base table with CREATE TABLE IF NOT EXISTS; in HA use the
   current ON CLUSTER context. Missing one table creates only that table. Re-read
   after creation/cluster propagation; do not equate a successful CLI return code
   with a completed cluster operation. Repeat and matching existing tables are
   unchanged. Run before account grants so table-specific grants can see the tables.
5. Verify reads all replicas and compares the expected structure: ordered column
   names/types/codecs, declared indexes, engine family/replication identity, keys
   and explicit settings. Use ClickHouse system metadata/native normalization,
   not a new home-grown SQL parser. Compare requested settings rather than every
   server default; do not compare volatile counters/merge progress or require
   byte-identical SHOW CREATE output. Bound waits for DDL/replica readiness.
6. No automatic ALTER, DROP/recreate, data rewrite or schema migration. A changed
   file updates desired DDL; an incompatible existing table produces a safe drift
   finding. A separate explicit task is needed for existing-data migration.
   Removing/changing a library or resource does not delete tables/data.

Use builtin Ansible loops, Jinja and filters for defaults/DDL rendering and ordinary
task flow where practical. Reuse the existing protected native-client execution;
small additions to existing application_scope/application_sql are justified only
for operations within that established custody/lock boundary. No new Python
executable or general migration framework. No separate runtime table witness is
needed for this create/verify-only scope; retain current DB/account witnesses.
Safe diagnostics identify provider/database/table, operation, mismatch or ClickHouse
error code. Keep raw credential/config/client output private; table failures remain
application-resource failures and do not revoke unrelated infrastructure evidence.

## DDL transcription checklist

Source images supplied by owner, read visually; not repository instruction files.

records (1.png):

- UInt32 + CODEC(T64,LZ4): systemId, objectId, parameterId, attrId.
- ts UInt64 CODEC(DoubleDelta,LZ4); ts2 Nullable(UInt64) same codec.
- quality Nullable(Int64) CODEC(T64,LZ4); invalid Nullable(Bool) CODEC(LZ4).
- value Nullable(Float64) CODEC(Gorilla(8),LZ4); strValue Nullable(String) CODEC(LZ4).
- service LowCardinality(Nullable(String)) CODEC(LZ4); dt Date CODEC(DoubleDelta,LZ4).
- ts3 Nullable(UInt64) and offs Nullable(Int64), both CODEC(DoubleDelta,LZ4).
- tagName Nullable(String) CODEC(LZ4); status Nullable(Int64) CODEC(T64,LZ4).
- Indexes GRANULARITY1: idx_set_objectId objectId set(1000),
  idx_set_parameterId parameterId set(1000), idx_minmax_h1 intDiv(ts,3600000)
  minmax, idx_minmax_offs offs minmax.
- Partition/primary/order/sample keys as in the example above.
- Full settings: index_granularity=8192; allow_nullable_key=1;
  ratio_of_defaults_for_sparse_serialization=0.95; ttl_only_drop_parts=0;
  columns_to_prewarm_mark_cache='parameterId,objectId,systemId,attrId,ts';
  prewarm_mark_cache=1; prewarm_primary_key_cache=1; use_primary_key_cache=1;
  primary_key_compression_codec='LZ4'; max_bytes_to_merge_at_max_space_in_pool=161061273600;
  max_bytes_to_merge_at_min_space_in_pool=1048576; max_parts_to_merge_at_once=100.

alarm_message (2.png), ordered columns:

```text
id UUID; system_id UInt32; object_id UInt32; parameter_id UInt32;
detail_nr UInt32; ts UInt64; ts2 UInt64; quality Int64; signal_val String;
ack_time UInt64; in_time UInt64; ack_state UInt32; alert_class_name String;
ackable Bool; direction Bool; text String; comment String; signal_state UInt32;
user_name String; description String; text0 String; arm String; prior UInt32;
invalid Bool; insert_ts UInt64; out_of_service Bool; alert_class String;
alert_class_by_group Map(String,String); tag_name String;
responsibility_area Array(String); control_time UInt64
```

ORDER BY(ts,ts2,id), index_granularity=8192; no added partition/version/TTL.
Verify the transcription and all engine settings on the pinned ClickHouse version
in isolated QA. Do not silently drop an unsupported setting from the screenshot.

## Acceptance and implementation sequence

1. Approve this contract/behavior, then extend schemas, defaults and existing
   Ansible/Core provider projection; update capability/catalog and fixtures.
2. Add create/verify to the current ClickHouse resource path with minimum code;
   add complete SDKU table defaults. Update contracts/Core/service docs and roadmap.
   Update shared UI design rules to record that table schema is file-only.
3. Confirm UI does not render/edit the schema and all unrelated generic library
   resource edits preserve file-authored resource_defaults. If the current writer
   reconstructs a mapping, preserve the new field; no table edit command in Go/UI.
4. Focused target-free tests: standalone/HA in the same library, two databases,
   overrides/default reset, all selected DBs even without ClickHouse accounts,
   present DB/missing tables, no default table definitions in unrelated libraries,
   duplicate physical resource conflicts, unsupported older runtime, revision and
   plan-fingerprint changes after file edits.
5. Owner-authorized isolated native QA: new DB; existing selected managed DB;
   existing-mode DB with no tables; one missing table; unchanged repeat; standalone
   engines without Keeper; HA creation and matching metadata on all three nodes;
   same table names in two DBs with independent Keeper paths and isolated data;
   file override and drift without alteration; read-only Verify; fail/retry and
   credential-safe diagnostics. Do not install applications for these tests.
6. Real React/Wails/Core check: select DB through existing library Resources UI,
   Save/reopen, external file override retained by an unrelated UI Save, fresh
   Verify/Build/Review against current runtime, no schema editor exposed. Native
   table checks supplement this flow; do not replace it with mocked bindings.
7. One independent FULL DIFF review (HIGH-RISK public contract/provider mutations),
   followed by the existing owner-approved correction/TARGETED_RECHECK budget if
   necessary. No production deployment, application Start, artifact acquisition
   or table mutation during this planning step.

FULL PLAN review precedes presentation for owner approval. No new persistent
ownership/source-selection boundary is planned; architecture decisions change
only if implementation proves a boundary change necessary.

References: [ClickHouse Replicated engines](https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/replication),
[ReplacingMergeTree](https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/replacingmergetree),
[ON CLUSTER](https://clickhouse.com/docs/reference/statements/distributed-ddl).
