# Kafka SASL SCRAM: listener, application accounts и ACL

Дата: 2026-10-20. Статус: **Реализация завершена, стендовая приёмка ожидается**.
KS-P04/KS-P05 закрыты PLAN recheck; KS-D01 закрыт targeted recheck;
KS-D02 отклонён владельцем. Исторический FULL DIFF BLOCK сохранён.
Установка на стенде пока не разрешена.
Владелец поручил подготовить и сохранить план, проверить Java-приложения,
исключить четыре приложения из Kafka scope и использовать существующие настройки
остальных приложений вместе с JAAS через Vault Agent. Затем владелец разрешил
реализацию с приоритетом обычных Ansible tasks, запретив установку на стенде.
Target mutation, миграция и запуски не разрешены.
Текущий статус и разрешения остаются в [CURRENT_STATE](../../../CURRENT_STATE.md).

## 1. Результат и существующая основа

Добавить клиентский Kafka listener `SASL_SSL` с SCRAM и обеспечить приложениям
пользователей и ACL через действующий механизм библиотек:

- topics — существующие библиотечные ресурсы `kafka.topic`;
- пользователь и grants — существующий application account экземпляра;
- credentials — существующая runtime custody и публикация в Vault;
- JAAS — existing Vault Agent ENV templates перед запуском приложения;
- listener — существующие library defaults, override и Reset.

Опорные контракты: [проект](../../project-contract.md),
[Core](../../ansible-core.md), [Kafka topics](kafka-topics-plan.md),
[library connections](library-connections-history-plan.md),
[A4 Vault/Agent](milestones/a4/a4-technical-plan.md) и
[A5 providers](milestones/a5/a5-technical-plan.md).
Прежний A5 SSL-only scope не является доказательством SCRAM acceptance.

Не вводить отдельный desired-state store, provider framework, Go/UI resolver,
параллельный runner или второй способ управления секретами. Ansible/YAML остаётся
поверхностью сопровождения; небольшие изменения существующих Python projections
нужны для target-free validation, snapshot и планирования. Go сохраняет guarded
writer/transport, React редактирует контракт и показывает результат Core.

## 2. Scope после проверки Java-приложений

### Включённые приложения

Проверены фактические JAR и байткод контейнеров на `192.168.56.102`, включая
остановленные контейнеры; состав контейнеров также просмотрен на `.101`.
Проверка выполнена чтением, без запуска приложений, смены конфигурации или
SCRAM-подключения. Это свидетельство возможности конфигурации, не runtime PASS.

| Приложение | Проверенный образ, tag | kafka-manager |
| --- | --- | --- |
| alarm-view-service | 0.4.0-96e90ee0-redos | 1.7.17 |
| alarm-service | 0.4.2-3a1d508c-redos | 1.7.17 |
| hmi-backend | 1.2.11-45c5e804-redos | 1.7.17 |
| kafka-history-writer | 0.0.67-412ebcbf-redos | 1.7.17 |
| kafka-ch-replicator | kafka-ch-replicatior:0.0.5-SNAPSHOT-14953056-redos | 1.7.17 |
| sdku-knp | 0.2.4-a4568c87-redos | 1.7.17 |
| sdku-vtor | 1.2.8-c8f4f8a5-redos | 1.7.17 |
| sdku-telemechanics | 1.2.3-6aa0b4a0-redos | 1.7.17 |
| sdku-tank-farm | 1.2.1-3091dc07-redos | 1.7.15 |
| sdku-status-calculation | 0.5.0-1508923e-redos | 1.7.17 |
| evo-manager | 3.10.21-eedea228-redos | 1.7.15 |

Image registry: `evoscada-docker.artifacts.tn.tngrp.ru`. Tags фиксируют объекты
проверки; при реализации привязать acceptance к фактическим image IDs/digests,
поскольку сам tag не доказывает неизменность образа.

Во включённых JAR найден `kafka-clients-3.9.1.jar`. В проверенном клиентском JAR
присутствуют `ScramLoginModule` и `ScramSaslClient`. Общие библиотеки совпадают
по SHA-256 между проверенными приложениями соответствующей версии:

- kafka-manager 1.7.17: `2e225c2b228f302b95aa7dc4ddb04d503b4ab140b3e1108ed3acb157bac4d93d`;
- kafka-manager 1.7.15: `af5c4ea983a2e03e6f16a6a29dd7599435aa9f83be2ee6223e58f20170459535`.

`KafkaManagerConfig.processSslProperties()` задаёт `security.protocol=SSL` и
`sasl.mechanism=PLAIN` через `putIfAbsent`, затем выполняет
`putAll(sslProperties.getProperties())`. Поэтому произвольные properties позволяют
выбрать `SASL_SSL` и `SCRAM-SHA-512`. Consumer/producer paths вызывают этот метод.
В общей библиотеке есть bindings `kafka.consumer`, `kafka.producer` и
`spring.kafka.ssl`; использовать существующие карты, не предполагать, что все
приложения используют стандартные Spring Boot consumer properties.

Особенности, обязательные для настройки и acceptance:

- `alarm-view-service`: `KafkaListenerFactoryConfiguration.alarmMessageConsumerFactoryWS()`
  сначала задаёт SSL/PLAIN, затем также применяет `SslProperties.getProperties()`.
  Собственные `KafkaProducerConfiguration` и `KafkaConsumerConfiguration`
  принимают `custom-kafka.ssl.properties`. Настроить общий и custom paths;
  двух ENV `KAFKA_SECURITY_PROTOCOL`/`KAFKA_SASL_MECHANISM` недостаточно для всех
  factories. Проверить consumers и producers, а не только health probe.
- `kafka-ch-replicator`: `KafkaStreamConfig.kafkaStreamsConfiguration()`
  наследует consumer configuration и накладывает streams properties.
  Проверить итоговые SASL settings именно Kafka Streams, включая ACL для
  внутренних topics/groups, требуемых фактической topology.
- `KafkaManagerConfig.lambda$consumerConfigs$1()` пишет consumer properties на
  TRACE. Секретный `sasl.jaas.config` не помещать в эту карту; использовать
  существующие producer/consumer SASL JAAS ENV и безопасный уровень логов.

### Исключённые приложения — решение владельца

`data-manager`, `user-preferences`, `evo-scheduler`, `ef-backend` исключены из
Kafka SCRAM scope: владелец подтвердил, что Kafka connections им не нужны.
Не добавлять им Kafka accounts, ACL, JAAS, secrets или миграцию подключений.
Изменение Java-кода `data-manager` не является задачей этого плана.

## 3. Listener и существующие defaults/override

Добавить именованный client listener с протоколом `SASL_SSL`, первоначальным
механизмом `SCRAM-SHA-512` и явно настраиваемым портом. Имя listener не является
протоколом: selector ссылается на имя из конфигурации выбранного deployment.
Расширить `services/kafka/service.yml`, генерируемые schemas, общие listener/runtime
и PKI projections, Ansible Apply/Verify/diagnostics. TLS должен распознаваться
также для `SASL_SSL`, а не только при сравнении протокола с `SSL`.

Выбор приложения проходит через существующий
`connection_defaults.kafka.connectionRef`: package default библиотеки →
deployment override в `group_vars`; Reset удаляет override. Приложение выбирает
существующий library connection key. Новый per-instance listener override этим
планом не вводится. Не дублировать selector в ENV, parameters или Go.

В derived connection projection передавать протокол, механизм SASL, TLS и ссылки
на credentials без их значений. Ошибка выбора listener блокирует план; fallback
на SSL после ошибки SASL отсутствует. Проверить все CLI callers с предположением
о единственном listener purpose, а также listener выбора provider topics.
Административное соединение provider не должно зависеть от ещё не созданного
application account.

Inter-broker/controller сохраняют SSL transport. SASL_PLAINTEXT, перевод внутренних
соединений на SASL, reformat KRaft и удаление данных не входят в scope.

## 4. Application accounts, topic/group ACL и ownership

Расширить capability Kafka и существующий `accounts.<connection>` для Kafka.
Использовать имеющиеся `credentials` descriptors и `mode: managed|existing`.
Topic остаётся ресурсом библиотеки; application account не становится новым
library resource kind. Один logical account на instance независимо от placements.

Типизированные grants ссылаются на logical resource keys выбранных topics;
Core проверяет совпадение Kafka provider с connection. Физические topic names
получаются из тех же ресурсов, которые создаёт библиотечный hook. Операции на
consumer groups задаются явно. TransactionalId и Cluster IdempotentWrite выдаются
явно по потребности приложения. Не выдавать автоматически wildcard/admin rights
и не считать выбор topic автоматической выдачей ACL.

До mutation проверить конфликты principals между библиотеками/instances и
существующими Kafka users. У principals/ACL Kafka нет нашего owner marker:
совпадение username не доказывает владение. До реализации согласовать минимальную
проверяемую связь managed principal с существующей credential custody; при
неопределённости BLOCK. Новый реестр desired-state ownership не предлагается.

Первый scope обеспечивает наличие заявленных ACL; destructive reconciliation,
автоматическое удаление accounts/topics и rotation не входят в scope. Если
декларация прав уменьшена, retained permissions/drift должны быть явно показаны,
а не представлены как выполненный отзыв прав. Для строгой синхронизации ACL
потребуется отдельно согласовать доказуемую границу удаления.
`existing` проверяет наличие, credentials и требуемые права без mutation.

## 5. Порядок hooks, secrets и Vault Agent

```text
Общий provider preflight
  → library Kafka topics
  → instance SCRAM account и ACL
  → authenticated check
  → existing Vault instance KV / policy / AppRole
  → Vault Agent materialization
  → приложение с existing Kafka settings и JAAS
```

Расширить действующие libraryJobs/instanceJobs и provider Apply/Verify stages;
переиспользовать Vault hooks и account secret bindings. Kafka metadata хранит
SCRAM verifier, Vault/runtime custody — исходные credentials. Пароли не входят
в portable desired state, plan, events, logs, audit или аргументы процессов.

Сначала использовать штатные Kafka CLI и builtin Ansible tasks. До выбора
mutation interface проверить на поставляемой Kafka 4.3.1 безопасный файловый
ввод credentials, escaping и cleanup. Helper допускается только при доказанной
невозможности безопасно выполнить нужную операцию штатным интерфейсом.
Temporary secret files ограничить существующей защищённой custody и удалять
через `always` при успехе и ошибке.

Повторный Apply описывает mechanism metadata и аутентифицируется существующим
секретом; он не сбрасывает пароль. Несовпадение credentials блокируется, не
превращается в скрытую rotation. Verify остаётся read-only.

Уточнение KS-P02, выбранное владельцем после выявления несовместимости regular
file templates с Vault Agent process-supervisor: использовать KAFKA_PRODUCER_SASL_JAAS_CONFIG и KAFKA_CONSUMER_SASL_JAAS_CONFIG ENV,
без file templates, wrapper или изменения entrypoint. Existing Agent env_template
формирует полную строку ScramLoginModule из account credentials и передаёт её как
runtime-only producer/consumer SASL JAAS ENV. Existing application Kafka property maps принимают
соответствующие ENV в `sasl.jaas.config`; при необходимости явной ссылки compose сохраняет её через `$$`, Spring
подставляет значение после Agent injection. В JAR проверены именно произвольные
карты properties; отдельного hardcoded alias JAAS_CONFIG в проверенных artifacts
не найдено. Пароль не входит в shell/JVM argv, desired state или plaintext `.env`.
Закрытое форматирование Kafka JAAS расширяет existing secret binding, не добавляет
универсальные операционные шаблоны. Existing supervisor отвечает за готовность
ENV, restart/signals/exit code; секрет остаётся в Java environment как остальные
existing Agent ENV secrets. Package default logging для KafkaManagerConfig — INFO:
его TRACE consumer property logging несовместим с secret sasl.jaas.config.

Protocol/mechanism/bootstrap настройки остаются обычной package configuration:
выбранный listener, `security.protocol=SASL_SSL`, `sasl.mechanism=SCRAM-SHA-512`
и существующие TLS settings. Применить их ко всем активным factory paths каждого
включённого приложения. Обновление Java images для этого пути не планируется;
runtime acceptance должно подтвердить статические выводы.

Уточнение владельца 2026-10-20 после ручной проверки alarm-view: сохранять в Vault
username/password, JAAS собирать existing Agent env_template. Для проверенного
JAR alarm-view legacy-флаги KAFKA_ENABLE_SSL, SPRING_KAFKA_SSL_ENABLE_SSL и
spring.kafka.ssl.enable-ssl не задавать: WS factory при true принудительно
выставляет SSL/PLAIN. В выбранных SASL SDKU/CSPA runtime-library defaults эти
флаги убраны; TLS задаётся явными Kafka security.protocol=SASL_SSL и
ssl.truststore.*. Проверка одного CSPA-контейнера подтвердила все factory paths,
SCRAM, truststore и HTTPS hostname validation; это не закрывает normal-plan
и остальные application acceptance gates. Подробности в SDKU/CSPA journal.

## 6. Decision gate: cluster-wide authorization и переход SSL

`StandardAuthorizer` действует на кластер, а не только на новый SASL listener.
Текущая TLS materialization задаёт stores, но сама не включает `ssl.client.auth`.
Поэтому сохранение SSL transport не гарантирует прежний доступ anonymous clients.

До исполнения проверить identities и grants для provisioning/admin,
brokers/controllers, Schema Registry и используемых legacy SSL clients.
Владелец уточнил конечную политику: anonymous сохраняет операции topics/groups,
включая CRUD topics, но users/ACL администрирует только `admin`. Явные ACL
`User:ANONYMOUS`: Topic/Group/TransactionalId All на wildcard names, Cluster
Describe/IdempotentWrite. Cluster All/Alter и права управления users/ACL не выдаются.
Legacy endpoint остаётся обходом ограничений SCRAM accounts на данные, но не
на управление безопасностью. Не добавлять anonymous в superusers и не включать
`allow.everyone.if.no.acl.found=true`.

Единственный конечный superuser — `User:admin`. `adminCredential.passwordSecretRef`
обязателен в desired configuration до построения плана; secret requirement
`kafka-admin-password`/SERVICE_PASSWORD проходит существующий runtime-secret
Broker/lease канал и диалог. Секретные значения не сохраняются в проекте/плане.
В metadata setting используется `x-runtimeSecretRequired: true`: generic Core
planner блокирует отсутствующую ссылку, не создавая Kafka-specific Go resolver.
`x-runtimeSecretDeploymentBound: true` включает существующий opaque identity
алгоритм для пары deployment/manifest requirement и purpose. Логическое имя
остаётся в manifest и desired SecretRef; публичный requirementRef выдаёт Core.
Existing Broker pending typed custody хранит один такой password на deployment
до Core attestation, затем переносит его в существующий password map/lease.
Go не вычисляет opaque identity. Два Kafka deployments могут использовать
одинаковую логическую ссылку, но получают независимые requirements и файлы.
Service files остаются deployment-scoped; library jobs используют публичный
runtime alias, исключая неоднозначное lookup по логическому имени.
Создание admin происходит как часть одобренного SERVICE_APPLY, не вне плана.

Владелец разрешил временный bootstrap exact member certificate identities с
обязательным удалением их из superusers до успешного завершения Apply:

1. Проверить runtime admin input и подтвердить финальное состояние работающих
   процессов всех участников. Требуются единственная финальная строка super.users,
   regular config file, active systemd MainPID, JVM command line с точным config
   path и ExecMainStartTimestamp строго позже config mtime. MainPID/startup/state
   повторно проверяются после чтения /proc, чтобы отвергнуть смену процесса.
   Если каждый процесс доказанно запущен с финальным файлом, bootstrap не нужен.
   Verify при незавершённом bootstrap блокируется без исправления.
2. Собрать identities выбранных PKI Kafka members штатным openssl до изменения
   authorizer; установить bootstrap superusers admin плюс эти exact identities.
   SSL client auth requested сохраняет клиентов без сертификата. Registry уже
   использует member certificate; сторонние cert-present clients автоматически
   не получают права.
3. Запустить quorum/brokers, один раз на deployment через временный mTLS доступ
   создать отсутствующий SCRAM admin из plan-declared runtime input. Существующий
   admin обязательно аутентифицируется; пароль не сбрасывается при несовпадении.
4. Переключить служебный CLI на SCRAM admin. Выдать anonymous только data ACL;
   member certificates получают legacy data ACL и ClusterAction/Describe/
   IdempotentWrite для внутренних связей, но не superuser/users/ACL права.
5. Удалить все временные certificate superusers из локальных конфигураций,
   перезапустить всех участников bootstrap, включая interrupted finalization,
   дождаться listeners и повторно подтвердить runtime proof каждого member.
   Только после этого
   разрешены обычный SERVICE_VERIFY и library stages. Повтор finalized Apply
   не возвращает временные privileges и не меняет пароль.

При ошибке до финализации SERVICE_APPLY неуспешен, library stages заблокированы;
повтор входит в тот же явный bootstrap sequence по отсутствию доказательства
финальной running configuration, даже если файлы уже финальные.
Автоматический rollback и скрытая rotation не предлагаются.
Application accounts не могут называться admin или получать административные
Cluster operations; application Cluster grants ограничены Describe/IdempotentWrite.
Если trusted bootstrap/admin path отсутствует, выполнение блокируется.

Проверить описанный порядок активации и interrupted transition с повтором
на трёх brokers с сохранением административного доступа и здоровья internal/Registry
connections. Для существующего SCRAM account наличие подходящего mechanism и
успешная аутентификация из existing credential custody являются проверяемой
границей possession; несовпадение блокирует захват/изменение. Удаления ACL нет.

Основание: [Kafka SASL](https://kafka.apache.org/43/security/authentication-using-sasl/)
и [Kafka authorization/ACL](https://kafka.apache.org/43/security/authorization-and-acls/).

## 7. UI и документация при реализации

Расширить существующие service listener, library defaults и application
accounts/grants формы, typed Wails transport и guarded writer. Сохранить
Review/Save, Reset, reopen, Project Verify и обычный свежий approved execution plan.
UI показывает Core effective values и не вычисляет Ansible precedence или права.

Проверенные [UI design](../../design/ui-design-01.md) и
[mockups](../../design/ui-design-01-mockups.html) сейчас не описывают полный Kafka
SCRAM account/ACL flow. До UI coding согласовать дополнение существующих форм,
затем повторить design check на acceptance. Новые самостоятельные вкладки,
credential store и runner не нужны. При реализации синхронизировать затронутые
versioned contracts, service capabilities и архитектурные документы; текущий
план сам по себе не объявляет новую capability реализованной.

## 8. Последовательность реализации и acceptance

1. Согласовать decision gates authorization/bootstrap и managed ownership.
2. Расширить Kafka listener/service contract и standalone Ansible Apply/Verify.
3. Расширить existing account/grants projection и Kafka provider hooks.
4. Добавить JAAS в existing Vault Agent materialization и настройки 11 packages.
5. Дополнить существующие Go/UI формы и guarded edit flow.
6. Выполнить focused checks, независимый FULL DIFF и реальную acceptance после
   отдельного разрешения соответствующих запусков.

Core tests запускаются на RED OS из текущего working tree по
[QA procedure](../../agent-procedures/qa.md). Проверить target-free resolve,
schema/capability errors, SSL/SASL selection, references, группы, collisions,
host-independent logical accounts и отсутствие значений секретов в projections.

Реализация и focused source QA завершены с учётом решений владельца.
Свежий standalone target-free SCRAM snapshot — PASS: 1 test, 18.289s;
подробные результаты и границы проверок — в [журнале](evidence/kafka-scram-journal.md).

### Оставшиеся проверки

- Подготовить и опубликовать проверенный runtime bundle, соответствующий исходникам,
  перед зависимыми UI/стендовыми проверками.
- Пройти реальные React/Wails flows: default/override/Reset, accounts/grants,
  Save/reopen, Project Verify и свежий план для точной saved revision/runtime.
- Проверить SCRAM и ACL на isolated standalone и трёх brokers: разрешённые операции,
  отрицательные проверки пароля/topic/group, anonymous topic/group compatibility
  и единственного admin при штатной конфигурации.
- Проверить bootstrap/finalization, прерывания и восстановление, Apply/Verify/repeat,
  отсутствие лишних изменений и очистку временных credential files.
- Проверить все используемые Kafka factory paths 11 приложений, доставку обоих JAAS
  ENV через Vault/Agent, Streams internal resources, Registry и internal connections.
- Проверить отсутствие секретов в логах, включая global TRACE; визуальную проверку
  фиксировать отдельно от функциональной приёмки.

Ни одна из этих оставшихся проверок не считается выполненной этим обновлением
статуса. Стендовые запуски требуют отдельного разрешения владельца.

### Условия оставшейся приёмки

Реальная Kafka проверка на isolated standalone и трёх brokers: создание account,
SCRAM authentication, разрешённые produce/consume и отказ для неверного пароля,
чужого topic/group; проверка всех используемых application factory paths,
JAAS через Agent, Registry и внутренних соединений. Для Streams учитывать
фактические внутренние resources. Повтор не сбрасывает пароль, не создаёт лишние
ACL/KV writes/restarts; Verify не изменяет targets. Проверить partial failures,
temporary-file cleanup и interrupted authorization transition.

Для включённых 11 приложений зафиксировать image identity, listener, group/topic
selections и наблюдаемый результат SASL-соединений. Исключённые четыре приложения
не получают Kafka account/JAAS и не входят в эту acceptance matrix.

Реальный React/Wails flow: default/override/Reset, accounts/grants, Save/reopen,
Project Verify, fresh revision/runtime-bound plan и отдельно разрешённый запуск.
Bundle-dependent проверки следуют обычной verified publication в active cache
по [bundle procedure](../../agent-procedures/runtime-bundle.md).
Статические выводы, automated tests, real bridge, визуальная и target acceptance
фиксируются отдельно. Source QA PASS не означает real bridge или стендовую SCRAM приёмку.

## 9. Review provenance

В этой сессии выполнен один независимый FULL PLAN review исходного восьмичастного
draft: `APPROVE_WITH_CHANGES`, ноль blocking findings. Fingerprint исходного
review artifact: SHA-256
`B760E57BBA321AC7C109EF1005AAA6E4E1B06B69A13B7D2813165CFC60BEC110`;
исходный HEAD: `930d5f71a83e3be99901ea40e2af6464394526f5` с существующим dirty tree.
KS-P01 (nonblocking): явно описать preparation/enforcement sequence и interrupted
authorization recovery. Дополнение включено в §6 и §8.

После исходного review владелец уточнил исключение четырёх приложений, два
JAAS ENV, обязательного admin и допустимость временного certificate bootstrap.
Для materially changed owner-approved admin/security revision выполнен новый
независимый FULL PLAN: **BLOCK**, KS-P04 и KS-P05. Проверенный SHA-256:
`B00C47DBF8AC18675B99B5E38A19BFB6C6029F8312C5B4AADA2EFE2FFF24CE73`.
Этот документ после записи findings уже не является тем же snapshot.
Полный результат и предложенные исправления сохранены в
[отчёте](reviews/kafka-scram-admin-plan-review.md).
Владелец принял обе минимальные коррекции: «KS-P04 принято KS-P05 - принято».
Реализация продолжена в согласованной границе. Единственный разрешённый
[TARGETED_RECHECK](reviews/kafka-scram-admin-plan-targeted-recheck.md) завершён:
**APPROVE**, KS-P04/KS-P05 RESOLVED на уровне плана, zero blocking.
Проверенный SHA-256: `8DF2F1F37AB98328A3BD4CDE39FC3B004B29ED77231511468EF2C6643F98FAF5`.
После записи результата текущий документ уже не является тем же snapshot.
DIFF approval и SCRAM acceptance этим recheck не заявляются.

## 10. Принятые владельцем исправления после BLOCK

- **KS-P04:** считать bootstrap завершённым только после доказательства, что
  каждый работающий member запущен с финальным `super.users=User:admin`.
  Проверять фактически загруженную конфигурацию либо подтверждённый запуск с
  финальным файлом через существующие Kafka/systemd средства. Несовпадение или
  отсутствие доказательства блокирует Verify; Apply перезапускает требуемые
  members и повторно проверяет состояние до SUCCESS. Один файл не служит
  доказательством. Новый persistence store не вводится. Нужны interruption
  проверки после записи файла до restart и после restart одного из трёх members.
- **KS-P05:** оставить логическое имя `kafka-admin-password` в manifest, но
  формировать deployment-bound requirement identity существующим механизмом
  `_secret_input_requirement_ref()`. Тот же идентификатор проходит plan,
  существующий runtime-secret Broker/lease и materialization. Не ограничивать
  проект одним Kafka deployment и не вводить второй канал секретов. Проверить
  два независимых Kafka deployments, раздельные inputs и блокировку только
  deployment с отсутствующей ссылкой/input.

Владелец согласовал обе коррекции и продолжение: исправить реализацию и выполнить
один TARGETED_RECHECK только KS-P04/KS-P05 и непосредственно затронутых границ.

## 11. Решение владельца по FULL DIFF

[FULL DIFF](reviews/kafka-scram-diff-review.md) зафиксирован по 93-file scope
`B2180611562B78362006A6A65A9D358827A3009484DAA8907F053DDCC20EAEF3`.
Его исторический verdict BLOCK сохранён; KS-P04/KS-P05 закрыты отдельным PLAN review.

- **KS-D01 — RESOLVED, TARGETED_RECHECK APPROVE.**
  Account/security job использует отдельные административные SASL candidates из
  resolved service listeners через existing resolve_connection. Admin requirement
  и runtime alias не зависят от первого library client selector. Existing provider
  action привязывает к admin candidate точный PKI materialization plan deployment/member.
  Account hook использует admin candidate; проверка app credentials — собственные
  account candidates. Topic-only legacy SSL и per-library defaults сохраняются.
  Проверки охватывают оба порядка SSL topic-only/SASL account, managed/existing,
  ambiguous admin listener и неверную PKI привязку. Один TARGETED_RECHECK ограничен
  KS-D01 и непосредственно затронутыми границами.
- **KS-D02 — OWNER_REJECTED.** Владелец явно отклонил предлагаемое резервирование
  principal mapping/builder: пользователь вправе произвольно менять конфигурацию.
  Новые запреты не вводятся. Это решение владельца, а не техническое устранение
  замечания и не положительный verdict ревьюера. Гарантии exact member DN и
  `super.users=User:admin` относятся к штатной конфигурации; при пользовательских
  mapping/builder overrides эффективные identities определяет эта конфигурация.
- **KS-D03 — неблокирующая коррекция.** Перед необходимыми обычным config restart
  и bootstrap-finalization restart добавлена секундная временная граница обычной
  Ansible task. Strict runtime proof сохранён; fixture использует секундную
  точность systemd timestamps. Verify и неизменённый repeat не ждут и не рестартуют.

Решение владельца не разрешает установку или запуск приложений на стенде.
Независимый [TARGETED_RECHECK KS-D01](reviews/kafka-scram-d01-targeted-recheck.md)
завершён APPROVE в scope KS-D01, blockers0. Проверены 11/11 fingerprints по
scope `05839E1A6DD0C18C1E42D7962A6DE5C03B6AC21F051DA5F3219781F2F5DE11FE`.
KS-D02 не пересматривался и не получил reviewer-resolution. Последующая правка
этого плана фиксирует результат review; проверенные production sources сохранены.
Актуализация QA 2026-10-20: повтор standalone target-free SCRAM snapshot на
основном RED OS узле .101 завершён **PASS: 1 test, 18.289s**, без увеличения
таймаута60s. На .102 сохранялась высокая нагрузка; .101 использован с меньшей
нагрузкой. Подробности и предыдущие timeout попытки сохранены в
[журнале](evidence/kafka-scram-journal.md#target-free-scram-repeat-after-load-check--2026-10-20).
Production sources не менялись; стендовая установка и real acceptance не выполнялись.


### Штатные Kafka Apply/Verify: исправления 2026-10-21

Отдельно разрешены исправления M01–M06 и подготовки admin inventory обычными
Ansible tasks, с изолированной проверкой. Сохраняются sole-admin и anonymous
data-access policy, runtime SecretRef и существующая PKI. Последовательная
финализация проверяет admin/quorum перед отзывом следующего member. Подробности,
QA и ограничения: [PEM journal](evidence/kafka-pem-journal.md#kafka-m01m06-source-repairs-and-admin-inventory--2026-10-21).
Штатная стендовая приёмка и cold-start/recovery остаются открыты; новая установка
или публикация runtime этим заданием не разрешены.

Read-only стендовая проверка текущей роли 2026-10-21 PASS на трёх узлах:
changed=0/failed=0/unreachable=0, admin SCRAM/ACL, PEM/TLS, quorum, broker
registration, Registry HTTP/HTTPS и исходные PKI/data checksums. Apply, rolling
bootstrap, cold-start/recovery и реальный Installer flow не запускались;
подробности и границы в [журнале](evidence/kafka-pem-journal.md#read-only-stand-verify-of-existing-qa-kafka-structure--2026-10-21).
