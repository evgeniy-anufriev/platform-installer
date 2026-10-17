# ClickHouse library resources

The `service.clickhouse.table` capability extends the existing application_provider
resource stage. Table specs come from the library's file-only `resource_defaults`;
there is no service-wide SDKU schema or UI table editor.

Ansible merges the package/deployment maps, renders the table DDL with the ordinary
role template, and passes it to the existing protected application_scope. Native
client TLS files, credentials, lock and DB/account witnesses retain their current
custody. Newly created DB ownership is saved before table creation, so table errors
can be retried without adopting a foreign DB.

Standalone creates MergeTree/ReplacingMergeTree; raft-ha creates their Replicated
variants once ON CLUSTER default and checks every projected member. Missing tables
are created even if the selected DB already exists. Metadata checks compare
columns/codecs/indexes/keys/requested settings and replication identity; Verify
does not write. No automatic ALTER, DROP, data migration or table ownership store.

Failures expose provider/database/table/operation and a safe code; raw native client
output and credentials remain private. See the [contract](../../docs/project-contract.md#file-only-clickhouse-base-tables)
and [implementation plan](../../docs/work/application-libraries/clickhouse-base-tables-plan.md).
