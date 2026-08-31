# `platform.kafka.kafka_kraft`

Kafka 4.3.1 KRaft role for one or more broker, controller or combined members.
It installs only from a caller-supplied offline artifact and does not download
from the Internet. Logical members remain ordinary role data; one physical
Ansible host may own zero, one or multiple members.

Required inputs are `platform_kafka_cluster_id`,
`platform_kafka_artifact_path` and `platform_kafka_artifact_checksum`. For
distributed operation, `platform_kafka_instances` contains the full deployment
member list. Every member declares `id`, `node_id`, `roles`, `host`,
`advertised_host` and isolated data/log paths. Broker members require
`client_port`; controller members require `controller_port`. Dynamic initial
controllers also require stable `directory_id` values. The legacy
single-instance variables are only a compatibility adapter into the same
normalized member model. Existing initialized storage is never reformatted
when its cluster and node identities match; mismatches fail before mutation.

Quorum projections contain controller members only. Dynamic and static quorum
modes are explicit and mutually exclusive. The role derives all, local,
controller and broker member sets, validates listener/path collisions per
physical host, prepares each host once and applies its local members in
deterministic node-id order.

Optional `platform_kafka_advanced_config` contains non-reserved Kafka
properties. Reserved keys are rejected with `ADVANCED_SETTING_RESERVED` before
the effective configuration is assembled. `kafka_effective_config` is an
internal role variable, not part of the public role input contract. The
serializer accepts strings, numbers and booleans deterministically; other
types are rejected explicitly until a serialization contract is defined.
