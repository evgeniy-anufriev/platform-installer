# Standalone Ansible Core

PKI wildcard SANs and endpoint wildcard DNS records have independent policies.
`platform_pki_policy_defaults.sanPolicy.includeEndpointWildcard` defaults to
`true`: certificates include `*.domain` for their resolved endpoint groups even
when `endpointGroups.<id>.address.wildcard` is `false`. A certificate profile
may explicitly set `sanPolicy.includeEndpointWildcard: false` to disable these
SANs. The endpoint flag controls DNS wildcard publication only.

## Ansible task names

Operator-visible play, task, block and handler names use Russian action nouns:
«Проверка наличия каталога», «Создание учётной записи», «Перезапуск PostgreSQL».
Use the concrete object and only conditions that distinguish the action or a
required safety check. The same rule applies to compound stage titles:
«Этап A — подготовка и проверка конфигураций».

Describe the actual operation: assertions are «Проверка», service restarts are
«Перезапуск», service configuration reloads are «Перечитывание конфигурации»,
and systemd `daemon_reload` is «Перечитывание unit-файлов systemd». Prefer
«Подготовка файлов», «Формирование конфигурации», «Расчёт параметров» and
«Защищённый каталог» over literal translations such as «материализация байтов»,
«отрисовка», «разрешение параметров» and «частный каталог». Retain precise
technical terms, including Kafka topics/partitions, TLS, PKI, ACL and principal.
Keep `notify`, `listen`, failed-task comparisons and test selectors synchronized
when renaming a task or handler; resource names and execution logic are unchanged.

## Product contract

Ansible Core must be installable and usable without Platform Installer. A Linux operator must be able to take a portable Ansible project and offline bundle and run the complete lifecycle with standard `ansible-playbook` commands.

The lifecycle is:

```text
inspect -> validate -> plan -> apply -> verify -> result
```

`apply` requires an exact validated plan fingerprint or generates and confirms it within one controlled standalone session. It may not silently execute a different intent.

Owner decision 2026-10-26: ordinary infrastructure service `verify` is a
read-only health check, analogous to application readiness. It checks the
configured protocol, TLS trust and authentication where enabled, and required
cluster participants/quorum. File/configuration drift and resource/ACL audits
belong to Apply reconciliation or explicit provider diagnostics, not ordinary
service Verify. `pki-resolve.yml` reconstructs the runtime PKI projection without
auditing target files; explicit `pki-verify.yml` remains available. This does not
change target-free project validation or explicit application-provider Verify.
BIND and HAProxy retain their existing configuration checks by owner decision.

Service entrypoints use `playbooks/validate-infrastructure.yml` for their
infrastructure prerequisites. It shares input preparation and the existing
validator with full `validate.yml`, but does not resolve application packages
or consume application findings. Its default artifact is
`infrastructure-validation-result.json`. It is not full Project Verify and
never authorizes a plan or Start; the full project Validate/Plan admission is
unchanged. Both native inventory and compatibility metadata keep the same
precedence/conflict checks. Full and infrastructure validation results remain
separate even when invoked in one Ansible process.

Infrastructure endpoint publication resolves the selected service directly;
it does not pre-resolve all application packages. Full HAProxy reconciliation
and mixed/application partial scopes still resolve application sources. No
empty marker is published that could suppress a later application fallback.
Endpoint publication remains after provider readiness and before consumers.

Artifact source probing batches requirement names in one node-local DNF query;
each requirement still passes the original exact name/version/architecture/OS
filter and repository-then-offline policy. A failed batch retains per-name
queries. It neither enables repositories nor caches source decisions across runs.

## Proposed distribution layout

```text
platform-ansible-core/
  ansible_collections/platform/installer/
    plugins/
      callback/
      inventory/
      modules/
    roles/
      common_prerequisites/
      target_preparation/
      <production-service>/
    playbooks/
      discover.yml
      plan.yml
      deploy.yml
      verify.yml
  catalog/
    services/<type>/manifest.yml
    services/<type>/schema.json
    compatibility/
  schemas/
    project-v1.schema.json
    plan-v1.schema.json
    event-v1.schema.json
    result-v1.schema.json
  artifacts/
    manifest.yml
  examples/
  docs/
```

This is a design target, not yet an implemented tree. Packaging may refine it without changing contracts.

## Service package

Each service type is a cohesive, versioned package:

- manifest with identity, modes and capabilities;
- configuration schema and safe defaults;
- topology constraints;
- declared listeners and dependency kinds;
- role entry points;
- validation and verification contract;
- offline artifacts and compatibility declarations;
- standalone fixtures and integration tests.

A service manifest describes capability, not project intent. A project can instantiate the service type zero, one or many times.

## Role contract

`platform.core.resolve_application_libraries` is the A1 controller-only library
resolver. Project snapshot/validate entrypoints call it only when application
deployments are declared. It loads validated package defaults using ordinary
Ansible include_vars in independent namespaces and uses built-in recursive combine
with list replacement for composition; Python does not evaluate Jinja or recreate
inventory precedence. Package templates are trusted operator-authored executable
inputs. A1 validates/fingerprints their closure but does not render them or execute
application tasks. See [standalone fixture](../examples/valid/application-libraries/README.md).

A2 adds explicit standalone `applications/apply.yml` and
`applications/verify.yml` entrypoints. They reuse that resolver and the
selected rootless Docker account; template rendering remains native Ansible.
Application orchestration lives under `ansible-core/playbooks/applications/`:
the top-level Apply/Verify/post-install entrypoints, `images/` for preparation,
`stages/` for imported playbooks and `tasks/` for included task lists. See the
[workflow layout and standalone invocation](../ansible-core/playbooks/applications/README.md).
These paths replace the former root-level `application-*.yml` files; ordinary
inventory and the Core/Go protocol are unchanged.
All selected placements pass preflight before materialization. Each library/host
has a shared `.env` and base Compose; per-instance Compose/config files use
validated package render descriptors. Source configs are read once on the Execution
Node with their SHA-256 computed from the returned bytes; final symlinks,
nonregular files and observed in-read mutations are rejected. Source content stays
under `no_log` and passes the existing secret-content validation. Overlap checks
compare unique paths of other libraries on the same host, preserving case.
Apply uses native Compose and a generated
config-digest ownership label to recover an interrupted configuration activation.
If ordinary Compose startup fails, Ansible handles the failure with `rescue`
and makes one `up --force-recreate` attempt for that exact instance. Both attempts
disable pulls, builds and dependency startup. Failed recreation stops Apply;
successful startup continues through the existing readiness check. Persistent
volumes and bind-mounted data are not removed.
Ordinary Verify uses one container inspect task per placement for locked image
identity, project/library/instance/host ownership, Running and configured
healthcheck. It does not inspect file/config digests or Compose hashes, and its
standalone entrypoint skips target/source preflight. It never starts or loads
containers. A3/A4 add PostgreSQL library resources/accounts, protected Vault
secret publication and container Agent/PKI materialization. A5 extends the same
provider jobs with Redis/Sentinel ACLs and ClickHouse databases/accounts.
Owner clarification 2026-10-21: library Verify checks container identity,
Running/configured healthcheck and endpoint availability; it does not repeat
provider resource/account/ACL or Vault AppRole/secret checks. Apply retains its
preflight/provider checks; container activation does not repeat AppRole login
and secret reads after readiness. The runtime role's
`application_runtime_verify_vault` defaults to true for direct Verify use;
container activation and the library Verify entrypoint set it to false. Explicit standalone provider
Verify tasks remain available for resource audits.
Kafka library topic/account hooks run only in Apply, without a preceding Kafka
live preflight or observation cache. Metadata, application authentication and
ACL inventory are checked before instance credential publication and startup;
conflicts may be detected after library resources have already been created.
Kafka account Apply and explicit provider Verify consume the existing
deployment-level provider jobs: one shared SCRAM metadata read and ACL list,
with exact principal/resource selection and separate per-account authentication.
Library target preflight selects image sources per placement; its final
Execution Node barrier verifies each unique full selected offline archive record
once before Vault/provider mutations. Existing manifest/component/digest/size/
symlink checks remain, repository-selected fallback bytes are not read, direct
role preflight still validates immediately by default, and target archive copies
remain independently checked before Docker load. No cross-run verification cache.
ClickHouse capability `service.clickhouse.table` adds file-only library table specs
to every selected database job. Ansible owns merge/rendering; the existing protected
native module checks metadata, creates missing tables and verifies all members.
Database ownership is persisted before table writes so partial creation can retry.
See [file-only table contract](project-contract.md#file-only-clickhouse-base-tables).

The SZI stage introduces a generic package script runner. The package declares
phase, placement, file, nonsecret argv and runtime secret references; Core
resolves those references without product-specific branches. Ansible copies
the allowlisted script to the target, stages mode-0600 secret files for the
selected account, executes exact argv with a timeout, validates a small JSON
result and removes transient secrets. Source inputs need only be readable,
nonempty files; no size, runtime-root, symlink, ownership or mode guards apply
to them. The target copies still use private permissions and no-log tasks.
Docker and Keycloak commands live in the
Keycloak package scripts. Application Apply completes shared providers first,
then runs materialization, image delivery, before-start scripts, activation,
after-ready scripts and Verify for each library in its explicit plan order.
New installation plans do not append a separate global application Verify
operation. They proceed from library Apply (including per-library health checks)
to optional post-install actions. Saved Apply/Verify manifests and the explicit
standalone Verify playbook remain supported.
The check at each library boundary calls `verify_container`: exact image/labels,
Running and configured healthcheck only. It does not repeat configuration-tree
or Vault identity/AppRole/secret-read checks. The standalone Verify entrypoint
retains its existing behavior.
Within a library, selected slots run by optional package `start_priority`
(default 100), then instance ID; each instance finishes its after-ready phase
before the next starts.
Direct multi-library Apply also requires an explicit order. PostgreSQL's
managed `restore_on_create` is part of the existing provider stage.

Invocation `platform_application_skip_libraries` selects library instance IDs
to omit from installation while preserving their provider definitions. Planned
execution supplies the same derived `platform_application_execution_scope` and
checks it against fresh native resolution. Resource/account and Vault write jobs,
runtime materialization, images and Verify contain only installed consumers.
Provider callbacks use minimal script contexts without Docker preflight.
At a skipped provider's library boundary the existing ordered integration and
account batches execute, followed by ordinary dependent Vault/Agent delivery.
Package v1alpha2 `integration_apply` hooks run on their declaring placements
before the next library, through the unchanged generic script runner.

Kafka library resources reuse these stages with capability `service.kafka.topic`.
Core projects topic defaults from the selected deployment's mode and broker members;
the Kafka role uses builtin command/template/assert tasks and its installed CLI.
Kafka topic/account preflight is omitted from the standard library pipeline.
Apply reads each declared topic batch once and its
effective configs once, then creates only missing managed topics. Successful creation does not trigger another describe/config read; CLI errors still fail Apply. ACL inventory is read once per deployment invocation. Missing ACL writes are grouped per account only for identical resource types, patterns and missing operations; resources are passed as repeated CLI selectors. A failed group stops Apply; a subsequent Apply reads fresh state and resumes the remaining delta. This batching is not atomic. Existing
resources and explicit provider Verify are read-only. Mismatching counts or
requested effective properties fail without altering topics. Temporary client
properties use mode 0600 and always cleanup; raw CLI output is suppressed and
separate diagnostics expose only provider/topic, address, timeout and safe codes.
See [topic contract](project-contract.md#kafka-topic-resources) and
[plan](work/application-libraries/kafka-topics-plan.md).

Library `resource_defaults.kafka.topics` supplies parameters for explicitly
selected resource IDs before RF/minISR calculation. Standard resolver tasks
merge package/instance/resource values and bind `application_topics.<alias>.<role>`
before application parameters/ENV expand. The same normalized resources feed
provider jobs. Named role maps and legacy list bindings keep their corresponding
snapshot/runtime shapes; missing/cleared/wrong-provider roles cannot execute.
Logical resource IDs let shared applications consume each library's physical
names. See [role/default plan](work/application-libraries/topic-role-bindings-plan.md).

Each library resource scope precedes logical instance account/grant scopes and
Vault publication. HA ClickHouse user/grant writes use one ON CLUSTER default
batch per logical instance, followed by per-server result/login verification.
Shared protected credential files use `platform_application_secret_root`; the
old PostgreSQL root is accepted at standalone Core entrypoints as a compatibility
alias, and conflicting nonempty roots fail. See
[A5 plan/evidence](work/application-libraries/milestones/a5/evidence/a5-test-journal.md),
[runtime fixture](../examples/valid/application-runtime/README.md) and
[A2 evidence](work/application-libraries/milestones/a2/evidence/a2-test-journal.md).

The account-access extension reuses these provider hooks. PostgreSQL's optional
databaseAccess policy batches grants/default privileges within each owned DB;
removed access stays in the hook's bounded reconciliation scope. An explicit
grant-policy switch is normalized after ordinary Ansible combine; no Go/UI
precedence resolver is added. Object owner authority is preserved when the
operator assigns ownership to the application account. ClickHouse managed
SELECT/INSERT/CREATE TABLE deltas are reconciled only for the witnessed account and its
library's witnessed managed DBs; cluster revokes/grants share the existing native
batch and per-server verification. Verify performs no grants or probe DDL.
The [canonical project contract](project-contract.md#application-account-database-access)
defines authority and compatibility; capability gating prevents stale runtimes
from silently ignoring the new PostgreSQL policy.

Public HTTPS endpoint verification retains its DNS, TLS and expected-status
policy, with bounded request retries after provider updates. Only the address,
expected/actual status, timeout and closed reason enter the existing HTTP
diagnostic event. Raw responses, headers, cookies and bodies remain private;
the Ansible display additionally reports attempts and omits URL query/fragment.

A7 adds target-free application descriptions to the existing machine plan and
runtime-secret descriptor entrypoints. Nonempty libraries use plan v1alpha4 and
descriptor v1alpha3; empty libraries preserve the infrastructure versions.
Requirements contain immutable image identities, policy and public secret refs;
repository probes and concrete image source selection remain execution-time.
Closed application operation descriptors select the existing standalone
Apply/Verify playbooks. New plans emit only application Apply after the required
infrastructure Verify prefix; the Verify descriptor remains for saved plans and
manual checks. Old planning-request consumers explicitly reject
application-aware plans; the new request/capability versions are opt-in.
See the [A7 technical plan](work/application-libraries/milestones/a7/a7-technical-plan.md)
and [contract versions](../contracts/README.md).

Production roles must also work with conventional manual inventory and variables:

```text
manual inventory + group_vars/host_vars -> role
portable project -> resolver -> ordinary resolved role variables -> same role
```

Rules:

- service-prefixed variables;
- required inputs asserted early;
- no Installer database IDs or DTOs;
- deterministic templates;
- OS mappings isolated from generic orchestration;
- idempotent second execution;
- handlers only on meaningful change;
- no undeclared network downloads;
- `no_log` and restrictive temporary files for sensitive operations;
- safe structured failure plus retained sanitized stdout/stderr.

## Project input and resolved projections

The initial portable project is a normal Ansible project:

```text
project/
  project.yml                  # optional machine metadata/compatibility
  inventory/
    hosts.yml                  # desired hosts and normal Ansible groups
    group_vars/all/platform.yml # service topology, endpoints and policies
    group_vars/<group>.yml       # ordinary service/group overrides
    host_vars/<host>.yml         # host/member desired overrides
  ansible.cfg
```

This multi-file layout is one versioned project contract. It avoids a proprietary launcher and does not make the role contract depend on a monolithic Installer DTO.

The Ansible-only user configures inventory and ordinary variables only.
`platform_desired_state` in `group_vars` owns logical deployments and policy;
host `platform_deployments` owns logical members and physical placement.
Generated identities, fingerprints and locks are machine-owned under
`platform_generated_state`, conventionally in
`inventory/group_vars/all/platform-state.yml`. They are not desired
configuration and are never merged back into `platform_desired_state`.

The repository `ansible.cfg` is part of the standalone execution contract.
It requires `hash_behaviour = merge` so inventory policy maps can recursively
overlay role defaults; execution environments must use this configuration.

Core playbooks validate the project and produce an ephemeral resolved workspace:

```text
.runtime/<run-id>/
  inventory/
    hosts.yml
    group_vars/
    host_vars/
  resolved/plan.json
  private/                 # runtime-only, restrictive, cleaned
  events/
  result.json
```

The resolver must:

- validate every reference before generation;
- resolve service modes, member roles and dependencies;
- preserve explicit placements;
- derive named inventory groups deterministically;
- deduplicate endpoints, SANs, ports and dependencies;
- report conflicts instead of silently correcting intent;
- emit stable ordering and canonical fingerprints;
- never write plaintext secrets into ordinary variables.

Generated workspaces are disposable evidence, not editable project state.

## Standard playbook interface

CORE-01 publishes one filesystem playbook entry point. From the installed or
checked-out Ansible Core root, validation uses:

```text
ansible-playbook -i <project>/inventory/hosts.yml playbooks/validate.yml
```

The collection does not currently publish `platform.core.validate`,
`platform.core.plan`, `platform.core.apply` or `platform.core.verify` collection
playbooks. Plan, apply and verify entry points will be named only when their
playbooks exist and their contracts are tested. The contract requires standard
Ansible inventory and automatic inventory-relative loading of normal
`group_vars` and `host_vars`. Playbooks write versioned machine-readable
artifacts separately from human diagnostics and return documented exit
behavior.

A later convenience CLI may wrap these commands, but it remains optional and Ansible Core, projects and roles must work identically without it.

## Plan

The immutable plan contains at least:

- contract, Core and planning-protocol versions;
- stable project identity, project revision and fingerprint;
- relevant catalog/service-definition and artifact-requirement fingerprints;
- phases, actions, dependencies and targets;
- required runtime credential references and purposes;
- reboot requirements;
- warnings and acknowledgements;
- deterministic plan fingerprint.

Planning is target-contact-free and contains no observed facts, repository
probe results or selected package source. `REPOSITORY` versus `OFFLINE_BUNDLE`
is resolved only during execution through the established target-scoped source
resolver.

No executor may introduce an undeclared mutating action.

## Events and results

Ansible callback plugins emit normalized events. Consumers never need to parse decorated stdout.

EXEC-OBS-01 implements the managed `platform.core.execution_events_json`
aggregate callback. The trusted controller enables it and supplies only
semantic identities. The shared `execution_lifecycle` writer resolves paths,
owns cross-process sequence/append/flush and protects critical capacity.
Task-detail failure is best effort and emits one normalized degradation
diagnostic per affected action; critical lifecycle integrity remains
fail-closed. `no_log` task names and all raw module results are excluded.

For task events, the existing `serviceDeployment` display field keeps the
controller-supplied infrastructure deployment when present. Within application
operations, the callback otherwise resolves only the scoped public identity:
`application_runtime_job.instanceId`, then `application_instance_id`, then
`application_library_id`. Post-install scripts bind these existing scoped
selectors from their selected target, falling back to the script's application
and library. General preparation has no deployment value. This
also applies to `no_log` task metadata; arguments, environment and raw results
remain excluded. Go and UI transport and display the field without inferring
application identities. Plan action deployment references are unchanged.

The Execution Node journal is authoritative. GetEvents returns bounded pages
to Go RunObserver, which maintains the operator's local Installer mirror and
typed subscribers. Local mirror errors cannot change the remote run result.
The existing runtime terminal artifact is `ExecutionResult` with state
`SUCCEEDED`, `FAILED`, `CANCELLED`, `INTERRUPTED` or `CORRUPT_ORPHANED`; richer published result
projections below remain distinct from this private lifecycle artifact.
See [EXEC-OBS-01](work/execution/exec-obs-01.md) for exact bounds, evidence and operator usage.

Event identity includes:

- schema version;
- run, phase, action, host and service deployment identifiers when applicable;
- task state and elapsed time;
- safe message and structured error code;
- redaction metadata.

Final result includes:

- `SUCCESS`, `PARTIAL`, `FAILED`, `CANCELLED` or `INTERRUPTED`;
- outcomes by phase, host and action;
- changed/reboot-required summaries;
- verification findings;
- references to sanitized full diagnostics;
- exact Core, collection, role, payload and artifact versions.

## Runtime role-variable transfer

Core-derived per-host role variables use `platform.core.runtime_role_variables`
and its narrow action-only `platform.core.apply_runtime_role_variables` adapter.
The adapter copies the current host's validated `platform_*` mapping into facts
without templating individual scalars: integers and boolean-shaped strings retain
their original types independently of Jinja native mode. It has no service rules,
Go dependency, target transport or file writes; it rejects task arguments/invalid
names, reports `changed=false`, and preserves `no_log`. Built-in `set_fact` was
insufficient because non-native mode coerced numbers and strings such as `false`.

## Registered loop-result convention

For ordinary per-member render/copy operations with downstream changed-member
tracking, use the standard Ansible loop variable `item`. Registered results then
retain member identity in `result.item.id`; a tracking loop reads `item.item.id`.
Templates may use a descriptive task-local alias (for example,
`vault_member: "{{ item }}"`) without changing the registered result contract.
Product loops retain their declared tuple shape (for example `item.item[0].id`).
Do not introduce service-specific result extraction into the generic lifecycle.
Explicit custom loop variables remain appropriate where nesting requires them,
but their result consumers must match that explicitly declared contract.

## Secrets

The standalone Core accepts secrets through a replaceable runtime provider, initially protected files, environment-owned descriptors or Ansible Vault where explicitly configured. The portable project contains only references and required-secret metadata.

Secret values must not appear in:

- project YAML;
- generated normal inventory variables;
- plan or result;
- events;
- command-line arguments;
- audit or diagnostics.

## Offline trust

SHA256 provides integrity but not authenticity. Artifact and Core manifests therefore use a signature-neutral envelope with:

- manifest format version;
- payload identifiers and hashes;
- signer/key identifiers;
- signature records as extensible data;
- verification policy and evidence output.

The concrete signature technology can be selected later without changing artifact lookup or project semantics.

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

### Automatic application image metadata

Application `defaults.image` remains the packaged image selection. An installation
may override `platform_desired_state.applicationLibraryDeployments.<id>.applications.<slot>.overrides.image`.
No parallel image_artifact/reference or operator-authored SHA/size is required.
`build_execution_runtime_bundle.py --application-image IMAGE artifacts/app.tar`
indexes a Docker-save archive without loading it. Its image ID is the config
digest; its archive digest and size belong to `components`, not the image entry.
Docker-save archives do not prove a registry manifest digest for an @digest alias.

The native `applications/images/inputs.yml` and `applications/images/prepare.yml`
playbooks resolve inputs locally, then use built-in setup/uri tasks on selected
targets. They require no Docker daemon for metadata inspection. Config/manifest
parsing and hashing use small filters; networking, node credentials and delivery
remain ordinary Ansible tasks. `applications/images/plan.yml` composes these steps
with the existing target-free machine planner. Supply the normal project/catalog,
bundle, runtime-release and deployment-order variables. For a manual invocation,
pass session-only registry values by runtime reference through a private extra-vars
file (`platform_application_image_secret_values`), never tracked inventory.

Installer negotiation uses PrepareApplicationImages in execution-runtime v1alpha6,
capabilities v1alpha10, plan v1alpha7 and execution-manifest v1alpha5. Preparation
binds to the saved revision/runtime; the fixed protocol then feeds frozen metadata
to BuildDeploymentPlan and the existing execution path. No Go/UI registry resolver,
new planning worker or persistent secret store is introduced. An older runtime
retains its explicit legacy-lock path. Source/identity policy and verification
remain in Core. See [the plan](work/application-libraries/application-image-metadata-plan.md).

### Terminal package scripts

Application/LibraryPackage v1alpha3 adds `phase: post_install`. The resolved
plan appends `APPLICATION_LIBRARIES_POST_INSTALL` only when selected packages
declare active terminal scripts. It runs after successful library Apply with
per-library health checks, never inside Verify, never after failure/cancel and never for skipped
libraries. The standalone entrypoint is
`ansible-core/playbooks/applications/post-install.yml`. It resolves
script contexts without image/container/provider preflight, reads only required
existing Vault fields and calls the existing `package_script` role sequentially.
Order: libraryOrder index, order, id, scope (library first), instanceId, hostId.
`execution: once` is once per scope in this invocation. Every new Apply calls
the script again; the script reports `status: ok` and actual `changed: false/true`.
`argv`, `secretInputs`, `target` and `run_on` keep their existing meanings.

New plans use plan/v1alpha9 and execution-manifest/v1alpha7; existing plans
without terminal scripts retain their previous versions. Execution capabilities
v1alpha12 advertise `applicationPostInstall: ApplicationPostInstall/v1alpha1`.
No new script editor or product-specific runner environment is introduced.

Provider hooks may opt into package-v1alpha4 batching. Core preserves ordered
provider boundaries and exact secret-reference isolation; the product script
receives original argv arrays through PLATFORM_SCRIPT_BATCH_FILE and owns its
single-session authentication. package_script remains context-free. Every invocation uses ordinary idempotent source copy. Only exact provider/
route/host/bridge network discovery is reused within the Ansible process.
Vault instance Apply performs one full fresh preflight before document writes;
deferred delivery does not call that same preflight twice. Existing generated
password runtime files retain the identity already provisioned before delivery.
