# `platform.haproxy.haproxy`

Предоставляет host-scoped HTTPS `public` routing, local stats и derived service
backends. До start/reload валидирует complete candidate и exact active graph на
каждом участнике.

Запуск: `services/haproxy/playbooks/apply.yml` и `verify.yml`. Настраиваются TLS
profile HAProxy deployment и relationship/backends публикуемого сервиса.
Standalone package paths, ports, `global`, `defaults` и stats-backend defaults
заданы в `defaults/main.yml`.

Public frontend, normalized Host routing, TLS bind, stats route и generated
backend names зарезервированы role. Не редактируйте `haproxy.cfg`, generated
`conf.d`, candidate directory, socket или PKI directory вручную.

Для partial endpoint publication можно передать обычную runtime-переменную
`platform_haproxy_partial_deployment_ids`: непустой список точных source IDs.
Прежний `platform_haproxy_partial_deployment_id` совместим как singleton; вместе
они допустимы только для одного совпадающего source. Пустой список, invalid IDs
и plural scope с full_reconcile отклоняются до mutation. Resolver получает общий
набор выбранных sources; каждый provider host фильтрует только свои backends.
Prepare строит один полный candidate на host, сохраняет чужие и невыбранные files;
все hosts проходят prepare до activation, затем active validation до reload.
Неизменённый partial graph не перезагружается. Проверки targets последовательны.
Сбой после начала многохостовой activation не означает автоматический rollback:
сохраняются существующие archive и HAPROXY_ACTIVATION_RECOVERY_REQUIRED evidence.
