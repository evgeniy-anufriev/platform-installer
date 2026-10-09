# Portable project contract

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
`docs/exec-generated-state.md`. `project.yml.desiredState` and legacy
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
- Import/export round trips preserve supported fields and unknown extension fields according to a documented policy. Export names the copied project's `metadata.name` after the export directory name; source files and project ID remain unchanged. Only the copied optional `project.yml` may have normalized formatting, with unsupported YAML references/ambiguous documents rejected as described in [UI-01I](ui-01i-architecture.md).
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
