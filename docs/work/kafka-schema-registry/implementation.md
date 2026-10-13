# Kafka Schema Registry

Owner authorization: implementation requested on 2026-10-12.

## Desired state and deployment

Schema Registry belongs to the Kafka deployment in the plan. Every broker member
gets an instance; combined members qualify, controller-only members do not.
`schemaRegistryEnabled` defaults to true, `schemaRegistryKafkaListener` to `SSL`,
HTTP to 8081 and HTTPS to 8082. Both REST listeners run simultaneously. Ports
may be overridden per member to support multiple brokers on one host.

The selected Kafka listener must exist on every broker, must not be a controller
listener and must use SSL or PLAINTEXT consistently. SSL with the existing
interBroker purpose is accepted. Existing Kafka runtime PKI is materialized into
the Registry consumer directory. No independently configured Registry PKI profile
or deployment placement is introduced.

Ordinary documented role variables remain supported. Core validates resolved
configuration, while the role uses the same pure projection for instance paths,
ports, units and bootstrap servers. The Installer's generic service editor reads
the package settings. Listener selection currently uses the generic string field.

## Installation and lifecycle

The approved source gate chooses the node's compatible repository artifact, then
the immutable offline bundle, otherwise blocks. The pinned offline distribution is
Confluent Community 8.3.2, SHA256
`dc4d6234e0f7e1a91b369f9cf1d27d7c9885edb9f6440170c3a6f00ba68fcc81`.
It includes Schema Registry and its Java dependency closure. Repository identity
is confluent-schema-registry, version 8.3.2, architecture noarch.

The package apply playbook completes Kafka on all selected hosts before Registry.
Manual role invocation supports full and component phases. Protected properties
contain runtime password values only on targets; Ansible suppresses their output.
Units and directories carry ownership markers; unsafe or foreign paths block.

Readiness requires all desired brokers, the exact `_schemas` policy, active
Registry units, HTTP and CA-verified HTTPS. `_schemas` has one partition,
replication factor min(3, broker count), compact cleanup and min ISR 1 for one
broker, otherwise 2. Existing incompatible policies block rather than migrate.
The offsets topic default is bounded by broker capacity so single-broker Registry
group coordination works. Explicit incompatible offsets replication blocks.

Verify performs no mutation. Repeat Apply must report changed=0. Explicit Kafka
deployment clear removes owned Registry instances before Kafka and retains the
shared approved distribution. Disabling Registry with owned installed instances
requires the explicit clear lifecycle.

## Contract additions

`x-enabledBy` activates an artifact through a resolved deployment boolean setting.
An unresolved value blocks artifact planning. `x-memberInputOnly` prevents member
overrides from being flattened into host-wide role variables; the canonical member
input is consumed by the role. These extensions do not add desired-state stores.

## Acceptance gates

Focused RED OS Core tests, native Apply/Verify/repeat, HTTP schema registration and
trusted HTTPS read are required. Split controllers, multiple colocated brokers,
multi-host readiness, negative ownership/topic/source cases, clear and real
React/Wails planning/execution remain distinct acceptance gates. Independent FULL
DIFF review is required by the repository procedure. Current status is recorded
only in CURRENT_STATE; evidence is in [the journal](evidence/test-journal.md).
