# Полная установка после очистки стенда

## Область и текущий статус

Владелец2026-10-26 разрешил удалить созданные/используемые Installer ресурсы
стенда и выполнить полную установку инфраструктуры и библиотек.
Сценарий отдельный от принятого Stage3 PASS.

Цели:101 — СДКУ;102 — ЦСПА;103 — СЗИ. Инфраструктура — все развёртывания
исходного проекта Stage3, FULL_PROJECT, без пропуска проверки инфраструктуры
и без пропуска библиотек. Установка через реальные React/Wails handlers.

Статус: очистка101–103 завершена; первый полный run завершился FAILED на
Apply BIND. Причина воспроизведена и исправлена; готовится повторный полный
запуск с обновлённым bundle. Автоматический режим Docker прошёл отдельные тесты.

## Подготовка

- Master fast-forward синхронизирован с origin/master до2a8ce14f.
- Строгий SSH platform-automation/sudo-n на101–103 подтверждён.
- Read-only инвентаризация:23 контейнера, включая старые QA-экземпляры;
  дополнительные четыре старые Kafka/Schema Registry unit на102.
- Установленные данные: /data/qa-clickhouse, /data/qa-kafka-structure,
  /data/qa-postgresql, /data/qa-redis, /data/qa-vault-consumer;
  конфигурации/юниты/монтирования фиксируются в приватной QA-инвентаризации.
- Источник проекта и установочные артефакты сохраняются; OS/SSH и identity
  platform-automation необходимы для повторного развёртывания.
- Свежие исходники доставлены стандартным qa-sync на102 в
  /var/tmp/platform-installer-qa-87b4ba2d016c48d2913a04ea8579e556.
- Новый bundle собирается на102 из сохранённого проверенного runtime03
  и восьми образов. До очистки требуется validate/publish и проверка точной
  привязки нового проекта к digest.
- Проверка репозиториев выявила отличие доступных последних версий
  от установленных; восстановимость сервисных пакетов уточняется до удаления.

## Выполнение2026-10-26

- В репозиториях подтверждены нужные версии Vault1.21.2, Redis8.6.4,
  PostgreSQL16.14 и pg_auto_failover2.2. rpm-e-test выбранных сервисных пакетов
  на102 PASS; bind-utils сохранён как зависимость компонентов ОС.
- Новый bundle full-stack-clean-20261026-01:
  sha256:1d8df9e0027110795863bb0af6804dd8ce16a393e8f172e3d895e86a82474ec5.
  Standard builder на102, validate/publish и project bundle digest PASS.
-23 контейнера остановлены по сохранённой инвентаризации. Очистка удаляет
  контейнеры/образы и Docker state, выбранные unit/config/data/service accounts,
  сервисные RPM и tar-installed Kafka/Confluent, старые PKI/runtime witnesses.
  SSH/platform-automation, OS и общие зависимости, исходники и bundle сохранены.
- Владелец выбрал один FULL_PROJECT run и разрешил вывести существующий
  applicationVaultSources в UI. Добавлен выбор per-Vault без новых Core/Go
  правил или чтения значения токена. RUNTIME_INPUT — default;
  CURRENT_RUN_BOOTSTRAP — явный выбор для этой чистой установки. Изменение
  выбора сбрасывает отображаемый план; library-only использует RUNTIME_INPUT.
  Макет такого выбора не содержал; изменение согласовано владельцем.
- UI focused117 PASS, lint PASS, TypeScript/Vite build PASS. Первый тестовый
  запуск выявил неполную новую fixture InstallationState.plan; fixture
  исправлена и весь focused набор повторён PASS. Реальный bridge pending.

## Уточнения владельца: Docker

- Docker-пользователь — platform-automation, dataRoot=/data/docker.
- Среди запретов имён остаётся только root; списки admin/platform-automation
  удаляются. Общие UID/home/path/PKI проверки сохраняются.
- Добавляется режим auto: существующий пользователь используется после
  проверки пароля; отсутствующий создаётся с переданным паролем. Legacy
  create-user/existing-user сохраняются для сохранённых проектов.
- Пароль передаётся всегда через прежний accountCredential/runtime input,
  включая existing-user; неверный пароль блокирует Apply без смены пароля.
- На стенде platform-automation имел состояние LK. Владелец отдельно разрешил
  задать его пароль из существующего runtime-секрета Docker на101–103;
  SSH-ключ и sudo сохраняются. Это отдельная подготовка стенда, не скрытый
  сброс пароля ролью.

### Реализация и проверки

Существующая account-последовательность выделена в account.yml и выполняется
до DNF. Новая учётная запись получает пароль прежним openssl/chpasswd.
Существующая проверяется через системный libcrypt без изменения shadow;
значение поступает только через stdin под no_log. Стандартный PAM helper
unix_chkpwd отклонён как вариант: его локальная man-page запрещает прямое
использование приложениями и считает интерфейс внутренним.

Первый новый native Ansible набор PASS:9 комбинаций mode/name, создание,
повтор auto/existing-user/create-user с changed=0, неверный пароль и
заблокированный существующий пользователь. Содержимое shadow не изменяется
при проверке, вывод не содержит синтетические пароли. Runtime и validate
fixtures очищаются; проверка всей Docker suite и независимое FULL DIFF pending.
Каталог и21 generated file/fixture locks пересобраны стандартным генератором
на102; digest24519346. Требуется новый bundle после завершения проверок.

### Последующие результаты и ревью

- Все10 уникальных Docker tests успешно выполнены: root-native account test
  отдельно; полный набор от platform-automation OK/skip1. Ошибочный запуск
  всего набора от root сохранил3 fixture/environment failures: Path.home=/root
  запрещён как dataRoot, а foreign-owner fixture получала владельца root.
  Production/fixtures для исправления этих failures не менялись; повтор в
  предусмотренном непривилегированном окружении PASS.
- Go projectlifecycle/desktop/executionnode PASS.
- Разрешённая владельцем установка пароля platform-automation выполнена
  на101/102/103 из существующего защищённого Docker runtime input через stdin.
  UID1001, состояние PS и доступ по SSH-ключу подтверждены без вывода значений.
- Empty-state readback: на101/102/103 нет Docker storage, включая rootful,
  старого platform-docker, automation/admin rootless и /data/docker;
  нет процессов dockerd/containerd/rootlesskit.
- FULL DIFF (base2a8ce14f,32-file scope b0cbc9bc + Docker contract89244066)
  BLOCK: FSCI-D01 — race между getent и созданием мог привести к смене пароля
  чужого существующего пользователя. Владелец согласовал атомарный useradd,
  native race test и один TARGETED_RECHECK. Исправление и тест выполняются.
  Не блокируют: FSCI-N01 (UI не восстанавливает выбор источника с прежним
  планом), FSCI-N02 (verifier unavailable имеет тот же код, что mismatch).
- Проверенный промежуточный bundle02 92a96873 опубликован и staged;
  он не активирован для нового run и заменяется исправленным bundle03.
- FSCI-D01 исправлен: атомарный useradd; password hash/chpasswd только после
  успешного создания. Native Ansible3 PASS/25.753s, включая race. Единственный
  TARGETED_RECHECK APPROVE, blocking0; [review](../docker/full-stack-auto-account-review.md).
  Не блокирующие N01/N02 остаются открытыми, на речеке не перепроверялись.
- Core fixture/catalog7 и deployment plan34 PASS; стандартный каталог
  воспроизводим24519346. qa-sync Verify окончательного исходника82323a PASS.
- Bundle03 собран из этого исходника; validate/publish выполняются. Старые
  промежуточные remote01/02 удалены после проверки их manifest digest;
  локальные проверенные копии сохранены. Образы исходного input сохранены.
- Bundle03 validate/publish/project-stage PASS:
  sha256:6176ee8ee7b334799c9233bbef55e52b086b79581ceaf39813d83b8ba1652336.
  Реальный Wails49664/34121 запущен с этим digest; React открыл отдельную копию
  проекта, штатный rebind UPDATED, SSH-доверие101–103 подтверждено. Подготовка
  Execution Node101 выполняется (SCP runtime); Plan/Approve/Start ещё pending.

## Первый Start и последующие исправления

Execution Node101 READY. Реальные React/Wails Project Verify VERIFIED,
сервисные inputs и20 app refs переданы в Broker. Запрос FULL_PROJECT,
skipInfrastructureVerify=false, skipLibraries=[], порядок szi/sdku/cspa,
qa-vault-consumer=CURRENT_RUN_BOOTSTRAP.

План plan-dc1671c542e80d1d585552b0, revision
sha256:5f00915beb9b6d233ae5ae45e3cb551e58bb37b8943d21b1da069aa576ffdb7c:
EXECUTABLE/APPROVED,24 actions: PKI1, SERVICE_APPLY10, SERVICE_VERIFY10,
application Apply/Verify/post_install по1. Start отклонён TARGET_HOST_TRUST_INVALID;
runId не получен, Apply не запускался.

Причина подтверждена размером фактического private manifest67457 bytes:
trust reader ошибочно применял к нему known_hosts limit65536. Исправлено
только чтение валидированного private manifest; режим/владелец/nlink/защита
от ссылок и binding checks сохранены, known_hosts и marker лимиты сохранены.
Native regression вызывает настоящий execution_protocol.py staging с manifest
больше64KiB и проверяет сохранение ограничения known_hosts. Trust7 + lifecycle61
PASS на102. Новый bundle04 собирается; активный runtime не патчился.

По замечанию владельца библиотечные checkbox и Vault source перенесены
из services в applications phase, summary содержит оба блока раздельно.
Текст пропуска исправлен для снятого флажка. UI118/lint/build PASS.
Отдельная попытка visual helper не дошла до готового плана после открытия
проекта в новом UI-сеансе без восстановления Execution Node binding;
visual PASS не объявляется. В основной flow добавлена проверка реального DOM
фаз и screenshot перед Start нового плана.

## Текущий реальный run

Bundle04 validate/publish/project-stage PASS:
sha256:4f28eb706da98675c488d1f31763fa9821fedd99c220008ff989509c1a27df1e.
Wails r2 PID45664, bridge34121. Execution Node101 READY; Project Verify VERIFIED.

Automation transient: ожидание UI-toast после сохранения одного app field
завершилось timeout. Resume использует тот же проверенный Wails-сеанс,
нажимает реальные React controls и подтверждает наличие через readonly
GetApplicationRuntimeSecretAvailability. Значения повторно введены в20 полей.
Одобрение затем остановилось INSTALLATION_SECRETS_MISSING: повторные публичные
запросы descriptors по штатной политике сбрасывают attached runtime values.
Повторный ввод инфраструктурных inputs через реальные сервисные dialogs и
единая финальная Core attestation восстановили комплект. Механизм Broker,
требования пароля и admission не изменялись ради обхода этого шага.

Новый план plan-92d03f7d39ea52720f430aaf, revision
sha256:dc2fd8db7cf9c0015b054654acb8e04dce483f433a83f5cb0268af9afb600f89:
EXECUTABLE/APPROVED. Реальный Start:
installer-4db8b8abd6da7e1e34c44b7a306e98ca RUNNING,2026-10-26 около12:42 MSK.
Параметры FULL_PROJECT/CURRENT_RUN_BOOTSTRAP/no skips прежние,24 actions.

Реальный DOM и screenshot просмотрены: services содержит0 library checkbox
и0 Vault-source selectors; applications содержит3 checkbox и1 Vault selector.
Все3 библиотеки включены. Размещение UI PASS; execution acceptance pending.

## Приёмка

Очистка и первый свежий Plan/Approve/Start выполнены; run завершился FAILED.
Успех полной установки и readback инфраструктуры,11 контейнеров, Keycloak и
ролей, nginx, Vault Agent, demo пока не подтверждены.

## Исправления перед повторным полным запуском2026-10-26

Run installer-4db8b8abd6da7e1e34c44b7a306e98ca завершился FAILED на apply:qa-bind.
PKI завершён успешно. Последняя задача BIND — вложенное чтение владельцев DNS;
событие1795 содержит ANSIBLE_UNDEFINED_VARIABLE. На исходной версии через
реальный Ansible воспроизведено: `{{ [platform_bind_a_record] }}:
{{ _platform_bind_record }}: '_platform_bind_record' is undefined`.
Это не конфликт написания singular/plural: внутреннее include переопределяет
singular до вычисления списка, который от него зависит. Исправление — сохранить
материализованный одноэлементный список до входа в пакетный цикл. Native BIND26
PASS, включая два владельца, полную цепочку base → single → batch → prepare и
повтор с changed=0. Предыдущие Stage3 runs пропускали инфраструктуру.

Дополнительная проверка переходов на пакетные операции:312 YAML-файлов,
246 статических include-связей; других аналогичных lazy-loop alias candidates
не найдено. Integration batch scope4, HAProxy partial2, application integration
batches11 и endpoint-stage4 PASS. Это ограниченная
проверка области, а не доказательство всех возможных динамических include.

Отдельно реальный Wails GetServiceConfigurationPreview при READY/VERIFIED
вернул PROJECT_SNAPSHOT_INPUT_INVALID. Причина — общий project_snapshot
требовал platform_application_rows даже для configuration_only, хотя этот
режим разрешает только инфраструктурные параметры. Ограничение оставлено для
полного snapshot и исключено для раннего возврата configuration_only.
Native preview10 и snapshot-action7 PASS. Новый тест вызывает production
service-configuration-preview.yml с инфраструктурой и непустым блоком библиотек,
проверяет ROLE_DEFAULT/RESOLVED и /data/accounting-db/postgres. Приложения для
этого read-only запроса не разрешаются и не запускаются. Подтверждение нового
bundle через реальный Wails/React ещё предстоит.

Frontend124/build/lint PASS. Наблюдающие QA-скрипты оставляют окно открытым и
при SUCCEEDED, и при FAILED до ручного закрытия пользователем.

Bundle06 sha256:9fc176c7bd68ca96b1eadc0460c5828b241ac6f114031586be6f4ddd111f203a
собран на доверенном102 из QA source c1552f38, проверен и опубликован стандартным
publisher; project/bundle проверен на тот же digest. Bundle05 не активировался:
его заменил06 с дополнительным исправлением preview. Собственное Wails-окружение
перезапущено после FAILED; новый React/Wails проход подготовки начат, новый
план/Start ещё не подтверждены.

На bundle06 реальный React/Wails VerifyProject VERIFIED,20 application secret
inputs и5 service-secret dialogs заполнены. GetServiceConfigurationPreview
успешен: каталоги из defaults возвращены как RESOLVED/ROLE_DEFAULT. Реальный DOM
и просмотренный screenshot default-data-paths-ui.png подтвердили поле
ClickHouse /data/qa-clickhouse и подпись «По умолчанию»; сообщение недоступной
Core-проекции отсутствует. Режим запроса плана FULL_PROJECT,
CURRENT_RUN_BOOTSTRAP, skipInfrastructureVerify=false, skipLibraries=[],
порядок szi→sdku→cspa. Формирование нового плана начато.

Свежий план plan-ffd816223eddb56206a1371f EXECUTABLE/APPROVED; revision
sha256:22ff211d9c0e235e5366310410e7c3d3baf9a4fd3176c425cea173657f5bf5e2,
runtime06 9fc176c7. Реальный Start вернул STARTED:
installer-8d3ad63eb9770e3c7a3c937a4175ac2e.24 actions, FULL_PROJECT,
CURRENT_RUN_BOOTSTRAP, no skips. Наблюдение выполняется через тот же React/Wails.

В run8d3ad63e PKI SUCCESS, apply:qa-bind SUCCESS и verify:qa-bind SUCCESS;
переход к apply:qa-dns-client подтверждён событиями ACTION_COMPLETED/STARTED.
Исправление BIND подтверждено полным штатным run, а не только изолированным тестом.
Для свободного места на acquisition102 удалён только remote output bundle04:
digest сверён с сохранённой локальной копией4f28eb70; активный06 и его inputs
сохранены. Readback nginx для cold-install больше не требует прежнего QA backup.

Во время run добавлены времена в Execution / «Действия плана»: RUN_STARTED
сверху, подтверждённое терминальное событие с соответствующими sequence/status
снизу только после terminal. Формат МСК; Core/backend/bundle не изменялись,
Vite обновил UI без перезапуска Wails. Frontend128/build/lint PASS. Отдельный
headless orphan-reconnect не применим к известному текущему run: Inspect возвращает
CURRENT, кнопка Attach отсутствует. Визуальная проверка Computer Use остановлена
политикой инструмента из-за невозможности достоверно определить URL браузера;
визуальный PASS для времён не заявляется. Основное окно и run не остановлены.

## Терминальный результат повторного run

installer-8d3ad63eb9770e3c7a3c937a4175ac2e завершился FAILED2026-10-26 около14:36
МСК на apply:qa-kafka-structure. Успешны13 действий: PKI, Apply/Verify BIND,
DNS Client, Keepalived, HAProxy, Redis, Vault. Kafka успела запуститься как минимум
на node1 и пройти проверку listener-портов. ClickHouse, Docker, PostgreSQL и
библиотеки ещё не выполнялись в этом run. Окно наблюдения оставлено открытым.

Ошибка APPLICATION_PROVIDER_IDENTIFIER_INVALID в задаче «Исключение
идентификаторов инфраструктуры из сверки паролей приложений». Причина в
services/kafka/.../tasks/application_account.yml: запрет admin/default при
phase=apply и mode=managed стоит в общем обработчике. authorization_setup.yml
использует тот же обработчик для инфраструктурного admin; при холодном bootstrap
его mode=managed, при ранее настроенном кластере mode=existing. Поэтому холодный
сценарий блокируется проверкой, предназначенной для учётных записей приложений.
Исправление Kafka и новый run пока не выполнялись. Успешный терминальный
результат полной установки и итоговые readback остаются неподтверждёнными.

### Удаление проверки имён и проверка соседних провайдеров

По прямому указанию владельца из общего Kafka application_account.yml удалён
assert имён admin/default; переноса или новой аналогичной проверки нет.
Проверки пароля, метаданных SCRAM, режима existing, транспорта и ACL сохранены.
Native accounts12 PASS: managed admin/default создаются, existing с неверным
паролем для обычного имени/admin/default блокируется без изменения пароля.
Service repairs12 покрыты:11 PASS в общем прогоне и исправленный устаревший
bootstrap-test PASS отдельно. Фикстура теперь допускает подтверждение existing
через password_probe, когда повторный login после создания закономерно skipped.
Cold bootstrap admin, existing/Verify и отказ чтения метаданных проверены через
production Ansible tasks с изолированным CLI; живой Kafka не изменялся.

Первая попытка accounts была ошибкой окружения QA — отсутствовал путь service
collection; повтор с явными Core+Kafka collections PASS. Негативные результаты
первого прогона не считаются продуктовым дефектом или успешной проверкой.

PostgreSQL: инфраструктурный admin настраивается напрямую в postgresql/tasks/
reconcile.yml, без application_provider; SQL-quoting фильтр не запрещает
конкретные имена. Contract29 и native HBA4 PASS. ClickHouse: default
материализуется в clickhouse_tls/templates/users.xml.j2; NativeClient подключается
под default через XML, без application_sql.identifier. Запрет default/system
находится только в обработке прикладных SQL-объектов. ClickHouse9 PASS/2 native
skipped — pinned ClickHouse/Keeper runtime отсутствует. Аналогичный конфликт
bootstrap не найден; полная установка этих сервисов ещё не проверена.

Отдельные ограничения служебных имён в Core application_providers.py применяются
к accounts приложений и не вызываются инфраструктурным bootstrap; они не менялись.
Текущие проверенные исходники для будущего bundle:
/var/tmp/platform-installer-qa-2028c02847e3415b9c4ee10ff57e2f04 на102.
Активный bundle06 не менялся, новый run не запускался.

### Bundle07 и повторная установка уже инициализированного Vault

Bundle07 a7503b52c12d07f43bc40978bea8ecf4024937fc291b0aa13e9d8e89ac17158d
собран из проверенного2028c028 на102 и опубликован стандартным publisher,
project/bundle проверен на тот же digest. Plan6c27ae0f EXECUTABLE/APPROVED,
run installer-fda0603948ce562ea38cb6ac0c83f18b STARTED, затем CANCELLED на PKI
до Apply Vault после замечания владельца о вводе unseal-ключей.

Первоначальное предположение о повторном использовании каталога bootstrap было
ошибочным: custody-каталог выбирается отдельно для каждого run; у fda06039 оба
файла отсутствовали. Предыдущие актуальные admin-token/unseal-shares сохранены
под identity run8d3ad63e. Наличие файлов проверено без вывода содержимого.
Для повторной установки подготовлены защищённые runtime-файлы, выбираемые
реальными UI-обработчиками секретов инфраструктурного Vault через существующий
конечный dev picker seam. В план передаётся RUNTIME_INPUT вместо
CURRENT_RUN_BOOTSTRAP: уже установленный Vault не генерирует новый root token.
Core и bundle для этого не изменяются; новый UI-проход выполняется.

Оба файла импортированы реальными UI-обработчиками: SERVICE_ADMIN_TOKEN и
SERVICE_UNSEAL_SHARES, состояние каждого STORED. Итоговая attestation перед
планом выполнена после ввода всех паролей и обоих файлов. Выбор источника
«Из секретов инфраструктурного Vault» даёт applicationVaultSources={} с
каноническим default RUNTIME_INPUT, без CURRENT_RUN_BOOTSTRAP.

По дополнительному запросу владельца проведён безопасный readback:
локальные файлы совпадают с custody результатов run8d3ad63e для deployment
qa-vault-consumer/project-b46aa3f5f57a495f. Все101/102/103 initialized=true,
sealed=false и имеют один clusterId370d084e-6c34-e783-fd53-542dcd16a971.
TLS-проверенный lookup-self административного токена успешен на всех трёх
узлах, root policy подтверждена. В предыдущем run имеются28 успешных задач
разблокировки; новые запросы seal/unseal для этой read-only проверки не делались.
Содержимое токена/ключей не выводилось. Метаданные: vault-input-readback.json.

Новый полный Plan7a7a974e EXECUTABLE/APPROVED; revision
1458b18c7fd402a4bfa336fede5e85f32de3fbc76ddaeef2cad001fc47ffb31a,
runtime07 a7503b52. Start installer-680e7daae6c8379c42f6ec2044de2842 STARTED/RUNNING.
FULL_PROJECT, no skips, порядок szi→sdku→cspa и размещение103/101/102 сохранены.
Приняты оба typed inputs; startError отсутствует. Успех Vault повторно и Kafka
после исправления должен подтвердить этот run; полный итог пока pending.

В run680e7daa подтверждены13 успешных действий: PKI и Apply/Verify BIND,
DNS Client, Keepalived, HAProxy, Redis, Vault. Повторный Vault с typed
SERVICE_ADMIN_TOKEN/SERVICE_UNSEAL_SHARES прошёл Apply и Verify. Настройки
аудита, хранилищ и auth methods прочитаны выбранным административным токеном
успешно. Начат Apply Kafka на bundle07; ошибок на этом checkpoint нет.

Kafka Apply в run680e7daa SUCCESS. Прежний отказ на admin устранён в реальном
полном run; после настройки SCRAM и ACL завершилась подготовка Schema Registry.
Начат Verify Kafka,14 действий SUCCESS. Финальный профиль Kafka Apply:
2240s (37:20),2021 TASK_STARTED. Kafka role1611s/71.9%, повторное разрешение
application libraries360s/16.1%, доставка артефактов113s/5.0%, выбор источников44s.
Подробная безопасная выборка: results/kafka-apply-timing.json в QA-каталоге.
Шкала последовательных TASK_STARTED не суммирует параллельное время хостов;
интервалы включают ожидание и оркестрацию, а не только CPU-команд.

Run installer-680e7daae6c8379c42f6ec2044de2842 завершился **SUCCEEDED**:
28 подтверждённых действий, failures0; полный infrastructure Apply/Verify,
СЗИ→СДКУ→ЦСПА Apply/Verify и post_install SUCCESS. Bundle07/revision1458b18c
не менялись этим наблюдением. UI не закрывался; отдельный readback pending.
Владелец разрешил выпуск нового optimized bundle и новый полный run без
дополнительного удаления ресурсов. Это повторный Apply, не новая clean-install
проверка; новые package-v1alpha4 hooks должны войти в проект явным обновлением.
