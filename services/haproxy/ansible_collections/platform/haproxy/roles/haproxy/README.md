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

Partial publication uses a dedicated short path shared by application endpoint
batches and singleton service hooks (including Vault and ClickHouse). Existing
frontend/backend templates are rendered in one native lookup per provider host;
`fragment_batch` compares or writes the selected files in one module call, with
bounded payloads, root-owned no-follow paths and atomic per-file replacement.
The selected source IDs, provider host filtering and ordinary role variables
remain authoritative. The retained graph ownership proof is checked before any
candidate reset. An unchanged selected graph keeps the candidate, validates the
active configuration with current TLS material and rechecks proof/content at the
activation boundary; no reload is requested. A changed graph retains all-host
prepare/activate barriers, full candidate and active validation, digest equality
and the existing archive/recovery evidence. This is not a whole-cluster atomic
transaction. Full installation/reconcile resets batch facts and keeps its own
path. No persistent cross-run readiness cache is introduced.
