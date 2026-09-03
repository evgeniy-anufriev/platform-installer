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
