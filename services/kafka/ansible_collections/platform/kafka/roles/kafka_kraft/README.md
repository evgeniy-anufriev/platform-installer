# `platform.kafka.kafka_kraft`

Reserved role contract for Kafka KRaft. This skeleton intentionally has no
`tasks/main.yml`: CORE-01 defines package shape and variables, while production
mutation begins only in SERVICE-01A.

Planned ordinary role variables use the `platform_kafka_` prefix. Resolved
topology inputs must contain stable deployment/member identities, explicit
hosts and roles, and no Installer DTOs or persisted secret values.
