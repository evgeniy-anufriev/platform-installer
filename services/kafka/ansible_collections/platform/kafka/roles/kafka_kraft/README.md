# `platform.kafka.kafka_kraft`

Standalone Kafka 4.3.1 KRaft role for one combined broker/controller on one
physical host. It installs only from a caller-supplied offline artifact and
does not download from the Internet.

Required inputs are `platform_kafka_node_id`, `platform_kafka_cluster_id`,
`platform_kafka_artifact_path` and `platform_kafka_artifact_checksum`. The
role accepts ordinary inventory variables and has no Installer DTO or runtime
launcher dependency. Existing initialized storage is never reformatted when
its cluster and node identities match; mismatches fail before mutation.

Optional `platform_kafka_advanced_config` contains non-reserved Kafka
properties. Reserved keys are rejected with `ADVANCED_SETTING_RESERVED` before
the effective configuration is assembled. `kafka_effective_config` is an
internal role variable, not part of the public role input contract. The
serializer accepts strings, numbers and booleans deterministically; other
types are rejected explicitly until a serialization contract is defined.
