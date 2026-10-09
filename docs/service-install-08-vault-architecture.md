# SERVICE-INSTALL-08 — HashiCorp Vault: TLS, Raft, audit, KV и userpass

Статус: SI08-A ACTIVE по разрешению владельца; Vault deployment не выполнялся.
Запрос владельца: следующий сервис HashiCorp Vault, TLS cluster, TLS API,
audit logs on, KV on, userpass on; обязательные размещения 1/1, 3/1, 3/3.
Документ не подтверждает завершение Redis и не запускает Vault на targets.

## 1. Объём и место в последовательности

Один service package `vault`, самостоятельные Ansible validate/apply/verify,
Core snapshot/plan/private execution projection, Go lifecycle и существующие
Wails/React страницы. Integrated Storage (Raft) используется в обоих режимах:
`standalone` — один member; `raft-ha` — три voting members.
Consul, dev mode, Enterprise replication и Kubernetes не нужны.

Предлагаемая нумерация: SERVICE-INSTALL-08 становится Vault; прежний финальный
общий тест переносится в SERVICE-INSTALL-09 и включает восемь сервисов.
До принятия плана старые записи roadmap/acceptance о SERVICE-INSTALL-08
считаются прежней последовательностью; этот документ не меняет DONE/NEXT.
После принятия синхронизировать `CURRENT_STATE.md`, `docs/roadmap.md`,
`docs/service-install-acceptance.md` и ссылку на следующий этап в Redis-плане.

## 2. Владение и повторное использование

Portable project хранит deployment, mode, members/hosts, TLS profile,
настройки и только разрешённые runtime SecretRefs. Raft database, cluster ID,
leader, seal state, Vault tokens, unseal/recovery shares, audit data и KV
contents не являются Installer desired state и не попадают в проект.

Core владеет service semantics, разрешением настроек, зависимостями PKI,
планом и итоговой проверкой. Go использует существующие typed intents,
EditSession → local Save → свежий BuildDeploymentPlan → approval → Start,
lease и RunObserver. React не рассчитывает порты, quorum, SAN или seal state.
Project Verify остаётся target-free и не обещает доступность живого Vault.

Использовать имеющиеся manifest/catalog extensions, generic member-list
projection и runtime source authority. Роль принимает документированные
обычные Ansible variables и работает без Go/UI. Никакой Vault SDK/database
в Go, отдельного daemon, универсального secret manager или generic HCL editor.
Vault как устанавливаемый сервис не становится secret backend Installer.

## 3. Размещение, порты и пути

| Сценарий | Режим | Vault processes | Hosts | Что проверяет |
| --- | --- | --- | --- | --- |
| 1/1 | standalone | 1 | 1 | TLS, storage, audit, KV, userpass |
| 3/1 | raft-ha | 3 | 1 | три voters, quorum, process failover, изоляция ресурсов |
| 3/3 | raft-ha | 3 | 3 | quorum и отказ одного host/member |

Manifest: MEMBER_SCOPED, role `vault`, standalone cardinality 1,
raft-ha cardinality 3, `distinctHosts=false`. UI не называет 3/1 защитой от
потери сервера. Схема 3/1 работает с defaults без ручного назначения портов.

Предложенные defaults: API base 8200, cluster base 8201, stride 2.
Стабильная сортировка memberId по deployment даёт slot 0..2; API = base +
2×slot, cluster = base + 2×slot. Таким образом пары 8200/8201,
8202/8203, 8204/8205 одинаковы на одном и на трёх hosts. Core/role normalizer
проверяет диапазон 1..65535, уникальность пар, достигaемые advertised addresses,
коллизии с соседними instances и фактическую занятость до мутаций.
Одна runtime projection используется apply, verify и диагностикой.

`api_addr` — HTTPS адрес конкретного member, `cluster_addr` — его достижимый
cluster endpoint; не 127.0.0.1 для распределённого кластера и не общий VIP.
Raft node_id стабилен и включает canonical member identity. Unit, config,
data и audit paths различаются по deployment/member; фиксированные roots
`/etc/platform-vault`, `/var/lib/platform-vault`, `/var/log/platform-vault`.
Идентификаторы/длины проверяются существующим безопасным naming подходом до
создания путей. Общие parent directories других сервисов не chmod/chown.

Не менять существующие member IDs, data paths, storage type или переназначать
порты при наличии Raft state. Такая миграция требует отдельного плана.
Повторный apply сохраняет membership, leader, tokens и данные. Никакого
автоматического remove-peer, force-new-cluster, удаления Raft или повторного init.

## 4. TLS: разные владельцы API и cluster

API listener всегда TLS: tls_disable=false, проверка цепочки и SAN, минимум
TLS 1.2; нет skip-verify. API certificate/key/CA поступают из существующего PKI
consumer materialization, выбранного по deployment/member/host/profile.
Core выводит SAN из advertised DNS/IP; разрешённый deployment scope не
выдаётся за независимые member certificates. Bootstrap Vault PKI не зависит
от этого ещё не запущенного Vault.

API authentication базового этапа: Vault token/userpass поверх TLS; обязательный
клиентский API certificate не вводится без отдельного требования владельца.
Raft join использует API HTTPS seed и наш PKI. В `storage "raft" / retry_join`
задаются `leader_ca_cert_file`, `leader_client_cert_file`,
`leader_client_key_file`, а при необходимости `leader_tls_servername`.
Эти файлы выдаёт существующая PKI materialization; client certificate требует
clientAuth, API certificate — serverAuth. Это действительно соединение между
Vault members с нашими сертификатами, но на API-порту для join/bootstrap.
Наличие client certificate в retry_join само по себе не означает обязательный
mTLS всех API-клиентов: это отдельно задаётся listener policy.
Внутренний cluster transport после join использует собственный Vault mTLS и ротацию
cluster certificates: Installer не подменяет их API-сертификатом и не хранит
их копию. Cluster listener никогда не публикуется как клиентский API endpoint.

| Соединение | Default port slot 0 | Владение TLS |
| --- | --- | --- |
| Клиент → API | 8200 | Наш PKI, listener tls_cert_file/tls_key_file |
| Member → leader API при Raft join | 8200 | Наш PKI, retry_join leader_* certificate files |
| Raft/forwarding через cluster listener | 8201 | Внутренние cluster certificates Vault |

Поэтому утверждение «наш PKI применяется только для внешних клиентов» неверно.
Но пути `leader_*` не являются override сертификата cluster listener.

Решение владельца по UX: это внутренняя реализация Vault, которую пользователю
Installer знать не требуется. В UI один выбор нашего PKI-профиля и понятные
результаты «API TLS включён» / «Кластерный трафик защищён». Не добавлять
отдельные controls для внутренних Raft certificates, их issuer/rotation,
TLS keyring или выбора механизма cluster TLS. Таблица выше предназначена
только разработчикам и тестам; runtime configuration формируется автоматически.
Зелёный статус защиты появляется после соответствующего execution verify;
до установки UI показывает требование TLS, а не выдуманное наблюдение.

Проверять фактические оба listeners и успешный TLS Raft join; один открытый
TCP порт не доказывает cluster TLS. Точное поведение повторного старта и
сертификатов проверяется на выбранной pinned версии.

## 5. Init, unseal и bootstrap authority — обязательное решение до реализации

Vault не становится готовым после одного запуска systemd: нужен init, unseal,
затем авторизованные API-вызовы. Init выполняется ровно один раз на seed.
Остальные members присоединяются к тому же cluster по одному, с ожиданием
здорового voter; независимый init каждого member запрещён.

Решение владельца: первый install выполняется одним Ansible run, по шагам:

1. Установить binary, PKI, config и units; проверить init status.
2. На новом seed выполнить init один раз, получить initial root token и
   Shamir unseal shares в защищённые runtime variables/temporary files.
3. Unseal seed; присоединить и unseal оставшиеся members по одному теми же
   shares, проверяя cluster identity и healthy voting membership.
4. Полученным token включить audit, KV v2 и userpass, затем выполнить verify.
5. Завершить согласованную передачу/сохранение recovery material и обработку
   root token; убрать временные plaintext копии согласно custody policy.

Двухшаговая ручная ceremony и отдельная provision-only операция более не
предлагаются. No-log применяется ко всей цепочке secret-producing/consuming
tasks, включая failure/rescue; cacheable facts, debug, argv и event payload
не содержат ключей/token. Временные файлы имеют directory 0700/file 0600,
располагаются в защищённой runtime зоне, не в portable project или Raft data.
Ansible Core/Execution Node владеет этими данными в течение run; Go/React их
не получает через обычные results. Настройки сервиса `unsealShares=3` и
`unsealThreshold=2` задают default 2-of-3. Проверка: целые числа,
1 <= threshold <= shares <= 255. Для shares > 1 threshold должен быть >= 2;
shares=1 допускает только threshold=1. Это точные ограничения
[SealConfig.Validate в Vault v1.21.2](https://github.com/hashicorp/vault/blob/v1.21.2/vault/seal_config.go),
а не новая Installer policy. Default 2-of-3 соответствует им. Независимые
primitive bounds присутствуют в settings descriptor; связь между двумя полями
проверяет Core/роль, а не React или generic Go editor.
Настройки действуют при первом init; изменение существующего initialized
кластера не запускает rekey автоматически и возвращает явный prerequisite.

Принята custody policy: два зашифрованных файла на Installer workstation,
отдельно от portable project: административный token и набор unseal shares.
На Execution Node сохраняется временный plaintext delivery package до
подтверждения durable локального сохранения обоих файлов. Он переживает
run workspace cleanup и позволяет повторную передачу того же материала.
ACK привязан к package identity, project/deployment, cluster ID и digest;
до ACK единственная восстанавливаемая копия не удаляется. Владелец явно принял
временное plaintext-хранение: directory 0700, files 0600, доступ только
выделенной execution identity/root, без backup/log/event exposure.
Пакет не становится
desired state и не попадает в обычные journals/events/results. Точные
encryption/transfer/ACK contracts должны быть описаны и проверены до кода.
Сохранение всех shares одним файлом не является раздельной custody между
операторами: этот компромисс защищён шифрованием файла и контролем доступа.

При initialized=true повторный init запрещён. Потеря ответа init либо crash до
надёжного сохранения material требует безопасного отказа и операторского
восстановления; автоматически стирать storage и пробовать init снова нельзя.
Acceptance включает этот fault boundary и повтор после частичного bootstrap.
Auto-unseal/KMS/transit и daemon для авто-unseal не добавляются. Повторный run
на sealed member использует согласованный recovery input либо сообщает
prerequisite; повторный input поступает из выбранных оператором файлов (§6).

## 6. Runtime secrets и UI

Имеющийся manifest seam `ui.x-runtimeSecretRequirement` сейчас допускает
`purpose=SERVICE_PASSWORD`; service setting — объект с passwordSecretRef.
Он не даёт автоматически права передавать initial root token, unseal shares
или административный Vault token.
Нельзя переименовать token в password ради прохождения текущего validator.

В первом новом install token появляется внутри Ansible как результат init и
используется следующими tasks там же. Для этого не требуется заранее вводить
его в UI или расширять workstation → Execution Node input transport.
Этот прежний prerequisite первого install снимается.

Для повторного apply/verify уже initialized Vault всё равно нужна API authority:
unseal shares открывают storage, но не авторизуют включение audit/mount/auth.
Источник token для такого run — выбранный оператором файл в «Секретах» Vault.
Требуется минимальное расширение существующих descriptors/lease,
без второго broker,
с exact plan/deployment/operation binding, expiry, revoke/cleanup, bounds и
no-log. Опубликованные closed contracts не расширять молча: определить
затрагиваемые версии на основе текущего кода, затем зафиксировать additive version.
До спецификации и проверки этого contract не реализовывать repeat transport.

SI08-A фиксирует additive определения и точные bounds в
[typed input contract freeze](service-install-08a-secret-contracts.md):
ExecutionCapabilities/v1alpha4, BuildRuntimeSecretDescriptors/v1alpha2,
PutRuntimeSecretLease/v1alpha2, TargetCredentialLeasePayload/v1alpha4.
Старые schemas не меняются; StartExecution/v1alpha2 сохраняется. Уточнение
операций до публикации runtime: admin token нужен для Apply и Verify, unseal
shares передаются только в Apply и никогда в Verify. В рамках
SI08-C исходный код runtime подключает эти версии только после прохождения
проверок descriptor, lease admission, manifest binding и Ansible forwarding.
Это ещё не означает, что существующий установленный runtime обновлён или что
Vault развернут: immutable release должен быть отдельно собран и активирован.
Manifest и роль Vault находятся в `services/vault/`; подключение сервиса в
рабочий catalog допустимо только вместе с полным C runtime path.

Initial root token разрешён для первоначальной настройки внутри этого run.
Он сохраняется зашифрованным для повторного доступа. Пользователь также может
предоставить другой административный token с достаточными правами. Не отзывать
сохранённый или пользовательский token при cleanup Installer lease; отдельный
scoped token не создаётся без необходимости. Точные ACL/API capabilities
проверить против pinned версии.
Installer lease revocation и Vault server-side token revocation — разные вещи:
для временно выданного token отдельно определить, кто отзывает его и что
происходит при сетевом сбое. До этого не обещать гарантированную ревокацию.

«Секреты» на странице сервиса доступны до Core plan через trusted catalog
descriptors, как принято для Redis. Local input validation не требует READY.
Core повторно связывает требования со свежим планом перед Start. Secret values
не возвращаются в Wails status DTO, project, diagnostics, events/result или audit
Installer. Userpass password в этом milestone не запрашивается: создаётся
только auth mount.

Дополнение владельца от 2026-10-09: также обязательно включается AppRole
на `approle/`. Существующий mount типа `approle` сохраняется; другой тип
на этом пути блокирует настройку до изменений. Verify требует AppRole.
Роли AppRole, политики, RoleID и SecretID автоматически не создаются.

В «Секретах» Vault два file inputs: «Административный token» и «Unseal keys».
Принимаются plaintext token, документированный JSON shares (включая стандартный
JSON output `vault operator init`) и один versioned encrypted file format
Installer. Из полного init JSON извлекаются только явно запрошенные поля;
raw объект не передаётся React. Не угадывать произвольные encrypted formats.
Неверный пароль/неизвестный encrypted version не приводят к plaintext fallback.
Исходные файлы пользователя не переписываются и не удаляются; пути не
сохраняются в project. Input passwords могут различаться для двух файлов.
Для unsealed существующего Vault достаточно token; sealed member требует
unseal shares. Новая установка генерирует material сама.

Общее поле «Пароль шифрования выходных секретных файлов» с подтверждением
находится на Установка → План. Оно обязательно для approval/Start, когда
доверенный service/Core contract объявляет создание secret output files.
Сам план можно построить и показать с незакрытым требованием. Это generic
Installer prerequisite, а не условие по service ID и не пароль внутри Core plan.
На workstation пароль существует только в памяти текущей сессии, не в
project/plan/logs. Пароль шифрования не передаётся на Execution Node или в Core.
Он общий для двух новых файлов; passwords расшифровки input файлов отдельные.
Workstation получает bootstrap material по защищённому каналу и шифрует его
в Go backend без передачи plaintext в React и без plaintext staging на локальном
диске. На Execution Node временный plaintext остаётся до ACK workstation,
в том числе при обрыве run. Шифрование использует пароль из UI; второй ключ не
нужен. Стандартный формат файлов — `age` с парольным шифрованием; SHA-256
используется только для digest/corruption detection encrypted bytes, не как
шифр и не как непосредственный ключ из password. Использовать стандартную
реализацию формата и её KDF/authentication, без собственного crypto scheme.
Конкретный API вызова должен поддерживать secret input без argv/stdout утечек;
offline доступность реализации на workstation доказать до кода. Автономный
Ansible сохраняет защищённый bootstrap output для оператора без зависимости
от Go; workstation delivery/ACK относится только к Installer execution path.

### 6.1. Каталоги standalone Ansible и Installer

Решение владельца: использовать существующий настраиваемый каталог
Ansible-проекта как default base для standalone output, без обязательного
второго пути. Роль принимает один параметр `platform_vault_bootstrap_output_dir`:
для Ansible-only он выводится как `<resolved-project-root>/secrets/<deploymentId>`.
Base берётся из существующего project/inventory context, а не из текущего
shell working directory. Если root нельзя однозначно разрешить, оператор
задаёт параметр явно; preflight проверяет путь до init. Это предлагаемая
переменная роли, ещё не реализованная.

```text
<ansible-project>/
  inventory/
  secrets/
    vault-ha/
      admin-token
      unseal-shares
    vault-standalone/
      admin-token
      unseal-shares
```

Подкаталог определяется canonical deploymentId, не displayName. Каталоги
0700, файлы 0600; безопасная проверка владельца/пути и отказ от symlink/reparse
и перезаписи чужих файлов обязательны. Проверять доступность до init;
это не устраняет отдельно описанный риск потери init response.
Standalone apply и отдельный verify читают тот же явно связанный с deployment
защищённый материал. ACK, UI, Go и пароль workstation для них не нужны;
операторские output files не удаляются автоматически.

`secrets/` — локальная служебная область, не portable desired state, хотя
физически находится под standalone project root. Она не является vars source
и должна быть исключена из project revision/fingerprint, экспортируемого
проекта, snapshot/planning input archive и target transfer. Generated project
Git policy должна исключать её; это не защищает уже tracked файлы, которые
нельзя автоматически untrack/delete. Реализация обязана доказать исключения
тестами, а не считать их уже существующими. Не добавлять произвольное
игнорирование остальных неизвестных project files.

В Installer execution `platform_project_root` указывает на ephemeral copy.
Поэтому backend передаёт тому же параметру retained directory на Execution
Node, привязанный к project/deployment/package identity, вне run workspace.
Workstation destination автоматически определяется как
`<project-root>/secrets/<deploymentId>/`; выбора папки в UI нет.
Encrypted outputs имеют имена `admin-token.age` и `unseal-shares.age`.
Role не получает filesystem path workstation.
Таким образом отличается resolver каталога, а не Vault install semantics.

Передача bootstrap material — по существующему проверенному SSH/SFTP transport
в память backend; plaintext запрещено выгружать обычным SCP в локальные файлы.
Workstation шифрует и сохраняет оба файла атомарно, проверяет identity и
целостность сохранённых encrypted bytes и
подтверждает доставку; Execution Node затем удаляет свой retained package.
Стандартный transport не заменяет bounded application ACK/retry semantics:
их нужно специфицировать без изменения опубликованных closed schemas на месте.
После перезапуска Installer retained plaintext доступен для повторной защищённой
передачи без нового init; оператор снова вводит output encryption password.
Очистка run workspace или timeout не удаляет последнюю недоставленную копию.

Сверка макета: существующие Топология → Сертификаты → Сервисы/«Секреты» →
Установка/План/Выполнение/Результат подходят для generic members и settings.
Сохранение выходных файлов — общий автоматический этап с безопасными сообщениями
в существующем онлайн-журнале «Ход выполнения», без отдельной Vault installation
страницы. Лог не содержит материал ключей и не заменяет delivery/ACK backend.
Макет ещё не изображает общий output encryption password/destination. Перед UI
подэтапом повторить сверку `ui-design-01.md` и `ui-design-01-mockups.html`.

### 6.2. Ограниченный delivery contract — SI08-PLAN-02/03

Эта спецификация относится к Installer output delivery. Автономный Ansible
использует §6.1 и не вызывает описанные ниже операции.

**Состояния и владельцы.** Execution Node сохраняет прежний immutable terminal
ExecutionResult; успешный apply/verify даёт SUCCEEDED независимо от связи с UI.
Go ведёт отдельную derived delivery projection: PENDING, SAVING,
ACK_PENDING, DELIVERED, UNAVAILABLE. SAVING — локальная transient стадия.
Установка завершается по собственному terminal result. Автоматическая попытка
локальной доставки выполняется отдельно после завершения run и не меняет его
итог или допуск следующего запуска. Успех локального сохранения и ошибка
доставки показываются как отдельные состояния; старые пакеты доступны для
явного повторного получения. Ни локальная квитанция, ни ACK не переписывают
terminal journal. Обычная автоматическая доставка не посылает ACK; удалённые
пакеты сохраняются до отдельной явной очистки.
В общем журнале/результате UI показывает execution outcome и output delivery
рядом, в том числе «Установка завершена; выходные файлы ещё не сохранены».
Это общий механизм для trusted service output descriptor, без ветвления по
service ID. Сообщения доставки — backend-local status, не поддельные удалённые
Ansible events и не новые записи в terminal ExecutionEvent journal.

**Remote package.** Используется существующий execution state root, отдельная
закрытая область `secret-outputs/<opaque-package-id>/` вне runs/project/archive.
Package ID — случайный 128-bit lowercase hex; пути из request не принимаются.
Несекретная metadata содержит schemaVersion, packageId, projectId,
deploymentId, sourceRunId, runtime digest, owner execution identity,
generation, состояние READY/ACKED_CLEANUP_PENDING/DELIVERED и descriptors двух
фиксированных entries. Каждый новый run получает собственный packageId и
следующее generation; retry того же run сохраняет прежнюю идентичность.
Ожидающий доставки пакет предыдущего run не блокирует новый run.
Сравнение stable identity обязательно; rename displayName ничего не меняет.
Installer связывает пакет с парой projectId + deploymentId. Go не угадывает и
не генерирует вместо Vault его внутренний clusterId; packageId и generation
идентифицируют конкретный набор выходов.

READY публикуется атомарно после записи/flush обоих plaintext entries и metadata.
Directories 0700/files 0600 принадлежат execution identity/root. Использовать
узкие существующие ownership/no-follow/atomic file операции; не создавать
универсальный filesystem framework. Apply и verify получают runtime-only
reference на этот пакет из trusted controller context; секретные values и
arbitrary paths не передаются в public plan или в command arguments. Generated
token читается отдельным verify процессом из этого же protected package.
Чтение и cleanup координируются per-package lock. ACK допустим после terminal
run и освобождения producer/verify use; пока они активны — безопасный BUSY.
При crash controller сначала использует существующее recovery определение
terminal состояния; package не удаляется по таймеру или самому PID. Локальные
зашифрованные результаты новых run сохраняются по
`secrets/<deploymentId>/<packageId>/`; прежний плоский каталог остаётся на
месте и читается только при точном совпадении его квитанции.

**Durable terminal evidence и retention guard (owner-authorized SI08-PLAN-02).**
Metadata пакета дополнительно содержит `producerCompletion`, отсутствующее до
доказанного окончания использования. Это closed несекретная запись с sourceRunId,
packageId/generation, terminal state (SUCCEEDED/FAILED/CANCELLED), digest
durable terminal result и `producerReleased=true`. Её публикует только trusted
controller/recovery после durable terminal journal и доказанного завершения
apply/verify и их дочерних процессов через существующий lifecycle ownership.
Terminal status сам по себе, пропавший PID или отсутствие journal не являются
доказательством освобождения. Запись не берётся из client ACK или role output.

Порядок: durable terminal journal → проверка released producer/readers →
atomic write/flush producerCompletion в package metadata → разрешение retention
удалить journal. Retention и публикация координируются с теми же lifecycle/run
и package locks, в фиксированном порядке run → package; операция не имеет окна
check-then-delete между guard и удалением. Пока хотя бы один связанный package
не имеет matching durable producerCompletion, journal сохраняется. Ошибка
записи evidence оставляет journal и package, с безопасной диагностикой.

Crash после terminal publication, но до evidence не теряет источник проверки:
retention удерживает journal; existing recovery подтверждает завершение
процессов и идемпотентно дописывает evidence. После сохранения evidence ACK
может использовать его даже при уже удалённом journal, дополнительно проверяя
package generation и отсутствие активных readers под package lock. Для
завершённой generation новое execution использование запрещено; повторный run
получает собственные runtime inputs, а не вновь открывает эту generation для
apply/verify. Fetch для доставки остаётся допустимым. Это исключает устаревший
producerReleased при новом execution consumer.

Отсутствующее/повреждённое evidence вместе с отсутствующим journal означает
recovery error: ACK и plaintext cleanup блокируются. История не восстанавливается
догадкой и terminal result не изменяется. Это guard существующего retention,
не новая БД, daemon или дополнительная remote service.

**Транспорт и совместимость.** Предлагается один узкий versioned protocol
`SecretOutputDelivery/v1alpha1` через SSH на тот же attested Execution Node.
Он отделён от обычного JSON command-output helper и не меняет опубликованные
Start/GetEvents/ExecutionResult schemas. Fixed remote entrypoint, фиксированные
operation names, никакого remote shell path из project/user input.
Новый runtime объявляет поддержку непосредственно безопасным handshake этого
протокола (`GetCapabilities`: protocol, maxPayloadBytes=65536,
operations=[ListPending,Fetch,Acknowledge]). Unsupported/malformed handshake
блокирует Installer bootstrap до init. Старый runtime не интерпретирует это
как поддержку и не получает незнакомые поля старого capability envelope.
Сами closed schemas и фикстуры публикуются при реализации этой спецификации;
никаких неявных additions в старые enums. Workstation cipher age не нужен на
Execution Node. Протокол не распространяет секреты в stdout обычных Go errors.

Все requests содержат protocol version, operation и projectId; Fetch/ACK
добавляют packageId и expectedGeneration. Identity grammar наследуется от
существующих contracts; неизвестные поля отвергаются. SHA256 fingerprints
наследуют canonical digest grammar. Request максимум 8 KiB; metadata response
максимум 32 KiB; payload Fetch максимум 64 KiB; timeout каждой операции
ограничен (30 секунд). Пределы проверяются до выделения памяти/декодирования.
Не использовать compression/unbounded JSON/произвольные вложения.

SSH identity и host key проверяются существующим trusted transport. На remote
стороне owner package сверяется с authenticated execution identity и project
binding; знание projectId/packageId само по себе не даёт доступ. Нельзя читать
чужую identity, project или substituted path. Это текущая execution trust
boundary; новая multi-user authorization система не вводится.

| Операция | Вход сверх общей оболочки | Результат |
| --- | --- | --- |
| ListPending | bounded opaque cursor?, limit 1..32 | Safe metadata READY/ACKED_CLEANUP_PENDING packages выбранного project; без token/shares |
| Fetch | packageId, expectedGeneration | Framed closed metadata + два bounded content entries; READY only |
| Acknowledge | packageId, expectedGeneration, receiptId, ciphertext digests двух entries | DELIVERED или ACKED_CLEANUP_PENDING; повтор того же ACK идемпотентен |

Имена двух role-owned постоянных файлов совпадают с trusted output entry IDs:
`admin-token` и `unseal-shares`. `unseal-shares` содержит bounded JSON. Временный
`init-response.json` используется только для восстановления после прерывания
между получением ответа init и записью обоих файлов; он не публикуется в output
package и удаляется после подтверждённой записи пары.

Fetch — отдельный binary-safe streaming метод transport в память backend:
stdout только ограниченный frame, stderr никогда не склеивается с stdout,
stderr content не включается в diagnostics. Ошибка возвращает fixed code
(например OUTPUT_TRANSFER_FAILED), без preview полученных bytes. Truncation,
nonzero exit, лишние trailing bytes, mismatch length/identity/version ведут к
отбрасыванию buffer и отсутствию ACK. Не применять helper, включающий первые
512 символов remote output в error. Plaintext digest допустим лишь внутри
protected transfer metadata и никогда не попадает в events/обычный receipt.
Payload schema — два fixed entries (`admin-token`, `unseal-shares`) плюс
identity metadata; token UTF-8 nonempty <=4096 bytes, shares JSON <=32768 bytes,
общий frame <=65536 bytes. Данные не передаются React, логам или disk staging.

**Durable local publication.** Output root выбирается до Start и хранится в
локальном runtime context, не portable project. По validated deploymentId и
packageId создаётся уникальная папка комплекта, с ограниченными ACL/mode.
Открытые directory handles и существующие safe filesystem primitives защищают
запись от symlink/reparse substitution; имя/путь из remote metadata не исполняется.
Никаких overwrite существующих пользовательских файлов. Каждый из двух age
файлов создаётся exclusive, flush выполняется для файлов и поддерживаемой
directory metadata. Файлы читаются обратно через verified handles и decrypt
проверяется в памяти с тем же password, с exact content/identity comparison.
Затем атомарно публикуется небольшой local receipt `complete` с packageId,
generation, project/deployment/cluster binding, двумя filenames и ciphertext
digests. Только такой комплект считается локально сохранённым. Отдельного atomic
replace пары файлов не обещать: commit point комплекта — complete receipt.
Платформенные durable-write гарантии проверяются отдельно Windows/RED OS.

Crash после первого файла или disk-full не публикует complete receipt. При
retry incomplete directory не считается готовой; создать
новую exclusive попытку, не перезаписывая предыдущую. Удалять только доказанно
owned staging; если безопасное удаление не доказано, оставить и сообщить
safe retained-staging diagnostic, согласно существующей filesystem policy.
Если complete receipt уже есть, повторно проверить файлы/identity/digests;
после перезапуска запросить password для decrypt proof. Это не требует ACK.
Абсолютный local path не отправляется Execution Node.

**Совместимость прежнего ACK.** Нормальная автоматическая доставка не вызывает
`Acknowledge`: удалённая копия остаётся для последующего получения и не влияет
на запуск. Существующий протокол ACK сохраняет прежнюю семантику только для
ранее начатых операций; отдельная явная очистка определяется позднее.
Server проверяет binding, generation, terminal
run, released readers и структуру receipt. Под lock durable receipt записывается
ПЕРЕД удалением plaintext: это ACK commit point. Receipt содержит только
идентичности, receiptId, ciphertext digests и cleanup state, без материала ключей.
После ACK commit identity-safe deletion удаляет plaintext entries; marker
переводится в DELIVERED. Сбой cleanup даёт ACKED_CLEANUP_PENDING и безопасную
диагностику; нельзя заявлять, что plaintext уже удалён. Следующий ACK того же
receipt завершает cleanup. Если ответ на успешный ACK потерян, повтор возвращает
DELIVERED из durable receipt, не NOT_FOUND и не повторный init. Другой generation,
receiptId или binding отклоняется безопасно; новый Fetch после ACK не раскрывает
материал. Receipt не доказывает будущую сохранность пользовательского backup,
а фиксирует подтверждённую доставку trusted Installer.

**Обнаружение после рестарта.** При открытии проекта и READY connection Go
вызывает ListPending для его stable projectId, независимо от текущего run
subscription/history. Metadata и ACK receipts не входят в обычную очистку
истории runs. List имеет ограниченную pagination; никаких scans всего диска.
Контекст последнего local output root/receipt хранится в локальной runtime
области приложения; при потере этого контекста пользователь снова выбирает
папку/пароль. Это не отдельная БД и не desired-state persistence. Очистка
истории и Cancel не удаляют READY package. Без подключения status UNAVAILABLE,
не DELIVERED. TTL auto-delete для недоставленных пакетов и daemon отсутствуют;
их удаление требует отдельной явной operator cleanup операции. При потере
remote package без receipt — recovery failure, никогда implicit success.

**Acceptance для этой границы.** Обязательны fault tests: disconnect после
verify до Fetch; mid-frame failure с secret-bearing bytes и безопасной error;
oversize/truncated payload; disk-full; crash после первого/второго файла до
complete; crash после complete до ответа UI; compatibility tests для
duplicate/stale/cross-project ACK, потери ACK response и cleanup; symlink/reparse
swap; CANCEL/FAILED с уже созданным material; restart Installer и очищенная
run history; отдельный apply/verify process; отсутствие secrets в diagnostics,
project archives и fingerprints. Проверить, что standalone проходит без
delivery protocol, Go, UI, age и ACK. Потеря самого init response остаётся
явной аварией с запретом повторного init/удаления storage (§5).
Отдельные fault tests: terminal → durable producerCompletion → удаление history
→ restart → Fetch/ACK/cleanup; crash между terminal и evidence с удержанием
journal и recovery; отказ ACK при active producer/readers; отсутствие evidence
и journal; retention racing с evidence publication; запрет повторного execution
использования завершённой generation.

## 7. Audit, KV и userpass

Обязательные invariants этапа: file audit enabled, KV v2 enabled на `secret/`,
userpass auth enabled на `userpass/`. Paths фиксированы в первом scope;
произвольные mounts/plugins/policies вне него. Audit включается первой
авторизованной операцией после bootstrap. Сам init/unseal не объявляется
полностью покрытым ещё не включённым audit.

Audit device cluster-wide, default `local=false`; конфигурация распространяется
Raft. Один и тот же file_path должен быть валиден на всех peers: для 3/1 каждый
systemd instance получает собственное файловое отображение фиксированного
audit path через стандартный per-unit mount namespace/BindPaths. Host backing
directory уникален по deployment/member. До применения этого варианта доказать
поддержку systemd/SELinux на RED OS, в том числе reopen при rotation. Не
предлагать cluster-wide device с разными member paths как будто это три
независимых local настройки. Если BindPaths непригоден — STOP и отдельное
решение, не вводить custom audit proxy. Audit directory writable только service
user, files 0600, log_raw=false; секретные значения не включать в исключения HMAC.
Rotation через logrotate и SIGHUP только соответствующему instance; bounded
retention и проверка доступного места. Потеря writable audit является failure,
не поводом автоматически отключить audit. Файлы audit не входят в event mirror.

Повторный apply читает sys/audit, sys/mounts и sys/auth, сравнивает owned
объекты и создаёт только отсутствующие. Несовместимый существующий mount
(например KV v1 на secret/) блокирует миграцию; не disable/re-enable и не
стирает secrets. Чужие mounts/auth methods сохраняются.

Если существующий audit device отличается по `file_path`, `local` или
`log_raw`, apply останавливается с безопасным finding до изменения device.
Автоматический disable/re-enable запрещён. Negative tests отдельно меняют
каждый из этих параметров и доказывают сохранность существующего device.

Решение владельца: userpass только enabled. Installer не создаёт пользователей,
пароли и пользовательские ACL policies. Verify доказывает наличие mount типа
userpass на `userpass/`; login тест без созданного account не требуется.
Существующие users/policies не изменяются.

KV smoke write/read/delete проводится в отдельном QA prefix с несекретным
маркером; production verify read-only. QA удаляет также KV v2 metadata/versions
своего маркера. Smoke и failover не маскируют changed apply. Повторный apply
должен дать changed=0; сам Vault при этом закономерно пишет audit и Raft logs.

## 8. Артефакт, runtime и отказоустойчивость

Pinned DEV artifact (owner-authorized acquisition, 2026-09-26):
`vault-1.21.2-1.red80.x86_64` из RED OS `updates`, BUSL-1.1.
RPM SHA-256 `sha256:11db853f514625835ed4516876311057b7021fbaf39a53040e5e13d111bc41dd`;
подпись существующим trusted ключом RED OS и равенство repository/remote/local
checksum PASS. Извлечённый binary сообщает Vault v1.21.2. Runtime-only import
в `.runtime/artifacts/vault/`; установка/immutable publication не выполнялись.
Подробное evidence и ограничения offline redistribution — в
[SI08-A](service-install-08a.md). Артефакт не подтверждает runtime acceptance.

До реализации выбрать точную доступную Vault edition/version для RED OS
и зафиксировать OS/arch, SHA-256 и лицензионные условия распространения.
`latest` запрещён. Approved repository получает приоритет по существующему
source policy; иначе verified immutable offline artifact; иначе block.
DEV acquisition отдельно разрешается владельцем. Target ничего не скачивает
из Интернета; runtime publication/activation и CAS artifactLock — существующие.

Dedicated service identity, instance units, защищённые config/data/TLS keys,
санитизированные ошибки и no_log для Vault API auth/response. Выбор mlock/swap
для Raft зафиксировать по pinned upstream guidance и проверяемой host policy;
не давать произвольных root capabilities. Cancellation останавливает
Installer-run, но не удаляет запущенный Vault или durable state.

Не создавать второй cluster при lost init response, restart или retry.
Проверять initialized/cluster ID/membership и owned paths; неизвестное либо
частично потерянное состояние требует восстановления оператором. Concurrent
apply одного deployment не допускает параллельный bootstrap. Existing lifecycle
locking использовать, его фактический scope подтвердить в SI08-A.

## 9. Подэтапы и gates

| Подэтап | Результат |
| --- | --- |
| SI08-A | Решения init/unseal/token custody, pinned artifact, проверенные contract gaps; закрытые manifest/settings/secret contracts |
| SI08-B | Standalone Ansible role: normalize/preflight/PKI/provision/configure/verify, 1/1 и 3/1 fixtures |
| SI08-C | Core package/catalog/source/PKI/member projection, target-free snapshot и fresh execution plan; Execution Node capability v1alpha4, typed lease v1alpha2 admission, manifest binding and operation-scoped Ansible input projection |
| SI08-D | Go lease client/provider and Start integration, age-protected workstation input/output handling, generic Wails/React authoring/status |
| SI08-E | Реальные 1/1, 3/1, 3/3 apply/verify/repeat и failover; regression/docs |

SI08-A не начинается до owner decisions и PLAN review. Начать B–E при
незакрытом token/bootstrap contract нельзя. Каждый этап имеет focused tests;
новые публичные версии либо secret/lifecycle boundary требуют предусмотренных
репозиторием review gates, без автоматических циклов исправлений/review.

Для каждого размещения: exact project/release identity, план через Go, UI
authoring/Start где доступна автоматизация, run IDs, terminal SUCCEEDED,
TLS API verification, требуемое число healthy voters, audit enabled/writable,
KV v2 и userpass auth mount proof, свежий повторный план и changed=0.
Health 200/standby codes анализируются по Vault semantics; uninitialized/sealed
не принимаются как readiness. Ошибки CA/SAN, port collisions, missing lease,
sealed state, чужой Raft state и incompatible mounts имеют negative tests.

Для HA: ровно один active leader, три voters; остановка выбранного active
member, выбор нового leader, доступ к тому же QA KV marker, восстановление
member и quorum. При Shamir нужен явный unseal восстановленного процесса.
3/3 дополнительно проверяет потерю одного host при доступности Execution Node;
для этого выбирать target, отличный от QA Execution Node. Все остановленные
QA members возвращаются в healthy состояние. 1/1 не обещает failover.

Standalone Ansible и Go-mediated execution оба обязательны. Отдельно
подтвердить UI create/save/reopen/settings/secrets, реальные API действия и
Installer-side event stream. Не признавать timeout теста успешным по логам.
Full Core suite, affected service tests, Go test/vet/race (RED OS), frontend
lint/test/build, Wails при bindings/UI changes, catalog/schema reproducibility,
secret/security audit, diff --check. Затем revision-bound high-risk DIFF review.

Legacy Vault cleanup только по доказанному QA ownership, с инвентаризацией
данных и отдельным разрешением для утраты содержимого Vault. Нельзя переносить
разрешение на Redis cleanup на неизвестный Vault data. Общий план всех восьми
сервисов относится к SERVICE-INSTALL-09; этот milestone его не запускает.

## 10. Принятые owner decisions и оставшаяся спецификация

1. ПРИНЯТО: init → temporary runtime material → unseal → configure → verify
   в одном Ansible run; default threshold/shares = 2/3, оба значения доступны
   в настройках сервиса. Два encrypted output files сохраняются на workstation.
2. Первый run использует generated root token внутри Ansible. Повторный input
   выбирается через два file controls Vault Secrets; plaintext и утверждённый
   encrypted format поддерживаются. Remote plaintext package сохраняется до
   подтверждения workstation; повтор доставки не выполняет повторный init.
3. ПРИНЯТО: userpass только enabled, без managed account/password/policies.
4. ПРИНЯТО: стандартная source policy — совместимый approved repository,
   иначе immutable offline bundle, иначе block. Точные version/edition/digest
   определяются при подготовке service package, не через плавающий latest.
5. ПРИНЯТО: общий session-only output encryption password на этапе плана,
   обязательный для approval/Start только при требовании secret output.
6. ПРИНЯТО (последнее решение): шифрование на workstation, пароль остаётся там.
   На Execution Node допустим защищённый временный plaintext до ACK доставки.
   Файлы age, transport SSH, SHA-256 только для проверки encrypted bytes.
7. ПРИНЯТО: Ansible-only output — `<project>/secrets/<deploymentId>`;
   Installer задаёт retained directory на Execution Node и автоматически
   сохраняет encrypted outputs в `<project-root>/secrets/<deploymentId>`
   на workstation. Выбора папки в UI нет. Пароль шифрования задаётся на
   странице «Установка», этапе плана. Secrets subtree не является portable input.
8. ПРИНЯТО: generic автоматическое сохранение и прогресс в существующем журнале
   установки, без Vault-specific installation flow.

Продуктовые решения закрыты. До реализации остаётся конкретизировать
bounded schemas, стандартную реализацию age, transfer/ACK/recovery и
согласованные версии существующих secret contracts. Одобрение направления
не заменяет проверку конкретной границы хранения и передачи. Документ не
разрешает deployment, удаление данных или незаметное расширение старых схем.

## 11. Первичные источники

- [Integrated Storage: cluster mTLS и join](https://developer.hashicorp.com/vault/docs/concepts/integrated-storage)
- [Raft storage configuration](https://developer.hashicorp.com/vault/docs/configuration/storage/raft)
- [Пример retry_join с собственными certificate/key/CA](https://developer.hashicorp.com/vault/docs/deploy/kubernetes/helm/examples/ha-tls)
- [Init API и generated key material](https://developer.hashicorp.com/vault/api-docs/system/init)
- [Userpass authentication](https://developer.hashicorp.com/vault/docs/auth/userpass)
- [File audit и SIGHUP rotation](https://developer.hashicorp.com/vault/docs/audit/file)
- [Audit logging operational guidance](https://developer.hashicorp.com/vault/docs/audit/best-practices)

Источники просмотрены 2026-09-26. Они описывают продукт; совместимость с
конкретным дистрибутивом и выбранной pinned версией доказывается тестами.

## 12. Архитектурный review

Один FULL PLAN review: APPROVE_WITH_CHANGES, 0 BLOCKING, 0 overengineering
findings. Reviewer: architecture-reviewer / Archimedes. Проверенная ревизия
плана SHA-256 `E9476B646DB0C5FA885740899FDC76625CC2EB0EE4DCD9DF4B6014BF80C7FC86`,
base HEAD `221b05dee8c54492991af0d61c92842d7cf10d75`.

SI08-PLAN-01 NON_BLOCKING: явно определить отказ при несовместимой конфигурации
существующего audit device. После review в §7 добавлены точные поля, запрет
disable/re-enable и negative acceptance. Это редакционная корректировка
реализатором; независимый повторный review не проводился и не требуется.
Review относится к указанной ревизии, дополненной этим ограниченным уточнением;
открытые owner decisions §10 остаются незакрытыми. Реализация не разрешена.

Последующее решение владельца заменило manual two-run ceremony одним Ansible
run и исключило managed userpass account. Для изменённых §5–7 review validity
PARTIALLY_INVALIDATED; прежний verdict не является проверкой новой custody
модели. После следующих owner decisions добавлены workstation encrypted files,
два file inputs, plan encryption prerequisite, 2-of-3 defaults и retained
delivery package. Эти изменения не покрыты прежним verdict.
Эти записи описывают историю review, последующий итог приведён ниже.
Последнее решение владельца заменяет remote encryption на workstation encryption
и разрешает временный plaintext package на Execution Node до ACK. Предыдущее
разрешение передавать output encryption password на Execution Node superseded.

Последующий FULL PLAN review ревизии
`EA522B0CFA1DC77844035C7788586B00A2999BFCC613662A6AACDA070C859F13`
вернул BLOCK: SI08-PLAN-02 delivery/ACK contract OPEN; SI08-PLAN-03 safe
binary transport NON_BLOCKING OPEN; SI08-PLAN-01 RESOLVED.
После owner-approved спецификации §6.2 выполнен один TARGETED_RECHECK ревизии
`4C8B3C42E36CDC863041F40B8BA6C449452D8518F5F2271BC685ABDED7E6D1A6`:
SI08-PLAN-03 RESOLVED, SI08-PLAN-01 остаётся RESOLVED, SI08-PLAN-02 BLOCK только
из-за отсутствия durable terminal proof после retention journal.

Владелец принял точечную коррекцию: §6.2 дополнен producerCompletion и retention
guard с fault matrix. SI08-PLAN-02 — correction applied by owner authorization;
независимая проверка новой редакции не выполнялась. Последний reviewer verdict
остаётся BLOCK для указанной предыдущей ревизии; нельзя объявлять эту коррекцию
review PASS. Автоматический review budget исчерпан, новый review не запускался.
Production code не менялся, реализация Vault не начата.
