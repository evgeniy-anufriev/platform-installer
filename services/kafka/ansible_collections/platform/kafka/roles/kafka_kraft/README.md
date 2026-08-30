# `platform.kafka.kafka_kraft`

Standalone Kafka 4.3.1 KRaft role for one combined broker/controller on one
physical host. It installs only from a caller-supplied offline artifact and
does not download from the Internet.

Required inputs are `platform_kafka_node_id`, `platform_kafka_cluster_id`,
`platform_kafka_artifact_path` and `platform_kafka_artifact_checksum`. The
role accepts ordinary inventory variables and has no Installer DTO or runtime
launcher dependency. Existing initialized storage is never reformatted when
its cluster and node identities match; mismatches fail before mutation.
