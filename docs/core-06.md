# CORE-06 — Canonical project state and runtime projection

Status: DONE.

CORE-06 establishes one portable desired-state model while preserving ordinary
standalone Ansible role use. Derived Kafka runtime input is disposable and is
never persisted as a second project model.

## Canonical ownership

| Concern | Canonical owner | Notes |
| --- | --- | --- |
| Deployment existence, service type, version and mode | `project.yml.desiredState.serviceDeployments` | Deployment-level logical desired state. |
| Deployment configuration | `project.yml.desiredState.serviceDeployments.<id>.configuration` | Contains managed deployment settings, not generated runtime objects. |
| Deployment identity | `project.yml.desiredState.serviceDeployments.<id>.identity` | Kafka `clusterId` is persistent identity, not ordinary configuration. |
| Physical hosts and logical members | Inventory host `platform_deployments.<deploymentId>.members` | A member is physically owned by exactly one inventory host; placement is implied by that ownership and is not duplicated in the member. |
| Member roles and configuration | Inventory member `roles` and `configuration` | Kafka `nodeId` is member configuration. |
| Member identity | Inventory member `identity` | Kafka controller `directoryId` is persistent identity, not ordinary configuration. |
| Explicit Ansible overrides and unknown extensions | `group_vars` / `host_vars` | Unmapped values remain opaque/pass-through inputs with safe fingerprints. |
| Effective role input | Runtime only | Managed Kafka projects to `platform_kafka_instances`; it is not written to the portable project. |

`project.yml.desiredState` is preferred. Legacy `platform_project` remains a
bounded compatibility input only: it is used when inline desired state is
absent, equivalent dual input produces a deprecation finding, and conflicting
dual input is blocked. New managed fixtures and future writers use only the
canonical model. The previous reference-list placement model is not persisted
by new fixtures.

## Resolution and runtime projection

Controller-side validation combines deployment state with inventory-owned
members and produces deterministic topology and configuration projections.
The Kafka projector then builds the existing public standalone role shape,
including deployment/member identity, roles, node IDs, quorum, effective
addresses and target config/data/log paths.

`runtimeProjectionFingerprint` hashes the canonical sanitized final service
runtime projection. Effective target paths and an inventory address used as an
effective Kafka address affect it. Execution-node selection, Ansible transport
overlays, controller workspaces, temporary files, source YAML formatting and
secrets do not. Explicit service-address overrides naturally supersede an
inventory transport address.

The Kafka role remains independently callable with manual
`platform_kafka_instances`, `platform_kafka_cluster_id` and controller
`directory_id` values and does not require `project.yml`, Core materialization,
Go or the Installer.

## Kafka identity lifecycle

Managed apply performs these ordered phases:

1. read canonical project and inventory state for discovery;
2. inspect existing Kafka `meta.properties` without mutation;
3. make a pure generate/recover/validate identity decision;
4. transactionally persist the complete required `clusterId` and controller
   `directoryId` set when it changed;
5. reload project and inventory from disk;
6. validate the reloaded canonical state;
7. resolve and project runtime Kafka input;
8. enter the existing generic Kafka role lifecycle.

Kafka service/storage mutation cannot start before successful persistence,
reload and validation. A no-change identity decision does not invoke persistence or
rewrite either YAML file. Initialized storage may supply a missing canonical
identity, but a persisted/storage mismatch is blocked without deletion,
formatting or implicit repair. Verify performs discovery and diagnostics only;
it never generates or persists identity.

The two-file persistence primitive detects concurrent edits, records an
interruption marker, and rolls back or recovers mixed project/inventory state.
It uses PyYAML `safe_load`/`safe_dump`: unrelated YAML data is semantically
preserved, and `group_vars`/`host_vars` are untouched, but comments, anchors,
scalar style and exact textual formatting are not guaranteed after a required
identity write. No-op materialization performs no serialization and preserves
bytes and modification times.

## Execution access boundary

EXEC-01 identity and known-hosts state live under the persistent Execution Node
runtime state root, outside ephemeral project/QA workspaces. Private keys are
runtime-only, restrictively permissioned, ignored by Git and never copied into
project, inventory or logs. The generic access gate prepares or reuses that
identity before service execution; Kafka contains no SSH recovery branch.

## Destructive Kafka operations

`platform_kafka_clean_install=true` explicitly includes `clear.yml` after full
topology validation and before normal member mutation. Exact deployment
acknowledgement is mandatory. Cleanup is deployment/host scoped: it inventories
Kafka JVMs and listeners, stops selected and attributable conflicting units,
force-terminates only processes whose config belongs to selected members,
verifies listener release, and removes only selected member config/data/log and
dedicated unit state. It preserves the shared Kafka installation, JDK, Kafka
account, approved offline payload and shared `kafka@.service`. Identity mismatch
never enables cleanup automatically.

`services/kafka/playbooks/reset_kafka_host.yml` is a separate destructive
administrative/QA operation. It requires the exact runtime acknowledgement and
may remove all managed Kafka runtime, storage, installation and unit files on
explicitly selected hosts. It is not part of normal managed apply and preserves
the EXEC-01 execution identity and approved controller-side offline payload.

## Deferred boundaries

- The future UI edits canonical deployment state in `project.yml` and physical
  member ownership in inventory. It must not persist the runtime projection or
  invent another placement/identity model.
- Generated identities and transactional persistence establish compatibility
  prerequisites for future stateful transitions, but upgrade, migration,
  replacement and identity-rotation workflows are not implemented by CORE-06.
- A generic Kafka listener/endpoint model is intentionally deferred. Current
  projection uses the explicitly supported address and port inputs proven by
  SERVICE-01A through SERVICE-01D.
- Failure/recovery acceptance remains SERVICE-01A–01D evidence. CORE-06 used
  fast apply, verify and repeat-apply idempotency regression and did not add a
  second failure orchestration framework.
