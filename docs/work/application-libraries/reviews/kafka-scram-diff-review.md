# Kafka SCRAM — FULL DIFF review

Дата: 2026-10-20. Независимый read-only reviewer
`/root/scram_compatibility_plan_review`, роль `architecture-reviewer`.
Вердикт: **BLOCK**, unresolved BLOCKING **2**.

База: `930d5f71a83e3be99901ea40e2af6464394526f5`, dirty tree.
[Frozen scope](kafka-scram-diff-scope.json) SHA-256
`B2180611562B78362006A6A65A9D358827A3009484DAA8907F053DDCC20EAEF3`.
Reviewer подтвердил 93/93 fingerprints повторно в конце.
Проверенный план: `273262E0E617DDBCD377243DA232A847ED96D1A32ED641107AD0662D68219C59`;
project contract: `D497327CD3B74466087D05E66A1F9576AF3306DD39C3DC9766D68EE8F6E7D598`.
Scope: Kafka hunks и прямые Core/provider/secret/Go/UI/package boundaries.
Существующие dirty Redis/resource изменения не атрибутированы этой реализации.

## KS-D01 — BLOCKING, OPEN: административный transport зависит от первой библиотеки

`application_providers.py:144–170`, provider(ref); `application_accounts.yml`,
`application_accounts_scope.yml`. Cached provider job выбирает candidates из
client defaults первой библиотеки; adminPasswordRef добавляется только при её
SASL targets. Для SSL-библиотеки A и SASL/account-библиотеки B того же deployment
hook B использует cached SSL/member-certificate transport. После финализации
сертификат лишён Cluster Alter, поэтому users/ACL provisioning не работает.

Минимальное исправление: отдельный однозначный admin SASL candidate и обязательный
admin requirement для account/security jobs, независимо от client defaults.
Переиспользовать existing connection projections, без нового resolver/framework.
Проверки: SSL topic-only + SASL managed account, оба порядка библиотек;
одинаковый admin transport при независимых client projections; existing/Verify.

## KS-D02 — BLOCKING, OPEN: advanced config может изменить principal authority

`services/kafka/service.yml`, x-reservedAdvancedProperties; `main.yml:275–298`,
`member.yml:150–158`, `authorization_identity.yml`. Global
ssl.principal.mapping.rules и principal.builder.class не защищены guards,
хотя bootstrap использует exact certificate subject. Разрешённый mapping
может отобразить TLS certificate в User:admin и сохранить superuser-доступ
после удаления certificate DNs из super.users. Другие mappings ломают bootstrap.
Основание: [Kafka principal mapping semantics](https://kafka.apache.org/43/security/authorization-and-acls/).

Минимальное исправление: запретить overrides default principal authority через
существующие manifest/Core/deployment/member advanced guards, либо разрешать
только доказанно эквивалентные defaults. Собственный mapping resolver не нужен.
Проверки: target-free и standalone role reject global/listener mapping в admin
и custom principal builder; штатные exact member principals сохраняются.

## KS-D03 — NON_BLOCKING, OPEN: секундная точность systemd timestamp

`authorization_status.yml:18–70`, `qa_kafka_authorization_status.py:68–73`.
Fixture использует доли секунды, а реальный systemctl может отдавать секунды.
Запись config и restart в одной секунде дадут безопасный ложный отказ strict
start > mtime. Добавить integer-second fixture и консервативное восстановление,
например ожидание следующей временной границы перед restart. Runtime proof
не ослаблять. Проверить same/different second, старый процесс, interruption.

## Остальные выводы

KS-P04/KS-P05 сохраняют исправления на уровне плана. Подтверждены existing
provider/account flow, файловый Kafka CLI input, отсутствие скрытого password
reset, authentication перед adoption/grants, additive ACLs, read-only Verify,
existing Broker/lease и Agent env_template supervisor. 11 packages содержат
обе JAAS bindings/formatter и INFO logger. Overengineering findings: 0.
Новых production Python executable, secret store, transport, daemon/sidecar
или lifecycle subsystem нет. Для D01/D02 достаточно existing selectors/guards.

Тесты reviewer самостоятельно не запускал; source QA взят из parent/journal.
Targets не посещал, секреты не читал, файлы не менял. Real React/Wails,
live Kafka transition, application connections и logging acceptance отсутствуют.
Review validity относится к указанному frozen scope; исправления не покрыты
этим verdict автоматически. Установка не разрешена.

Следующее действие по процедуре: остановить заблокированные границы, передать
владельцу D01/D02 и минимальные коррекции. Один TARGETED_RECHECK потребует
owner approval исправлений; автоматический повтор этим отчётом не разрешён.
