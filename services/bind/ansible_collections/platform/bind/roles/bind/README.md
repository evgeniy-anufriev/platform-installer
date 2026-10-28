# `platform.bind.bind`

Управляет authoritative BIND primary с необязательными secondary. Для standalone достаточно одного primary; role выводит project-host,
endpoint и wildcard records, валидирует complete candidates на всех участниках
и активирует их только после cluster barrier. Secondary получает зону native
transfer, не Ansible copy.

Фаза `start` ожидает авторитетный SOA каждой локальной зоны на всех участниках,
включая завершение первоначального transfer на secondary. Число повторов и пауза
задаются `platform_bind_readiness_retries` (60) и
`platform_bind_readiness_delay` (2 секунды). Готовая зона проходит с первой попытки,
без изменений; тайм-аут завершает Apply ошибкой. Отдельный Verify не изменён.

Запуск: `services/bind/playbooks/apply.yml` и `verify.yml`. В desired state
настраиваются `zone`, `defaultTtl` и
`advancedConfig.options.minimal-responses`; package/path/phase defaults — в
`defaults/main.yml`.

Тип зоны/files, transfer/update policy, recursion и notifications зарезервированы
role. Не редактируйте `/etc/named.conf`, Platform includes, zone/slave/candidate
files или generated DNS serial/fingerprint: их render/activation выполняет role.

`tasks_from: publish_source` группирует обычные `platform_bind_source_dns_records`
по bindDeploymentId/zone и выполняет один local authenticated `nsupdate -l -v`
для изменившейся зоны только на primary. Singleton `update_a_record.yml` использует
тот же путь через `platform_bind_a_records: [platform_bind_a_record]`.
Перед update проверяется каждый owner/AA/CNAME/TTL/IPv4, точные прежние RDATA и
existence связываются DNS prerequisites; после — exact authoritative TTL/IP.
TTL-CAS не обещается: конкурентный TTL-only update может быть заменён desired TTL.
Пустой/конфликтующий scope и oversized message отклоняются до update.
Консервативный message bound: ASCII presentation length*2+512<=60000 bytes.
Результат не является транзакцией нескольких зон; failure сохраняет фактический
scope, обычный повторный reconcile доводит желаемые RRsets. Unchanged update0;
zone-файлы не перезаписываются и service reload не добавляется.
