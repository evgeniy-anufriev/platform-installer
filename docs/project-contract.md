# Portable project contract

## Purpose

The portable project directory contains the single canonical user-owned desired
state shared by standalone Ansible, the future backend and the UI. Desired
state is ordinary inventory, `group_vars`, `host_vars` and role defaults. The
Installer edits those same files and invokes the same playbooks. An
Ansible-only user does not need to create or understand `project.yml`.

## Physical layout

```text
project/
  project.yml                         # optional compatibility/machine metadata
  inventory/
    hosts.yml
    group_vars/all/platform.yml       # user-owned desired state
    group_vars/all/platform-state.yml # machine-owned generated state
    group_vars/<service-or-operator-group>.yml
    host_vars/<host>.yml
  ansible.cfg
```

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
      definitionVersion: '1'
      mode: kraft-distributed
      configuration:
        quorumMode: dynamic
```

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
enforces this boundary. `project.yml.desiredState` and legacy
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
suffix, wildcard intent and IPv4 VIP. The resolved FQDN is deterministic:
`<serviceDeploymentId>.<endpointGroup.address.domain>`. There is no
`endpointBindings`, alias, listener reference, port override or manually
authored FQDN. Endpoint-enabled deployment IDs must be valid lowercase DNS
labels.

`ResolvedServiceEndpoints` is a read-only projection. It contains FQDN and VIP
identity for PKI and future network providers, but is not desired or generated
state. Transport ports and routing are deferred to NET-03. Kafka is not a
generic NET-01 endpoint consumer because its client reachability is governed
by package-owned named and advertised listeners.

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

- Published schemas version portable machine state and resolved projections.
- Every service deployment pins a compatible service-definition version through the catalog lock.
- Plans pin project, catalog, artifact and Core fingerprints.
- Readers reject unknown major versions safely.
- Migrations are explicit, deterministic and preserve an original backup.
- Import/export round trips preserve supported fields and unknown extension fields according to a documented policy.
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
