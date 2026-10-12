# CORE-07 — Ansible-native canonical desired state

CORE-07 makes the standalone Ansible interface the ownership model, not merely
an execution adapter.

## Ownership

- Role defaults own product defaults.
- `group_vars` and `host_vars` own user overrides through normal Ansible
  precedence and the required `hash_behaviour = merge` project convention.
- `platform_desired_state` owns logical service deployments and policy.
- Host `platform_deployments` owns logical members and physical placement.
- `platform_generated_state` owns generated identities, fingerprints, locks
  and machine metadata only.
- Runtime workspaces, credentials, facts and execution results remain derived
  or runtime-only state.

`project.yml` is not required by managed Kafka, managed PKI or validation. Its
desired-state form and legacy `platform_project` remain bounded compatibility
readers. New fixtures and writers use Ansible-native variables.

## Managed execution boundary

Managed Kafka apply performs read-only validation and identity discovery,
materializes missing identity into the dedicated generated-state file,
reloads inventory variables from disk, validates again, projects the existing
public Kafka role input, and only then permits service mutation. Verify is
strictly read-only. A no-change identity decision does not rewrite files.

PKI derives requests from the same Ansible-native topology. Manual Kafka
`platform_kafka_instances` and manual PKI request/plan inputs remain standalone
public contracts and do not require project metadata or the managed resolver.

CORE-07A adds a read-only authoring validation gate before managed Kafka
identity materialization. See [CORE-07A](core-07a.md) for namespace ownership,
closed managed configuration and advanced-setting safety.

## Compatibility and safety

- Desired state duplicated in compatibility sources must be semantically
  identical; conflicts are blocked.
- Desired members may not be duplicated outside inventory placement.
- Generated state cannot contain configuration or secrets.
- Inventory placement changes topology fingerprints.
- Execution transport variables do not become service desired state.
- Materialization preserves unrelated inventory, `group_vars` and `host_vars`.

The Kafka `clientPort`/`controllerPort` projection remains a service-package
PLAINTEXT compatibility model, not a Generic Core endpoint contract. Named
listeners and Kafka SSL remain a later service milestone.
