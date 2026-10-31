# Portable project contract

### Package script execution location and failure diagnostics

`scripts[].run_on` defaults to `target`. `execution_node` runs a
`provider_prepare`, `connection_apply`, `account_apply` or v1alpha2 `integration_apply` script with
`execution: once` on the selected Core Execution Node. `target.connection`
still identifies the provider dependency. The working directory is the
invocation project root and the account is the Core process account.
No container context is injected; existing target execution is unchanged.

A failing script may return a JSON object (at most 2048 characters) with
`status: error` and numeric `step` (0–65535), `http_status` (0–599),
`curl_exit` (0–255). The runner captures stdout/stderr under `no_log`, then
publishes only these numeric fields and the process exit code through
`APPLICATION_SCRIPT_EXECUTION_FAILED` in the existing execution journal.
Raw output, response bodies and arbitrary error text are withheld. Invalid
output retains only the exit code. The journal/UI retain this safe diagnostic.

## Purpose

The portable project directory contains the single canonical user-owned desired
state shared by standalone Ansible, the future backend and the UI. Desired
state is ordinary inventory, `group_vars`, `host_vars` and role defaults. The
Installer edits those same files and invokes the same playbooks. An
Ansible-only user does not need to create or understand `project.yml`.

## Physical layout

Standalone Ansible projects may use ordinary variable files such as
`group_vars/all/platform.yml` and `host_vars/<host>.yml`. Installer-managed
projects use one fixed owned document per scope so readers and writers do not
guess Ansible file precedence:

```text
project/
  project.yml                         # optional compatibility/machine metadata
  inventory/
    hosts.yml
    group_vars/all/platform.yml       # user-owned desired state
    group_vars/all/platform-state.yml # optional standalone machine-owned state
    group_vars/<service-or-operator-group>.yml
    host_vars/<host>.yml
    group_vars/all/platform-installer.yml             # Installer-owned desired state
    host_vars/<host>/platform-installer.yml            # Installer-owned host placement
  ansible.cfg
```

For an Installer-managed field, the `platform-installer.yml` document is the
canonical input. A flat `host_vars/<host>.yml` is accepted by bounded Core
readers only as a standalone compatibility fallback when the managed document
does not exist. New Installer writes always use the managed directory form.
Readers must not recursively scan `host_vars` or independently invent another
precedence rule.

The contract covers the directory as a whole. Inventory declares desired
hosts; platform topology and policy live in ordinary variable documents;
service and host overrides use normal Ansible precedence. Optional
`project.yml` and `platform_generated_state` may carry machine-owned metadata,
generated identities, fingerprints and locks only.

The project execution configuration must keep `hash_behaviour = merge`.
This is a required Platform Installer convention: partial map values in
`group_vars` and `host_vars` recursively overlay role defaults.

## User-owned desired state

### TLS profile selection during Installer Save

For a deployment setting declared by the service catalogue as a managed
`TLS_PROFILE` reference, ordinary project Review/Save assigns the first
available project TLS profile in alphabetical ID order when the setting is
absent. The existing guarded writer persists that value in the deployment's
canonical `configuration`. This also applies when a profile is added after
the service. Existing authored selections remain unchanged; the operator may
select another profile through the same editor.

The selection uses local compatible catalogue metadata and requires no Core
request or Execution Node. An unavailable catalogue does not block unrelated
local Save. Save without any TLS profile remains structurally valid; Project
Verify reports `TLS_PROFILE_REQUIRED` for an unresolved TLS-profile setting.
This requirement applies to service modes declaring that reference. Verify
and Core preview never select or persist a profile. Role defaults declare an
empty string as an unset input instead of a particular profile name; explicit
authored values retain the usual validation. Standalone Docker/ClickHouse
roles retain their existing prepared TLS-directory input path.

`inventory/group_vars/all/platform.yml` owns logical desired state:

```yaml
platform_desired_state:
  serviceDeployments:
    kafka-main:
      serviceType: kafka
      mode: kraft-distributed
      configuration:
        quorumMode: dynamic
```

`definitionVersion` is catalog-owned metadata and is not configured by the
user in desired state. Older projects may still contain it for compatibility;
when present, it is validated against the catalog lock.

Two portable project-wide variables may be written beside
`platform_desired_state` in Installer-owned
`inventory/group_vars/all/platform-installer.yml`:

```yaml
platform_data_root_directory: /var/lib
platform_name_prefix: ''
```

The data root supplies the default data path for services only; explicit
deployment/member paths take precedence. It does not relocate application
data or Installer runtime state. An empty prefix creates service resource names without an added prefix. A
nonempty prefix is prepended to newly managed service resources and must match
`^[a-z][a-z0-9_]{0,23}$`. These variables remain ordinary Ansible inventory
input for standalone Core and are edited through project Review/Save in UI.

Inventory hosts own physical placement and member-scoped desired settings:

```yaml
all:
  hosts:
    node1:
      platform_deployments:
        kafka-main:
          members:
            kafka-1:
              roles: [broker, controller]
              configuration:
                nodeId: 1
```

Machine materialization writes only generated state, for example Kafka
`clusterId` and `directoryId`, under `platform_generated_state`. It must not
write service configuration, placement or secrets. The generated-state schema
enforces this boundary. In Installer-managed execution, that document is
machine-owned persistent Execution Node data at
`<execution-state-root>/projects/<projectIdentity>/generated/platform-state.yml`,
not part of the portable project or its ephemeral run workspace. Standalone
Ansible may continue to pass an explicit local generated-state path. See
`docs/work/execution/exec-generated-state.md`. `project.yml.desiredState` and legacy
`platform_project` are bounded readers for older projects: identical duplicate
input is deprecated, conflicting input is blocked, and new writers emit only
the Ansible-native shape.

## Identity model

Stable project keys are meaningful within a project and independent of local database row IDs.

- `serviceType` identifies a catalog capability, such as `postgresql`.
- `serviceDeployment` identifies one desired deployment, such as `accounting-db`.
- `member` identifies a member within that deployment, such as `database-1`.
- `host` identifies an intended target host.
- endpoint group and certificate scope have their own stable identities.

This supports multiple independent deployments of one type without duplicating service definitions.

## Catalog versus desired topology

The catalog answers “what can this Core install?” The project answers “what does this customer want installed?”

If PostgreSQL is in the catalog but absent from `serviceDeployments`, no PostgreSQL plan action, role invocation or resolved execution group is generated. If two PostgreSQL deployments exist, both are resolved independently using the same pinned definition. PostgreSQL scenarios remain conformance fixtures while Kafka KRaft is implemented first.

## Desired/discovered/resolved separation

Not stored in the portable desired project:

- CPU, memory and OS facts discovered from hosts;
- SSH reachability and sudo probe results;
- compatibility evaluation outcomes;
- generated execution groups and runtime variables;
- resolved ports, SAN lists or dependency DAG;
- active run state and logs;
- plaintext credentials.

These are separate snapshots or derived outputs tied to fingerprints.

Package-declared `SERVICE_PASSWORD` settings may opt into
`x-runtimeSecretRequired: true` (a saved reference is required before planning)
and `x-runtimeSecretDeploymentBound: true` (Core issues an opaque requirement
identity bound to deployment, logical manifest requirement and purpose).
Kafka admin uses both. Its logical `runtime:kafka-admin-password` reference
stays in desired configuration; plaintext stays only in the existing runtime
Broker/lease custody. Each deployment receives a separate protected file, even
when logical references match. Library provider hooks address its unambiguous
Core-issued runtime alias. No second secret transport or desired-state store
is introduced. The existing pre-Core dialog supports one deployment-bound
password setting per deployment; Kafka declares exactly one admin credential.

## Service deployments and modes

Modes are defined in the pinned service manifest. The project selects a mode but does not redefine its rules.

Examples:

- `postgresql/standalone` may require exactly one database member;
- `postgresql/patroni` may require a minimum member count and a DCS dependency;
- `postgresql/pg_auto_failover` may declare monitor and database roles.

Exact constraints belong to the production service package and are evaluated identically in standalone and Installer workflows.

## Placements

Every member has a stable identity and either:

- an explicit `host`; or
- an explicit placement constraint requesting deterministic planning.

The first production version should prefer explicit placement. Automatic placement can be added only with deterministic output, explanations and a rule that it never overwrites explicit operator intent.

## Endpoints

NET-01 has one desired endpoint assignment: an endpoint-capable service
deployment may set `endpointGroup`. `endpointGroups.<id>.address` owns one DNS
suffix and wildcard intent. The resolved FQDN is deterministic:
`<serviceDeploymentId>.<endpointGroup.address.domain>`. There is no
`endpointBindings`, alias, listener reference, port override or manually
authored FQDN. Endpoint-enabled deployment IDs must be valid lowercase DNS
labels.

`ResolvedServiceEndpoints` is a read-only DNS identity projection. A
Keepalived endpoint-provider deployment owns virtual addresses for its
`endpointGroupRef`; PKI may include those addresses when `includeEndpointVip`
is enabled. Neither projection nor EndpointGroup owns a VIP. Transport ports
and routing are deferred to NET-03. Kafka is not a
generic NET-01 endpoint consumer because its client reachability is governed
by package-owned named and advertised listeners.

HAProxy backend destinations are derived by Core from the service's
`endpointGroup`, matching Keepalived `endpointGroupRef` placements, and
same-group HAProxy placements on those hosts. All matching provider/host
pairs participate; partial VIP coverage does not block planning. Legacy
`haproxy.deploymentRef` remains readable but does not select a provider.
`haproxy.backend` overrides package-owned `x-haproxyBackendDefaults`; no
relation object is required to activate the derived integration. Missing
HAProxy produces a nonfatal Core error and skipped integration. Existing
source-owned publication and explicit full reconcile remain authoritative.

## Certificates

Certificate identity is resolved by explicit certificate scope and profile, not by creating one request per service instance. A scope aggregates selected host, endpoint and explicit sources. SANs are deduplicated and deterministically ordered.

Common Name selection is deterministic but SAN remains the primary identity:

1. first concrete endpoint FQDN;
2. first host DNS name;
3. first permitted wildcard;
4. explicit documented fallback.

## Dependencies

Dependencies reference deployments and declared capabilities/listeners rather than copied IP lists. The resolver builds a DAG, rejects missing/cyclic mandatory dependencies and passes resolved values to roles.

## Configuration sources

Effective role values are composed from distinct sources:

- `DEFAULT`: immutable service/role defaults;
- `OVERRIDE`: desired project configuration;
- `NODE`: placement-specific input;
- `COMPUTED`: deterministic resolver output;
- `RUNTIME`: ephemeral execution values;
- `SECRET`: runtime-only secret material.

The project stores only supported desired overrides and references. It does not copy every default.
Deployment configuration applies to the logical deployment; member
configuration applies to one logical member and is never converted into
`host_vars`. A physical host may contain multiple members, including members
from different deployments. Service-package mappings declare which settings
permit the member scope.

## Versioning and migration

Application libraries opt into desired state v3alpha1 through ordinary group vars:
`platform_desired_state_contract: platform.installer/project-desired-state/v3alpha1`.
`platform_desired_state.applicationLibraryDeployments` references exact local
`application-packages/<name>/<version>` and `library-packages/<name>/<version>`;
their manifest file allowlists and content digests participate in project revision.
An application manifest may list a directory with a trailing `/` (for example,
`assets/providers/`). Core expands that entry to its files, hashes each relative
path and content, and requires the resulting set to match the package contents.
Application settings may declare `config_directories` with a source directory,
target destination, file mode and directory mode, or `config_archives` with an
allowlisted `tar.gz` source and target destination. The archive contains one
top-level directory named after the destination's final path component. Both
forms produce read-only directory mounts. Apply reconciles changed directory
members and removes stale members; archive extraction is staged and replaced
when its source digest changes. Verify requires the declared directory mounts.
Archive reconciliation trusts a machine-owned digest marker for an unchanged
archive; Verify checks that the mounted directory exists but does not hash every
extracted file. External edits inside the extracted directory are outside this
bounded repeat-Apply check.
Package manifests may also declare allowlisted executable `scripts` with a
`before_start` or `after_ready` phase and `each_target` or deterministic `once`
placement. `argv` contains literals or resolved nonsecret references; runtime
secrets are declared separately as `secretInputs`. The generic target runner
receives only the script file, account, working directory, argv and private
secret files. Source inputs are checked for readable nonempty file availability,
without size, runtime-root, symlink, owner or mode restrictions. Runtime copies
remain private, are never logged and are removed after invocation.
Package-specific behavior belongs inside the package script.

Package manifest `platform.installer/application-package/v1alpha2` adds
`integration_apply` and the nonsecret JSON argument source `integration_consumers`.
The old v1alpha1 enums remain closed. The new phase runs at the declaring
library's boundary, after its ordinary lifecycle when selected, and before
the next library. Target scripts use the declaring application's placements;
Execution Node scripts use `execution: once`. The argument contains selected
consumer IDs, connection aliases, endpoint/parameter placements and public URLs;
it contains no accounts, credentials or runtime environment.

Infrastructure selection follows the same invocation-only ownership:
`skipServiceDeployments` contains deployment IDs, never service types or hosts.
Request v1alpha8, plan v1alpha11 and manifest v1alpha8 bind the sorted selection
and Core-derived `serviceExecutionScope` to approval and fresh Start. The complete
snapshot remains authoritative for validation, connections and provider jobs.
For a partial selection, skipped deployments have neither SERVICE_APPLY nor
SERVICE_VERIFY, own installation artifacts/inputs/outputs or own PKI delivery.
The full infrastructure SERVICE_PASSWORD credential set remains required, as in
skipInfrastructureVerify. Selected consumers retain resource/account reconciliation,
Vault/Agent delivery and endpoint integration. Integration writes may still modify
an existing provider. Skipping asserts neither readiness nor Verify success.
When all infrastructure checkboxes are cleared, UI uses the established
APPLICATION_LIBRARIES_ONLY + skipInfrastructureVerify path, rather than another
all-infrastructure execution mode. A skipped Vault cannot supply
CURRENT_RUN_BOOTSTRAP; its consumers use the existing runtime token input.
Selection is not saved in portable project YAML. Changing it requires a fresh
plan and approval. A runtime without ServiceSelection/v1alpha1 refuses partial
selection before image preparation or plan staging.

`skipApplicationLibraries` is an invocation-only list of library instance IDs,
not a portable desired-state setting. Request v1alpha7, plan v1alpha8 and
execution manifest v1alpha6 bind it and the Core-derived execution scope.
The complete project and library order remain authoritative for validation and
provider resolution. Skipped libraries have no installation images, own resource
or account writes, own Vault/Agent/PKI delivery, lifecycle, endpoint publication
or Verify. Declared callbacks for selected consumers and `integration_apply`
hooks may still use their providers. Provider API failures stop consumers;
skipping does not fabricate readiness or verification success. Existing objects
and routes are retained when a consumer is no longer selected.
Provider integration hooks may declare integer `order` (default 0). They run in
ascending order before the provider's account batch; equal values retain the
library-before-instance, stable identity ordering. This allows one library hook
to prepare objects before instance hooks and another to assign references after
those instance hooks, without product-specific phases or runner behavior.
A provided connection may declare `connection_provisioner: {apply_script: <id>}`.
The referenced allowlisted script belongs to the provider application package,
has `phase: connection_apply` and `execution: once`, and is a callback rather
than a normal startup script. For every resolved enabled consumer connection,
Apply resolves one invocation using the consumer's identity, settings parameters
and current endpoint; `provided_connection` references use the provider library.
The callback joins the same ordered provider batch before accounts. Its source
and execution target come from the selected provider, without consumer wrapper
scripts. `secretInputs` may reference a consumer `secret_binding` by `binding`;
an explicitly optional absent binding supplies no input. Credential values are
still delivered only through the existing protected files. Verify is unchanged.
Package manifest v1alpha4 adds opt-in `batch: true` only for `provider_prepare`
and `connection_apply`, with `execution: once`. Older schemas remain closed.
Within one ready provider batch, only adjacent hooks with the same script ID,
allowlisted source digest, order, target, execution location and exact secret
references share an invocation. Original argument arrays retain their order in
a private JSON input at `PLATFORM_SCRIPT_BATCH_FILE`; a batch script receives
no command-line arguments. Singleton opt-ins receive a one-element array.
The generic runner supplies only this file and the usual secret-file paths;
product-specific authentication and operation dispatch remain inside the script.
The timeout is 300 seconds times the original invocation count. Failure stops
later operations; this is not an atomic transaction. Dependencies are derived
before grouping, and accounts/Vault delivery wait for the complete batch.
Each invocation restores directory ownership and uses the ordinary idempotent
builtin copy for its allowlisted source; script source readiness is not cached.
Secret inputs are freshly copied and cleaned
for every invocation, including failure; batch input also uses this cleanup.

Slots in every library package may specify `start_priority` (default 100); Apply orders selected
logical instances by this value and then by instance ID, completing each
instance's readiness and after-ready scripts before starting the next.
Managed PostgreSQL database resources may declare `restore_on_create` with an
allowlisted custom-format dump and exact digest. The provider restores it only
when first creating that managed database; a partially restored, unmarked
database blocks automatic retry rather than being silently overwritten.
Host membership is `platform_application_libraries.<library-id>` in host_vars.
Ansible resolves namespaces/defaults/overrides before Core validates the derived
rows. No project.yml is required. Infrastructure-only projects retain v2alpha1
desired-state validation and v1alpha1 snapshots without application packages.
Applications produce snapshot v2alpha1. A7/A8 extend the execution planner with
application-aware planning and the mixed execution barrier; the original A1
rejection is historical, not a current restriction.
Library packages may declare `instance_id_strategy: application-name`; Core then
uses the application's package name as its `instanceId` in the endpoint,
Compose and execution projections. The omitted/default `qualified` strategy
continues to use `<application-name>-<library-id>`. IDs must be unique across
selected libraries. SZI selects `application-name` because a project has one
SZI library deployment.
See [A1 implementation notes](work/application-libraries/milestones/a1/evidence/a1-test-journal.md).

### File-only ClickHouse base tables

Library defaults files may declare `platform_library_definition.resource_defaults.clickhouse.tables`.
The same `resource_defaults` subtree on a library deployment in group_vars is a
file-only override. Ansible recursively merges maps and replaces lists. It is
separate from application common defaults and is not inherited into application
ENV or configuration. UI exposes no schema editor and preserves this subtree
when saving unrelated library/resource edits.

SDKU declares records and alarm_message with ordered columns, codecs/indexes,
keys and explicit table settings. Every selected ClickHouse database receives
this set, including existing-mode databases and resources unreferenced by accounts.
Standalone uses MergeTree/ReplacingMergeTree; raft-ha uses their Replicated
counterparts through the selected provider's cluster. Core projects tables and
Keeper paths by project/deployment/database/table before execution. Changes to
defaults or overrides participate in the saved revision and plan fingerprint.

Capability `service.clickhouse.table` is required. Existing databases retain
their ownership/mode; table creation is an explicit child-resource operation.
Only missing tables are created. Verify is read-only on every replica and reports
structural drift; no automatic ALTER, DROP, migration or application opt-in.
See the [plan](work/application-libraries/clickhouse-base-tables-plan.md).

### Kafka topic resources

A library resource may declare `kind: kafka.topic`, a Kafka `binding`,
`mode: managed|existing` and `parameters: {name, partitions?, replication_factor?, config?}`.
Partitions default to 1. Core derives automatic replication from the selected
deployment: standalone RF/minISR are 1/1; distributed RF is min(3, broker members),
minISR is min(2, effective RF). Controller-only members do not count. Explicit
values override these defaults; `config.min.insync.replicas` is the minISR setting.
Other Kafka topic properties are passed as scalar strings. minISR above RF is
reported as a warning, not rejected as policy.

Library `resource_defaults.kafka.topics.<resourceId>` supplies Kafka parameter
defaults. The same subtree in library instance group_vars overrides the package;
`resources.<resourceId>.parameters` overrides both (recursive config merge).
Only selected `resources` are created. Defaults alone create nothing. Effective
RF/minISR are calculated after merging against the selected deployment.

Application defaults or instance `overrides.topicBindings` map declared Kafka
connection aliases to named roles, e.g. `kafka: {main: events}`. Values are library
resource IDs; Core requires the same Kafka provider. Before parameters/ENV expand,
Ansible exposes `application_topics.kafka.main.resourceId` and `.name`. ENV can
use `MAIN_TOPIC: '{{ application_topics.kafka.main.name }}'`. Snapshot/runtime
`topics.kafka.main` contains the complete resolved topic. No startup lookup or
ACL is introduced. An empty role value is a saveable incomplete draft but Core
rejects it before execution; removing a role override restores its default.

Legacy alias-to-array bindings remain supported with their list projection.
An empty array selects none. Lists do not rewrite ENV automatically. Existing
projects are never silently migrated to roles. Use a matching Core runtime for
new role/default declarations; local structural Save does not prove resolution.

Managed topics are created only when missing. Matching existing topics are reused;
existing mode requires their presence. Requested partition/replica counts and effective
properties must match. This contract does not alter, reassign or delete topics.
Physical provider/name conflicts are resolved before resource mutations. Kafka
packages must declare `service.kafka.topic`; older Core schemas reject this kind.
Use a matching published runtime rather than expecting an older runtime to omit it.

### Application account database access

The existing account contract accepts PostgreSQL `databaseAccess`, an array of
`{databaseRef, privileges, additionalCreatorRoles?}`. Each databaseRef selects a
managed library resource on the account's provider. Privileges are SELECT,
INSERT, UPDATE, DELETE and CREATE. CREATE grants object creation inside the user schemas of that managed database, including future schemas created by approved creator roles. It grants neither database-level CREATE (schema creation) nor CREATE DATABASE, membership or ownership. Removing CREATE revokes its direct/default schema grants and preserves existing objects and owner authority. Older runtimes reject CREATE before execution; use a newly published matching bundle. One managed account/credential is retained across
all entries. An empty array removes managed object access without deleting the
account, database or data; normal PUBLIC CONNECT/TEMPORARY are unchanged.

An account declaration cannot contain both databaseAccess and legacy
databaseRef/grants. Core makes the grant-policy alternatives atomic after the
ordinary Ansible combine, in the same existing layer order. An explicit new
policy replaces inherited legacy policy, not inherited credentials. Reset
restores the package policy. There is no automatic legacy-access broadening.
The UI requires confirmation and ordinary Review/Save for this switch.

The PostgreSQL provider requires capability `service.postgresql.database-access`.
All existing user schemas/tables/sequences are reconciled in bounded SQL batches;
database-wide default privileges cover future schemas/tables/sequences created
by the library owner and explicitly listed, validated same-library creator roles.
Member roles must actually SET ROLE when creating objects. Unknown future roles
are not covered. INSERT implies sequence USAGE, not sequence UPDATE/setval.
System schemas, foreign ownership, PUBLIC DML, membership and unsupported grants
retain their conflict guards. Per the owner decision, the app account may itself
own objects/be a creator: its ownership/implicit grant authority is preserved,
and deleting DML access does not claim to remove that owner authority. No
ownership transfer or elevated role attributes are performed by this feature.

ClickHouse retains its existing grants format, supporting databaseRef plus
tables `['*']` and SELECT/INSERT, with optional CREATE TABLE in defaults/group_vars
for applications that initialize tables. The UI grants access on the selected database's
`database.*`, covering existing and future objects without requiring individual
tables to exist when grants are applied. For managed accounts, these direct privileges
in the same library's managed databases are authoritative. The existing
UUID/marker witness must verify both account and every database before a
calculated REVOKE. Foreign database grants, roles, grant option, column grants
and partial revokes remain conflicts, never cleanup candidates. Observed grants
for other accounts are untouched. Verify is readonly and refuses any remaining
delta. Existing accounts retain their prior non-mutating policy. Redis/Sentinel
use the same structured commands/keys/channels ACL contract. The operator's
ordered command/subcommand and +@category/-@category rules in defaults/group_vars define permission
policy, including administrative commands. Core and the standalone module have
no command allowlist/denylist. They validate bounded typed syntax; key/channel
patterns are literal data prefixed by the existing RESP writer. Bare commands
and categories are additive shorthand. Redis metadata defines categories;
Core preserves command order and duplicates. Owned managed accounts reconcile
command permissions, including exclusions; existing accounts and Verify are
readonly. Identity/password and key/channel custody retain their existing rules.
Raw account/password control tokens are outside the command-rule format.

Vault paths and stored username/password fields are unchanged. Application
variables use existing secret_bindings; runtime values use only the existing
lease, never project data. See the [access plan](work/application-libraries/milestones/c/secrets-access-technical-plan.md)
and [journal](work/application-libraries/milestones/c/evidence/secrets-access-journal.md)
for current implementation acceptance; this contract is not a QA PASS claim.

B2 adds bounded local library edits through the existing structural writer and
explicit data-only package import. Package bytes participate in local revision and
portable export. Save remains local and does not prove Core validity or admission.
See the [B2 writer contract](contracts/application-library-writer.md) and additive
[project-edit v1alpha11](../contracts/project-edit/v1alpha11/schema.json).

For legacy standalone A2 projects, the existing `platform_artifact_lock` carries the typed
`x-container-images` extension described by artifact-source/v1alpha2. It is not
a separate desired-state lock file. Each image records its config/image digest,
platform and optional registry platform-manifest and offline archive descriptors;
these digests identify different objects. The internal delivery reference is derived
from the full image ID; a supplied `localReference` must equal that reference.
Compose preserves the original settings.image exactly. Standard Docker tasks tag
the verified imageId with that reference and verify it before startup; container
Verify still checks the actual imageId. Supported managed execution is sequential.
Node-approved compatible registry delivery wins; selected offline fallback bytes
are verified only when fallback is needed. An unused archive need not exist.
Rendered files, ownership/config labels and Docker observations are derived state.
Standalone A2 entrypoints remain independently usable. Their existence does not
authorize Installer execution, which requires the current versioned Core plan,
approval and Start contract. See
[fixture contract](../examples/valid/application-runtime/README.md).

New image selection uses application `defaults.image` and the ordinary instance
override only. Operators do not enter imageId, archive digest or size. The bundle
builder indexes Docker-save inputs in manifest `containerImages`; `archiveRef`
points to the existing component record, which owns archive SHA-256 and size.
Registry metadata is prepared by Ansible on the selected target nodes before the
target-free deployment planner. The resulting per-placement image authority is
derived private plan state, never a new project lock or an application default.
Legacy image locks remain pinned and are not rewritten automatically.

Library `registry_credentials` maps a registry host[:port] to username/password
`runtime_secret_ref` descriptors. Only references are saved; values use the
existing runtime session and request-scoped preparation lease. An explicit pair
is required when assigned. Otherwise existing node Docker credentials or anonymous
access remain available. Target TLS/auth/transport failures block preparation;
an absent compatible registry image may use an indexed offline image. Apply and
Verify reuse the selected identity and a private transient Docker configuration.
Preparation does not authorize execution. Fresh Build/Approve/Start remain
mandatory. See the [implementation plan](work/application-libraries/application-image-metadata-plan.md).

## Server type metadata

An inventory host may carry one stable descriptive type ID as
`platform_host.type`. The field is optional when reading historical projects;
it is required when a new server is created by current Installer edit sessions.
The portable schema validates only lowercase bounded identifier grammar. The
selectable list and localized labels belong to versioned Installer application
configuration and are not copied into the project.

A grammar-valid type absent from the local application configuration remains
portable and readable. It is preserved until explicitly changed and may
produce only a local presentation warning. Server type is separate from host
identity and has no implicit effect on services, topology, placement,
Execution Node selection, package or artifact-source selection.

## Versioning and migration

- Published schemas version portable machine state and resolved projections.
- Every service deployment pins a compatible service-definition version through the catalog lock.
- Plans pin project, catalog, artifact and Core fingerprints.
- Readers reject unknown major versions safely.
- Migrations are explicit, deterministic and preserve an original backup.
- Import/export round trips preserve supported fields and unknown extension fields according to a documented policy. Export names the copied project's `metadata.name` after the export directory name; source files and project ID remain unchanged. Only the copied optional `project.yml` may have normalized formatting, with unsupported YAML references/ambiguous documents rejected as described in [UI-01I](work/ui-01/ui-01i-architecture.md).
- No silent semantic migration occurs during apply.

## Required invariants

- all references resolve;
- keys are unique in their scope;
- each member placement targets a declared host;
- member roles are supported by the chosen mode;
- endpoint listeners exist in the service definition;
- host ports, VIPs, VRIDs and DNS identities do not conflict;
- dependencies form a valid DAG;
- required secret references exist without exposing values;
- catalog and artifacts satisfy their locks;
- generated projections are deterministic.

## SDKU deployment correction: library connections and paths

Library definitions may declare shared connections using the application connection
shape and existing bindings/connection_defaults. Core resolves a library-wide
projection for base Compose; application-specific connections remain separate.
Schema Registry uses purpose schema-registry and HTTPS, with all eligible broker
members and actual Registry member ports from the existing provider projection.

Library runtime_directory belongs to package defaults and the library deployment
in group_vars. Its default is ~/<library instance ID>; target Ansible expands ~
against the selected Docker account HOME. A deployment empty value resets to the
package default. Files are <library-root>/.base_compose.yml and
<library-root>/<app-instance>/{compose.yml,config,vault,pki}; Apply/Verify/Vault use
one placement. Existing ownership/symlink checks remain; old paths are never
automatically moved or deleted.

Application PKI delivery uses the library's selected PKI profile and the existing
host materialization plan, independently of Vault Agent or a keystore-password
secret binding. The private instance `pki` directory receives `certificate.pem`,
`private-key.pem`, `ca-chain.pem`, `keystore.p12` and `truststore.p12` for the actual
rootless container UID/GID, with directory mode0700 and file mode0600. Existing
byte-identical files are unchanged on repeat Apply. Vault identity files are
delivered only for Agent applications. The existing required Agent PKI directory
bind remains `/opt/application/pki:ro`; non-Agent package templates declare their
own needed PKI mounts and do not acquire a new mandatory mount.

Original-tag preservation applies to tagged references, including uppercase tags.
Existing @sha256 inputs retain their immutable local startup alias: Docker cannot
assign a RepoDigest using docker tag, and offline loads need not retain it.

### Direct library resource keys

Standard Ansible tasks merge library package resource_defaults, instance
resource_defaults and explicit selected resource.parameters, in that order.
Kafka uses resource_defaults.kafka.topics; PostgreSQL uses
resource_defaults.postgresql.databases. Defaults alone select/create nothing.
Before parameters and ENV expand, each placement receives
application_topics.<connection>.<resourceId>.name and
application_databases.<connection>.<resourceId>.name (plus resourceId).
Only selected resources of the matching kind on that connection's provider are
exposed; contexts reset per placement. Missing keys fail instead of falling back.
The same merged resources feed provider jobs and plan identities. PostgreSQL
account databaseAccess.databaseRef remains the resource ID, sharing the JDBC
name without an additional binding map. PostgreSQL database names allow hyphens;
existing identifier, ownership and SQL quoting checks remain.

SDKU uses direct keys without topicBindings. Legacy topicBindings lists/maps
remain supported; explicit legacy maps overwrite colliding direct keys. Removing
those maps restores direct access. Migration must remove old authored SDKU maps.
Resource IDs are unique across kinds: SDKU Kafka alarms and PostgreSQL alarms_db
are distinct. PostgreSQL ef-store retains its own database. No UI/Go resolver or
second desired-state store is introduced.

### Library-owned connection declarations and ClickHouse history

Applications may select a unique list of library connection keys, e.g.
connections: [clickhouse, kafka, redis, vault]. Library connections remains a map
of full library_binding/protocol/purpose declarations. Old application declaration
maps remain supported. Standard Ansible tasks validate keys and resolve one map
before resource contexts and parameters/ENV; providers and accounts reuse it.
Accounts, usernames, privileges and ENV remain application-owned. No per-app
connection inference from credentials/ENV or independent UI/Go resolver is added.

resource_defaults.clickhouse.databases.history.name defaults to
{{ library_instance_id | replace('-', '_') }}. It is resolved on the Execution
Node after binding the current library identity. Library instance resource_defaults
in group_vars overrides the package; selected resource.parameters overrides both.
Defaults alone create nothing. ClickHouse JDBC and account databaseRef use history,
ENV reads application_databases.clickhouse.history.name. The same normalized DB
name feeds provider jobs; existing table templates, grants and standalone/cluster
engine selection are unchanged. Tables are created for selected ClickHouse DBs.

Resources supports selecting history from defaults, explicit name/clear-reset and
fresh-only Core name display. UI never evaluates the default expression. Existing
installed resource IDs/ownership must be preserved via account/ENV/name overrides;
key changes do not migrate/adopt installed objects. No automatic project migration.


Redis name references use resource_defaults.redis.keys and redis.key selections;
shared ENV and app grants read the normalized library_resources map. Redis data
lifecycle is excluded; existing account ACL jobs are unchanged. See
[Redis key bindings](work/application-libraries/configuration.md#redis-key-name-bindings)
for precedence, isolated evaluation order and template variables.
