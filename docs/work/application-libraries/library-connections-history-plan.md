# Library-owned connections and ClickHouse history

Owner authorizes implementation: library owns binding/protocol/purpose; SDKU
applications select only connection keys, retain own users/grants/ENV. ClickHouse
resource ID is history; default name is `{{ library_instance_id | replace('-', '_') }}`.
Use underscore, not a literal backslash. No application installation, SQL/Kafka
writes or automatic working-project/resource-ID migration.

## Bounded implementation

- Extend existing application connections schema with a unique list of library
  connection keys. Legacy explicit maps remain valid. SDKU uses lists; library
  declares all used connections, including vault. No inferred service/selector.
  Library connections remains a map of complete declarations: constrain its
  existing application-schema reference with allOf/type:object (LCH-P01).
- Standard Ansible tasks reset/resolve the selected connection declarations from
  that library before resource contexts and ENV expand. Fail safely on a missing
  library key; legacy maps retain their exact declarations. The same derived map
  feeds rows, providers, resource contexts and legacy topic-role validation.
  No new Python script, Go resolver, persistence, lock or DTO.
- Existing UI reads selected keys and their library package declarations as a
  direct reference projection for its existing connection/account controls. It
  never merges Ansible values or resolves endpoints/topology. Missing references
  remain incomplete until Core validation; legacy map UI stays available.
- Extend existing resource_defaults.clickhouse with databases.<id>.name alongside
  unchanged file-only tables. Use include_vars library defaults after identity is
  bound so history.name templates evaluate for each library placement. Merge
  package -> library instance resource_defaults -> selected resource.parameters.
  Defaults alone create nothing. Reuse normalized resources/provider jobs and
  application_databases.<connection>.<id> context for ClickHouse.
- SDKU uses history for every ClickHouse account databaseRef/databaseAccess and
  JDBC ENV. Remove duplicate ClickHouse database_name parameters once unused.
  PostgreSQL/topic defaults and per-app users/grants stay unchanged. Keep existing
  table creation for every selected ClickHouse DB, standalone/replicated behavior.
- Reuse Resources UI for ClickHouse add-from-default, blank-name inheritance,
  override/clear reset and fresh Core preview. Template/table structure stays
  file-only. Update contracts/docs/design/example/catalog hashes and validator.
- Existing installed resource IDs/ownership are preserved: old projects can keep
  their IDs via account/ENV overrides; no automatic rename/adoption or SQL change.
  Library connection key clickhouse and provider binding analytics are distinct
  from database resource ID history; do not rename existing provider bindings.

## Checks and gates

One mandatory independent FULL PLAN and one FULL DIFF for the contract extension;
BLOCK stops for owner disposition; nonblocking clarifications do not trigger
automatic re-review. Current-tree RED OS native: list/legacy compatibility,
unknown key, provider/purpose/protocol preservation, per-library identity/template
evaluation, package/instance/resource precedence/reset, ClickHouse JDBC/account
name agreement and table projection unchanged. SDKU27 schemas/digests/26 renders
and native26; affected Go/frontend tests/build/lint. Real React/Wails connection/
account rendering and history select/override/reset/Save/reopen/Verify/fresh plan
on matching standard-published runtime, no Approve/Start. Record run/revision IDs,
existing context-loss limitations and cleanup; do not claim visual/SQL acceptance.
