# `platform.kafka.kafka_kraft`

Kafka 4.3.1 KRaft role for one or more combined broker/controller members. It
installs only from a caller-supplied offline artifact and does not download
from the Internet. Distributed members are logical instances inside one
ordinary Ansible host execution; they are not fake inventory hosts.

Required inputs are `platform_kafka_cluster_id`,
`platform_kafka_artifact_path` and `platform_kafka_artifact_checksum`. For
distributed operation, `platform_kafka_instances` contains ordinary Ansible
member dictionaries with explicit `id`, `node_id`, ports and data/log paths.
The legacy single-instance variables are normalized to one internal member.
Existing initialized storage is never reformatted when its cluster and node
identities match; mismatches fail before mutation.

Optional `platform_kafka_advanced_config` contains non-reserved Kafka
properties. Reserved keys are rejected with `ADVANCED_SETTING_RESERVED` before
the effective configuration is assembled. `kafka_effective_config` is an
internal role variable, not part of the public role input contract. The
serializer accepts strings, numbers and booleans deterministically; other
types are rejected explicitly until a serialization contract is defined.
