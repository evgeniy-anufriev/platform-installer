# A2 — материализация библиотеки и запуск простого приложения

Технический план от 2026-10-10 для A2 и A2.1 из [общего плана](../../implementation-plan.md).
База: A1 `05bc2ff`, включённый в `master` merge-коммитом `ac4340b`.
Документ разрешает обсуждение и ревью плана; он не разрешает реализацию,
изменение targets, приобретение образов или публикацию bundle.
Текущие статусы и разрешения остаются в [CURRENT_STATE](../../../../../CURRENT_STATE.md).

## 1. Результат и границы

Обычный `ansible-playbook` на Execution Node устанавливает простую библиотеку
на ранее подготовленных RED OS Docker-хостах. Используются inventory,
group_vars, host_vars и defaults пакетов; Go, Wails, SQLite и project.yml не нужны.

В пределах A2:

- общий несекретный `.env` и base Compose на сочетание project/library/host;
- отдельные Compose-файлы и локальные Compose projects экземпляров;
- доставка закреплённых образов из approved registry или immutable bundle;
- запуск в выбранном существующем rootless daemon;
- read-only Verify, readiness, повтор без изменений, безопасное обновление;
- один экземпляр на двух хостах и две библиотеки на одном daemon.

A2 не создаёт БД, УЗ, Vault secrets/AppRole, agent.hcl, PKI и HAProxy/DNS endpoint.
Это A3–A6. Нет общего Installer execution-плана, approval/Start, нового writer
или UI: они подключаются в A7/A8/B/C. Защитная ошибка
`APPLICATION_LIBRARY_EXECUTION_NOT_IMPLEMENTED` в существующем deployment planner
сохраняется. Standalone playbook не публикуется как скрытый Installer Start.

Для A2 весь устанавливаемый набор должен иметь пустые accounts/secret bindings,
не требовать Agent, ресурсов библиотеки и включённого endpoint. Если имеются
потребности A3–A6, Apply блокируется до первой мутации любого placement.
Связи с инфраструктурой допускаются только как несекретные адреса без provider
mutations и PKI materialization. Для основной QA используются приложения без них.
По уточнению владельца после разрешения реализации для A2 используется публичный
`docker.io/library/nginx:1.28.0-alpine`, закреплённый Linux/amd64 manifest digest
`sha256:09ab424a8c788f8d0fe3a64429f6d19dfa526885c8609b748d0943a75dcb9f8c`
и image ID `sha256:c318e336065b17ff460aeac6d14bce5d0b13e35f25d5cb1843b635359fc00c9a`.
Digest получен из registry API и проверен после pull на RED OS. Это разрешение
на получение одного публичного QA образа; оно не разрешает сборку, установку
Docker, изменение provider-сервисов или публикацию execution bundle.

QA package явно запускает `nginx -g 'daemon off;'`, монтирует readonly
`default.conf` и публикует `/status`, возвращающий identity и параметр приложения.
Nginx читает файл при старте: после записи нового файла старый HTTP ответ должен
сохраниться до Compose recreate, а после retry — отразить новое значение.
Это проверяет фактическое потребление конфигурации, помимо labels/IDs/checksums.
Собранный connection-probe сохраняется для Agent/PKCS12/УЗ проверок A4–A9.

## 2. Существующие механизмы и необходимые дополнения

| Потребность | Основа | Изменение A2 |
| --- | --- | --- |
| Resolve/идентичность | `resolve_application_libraries`, `application_libraries.py` | Переиспользовать строки A1 и подготовленные пакеты, без второго resolver |
| Docker account/socket | `platform.docker.docker_rootless`, `tasks/verify.yml` | Read-only preflight выбранного runtime; account/UID/HOME из runtime/facts |
| Источники | `artifact_source_resolution`, `artifact_source_gate`, `artifact-source` | Добавить контейнерную ветвь discovery; не применять `dnf repoquery` к образам |
| Offline transfer | `artifact_delivery`, verified bundle metadata | Переиспользовать проверку SHA256/size и copy; `docker load` после проверки |
| Render | `ansible.builtin.template`, `copy`, `file` | Одна общая application runtime role; package templates остаются в пакетах |
| Compose | Уже установленный Docker Compose CLI plugin | `command: argv`; Core сверяет только собственные projections, не пользовательские поля Compose |
| Повторы | Compose reconciliation + Ansible registers | Сравнивать наблюдаемые ID/state до и после, не парсить человекочитаемый progress |
| План/результат | Существующие structured Core границы | Только минимальные runtime descriptors, без нового scheduler/plan store |

Текущий artifact source contract описывает `REPOSITORY`, `OFFLINE_BUNDLE`, `BLOCKED`,
archive digest/size и targetNode, но не доказывает Docker image identity.
Нужно дополнить существующий contract/authority допустимой типизированной image
metadata и проверить старую RPM-ветвь. Точное версионирование расширения выбрать
по existing version dispatch: обязательные новые поля требуют новой версии,
старые service inputs остаются работоспособны. Нельзя передавать контейнерную
семантику через произвольные `version/name` RPM-поля без документированного типа.

Standalone preflight получает image authority через переиспользуемую Core
assembly typed artifact requirements, без вызова `BuildDeploymentPlan`.
Существующую `_artifact_source_authorities()` из `deployment_plan.py` вынести/
расширить в общей Core функции: RPM planner и standalone caller используют её,
target-local resolver реализует одну authorized policy. Application planner guard
остаётся включённым. В A2.1 до Apply закрепить version dispatch, location record
в existing lock и конкретный пример image authority; отдельного обхода planner нет.

## 3. Минимальные дополнения контрактов

### 3.1. Выбор файлов рендера

A1 проверяет полный package allowlist и defaults namespace, но не определяет,
какой из разрешённых templates запускать. В package manifest добавить явный
необязательный блок `render`: обязателен для A2 Apply, не для старого A1 resolve.

```yaml
# application.yml; остальные поля A1 сохранены
render:
  compose_template: roles/application_apigateway/templates/apigateway.compose.yml.j2

# library.yml
render:
  base_compose_template: roles/library_sdku/templates/.base_compose.yml.j2
  base_compose_filename: .base_compose.yml
  base_service: base
```

Каждый source — exact allowlisted regular file внутри выбранного package.
Не добавлять discovery по glob, автоматическое исполнение package tasks,
lookup произвольных host paths или hook DSL. Filename — безопасное локальное имя,
без separators/`..`; исходные `.base_compose_test.yml` можно сохранить.
Library `files/.env` сохраняет фиксированное место из A1; если файла нет,
создать runtime `.env` с обязательными projection keys.

Package templates — доверенный код на Execution Node, а не sandbox:
проверить digest и разрешённый execution scope до рендера. Hash не означает
самостоятельного доверия неизвестному пакету. Standalone оператор явно выбирает
local packages; будущий Installer trust/transfer остаётся в B.

### 3.2. Readiness и конфигурационные файлы

Добавить в application defaults небольшой schema-checked `readiness`:
`mode: container` или `mode: healthcheck`, с ограниченными retries/delay.
`healthcheck` требует Docker healthcheck из шаблона; absence/unhealthy/timeout
блокируют Verify. Для healthcheck QA использовать только image/runtime с реальным
capability; existing probe в прямом A2 режиме использует `container`.
`container` доказывает только запущенное состояние, не готовность HTTP/подключений.

Для mounted несекретных конфигов добавить список `config_files`:
каждый элемент задаёт allowlisted `template` либо `source`, относительный
`destination` под instance `config/` и mode. Источники взаимоисключающие,
destinations уникальны; traversal/symlink запрещены. Это встроенные template/copy,
без пользовательских команд. Compose template задаёт bind mount `:ro`.
Секретные файлы и произвольные внешние host volumes не входят в этот A2-контракт.

### Автоматический digest конфигурации — коррекция A2-P01

`application_config_digest` — только derived runtime value. Пользователь не
задаёт его в defaults/group_vars/host_vars; override digest и служебного label
запрещён. Ansible вычисляет SHA256 итогового содержимого каждого declared config
после template/override, собирает отсортированный по destination список пар
`[relative_destination, content_sha256]` и хеширует его детерминированную JSON
сериализацию. Для пустого списка получается стабильный digest. Использовать
built-in filters/renderer; документировать одинаковую сериализацию Apply/Verify.
Имена файлов входят в digest: замена destination также меняет его.

В rendered Compose автоматически добавляется managed label:

```yaml
labels:
  platform.installer.config-digest: "{{ application_config_digest }}"
```

Порядок: вычислить desired digest → записать configs → записать Compose с label
→ ordinary up/recreate → readiness → проверить image/config label.
Digest не считается пользовательским input, не хранится в portable desired
state и не требует отдельного pending/activated journal.

После прерывания между config write и up контейнер сохраняет старый label.
Retry заново вычисляет desired digest даже при `copy/template changed=false`;
Compose видит изменённый label и пересоздаёт только этот instance. При изменении
config используется **recreate**, отдельный restart по changed flag не нужен.
Это явный tradeoff: container ID меняется при config update.

По решению владельца 2026-10-10 обычный Verify выполняет один task `docker
container inspect` на экземпляр: locked image ID, ownership labels проекта,
библиотеки, экземпляра и хоста, Running и настроенный healthcheck. SHA256 файлов,
config-digest и Compose config hash не проверяются. Это проверка идентичности и
готовности, а не аудит конфигурационного drift. Apply сохраняет полный preflight
и механизм config-digest/recreate; прикладное чтение конфигурации проверяется QA.

Host/application overrides проходят ту же схему A1. Команда, user/restart,
environment, ports берутся из effective settings, не из констант runtime role.
Identity environment автоматически заполняется из A1.

### 3.3. Образы

В defaults остаётся `image`, доступный для override. Apply требует image lock
в существующем artifact/lock механизме, покрывающий этот reference и target platform:

| Поле image metadata | Смысл |
| --- | --- |
| requested reference | Desired `image`, для сверки defaults/override с lock |
| registry reference + manifest digest | Закреплённый approved registry источник |
| platform | OS/architecture, при необходимости variant |
| image ID/config digest | Identity конкретного platform image после pull/load |
| bundle artifact ref, SHA256, size | Exact archive внутри verified bundle |
| local reference | Автоматический platform-application:sha256-<полный config digest>, общий только для одного image ID |

Manifest digest, config/image digest и SHA256 архива — разные значения.
Multi-platform registry index должен быть связан с выбранным platform manifest.
Не добавлять отдельный images.lock или image catalog. Если существующий lock
не выражает эти поля, расширить его один раз и добавить backward-compatible dispatch.
Точный JSON/YAML shape и образец lock закрепить первым подшагом A2.1 до Apply.
Изменение image/lock/package входит в существующую revision binding.

Mutable tag без lock не является достаточным основанием установки. Наличие
локального образа само по себе не заменяет authorized source selection.

### Коррекции по принятому FULL DIFF A2-D01/D02

Fallback descriptor проверяется при подготовке, а файлы bundle/archive — только
после выбора OFFLINE_BUNDLE на target. Эта проверка выполняется для всех выбранных
placements в общем preflight до filesystem/container mutations. Доступный registry
не зависит от наличия или исправности необязательного fallback. Auth/transport
ошибка не превращается в отсутствие image и не скрывается offline fallback.

Runtime local reference автоматически вычисляется из полного config/image digest:
`platform-application:sha256-<64 hex>`. localReference в lock не требуется;
если задан, он обязан совпасть с вычисленным. Чужой image под зарезервированным
именем блокируется до записи файлов. Разные image IDs имеют разные имена на daemon,
в том числе между независимыми параллельными установками библиотек. Не вводятся
daemon-wide tag registry/lock, новый store либо пользовательский image ID параметр.

## 4. Target layout и контекст шаблонов

Root размещения задаётся обычной переменной runtime role, затем проверяется
по выбранному account HOME и разрешённому application subtree. UID/HOME нельзя
угадывать по SSH login. Под root применяются относительные пути A1:

```text
<application-root>/applications/<project>/<library>/<host>/
  .env                         # один на библиотеку/хост
  .base_compose.yml             # имя из library render
<application-root>/applications/<project>/<library>/<app-instance>/<host>/
  compose.yml
  config/                      # только объявленные config_files
```

Для `apigateway-sdku` на `node1` context включает `application_name: apigateway`,
`application_instance_id: apigateway-sdku`, `SERVER_ID: node1`, effective settings,
identity environment, verified local image, container/compose names A1,
путь общего base Compose и instance config directory. Контекст каждого элемента
изолируется обычным include_tasks loop_var; предыдущий instance не оставляет vars.

Compose CLI всегда получает явные `--project-name`, `--project-directory`,
`--env-file <library-host/.env>` и `-f <instance/compose.yml>`, выбранный socket
через `-H`/`DOCKER_HOST`, runtime environment и become_user Docker account.
Автоматический поиск `.env`, cwd workstation и rootful socket исключены.
`extends.file` шаблона получает корректный относительный путь к общему файлу.
Mount paths материализуются явно: относительные пути extends интерпретирует Compose.

### Общий .env и base Compose

Исходный `.env` библиотеки — несекретный desired input. Сохранять пользовательские
строки, comments и значения без переименования ключей. A1 grammar:
пустые строки/comments и уникальные `KEY=value`; расширенный dotenv parser не нужен.

В runtime копию добавить единственный `SERVER_ID` из inventory ID хоста.
Не добавлять instance ID в общий `.env`: разные приложения одной библиотеки
получают свои identity vars через Compose environment. УЗ/пароли/RoleID запрещены.
Другие projected library keys требуют явно объявленного allowlist и проверки
конфликта с source `.env`; пользовательский ключ не перезаписывать молча.

Общие несекретные infrastructure settings, если они используются, рендерятся
в base Compose из A1 connection projection. Instance Compose наследует base
через штатный extends и добавляет только свои settings/identity/overrides.
Пример: `REQUEST_TIMEOUT_MS: ${REQUEST_TIMEOUT_MS}` в base, значение в library `.env`.
Не разворачивать общий base в независимые копии экземпляров.

## 5. Последовательность исполнения

Предлагаемые standalone entrypoints:
`ansible-core/playbooks/application-libraries-apply.yml` и
`application-libraries-verify.yml`. Роль:
`platform.core.application_runtime` с небольшими tasks для preflight,
materialize, image_delivery, compose_apply и verify. A1 resolve role переиспользуется.

### Фаза 1. Полная проверка выбранного набора

1. Запустить existing project validation/read-only resolve; получить все rows A1.
2. Проверить A2 prerequisites всех библиотек/экземпляров до target writes:
   render descriptors, отсутствие deferred features, image locks и capabilities.
3. Проверить принадлежность runtimeRef и inventory placement, package digest,
   bounded paths, port/name collisions, scheme/schema версий.
4. На каждом target проверить фактическую platform, account, UID, выбранный
   socket/rootless daemon и Compose version/нужные CLI capabilities.
5. Проверить существующие runtime directories/container ownership и bindings
   портов с учётом управляемого текущего container. Чужой объект — BLOCK, не takeover.
6. Разрешить image source для каждого host/image: approved compatible registry,
   иначе exact immutable bundle, иначе BLOCK. Auth/transport failure не считать
   доказательством отсутствия compatible registry image: safe diagnostic и BLOCK.

Не обещать распределённую транзакцию: ошибки и гонки после preflight возможны.
Но известный missing dependency любого placement должен блокировать весь Apply
до записи файлов и запуска контейнеров. При `--limit` явно ограничивается
standalone host scope; ни full library success, ни готовность исключённых хостов
такой запуск не доказывает. Не скрывать выбор хостов через второй placement list.

### Фаза 2. Материализация Compose

1. Создать/проверить managed directories, owner/group и режимы; разрешённый
   subtree проверять также по resolved real paths, включая существующие symlinks.
2. Render library-host `.env` и base один раз, до действий экземпляров на хосте.
3. Render instance config files и Compose из package templates. Core подставляет
   предусмотренные template-переменные, включая published и container ports;
   Compose-автор задаёт literal host bind address и прочие Compose-параметры.
4. Разобрать Compose через CLI только для сверки значений, проецируемых Core:
   instance/service identity, locked image, Core command/labels/environment,
   published/container ports и обязательные Core mounts. Не ограничивать
   произвольные пользовательские поля или literal host bind address.
   `pull`/`up` используют обычный Compose CLI; Verify выполняет один `docker inspect`.

### Фаза 3. Доставка image

Registry: штатный `docker compose ... pull <service>` с закреплённым registry
reference и явной фазой доставки. Если offline local reference отличается,
использовать временный runtime-only delivery Compose override с exact locked
registry reference; не менять desired templates ради pull. Перед передачей
архива/доступом в registry проверить уже имеющийся authorized image по image ID
и platform: это оптимизация повторов, не альтернативная source policy.

Bundle: копировать только разрешённый archive, сверить target SHA256/size,
выполнить `docker load` выбранным account/socket. Проверить image ID/platform
через `docker image inspect`; локальный tag при необходимости назначить через
`docker tag <verified-image-id> <digest-bound-managed-reference>`. Не угадывать tag из
tar filename или load stdout. Проверить tag ещё раз перед startup.

Existing artifact delivery сохраняет root-owned staging с directory 0700 и
archive 0600 для прежних consumers. Для image consumer после проверки копировать
exact archive в приватный bounded staging Docker account, directory 0700/file
0600, owner выбранного account; повторно проверить SHA256/size и только затем
выполнить load под этим account. Cleanup в always. Не расширять права общего
root staging; RPM defaults не менять. Эта коррекция закрывает уточнение A2-P03.

Registry credentials использовать существующим runtime-secret механизмом,
временным приватным DOCKER_CONFIG и no_log; cleanup в always. Не создавать
постоянный Docker login в HOME, не передавать password через argv. Реальная
частная registry QA требует заранее предоставленного runtime credential.
Нет secret-aware application provisioning в A2: это отдельная transport credential.

Сбой digest/platform или неправильный local tag — BLOCK перед up.
Скачивание из Internet, image build, DEV acquisition и мутация bundle не выполняются.
Архив — existing artifact type archive; cleanup staging по существующей процедуре.

### Фаза 4. Apply и Verify

1. Снять безопасную наблюдаемую информацию exact managed containers: ID,
   image ID, running/health/restart count и labels.
2. Выполнить `docker compose ... up -d --no-build --pull never --no-deps <service>`.
   Отдельный Compose project на instance/host; не использовать down,
   remove-orphans, force-recreate всего набора или image prune.
3. Снять ID/state после reconciliation; changed означает создание/recreate/
   запуск остановленного managed container, image load/tag или изменённые файлы.
   Не ставить changed_when false на безусловный up для искусственного clean repeat.
4. Readiness с bounded retries; healthcheck mode проверяет healthy именно нового
   exact container. Container mode отдельно отражается в результате.
5. Verify проверяет только image ID, ownership identities, Running и настроенный
   healthcheck одним inspect task. Standalone Verify разрешает ожидаемые inputs
   и обнаруживает account identities один раз на хост; target preflight,
   registry/archive/file/port/Compose проверки не выполняются.
   Verify не исправляет drift и не выполняет pull/load/up.

Ownership: директория и существующий container должны принадлежать exact
project/library/instance/host. Использовать existing Compose labels плюс
явные managed identity labels в template; неизвестный контейнер с совпавшим
container_name либо небезопасный directory блокирует Apply. Для новой директории
маленький runtime ownership marker допустим как derived state, без отдельного registry.

Остановившийся во время Verify контейнер, unhealthy и неправильный image — failure.
Достижимость published HTTP port проверить с target host по resolved bind address,
если fixture имеет HTTP. Это direct port check, не endpoint/HAProxy/DNS из A6.
Сетевой режим rootless Docker не считать заранее ни доступным, ни недоступным:
результат подтвердить фактической проверкой.

## 6. Повторы, обновления и ошибки

- Clean repeat: никаких повторных load/tag/recreate и file writes; `changed=0`,
  те же container IDs, image identity и health на всех selected hosts.
- Instance-only environment/config/image change: Compose меняет только этот
  instance; соседняя библиотека и другие instances сохраняют container IDs.
- Изменение library `.env`/base: render один раз на host, выполнить обычное up
  для consumers; пересоздаются только те, чья effective config изменилась.
- Bind config content меняет автоматически вычисленный config-digest label:
  Compose пересоздаёт exact instance. Проверка выполняется и на retry при
  unchanged files, поэтому прерывание до up не теряет обязательную активацию.
  Обычный Verify проверяет image/ownership/readiness; config drift не проверяет.
- Interrupted copy/load/up: повтор использует фактические files/images/containers,
  не флаг «успешно» из прошлого запуска. Provider rollback не обещается.
- Multi-host failure: показать success/failure каждого host, библиотека целиком
  не PASS, если хотя бы один выбранный placement не verified. Успешный host
  не удаляется автоматически; retry сохраняет его работающий container.
- Удаление instance, rename/move, down и clearing не включаются в A2. Обнаруженные
  лишние managed containers отметить как drift, не удалять автоматически.
- Конкурирующие Apply к одному project/library-host subtree не поддерживаются:
  до mutations получить один host-local lock этого subtree существующим lock
  primitive либо atomic mkdir; при занятости BLOCK. Освободить в always; crash
  recovery требует явной проверки abandoned owner, не автоматического takeover.
  Это bounded execution guard, не второй scheduler или desired-state store.

## 7. Изменяемые файлы и порядок реализации

| Подшаг | Файлы/ответственность | Критерий выхода |
| --- | --- | --- |
| A2.0 | Application/library/package schemas, A1 loader/resolve row, соответствующий snapshot schema | Явные render/readiness/config descriptors; старый infra-only и A1 fixtures resolve прежним путём |
| A2.1 | Existing artifact/lock/source authority и delivery, runtime bundle metadata validation | Registry/offline images строго pinned; target-local compatibility/identity; старые RPM tests PASS |
| A2.2 | `application_runtime` preflight/materialize, два standalone playbooks, package templates | Один общий env/base, exact paths/ownership; сверяются только значения, проецируемые Core |
| A2.3 | `application_runtime` image delivery/compose_apply/verify | Реальный rootless startup, readiness и честный repeat |
| A2.4 | New representative simple-library fixtures, focused/standalone QA, docs | Две библиотеки и два hosts, isolation/failure/retry, весь acceptance scope доказан |

Не менять Redis/Sentinel исправления, Go/frontend, existing Docker installation
или текущий SI11 bundle ради этого этапа. Перед coding подтвердить рабочую ветку
`codex/application-libraries` и сохранить незакоммиченные изменения master.
Bundle format extension/test не разрешает acquisition/build/publication действующего bundle.

Рекомендуемые новые tests: `test_application_runtime_contract.py` для точечных
границ и `qa_application_runtime.py` для реального Ansible/Compose. Не писать
tests, которые только проверяют наличие строк в новых tasks вместо поведения.

## 8. QA и критерии приёмки

QA выполняется на RED OS текущими исходниками через [qa-sync](../../../../../scripts/qa-sync.ps1)
и [QA procedure](../../../../agent-procedures/qa.md). Read-only tests не изменяют targets.
Mutating A2 QA требует отдельного разрешённого scope: existing Docker deployment,
account, два hosts, уникальные project/library identities, допустимые ports и
заранее подготовленные pinned simple image/registry/bundle artifacts.
Docker не устанавливать автоматически. Для указанного публичного QA образа владелец отдельно разрешил pull; остальные missing prerequisites блокируют QA.

| Проверка | Ожидаемый результат |
| --- | --- |
| A1 focused и standalone regression | Сохранены vars/identity, connection selectors, secret safety и infra-only |
| Schema/version negatives | Missing render/lock, incompatible version, unsafe template/config path блокируют Apply |
| Provider-feature gate | Accounts/shared binding/Agent/resources/enabled endpoint блокируют весь набор до writes |
| Existing RPM artifact regression | Прежние repository/offline требования и source authority работают без изменений |
| Approved registry | Exact pinned image и platform; явный pull, повтор использует проверенный local image |
| Registry отсутствует/нет совместимого image | Verified bundle fallback; отсутствие обоих источников BLOCK |
| Registry auth/TLS failure | BLOCK с безопасной причиной; не скрывать ошибку fallback |
| Offline | Registry недоступен по policy; load exact archive, inspect identity/platform, up без сети/pull/build |
| Wrong archive/hash/image/platform | Нет startup; существующий хороший container не удалён |
| Materialization | Source env keys/comments сохранены; SERVER_ID из host ID; один env/base на library-host |
| Две библиотеки на одном Docker | Разные names/paths/projects/ports; нет inheritance/vars leakage |
| Несколько приложений одной библиотеки | Общий env/base; разные instance identity vars; изменение одного изолировано |
| Одна библиотека на двух hosts | SERVER_ID различается, logical instance ID одинаков, оба Verify PASS |
| Rootless runtime mismatch | Wrong account/socket/rootful daemon BLOCK до mutations |
| Ownership/port/path collision | Нет takeover/rewrite/delete чужих объектов |
| Clean repeat | changed=0 и прежние container IDs; нет повторной доставки/recreate |
| Env/base/config/image update | Только затронутые consumers меняются; readiness после изменения |
| Readiness/identity negatives | Verify read-only; stopped/unhealthy/wrong image/ownership — failure; config drift вне обычного Verify |
| Interrupted operation/multi-host failure | Retry восстанавливает exact desired state; нет ложного общего PASS |
| Interrupted config write → recreate | Обычный Verify не обнаруживает file/config drift; Apply retry меняет ID/label только нужного instance, disk/label совпадают; следующий repeat changed=0 |
| Application config consumption | На startup-reader fixture значение в памяти меняется после retry; если такой режим existing image недоступен, prerequisite отмечен отдельно без ложного PASS |
| Scope limit/parallel run | Исключённые hosts не считаются verified; конкурентный library-host Apply BLOCK |

Журнал `evidence/a2-test-journal.md` создавать при реализации: source fingerprint,
package/image/archive identities, selected hosts/runtime, safe commands/results,
recaps changed и container IDs до/после, failures и cleanup. Не помещать secrets,
raw inspect/config/environment или private Docker auth в evidence.

Cleanup QA удаляет только созданные exact test objects с проверенным ownership,
в рамках заранее согласованного scope. Не выполнять compose down чужих projects,
image prune и рекурсивное удаление вычисленных непроверенных путей.

**Выход A2:** обычный standalone Apply/Verify на existing Docker, registry и
offline доставка по одной source policy, два изолированных библиотечных запуска,
multi-host и clean repeat с реальным evidence. Это baseline без provider/Agent/
endpoint provisioning и без Installer UI acceptance. Следующий этап A3 отдельно
разрешает владелец; A2 PASS не означает готовность полного приложения с подключениями.

## 9. Ревью и разрешение реализации

Перед представлением плана владельцу — один независимый FULL PLAN review
по [процедуре](../../../../agent-procedures/review.md), отчёт `reviews/a2-plan-review.md`.
Особое внимание: image/source trust, package render authority, secrets,
rootless isolation, managed ownership, concurrency и обоснование новых механизмов.
При BLOCK остановиться; корректировки blocker IDs и единственный
TARGETED_RECHECK выполняются только по разрешению владельца.

Будущая реализация меняет artifact/security boundaries и требует независимого
FULL DIFF review. Плановое ревью не заменяет его и реальный target QA.
