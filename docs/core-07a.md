# CORE-07A — Ansible authoring safety baseline

CORE-07A hardens the existing Ansible-native ownership model without changing
topology or standalone role contracts.

`hash_behaviour = merge` remains a required Ansible project policy. It is not
implemented by Core and is not reinterpreted by the resolver.

## Pre-materialization gate

Managed Kafka apply validates Ansible-resolved desired state before identity
discovery or materialization. A failed validation therefore cannot create or
change `platform_generated_state`, including Kafka cluster and controller
directory identities. After a successful materialization and inventory refresh,
the existing second validation remains in place before the Kafka role mutates a
target.

## Authoring namespaces

- `platform_desired_state.serviceDeployments`: logical deployment intent and
  closed service-managed `configuration`.
- Inventory `platform_deployments`: member ownership, placement and permitted
  member configuration. Its deployment key is a validated reference, not a
  second deployment definition.
- `configuration.advancedConfig`: explicit service-native settings namespace.
- Ordinary variables outside these namespaces remain opaque Ansible input.
- `platform_generated_state`: machine-owned generated identities, fingerprints,
  locks and safe reconcile metadata only.

Kafka rejects unknown managed fields with
`SERVICE_CONFIGURATION_PROPERTY_UNKNOWN`; deterministic close matches are
reported when available. `advancedConfig` accepts arbitrary Kafka-native
properties, except role-controlled settings such as node identity, listeners,
quorum, role selection and managed paths. Those return
`ADVANCED_SETTING_RESERVED` before any target mutation.

Manual standalone `platform_kafka_instances` remains unchanged and does not
require managed desired or generated state.
