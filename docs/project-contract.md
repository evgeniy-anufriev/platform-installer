# Portable project contract

## Purpose

The portable project directory is the single canonical desired state shared by standalone Ansible, the future backend and the UI. It uses standard inventory, `group_vars` and `host_vars`, is human-reviewable and versioned, and is free of discovered facts, execution state and plaintext secrets.

## Physical layout

```text
project/
  project.yml
  inventory/
    hosts.yml
    group_vars/all/platform.yml
    group_vars/<service-or-operator-group>.yml
    host_vars/<host>.yml
  ansible.cfg
```

The contract covers the directory as a whole. `project.yml` carries metadata and locks; inventory declares desired hosts; platform topology and policy live in an ordinary group variable document; service and host overrides use normal Ansible variable precedence within the restrictions defined by the contract.

## Root outline

`project.yml` is the only owner of identity and contract/lock versions:

```yaml
apiVersion: platform.installer/v2alpha1
kind: PlatformProject
metadata:
  id: production-scada
desiredStateContract: platform.installer/project-desired-state/v2alpha1
catalogLock:
  apiVersion: platform.installer/catalog/v1alpha1
  digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
  services: {}
artifactLock:
  apiVersion: platform.installer/artifacts/v1alpha1
  digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
```

The illustrative `inventory/group_vars/all/platform.yml` shape contains only
desired topology and policy. It does not repeat the project ID or API version:

```yaml
platform_project:
  serviceDeployments:
    accounting-db:
      serviceType: postgresql
      definitionVersion: 1
      mode: standalone
      configuration: {}
      members:
        database-1:
          host: redos-node1
          roles: [database]

  endpointGroups:
    applications:
      baseDomain: scada.local
      additionalDomains: [apps.example.local]
      wildcard: true
      vip: 10.10.10.2

  endpointBindings:
    accounting-client:
      serviceDeployment: accounting-db
      listener: client
      endpointGroup: applications
      alias: postgres

  certificateProfiles:
    infrastructure:
      authorityRef: platform-ca
      sanPolicy:
        includeHostDns: true
        includeHostIp: true
        includeEndpointFqdns: true
        includeEndpointWildcard: true
        includeEndpointVip: true

  certificateScopes:
    infrastructure-services:
      profile: infrastructure
      sources:
        endpointBindings: [accounting-client]
        serviceDeployments: [accounting-db]

  secretRequirements:
    postgres-admin:
      purpose: postgresql_admin_password
      providerRef: runtime:postgres-admin
```

## Identity model

Stable project keys are meaningful within a project and independent of local database row IDs.

- `serviceType` identifies a catalog capability, such as `postgresql`.
- `serviceDeployment` identifies one desired deployment, such as `accounting-db`.
- `member` identifies a member within that deployment, such as `database-1`.
- `host` identifies an intended target host.
- endpoint binding and certificate scope have their own stable identities.

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

An endpoint binding references:

- a service deployment;
- a declared listener from its service manifest;
- an endpoint group;
- an alias.

The endpoint group supplies domains, wildcard policy, VIP/address and network profile. Concrete endpoint FQDNs are derived from alias plus every applicable domain. Service IDs are metadata and never become DNS names implicitly.

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

- `apiVersion` versions the portable project structure.
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
