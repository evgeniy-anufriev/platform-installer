# Kafka и Schema Registry: PEM без паролей PKCS12 в properties

Дата: 2026-10-20. Реализация и isolated QA завершены. Позже владелец разрешил
отдельное ручное обновление существующего qa-kafka-structure без перевыпуска PKI.
Kafka/Registry на трёх узлах обновлены; ручные компонентные проверки PASS.
Штатная автоматическая приёмка остаётся открытой: реальные ошибки KAFKA-M01–M06
перечислены в [журнале](evidence/kafka-pem-journal.md). В production-коде они
не исправлены в рамках ручного запуска. Приложения и соседние deployment
этот запуск не обновлял.

## Scope и существующая основа

Повторно используются PKI-01 requests/materializationPlans и точная привязка
host/deployment/member/profile. PKI уже выдаёт private-key.pem (PKCS#8 через
openssl genpkey), certificate.pem, ca-chain.pem. Новых resolver, secret store,
transport, UI полей, identities или ACL policy нет.

platform_kafka_store_type по умолчанию PEM; явный PKCS12 override сохранён.
PEM-потребители не читают storePasswordSecretRef и не записывают пароли stores
в properties. Общий PKI pipeline продолжает выдавать существующие форматы и
может требовать пароль для PKCS12/других Java-потребителей. Удаление этого
глобального требования и изменение PKI Java-приложений вне scope.

## Реализация

1. Existing resolve_tls_runtime.yml выбирает тип/пути в одной runtime projection,
   проверяет exact request и serverAuth/clientAuth; store password нужен только
   при explicit PKCS12. Неверный формат блокируется без fallback.
2. Обычные Ansible stat/slurp/command/copy формируют identity.pem из незашифрованного
   PKCS#8 key и certificate chain. Проверяются формат и соответствие key/cert.
   Consumer directory0700, identity0600, сервисные owner/group, no_log/diff=false.
3. Broker/controller listener properties и CLI используют выбранные пути. Verify
   существующего PEM проверяет checksum/права/владельца и доверие без ремонта.
   Apply/repeat учитывают изменения identity при решении о restart.
4. Library-only topic/account hooks и SCRAM bootstrap собирают identity.pem внутри
   существующей invocation-private directory с always cleanup. Service Apply
   не нужен; authoritative PKI targetDirectory не меняется. Постоянные consumer
   copies остаются только в owned Kafka/Registry directories.
5. Schema Registry остаётся на SSL listener. Kafka client, HTTPS и inter-instance
   TLS используют PEM; explicit PKCS12 сохраняет прежнюю доставку пароля.
   Не удалять старые файлы установленных сервисов. Смена формата требует отдельно
   разрешённого Apply; Verify старого PKCS12 под новым PEM default должен отказать
   без изменения targets, либо оператор выбирает explicit PKCS12 override.

## Изолированная проверка

Только свежие исходники на RED OS, transfer/cleanup через qa-sync. Synthetic PKI
и временные каталоги, существующие Kafka4.3.1/rest-utils8.3.2/JDK21 binaries;
без загрузки артефактов и изменения установленных unit/process/data.

- PEM Apply/repeat/Verify без password input; exact source/consumer custody.
- PKCS12 override с корректным input и отказ без него; invalid type/wrong request.
- Verify до перехода, повреждение bundle/права и key/cert mismatch: отказ без ремонта.
- Library-only hooks, success/error cleanup, authoritative source hash unchanged.
- Реальный Kafka SSL engine и Registry HTTPS PEM loader: загрузка rendered configs,
  loopback TLS handshake с проверкой CA/hostname/client certificate.
- Актуальные service/Registry/Core contract tests и syntax checks.

Полная трёхузловая и React/Wails/стендовая приёмка остаётся отдельным gate.

## Review

FULL PLAN APPROVE_WITH_CHANGES, blockers0, reviewed fingerprint
DCDC05569DD4A69E696FED5DF3BB5156FF975A5E3B443D20EF75957464B1C66B.
PEM-P01/P02 incorporated: temp-hook boundary и explicit compatibility matrix.
[Независимый PLAN отчёт](reviews/kafka-pem-plan-review.md). Это уточнение документа,
а не повторный PLAN review. [FULL DIFF](reviews/kafka-pem-diff-review.md):
APPROVE_WITH_CHANGES, blockers0. Необязательное PEM-D01 исправлено: Registry
не создаёт лишние отдельные copies ключа/сертификата; существующие файлы не удаляет.
Работа изолирована в managed worktree kafka-pem от параллельных master edits.

Результаты и ограничения isolated QA: [журнал](evidence/kafka-pem-journal.md).
99 тестов и четыре syntax checks PASS; после PEM-D01 повторно выполнены два
native PEM/PKCS12 теста, PASS (208.561s).
Впоследствии выполнено разрешённое ручное обновление на трёх узлах, с прежними
сертификатами/ключами/CA и неизменными идентификаторами данных. Штатный отдельный
план не одобрялся и не запускался: его PKI reissue противоречил условию сохранения
сертификатов. Полный Installer Apply/Verify, cold-start и failure-path acceptance
не закрыты; ручной PASS не заменяет эти gates.
