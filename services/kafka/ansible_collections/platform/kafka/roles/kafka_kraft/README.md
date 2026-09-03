# `platform.kafka.kafka_kraft`

Role Kafka 4.3.1 KRaft для broker, controller или combined members. Установка
возможна только из явно переданного offline artifact; загрузка из Интернета не
выполняется. Один physical Ansible host может владеть несколькими logical
members.

Обязательные входы: `platform_kafka_cluster_id`,
`platform_kafka_artifact_path`, `platform_kafka_artifact_checksum`. В
distributed mode `platform_kafka_instances` содержит полный список members:
`id`, `node_id`, `roles`, `host`, `advertised_host` и isolated data/log paths.
Broker требует named listeners; dynamic initial controller — стабильный
`directory_id`. Existing initialized storage не форматируется при совпадающих
cluster/node identities; mismatch останавливает mutation.

Quorum состоит только из controller members. Dynamic/static quorum mutually
exclusive; role детерминированно выводит member sets и проверяет listener/path
collisions на physical host.

## Запуск и настройка

Используйте `services/kafka/playbooks/apply.yml` и `verify.yml`; `discover.yml`
и `discover_deployment.yml` — read-only диагностика. Настраиваются approved
artifact, cluster identity, members, listener ports/topology, service-wide TLS
profile, retention и non-reserved `platform_kafka_advanced_config`.

Default listeners: `PLAINTEXT`, `SSL`, `CONTROLLER`. Переопределяйте их только
для topology/additional ports. SSL listeners используют effective
deployment/member TLS profile, а не собственный profile.

Generated `server.properties`, PKI consumer directory, systemd unit, KRaft
metadata и identities редактировать нельзя. Listener/security, KRaft identity,
paths и service-managed properties зарезервированы от advanced configuration.
`reset_kafka_host.yml` и `platform_kafka_clean_install=true` — только явное
destructive recovery с точным acknowledgement deployment ID; обычный reconcile
никогда не запускает cleanup.
