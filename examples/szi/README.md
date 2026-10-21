# СЗИ — пакеты и первый этап установки

Библиотека содержит обычные пакеты `keycloak`, `grant-access`,
`grant-access-front`, `grant-access-audit` и `nginx`. На этапе 1 выбирается
только `keycloak`; остальные приложения необязательны и относятся к этапу 2.
Redis credentials для grant-access не требуются: это legacy.

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
и три согласованные группы сохранены. Повторный Apply не восстанавливает БД.

Пакет Keycloak объявляет два скрипта общего контракта, оба с `execution: once`:

1. `before_start`: временный service-account создаётся штатной командой
   `kc.sh bootstrap-admin service`. Временный процесс не публикует порты,
   HTTP management не требует серверного TLS keystore.
2. `after_ready`: через API создаётся постоянный admin с паролем из runtime
   secret, проверяется вход и удаляется временный клиент. Если admin уже
   существует, проверяется текущий runtime пароль; пароль не сбрасывается.

Core передаёт скриптам точные argv и защищённые файлы секретов. Docker,
Keycloak и особенности bootstrap принадлежат самим скриптам.
Последовательность и контракт описаны в
[техническом плане](../../docs/work/application-libraries/szi-stage1-technical-plan.md).

Основной Keycloak запускается в production режиме через Vault Agent.
Используются стандартные PKI `keystore.p12` и `ca-chain.pem`; пароль keystore
поступает через существующий `pki_credential` binding. PostgreSQL targets,
порты и имя БД выводятся из разрешённых подключений библиотеки.
Heap: `-Xms256m -Xmx1g`, лимит памяти по умолчанию `2G`.

## Внешние файлы пакета

Следующие файлы исключены из Git и должны передаваться отдельно:

- `application-packages/keycloak/1.0.0/assets/providers/*.jar` — девять плагинов;
- `application-packages/keycloak/1.0.0/assets/themes.tar.gz` — полная тема;
- `library-packages/szi/1.0.0/assets/keycloak-clean.dump` — чистая база без admin.

SHA-256 чистого дампа:
`5928ad8c51aa50e7528533e78e0b729eba915e23a9b96cf313384083c4f1eae8`.
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

Установка остальных приложений, создание служебного клиента grant-access и
интеграции других библиотек ещё не выполнены. Единый ключ интеграции —
applicationId: client ID Keycloak, nginx subpath, endpoint и аварийный маршрут.
Принятый redirect URL клиента: `https://nginx…/<clientId>/*`.
