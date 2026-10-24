# СЗИ — полная библиотека приложений

Библиотека содержит обычные пакеты `keycloak`, `grant-access`,
`grant-access-front`, `grant-access-audit` и `nginx`. На этапе 1 выбирается
только `keycloak`; остальные приложения необязательны и относятся к этапу 2.
Redis credentials для grant-access не требуются: это legacy.

## Native-проверки перед планом

На Execution Node проверка `ansible-core/tests/qa_szi_runtime_render.py`
принимает `--project` (QA-копию проекта), `--prepared-images` (метаданные
подготовленных образов) и `--report` (путь отчёта). Она использует штатное
разрешение проекта, реальные задачи рендера роли `application_runtime`,
`docker compose config` и тот же валидатор Core, что Apply. Контейнеры,
инфраструктурные API и новый план не запускаются; файлы создаются только
во временной тестовой копии.

Матрица проверяет все размещения пяти приложений, повторный рендер,
переопределение портов и отклонение двух прежних вариантов нераскрытых
Hazelcast-адресов. Порты задаются в `defaults.ports.port-*` с обычными
overrides; listener, public address, список участников и healthcheck
используют соответствующие container/published значения.

`test_vault_write_diagnostics_native.py` вызывает реальные задачи Vault с
`delegate_to: localhost` и `delegate_facts: true` против локального HTTP-стенда:
запись и отсутствие изменений, отказ HTTP, CAS retry с сохранением чужих
полей, policy/AppRole и повторное применение без повторной записи.
Эти проверки не заменяют установку, readiness и проверку Vault Agent на стенде.

Установка Keycloak на узлах 102 и 103 через настоящий React/Wails/Core план
завершилась Apply/Verify PASS с `SkipInfraVerify`. Проверены восстановление
чистой БД, темы и плагины, создание admin с паролем из runtime secret,
вход через API, TLS и повторный запуск скриптов без изменения пароля.
Подробности и ограничения приёмки:
[журнал установки](../../docs/work/application-libraries/evidence/szi-stage1-install-journal.md).
Полная приёмка этапа и визуальная проверка остаются отдельными воротами.

## Порядок и идентичности

Приоритеты библиотек задаются в `config/application.yml`, порядок приложений
внутри библиотеки — `start_priority` её slots. Общие ресурсы готовятся до
запуска приложений; Apply, readiness и Verify выполняются побиблиотечно.
Порядок должен ставить СЗИ перед интегрируемыми библиотеками.

Для единственной библиотеки СЗИ в проекте `instance_id_strategy:
application-name` задаёт applicationId равным имени приложения (`keycloak`,
`nginx` и т. д.). Остальные библиотеки сохраняют прежнюю стратегию ID.

## Чистая база и bootstrap

Ресурс PostgreSQL объявляет `restore_on_create`: дамп восстанавливается только
при создании новой БД. Исходный дамп не содержит admin; шесть служебных клиентов
и три группы администраторов сохранены. Также включены группа `ТУЗ` с прежним ID
и пользователь `---`, состоящий в ней. Всего четыре группы; учётные данные
в дамп не включены. Повторный Apply не восстанавливает БД.

Пакет Keycloak объявляет два скрипта общего контракта, оба с `execution: once`:

1. `before_start`: временный service-account создаётся штатной командой
   `kc.sh bootstrap-admin service`. Временный процесс не публикует порты,
   HTTP management не требует серверного TLS keystore.
2. `after_ready`: через API создаётся постоянный admin с паролем из runtime
   secret, затем проверяется вход и удаляется временный клиент. До установки
   начального пароля пробный вход нового пользователя не выполняется. Если admin уже
   существует, проверяется текущий runtime пароль; пароль не сбрасывается.

Core передаёт скриптам точные argv и защищённые файлы секретов. Docker,
Keycloak и особенности bootstrap принадлежат самим скриптам.
Последовательность и контракт описаны в
[техническом плане](../../docs/work/application-libraries/szi-stage1-technical-plan.md).

Основной Keycloak запускается в production режиме через Vault Agent.
Серверный TLS использует стандартные PKI `certificate.pem` и `private-key.pem`;
CA и truststore доставляются той же общей PKI-логикой. PostgreSQL targets,
порты и имя БД выводятся из разрешённых подключений библиотеки.
Heap: `-Xms256m -Xmx1g`, лимит памяти по умолчанию `2G`.

## Клиенты и отключённый provision listener

Потребители задают `IDENTITY_CLIENT` через обычный Ansible lookup шаблона
`assets/keycloak-client.json.j2`. В шаблоне используются `application_instance_id`
и `application_connections.sso.parameters.proxy_url`; готовый JSON передаётся
провайдеру. `description` провайдер заполняет endpoint приложения из argv Core.
Настройки клиентов, их роли и authorization settings перенесены из исходного
экспорта; секреты и UUID в шаблонах не хранятся.

`dmz-provision` сохранён в listeners чистого realm. Его JAR остаётся в providers,
а `assets/conf/keycloak.conf` задаёт
`spi-events-listener--dmz-provision--enabled=false`. Legacy ENV provisioner удалены.
Keycloak пишет сообщение о зарегистрированном выключенном провайдере;
для этапа 2 владелец согласовал его как ожидаемое. Остальные ошибки проверяются
отдельно в QA; штатный Verify сохраняет проверки работоспособности сервиса.
JDBC acquisition timeout по умолчанию — 30 секунд.

## Внешние файлы пакета

Следующие файлы исключены из Git и должны передаваться отдельно:

- `application-packages/keycloak/1.0.0/assets/providers/*.jar` — девять плагинов;
- `application-packages/keycloak/1.0.0/assets/themes.tar.gz` — полная тема;
- `library-packages/szi/1.0.0/assets/keycloak-clean.dump` — чистая база без admin, с пользователем `---` в группе `ТУЗ`.

SHA-256 чистого дампа:
`2ea1a1d6da9acd2ea2445914821d1f1be88341fb29ee46dd66464a620fc6e061`.
Дамп с новым runtime паролем не создаётся. При отсутствии внешних файлов
полный пакет не проходит проверку.

Плагины задаются через `config_directories`, темы — через `config_archives`.
Повторный Apply обновляет изменённые файлы каталога и удаляет устаревшие;
архив при совпадении digest повторно не распаковывается. Для объявленной
конфигурации сняты отдельный предел 8 МиБ и фильтр слов `password`/`token`.
Суммарный предел протокола сохраняется, реальные секреты остаются runtime-only.

## Этап 2

Образ nginx:
`evoscada-docker.artifacts.tn.tngrp.ru/lawellet/nginx-lua-resty:1.0.3-redos3-certs`.
Адреса в `scada-lawellet.conf` и конфиге grant-access-front выводятся из
applicationId и endpoint-групп. Аварийные маршруты `script.lua`/`data.env`
рассчитаны на динамическое заполнение интеграциями.

Полная библиотека установлена на двух узлах через реальный React/Wails/Core:
по пять приложений, чистый импорт БД и bootstrap admin, затем успешный повторный
Apply/Verify без повторного импорта и перезапуска контейнеров. Единый ключ интеграции —
applicationId: client ID Keycloak, nginx subpath, endpoint и аварийный маршрут.
Принятый redirect URL клиента: `https://nginx…/<clientId>/*`.

Подключение `sso` предоставляется Keycloak и содержит произвольные `parameters`
и ссылки на `credentials`; пароль администратора привязан к `szi_admin_secret`.
Интеграция потребителя включается в defaults и переопределяется файлами
`group_vars`. Создание клиентов и accounts выполняет скрипт провайдера на
Execution Node через curl/jq. Раннер остаётся универсальным.

Настройки групп и назначения realm/client roles описаны в [GROUP_ROLES.md](GROUP_ROLES.md).
`IDENTITY_GROUPS` редактируется только в файлах. Пароль пользователя
`admin-grant-access`, client secret и пароль Java truststore доставляются через
Vault Agent; JVM запускается скриптом `start-java.sh` с параметрами truststore.

Проверены четыре группы, три прикладных клиента с параметрами исходного экспорта,
членство и прямые роли пользователей, запросы grant-access и nginx. После повторного
Apply IDs объектов, метаданные паролей и версии Vault остались прежними.
Подробности: [журнал этапа 2](../../docs/work/application-libraries/evidence/szi-stage2-connections-journal.md).

### Диагностика

До успешного завершения этапа 2 включены полный вывод CLI и shell xtrace
скриптов bootstrap, создания admin и REST-интеграции. Логи сохраняются в
`.scripts/diagnostics/` рабочего каталога скрипта с датой и PID в имени.
Секреты и JWT маскируются до записи; неочищенная трассировка идёт только
через pipe в память фильтра. Временные файлы удаляются, диагностические логи
сохраняются. Машинный результат скрипта остаётся отдельным JSON в stdout.
