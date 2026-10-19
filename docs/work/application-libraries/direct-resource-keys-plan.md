# Direct library resource keys

Owner approved replacing redundant topic role maps with direct logical resource
keys, and analogous PostgreSQL defaults. No application installation, Kafka/SQL
mutation, new lock, new Python script or automatic working-project migration.
Previous uncommitted ENV/ports/topic work is preserved.

## Contract and implementation

- Standard Ansible tasks merge selected resources with library resource_defaults:
  Kafka topics and PostgreSQL databases, keyed by resource ID. Package -> instance
  resource_defaults -> explicit resource.parameters, recursive combine. Defaults
  alone create nothing. Existing provider/account/job validation remains owner.
- Before app parameters/ENV expand, reset and build application_topics.<alias>
  and application_databases.<alias>, keyed directly by selected resource IDs on
  the same provider as that declared connection. Values expose resourceId/name.
  No role map or inference from ENV text. Missing requested key fails before plan;
  aliases/providers remain separated, context reset per placement. Same merged
  resources feed provider jobs and plan identity. No UI/Go name resolver.
- Keep old topicBindings lists/maps only for existing packages' legacy context
  and snapshot/runtime projection. Direct context is built first; legacy explicit
  bindings retain old behavior. Remove topicBindings from all SDKU app defaults.
  Explicit legacy bindings win on colliding direct keys; removing authored
  bindings restores direct key access. Migration removes old SDKU topicBindings.
  UI shows legacy controls only when defaults/authored settings declare them.
  New SDKU users select library resources and edit ENV through existing controls.
- Extend existing resource_defaults.postgresql.databases.<id> with name defaults
  only (current DB resource parameter). Use model:tn-scada, alarms_db:tn-scada-alarms,
  preferences:user-preferences. Preserve existing ef-backend isolation with
  ef-store:ef-store, rather than redirect it to model. Nothing applied to servers.
- PG application JDBC ENV uses application_databases.postgres.<id>.name; account
  databaseAccess/grants reuse the same existing databaseRef ID. Preserve own users
  and database-wide existing/future-object grant semantics. Do not infer primary
  JDBC database from a possibly multiple-entry grant list.
- Remove PG-only duplicate database_name parameters. Alarm-view's ClickHouse
  database_name remains independent; no ClickHouse binding change in this scope.
- Existing Resources UI adds PG DBs from declared default IDs, allows blank name
  for inheritance and explicit name override/reset. Show Core resolved resource
  name only on fresh revision/no draft; template/schema editors remain absent.
  Existing generic guarded writer stays node-free, preserves file-only defaults.
- Update schemas, canonical docs/design, sample resources and catalog digests;
  document explicit migration, preserve saved working project and historical
  evidence. No new desired-state store/DTO/API or filesystem lifecycle changes.

## Acceptance

Focused current-tree RED OS native tests: direct keys without topicBindings,
multiple aliases/providers/libraries/hosts, legacy compatibility, missing keys,
PG defaults/instance/resource precedence/reset, same JDBC/account/provider DB name,
existing grant semantics, no implicit resource creation. SDKU all package hashes/
schemas/rendering and native resolver, Go/vet and frontend tests/build/lint.
Real React/Wails resource Save/reopen/override/reset, Verify and fresh plan on
verified matching runtime. No Approve/Start/SQL/Kafka writes. Prior observed
Execution Node context loss must stay explicit if rebind is needed; do not claim
it fixed. Mandatory FULL PLAN then FULL DIFF for this revised public contract;
BLOCK stops for owner disposition, no automatic extra review cycles.
