# A6 — публикация application endpoints через HAProxy и DNS

Дата: 2026-10-11. Рабочая ветка: `codex/application-libraries`.
Исходная ревизия: `540aa05c49ae531b3041da16cbad4771f5ccdd6e`.
Документ описывает следующий standalone этап после A1–A5. Запрошена подготовка
плана; реализация и target QA этим документом не разрешаются. Текущий статус
ведётся в [CURRENT_STATE](../../../../../CURRENT_STATE.md).

## 1. Результат и границы

Для логического экземпляра `apigateway-sdku`, размещённого на двух Docker-хостах,
Core разрешает один endpoint `https://apigateway-sdku.<domain>`. HAProxy получает
два backend targets: inventory-адрес каждого хоста и его опубликованный Docker
порт. DNS указывает на существующий frontend/VIP endpoint group.

Публикация начинается после готовности всех выбранных placements экземпляра.
Ресурсы библиотеки, accounts, Vault Agent и контейнеры используют A1–A5. Endpoint
не зависит от наличия accounts или secret bindings.

В A6 входят:

- typed endpoint settings в defaults приложения с обычными overrides;
- одна target-free проекция endpoint на logical instance;
- расширение существующих endpoint/HAProxy/DNS resolver и source-owned hooks;
- HAProxy candidate validation, partial activation и reload только при изменении;
- source-only DNS update и read-only Verify внешнего endpoint;
- standalone Ansible путь, включая multi-host, repeat и частичный сбой.

Публичный endpoint использует HTTPS/443; порт в URL и app configuration не задаётся.
Существующий public frontend HAProxy работает в `mode http`. A6 поддерживает
HTTP и HTTPS backend приложения. TCP/UDP endpoints отклоняются как неподдерживаемые
этим frontend; их публикация требует отдельного расширения frontend-контракта.
Для инфраструктурных Kafka/PostgreSQL/Redis connections сохраняются A1–A5 rules.

Общий production execution DAG и bundle closure завершаются в A7/A8. Go/UI,
установка отсутствующего HAProxy/BIND/Keepalived, создание endpoint group,
автоматическое удаление библиотеки и миграция старых provider hosts сюда не входят.

## 2. Фактическая основа и необходимые изменения

| Существующее место | Что уже делает | Изменение A6 |
| --- | --- | --- |
| `application_libraries.py` | Проверяет endpoint listener/group, сохраняет endpoint в каждом placement | Проверять typed settings и согласованность общего endpoint; собрать все host targets |
| `application_runtime.py` | Пока отклоняет endpoint-enabled runtime как неподдерживаемый | Снять только A6 prerequisite после подключения публикации; сохранить A2 authority/Compose проверки |
| `application-libraries-apply.yml` | Providers → materialization → image/container Apply и lightweight Verify | Добавить публикацию после завершения play на всех Docker-хостах |
| `service_endpoint_resolution.py` | Вычисляет service FQDN и collisions | Добавить derived application sources и общую collision-проверку |
| `service_integration_resolution.py` | Выбирает HAProxy на Keepalived-hosts и BIND по зоне | Использовать ту же выборку для application source |
| `haproxy_resolution.py` | BackendSettings, target addresses, TLS identity, fingerprint | Разрешать application placements/published ports и выбранный app listener |
| `services/integrations/playbooks/apply-endpoint.yml` | Source-only HAProxy → DNS → внешний probe | Поддержать typed application source без фиктивного service deployment |
| `services/haproxy/.../roles/haproxy` | Capture owned inventory, candidate, validation, partial publish/reload | Потреблять app backend через те же фазы и ownership |
| `services/bind/playbooks/integrate.yml` | Изменяет точные source A records на primary | Потреблять app FQDN/VIP через тот же update task |
| `services/integrations/tasks/probe-endpoint.yml` | DNS и HTTP probe `/`, `validate_certs: false` | Для app использовать typed probe path/status и проверенную CA; service compatibility сохранить |

Использовать existing canonical contracts: [Core](../../../../ansible-core.md),
[project contract](../../../../project-contract.md), [endpoint placement plan](../../../endpoint-placement/endpoint-haproxy-placement-plan.md),
[общий план](../../implementation-plan.md#a6-endpoints-через-существующие-haproxydns-hooks)
и [порядок выполнения](../../execution.md#публикация-endpoint).

## 3. Defaults приложения и group_vars

Endpoint задаётся в `platform_application_definition.defaults`. Для A6 использовать
один существующий `BackendSettings` формат. Ранний вложенный пример
`health_check/connection/tls` из `configuration.md` является черновиком;
при реализации синхронизировать его с этим плоским shared contract. Отдельный
конвертер между двумя равноправными описаниями backend не нужен.

```yaml
# application-packages/apigateway/1.0.0/
# roles/application_apigateway/defaults/main.yml
platform_application_definition:
  name: apigateway
  version: "1.0.0"
  defaults:
    ports:
      http: {container: 10101, published: 18081}
    endpoint:
      enabled: false
      listener: http
      protocol: http
      endpoint_group: applications
      haproxy:
        backend:
          balance: roundrobin
          check: true
          fall: 3
          rise: 2
          ssl: false
          checkInterval: 5s
          httpCheck: {method: GET, path: /status, expectedStatus: 200}
          maxconn: 100
          timeoutConnect: 5s
          timeoutServer: 60s
      probe:
        path: /status
        expected_status: 200
        timeout: 10
```

```yaml
# inventory/group_vars/all/platform-installer.yml
# Существующие serviceDeployments/endpointGroups сохраняются.
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      libraryRef: sdku@1.0.0
      runtimeRef: docker-apps
      # bindings/resources/shared_secrets из A1–A5
      applications:
        gateway:
          overrides:
            endpoint:
              enabled: true
              endpoint_group: applications
              haproxy:
                backend:
                  balance: leastconn
                  timeoutServer: 120s
```

`gateway` — существующий recipe slot. `application_instance_id` вычисляется
как `apigateway-sdku`; ID/FQDN/backend name пользователь повторно не вводит.
Host membership остаётся в `platform_application_libraries` из `host_vars`.
Published port может различаться на хостах через существующие разрешённые
overrides. `.env` остаётся library-host файлом; endpoint не переносит его
параметры или credentials в HAProxy/DNS.

Ansible выполняет существующий merge defaults/recipe/deployment/host inputs.
Endpoint/backend nested override объединяется тем же документированным
`combine(recursive=true)` пути A1; отдельный precedence resolver не добавляется.
Backend settings и внешний probe у logical instance должны быть одинаковы
на всех placements; различающиеся значения — validation finding. Host ports
и addresses относятся к placements и могут отличаться.

### 3.1. Shared BackendSettings

Существующие обязательные effective поля: `balance`, `check`, `ssl`; зависимости
`fall/rise` при `check=true`, `sslVerify` при `ssl=true` сохраняются. Поддерживаемые
balance: `roundrobin`, `leastconn`, `source`.

В том же Core normalizer/schema и существующем backend template добавить только
следующие optional поля, необходимые для описанных application defaults:

| Поле | HAProxy projection | Проверка |
| --- | --- | --- |
| `checkInterval` | `default-server inter` | Ограниченная duration, только при check |
| `httpCheck` | `option httpchk` / structured HTTP check | GET/HEAD, абсолютный path без CR/LF, один ожидаемый status 100–599; только HTTP/HTTPS backend и check=true |
| `maxconn` | `default-server maxconn` | Положительный bounded integer |
| `timeoutConnect` | `timeout connect` в backend | Ограниченная duration |
| `timeoutServer` | `timeout server` в backend | Ограниченная duration |

Duration принимает целое число с `ms` или `s`: `checkInterval` в диапазоне
100ms–60s, backend timeouts 100ms–300s. `maxconn` — 1–100000. HTTP path —
1–2048 символов, начинается с `/`, без whitespace/control characters;
method — GET/HEAD. `probe.timeout` — 1–60 секунд. Значения проверяются до render.

Использовать одно shared schema definition для service/app backend settings либо
существующий schema generator/ref-механизм. Известные service backends без новых
полей должны давать прежние effective settings и прежний rendered fragment.
Не разрешать arbitrary HAProxy directives, shell, raw snippets или secret fields.

`protocol=http` требует `ssl=false`. `protocol=https` требует `ssl=true` и
`sslVerify=required` для application endpoint. `sslVerify=none` не доказывает
backend identity и не считается поддержанным application TLS вариантом A6.
Frontend сертификат и backend trust используют существующие PKI/HAProxy plans.
HTTPS backend должен представить сертификат с endpoint FQDN в SAN, а CA должна
быть доверена HAProxy. SNI/verifyhost выводятся из того же FQDN. Пробел trust/SAN
блокирует TLS publication; отдельное CA-хранилище для A6 не вводится.

## 4. Target-free endpoint projection и идентичность

### Универсальный вход endpoint hooks — решение владельца

За основу взять текущую реализацию hooks без кардинальной переделки. Сохранить
existing entrypoints, resolver outputs и provider phases/tasks; расширять их
additively лишь там, где application source нельзя передать существующими полями.
Универсальный вход не означает создание нового framework, замену действующего
pipeline или обязательную миграцию сервисов на новый API. Legacy service-only
вызовы остаются рабочими. Изменения ownership matching и порядка routing из
P01/P02 выполняются точечно в существующем коде. Если минимальная адаптация
невозможна без существенного изменения контракта, вынести конкретное расхождение
владельцу до такой переделки.

Core приводит инфраструктурные deployments и экземпляры приложений к одной
существующей runtime endpoint/backend projection, расширенной только необходимыми
полями. Это derived input, не новый desired-state контракт или отдельное хранилище.
Различия исходных настроек и размещения обрабатываются при формировании проекции.

Общий вход содержит `sourceId`, `endpointGroupId`, `fqdn`, backend identity/settings,
список targets с address/port/serverName, разрешённые DNS addresses/TTL и необходимые
probe/TLS параметры. Поля существующих resolver outputs переиспользуются; пример
ниже показывает application source, но не вводит отдельный provider API.

HAProxy, DNS и общий endpoint orchestration потребляют эту проекцию без
`if service / if application`. Метаданные происхождения могут сохраняться для
диагностики, но не выбирают provider execution path. Source identity определяет
принадлежность файлов/записей независимо от происхождения. Отдельных application
hooks, копий provider tasks и второго DTO нет. Full reconcile использует общий
набор нормализованных источников; legacy service-only вызовы сохраняются через
existing Core resolution. Не пересчитывать проекцию на каждом provider host.

Проверка: одинаковые нормализованные входы дают одинаковый provider render/action
независимо от происхождения; service/application neighbors сохраняются при partial
Apply/repeat/retry и full reconcile. Существующие TLS/probe semantics сервисов
сохраняются через значения проекции, а не ветвление по типу источника.

Получать source records из готовой application projection после A1 resolve,
не добавляя приложения в desired `serviceDeployments` и не создавая fake catalog
service. Дополнительный runtime input существующих resolver по умолчанию пуст.

Для каждого endpoint-enabled logical instance собрать одну запись:

```yaml
source:
  kind: application
  projectId: qa-applications
  libraryId: sdku
  instanceId: apigateway-sdku
sourceId: apigateway-sdku        # computed routing/file key
endpointGroupId: applications
fqdn: apigateway-sdku.apps.example.test
backendName: apigateway-sdku-applications
configFileName: 30-backend-apigateway-sdku-applications.cfg
protocol: http
targets:
  - {hostId: node1, address: 192.168.56.101, port: 18081, serverName: node1}
  - {hostId: node2, address: 192.168.56.102, port: 18081, serverName: node2}
```

Префикс `30-backend-` и existing managed ownership header сохраняются: текущий
capture/archive module уже проверяет эти files. `backendName` совпадает с текущей
HTTP Host routing формулой `<first DNS label>-<endpointGroupId>`. Service records,
file names, FQDN и ownership headers не переименовываются.

Решение владельца по A6-P01: partial prepare/activate/archive выбирают файлы по
точной проверенной source/group mapping, а не по префиксу sourceId. Обновление
`apigateway-sdku` не должно затрагивать `apigateway-sdku-test`; новых registry нет.

Решение владельца по A6-P02: существующий suffix Host routing сохраняется.
ACL/use_backend выводятся по убыванию длины нормализованного domain; при равной
длине используется стабильный порядок по ID. Более конкретный domain проверяется
раньше общего. Одинаковые нормализованные domains разных endpoint groups
блокируются target-free до mutation. Уникальность полного FQDN сохраняется.
Frontend не ограничивается одной группой. DNS zone BIND и domain endpoint group
не отождествляются: `cspa.scada.local` и `sdku.scada.local` могут направляться
на один VIP с разными backend. Изменение существующей привязки provider/Keepalived
не подразумевается этим исправлением и требует отдельного согласования контракта.

Типизированная identity отличает приложение от service. Валидный набор routing/file
keys обязан быть уникален между service и application источниками; совпадение
`instanceId` с endpoint-enabled service ID блокируется до target mutation.
Также проверять FQDN/backend/file collisions, в том числе между endpoint groups
с совпадающим domain. Для endpoint-enabled instance ID требуется DNS label ≤63
символов; молчаливого усечения или ручного второго ID нет.

Addresses берутся из existing inventory host address projection. Backend port —
`placements[host].ports[endpoint.listener].published`, не container/bridge port.
Проверять valid TCP port и наличие ровно одного выбранного listener на каждом host.
Все выбранные placements входят в target list в стабильном порядке.

Проекция содержит настройки, source identity, targets, выбранных providers и
fingerprint. В ней нет secrets, raw hostvars, container bridge IP или runtime
readiness claims. Readiness — отдельный observed результат исполнения.

Для проектов без libraries или с `endpoint.enabled=false` optional application
projection пуста; никаких endpoint jobs и target calls не создаётся.

## 5. Выбор providers и пропуск optional hooks

Использовать `haproxy_provider_hosts` без второй формулы: endpoint group →
Keepalived placements → HAProxy deployments на этих хостах. BIND выбирается по
существующему matching zone правилу. App не задаёт отдельные HAProxy/BIND deployment
refs и не меняет инфраструктурный provider selection.

Отсутствие endpoint declaration/enabled flag пропускает весь endpoint hook.
Отсутствие найденного HAProxy или DNS provider сохраняет existing diagnostics/skip
соответствующего mutation hook. Явная ошибочная ссылка/group, неоднозначный provider,
collision и неподдерживаемый protocol — validation BLOCK.

Отдельный endpoint Verify обязан сообщить `APPLICATION_ENDPOINT_NOT_PUBLISHED`,
если enabled endpoint не получил необходимый provider или не доказан внешний route.
В этом случае не утверждать, что URL работает, даже если контейнер Running.
Standalone Verify использует существующий failure/result путь; нового execution
terminal state не вводить. При внешнем DNS, не управляемом проектным BIND, его
наличие подтверждается обычным DNS probe, без автоматической записи чужой зоны.

## 6. Последовательность Apply

1. A1/A2 preflight один раз разрешает selected libraries, runtime jobs и endpoint
   sources. Все статические collisions/provider/TLS prerequisites проверяются
   перед provider/container mutations.
2. A3–A5 выполняют resources библиотеки, shared secrets, accounts/grants и AppRole.
3. A2 materializes library `.env`/base Compose и instance configs/Agent/PKI;
   доставляет image и запускает контейнеры на выбранных Docker-хостах.
4. A2 lightweight Verify подтверждает image/ownership/Running и настроенный
   healthcheck каждого placement. Барьер play с `any_errors_fatal` не допускает
   публикацию instance при failed placement. Unconfigured healthcheck не заменять
   фиктивным readiness claim.
5. Для каждого logical instance выполнить один endpoint hook. Общая inventory,
   package resolution и provider selection переиспользуются в пределах invocation.
6. С HAProxy provider hosts проверить доступность каждого app published target.
   HTTP backend — typed HTTP path/status; HTTPS — тот же HTTP probe с проверенной
   CA/hostname плюс существующая TLS identity проверка. Применить bounded timeout;
   не делать probe для env variable/credential/privilege.
7. Existing HAProxy partial pipeline: capture proven prior inventory → собрать
   полный candidate с сохранением соседних fragments → `haproxy -c` на всех
   participating provider hosts → activation barrier → publish только selected
   source fragment → reload только при изменённом active graph.
8. После успешной HAProxy activation/reload передать точный app FQDN/VIP/TTL в
   existing BIND source update на primary. Wildcard и соседние records не менять.
9. Выполнить read-only external probe `https://<fqdn><probe.path>` с CA и hostname
   verification. Подтвердить DNS addresses и expected HTTP status. Для QA `/status`
   дополнительно проверяется на стороне fixture как содержательный A4/A5 результат.

Один endpoint содержит все ready targets logical instance. Не публиковать только
часть targets молча. Если один host не готов, новое endpoint mutation не начинается;
существующий ранее опубликованный backend сохраняется, а run сообщает failure.

User Compose может выбирать `127.0.0.1`, `0.0.0.0` или конкретный bind address.
A2 не навязывает его. Для enabled endpoint A6 проверяет фактическую доступность
published port с provider hosts. Loopback-only port на отдельном Docker-хосте
даёт понятный endpoint reachability failure; Core не переписывает Compose.

## 7. Verify, repeat и частичный сбой

Обычный application Verify сохраняет один `docker inspect` на placement.
Endpoint Verify добавляется отдельной фазой для enabled logical instances:
read-only provider evidence, authoritative/consumer DNS и external HTTPS probe.
Не добавлять обратно Compose hash, SHA256 всех files и mounts в обычный Verify.

Verify не вызывает candidate prepare, DNS update, HAProxy reload, account hooks
или container restart. Проверять все expected targets через existing HAProxy
runtime/status evidence либо прямые bounded backend probes; один успешный public
HTTP request сам по себе не доказывает второй target. На публичной стороне
проверять TLS trust/hostname, exact status и фактический route. Redirect не является
автоматическим PASS. Secret response bodies в events/logs не выводить.

На repeat совпадающие backend/DNS settings дают `changed=0`; HAProxy reload,
nsupdate, container restart и image delivery не выполняются без причины.
Existing candidate safety checks сохраняются. Дополнительных benchmark-серий нет.

| Сбой | Поведение и retry |
| --- | --- |
| Один Docker placement не готов | Endpoint hooks не стартуют; ранее активный route не меняется |
| Target недоступен с HAProxy host | Failed bounded probe до activation; user bind address не исправляется автоматически |
| Candidate invalid на одном provider host | Activation barrier удерживает прежнюю конфигурацию на всех hosts |
| Activation/reload частично выполнен | Existing provider error; DNS phase не начинается; retry сводит только selected source, без обещания общей транзакции |
| DNS update не выполнен | Контейнер/HAProxy могут уже работать; результат отдельно показывает DNS failure; повтор исправляет exact owner |
| External TLS/status probe не прошёл | Existing failure; не выдавать Running за доступный endpoint, не удалять accounts/data |
| Чужой backend file/CNAME/desired FQDN collision | Existing ownership/collision BLOCK; не заменять соседний источник |
| Изменён endpoint group/placement | Current hosts/source-only reconcile; formerly excluded hosts требуют existing explicit full reconcile |

`endpoint.enabled=false` пропускает hook и не становится скрытой командой удаления
ранее опубликованного endpoint. Очистка отсутствующих desired sources относится
к существующему explicit full reconcile. A6 full reconcile обязан видеть both
service и application sources, чтобы не архивировать живые app fragments и не
удалять их DNS records. Бывшие hosts, которых нет в current inventory, по-прежнему
не обнаруживаются автоматически.

## 8. Скорость и минимальное число действий

- Application packages/settings/source jobs вычисляются один раз на invocation.
- Provider placement/discovery и безопасная host projection выполняются один раз,
  а не на каждый app/host. Не переносить loop hostvars collection из существующего
  playbook в повторяющийся per-instance hook.
- Один logical hook на instance: его targets проходят provider fan-out внутри
  текущего scope. Разные instances не объединяются в provider-wide mutation batch.
- HAProxy prepare/activate/reload barriers переиспользуются; отдельный генератор,
  daemon, registry endpoint jobs и durable ledger не создаются.
- Backend settings render выполняется одним template task на source/provider host,
  а не task на настройку или target. DNS owner применяется одним `nsupdate` batch
  через existing task; текущие comparison/read-after-change safeguards сохраняются.
- Container inspect result A2 Apply используется как readiness evidence в том же
  run; дополнительный Docker inspect перед publication не нужен.
- Record elapsed time/task/provider call counts first Apply/repeat/Verify в обычном
  QA run. Числового SLA и отдельного benchmark campaign нет.

## 9. Карта изменений и подэтапы

| Подэтап | Файлы/ответственность | Проверяемый выход |
| --- | --- | --- |
| A6.0 | `contracts/application-libraries/v1alpha1/settings.schema.json`, shared BackendSettings schema, `application_libraries.py` | Typed settings, host consistency, listener/source/FQDN collisions, infra-only compatibility |
| A6.1 | Existing `service_endpoint_resolution.py`, `service_integration_resolution.py`, `haproxy_resolution.py`, `dns_resolution.py` и thin Ansible module adapters | Target-free application source projection через существующие resolver, deterministic fingerprint |
| A6.2 | `services/integrations/playbooks/apply-endpoint.yml`, HAProxy integrate/role tasks/template, BIND integrate input | Selected app source uses existing provider pipeline and ownership; service path unchanged |
| A6.3 | `application-libraries-apply.yml`, endpoint Apply/Verify stage entrypoints, existing integration probe tasks | Post-readiness barrier, one logical instance hook, read-only Verify и explicit unpublished evidence |
| A6.4 | Focused tests, representative A5 probe fixture, docs/QA journal | Two-host external `/status`, repeat, TLS, failures and neighbor preservation |

New application endpoint stage playbook допустим как короткая последовательность
вызовов existing entrypoints. Не дублировать HAProxy prepare/activate/start или BIND
update task files в application-specific roles. Public modules/outputs расширять
additively; legacy service-only calls должны сохранять результат. A7 добавляет
полную snapshot/plan/execution exposure; A6 готовит только необходимые поля.

При изменении service manifest/schema использовать existing catalog/schema
generators на Execution Node и обновить locks в fixtures. До QA прочитать
[QA procedure](../../../../agent-procedures/qa.md). Core/Python/Ansible выполнять на RED OS
из актуального дерева через стандартный `qa-sync.ps1`, затем удалить QA workspace.

## 10. Проверки и критерии завершения

| Проверка | Требуемое доказательство |
| --- | --- |
| Нет libraries / endpoints disabled | Старый infra-only snapshot/resolve и Apply/Verify работают; endpoint target calls отсутствуют |
| Defaults + малый override | Backend field override не стирает остальные defaults; пользователь не повторяет ID/targets/FQDN/443 |
| Два Docker-хоста, один instance | Два правильных host published targets, один FQDN/backend, SERVER_ID host-specific |
| Host endpoint setting mismatch | Validation BLOCK до mutation; различные published ports разрешены |
| Service/app/FQDN/file collision | Finding с exact field, никакого takeover |
| HTTP backend | HTTPS/443 frontend → два HTTP targets; `/status` подтверждает A4/A5 connections |
| HTTPS backend | Valid trust/SAN/SNI PASS; wrong CA/hostname/expired certificate BLOCK |
| HTTP health/timeout settings | Shared schema и реальный `haproxy -c`; неиспользуемые поля не меняют service render |
| Неподдерживаемый TCP/UDP endpoint | Явный target-free finding; HTTP probe не применяется |
| Readiness/reachability failure | Второй target unhealthy или loopback-only; publication не начинается, прежний route сохранён |
| Provider missing | Existing mutation skip/diagnostic и endpoint Verify `NOT_PUBLISHED`, без ложного URL PASS |
| Partial source isolation | Existing service и другая library сохраняют backend/DNS/container identities и содержимое |
| Prefix source IDs | Apply/repeat/retry `apigateway-sdku` сохраняет файл/route `apigateway-sdku-test`, включая service/application сочетание; соседний файл не архивируется |
| Endpoint group routing | `cspa.scada.local` раньше `scada.local` независимо от ID; sibling domains выбирают свои backend; одинаковые нормализованные domains BLOCK до mutation |
| Repeat | `changed=0`; нет reload/nsupdate/restart без изменения |
| Partial failure/retry | Invalid candidate, provider-host failure и DNS failure; bounded retry исправляет selected source |
| Explicit full reconcile | Service/app sources объединены; active app fragments/records сохраняются, отсутствующие обрабатываются existing policy |
| External probe | DNS указывает на expected frontend/VIP, проверены TLS и exact HTTP status; HTTP 502/503/redirect не PASS |
| Secret safety | Backend/DNS/jobs/events не содержат account passwords, RoleID/token/private key/response secret values |

Реальное A6 QA использует существующий digest-pinned connection-probe image A5,
изолированную owned библиотеку и два Docker-host placements. Подтвердить `/status`
через фактический HAProxy endpoint и управляемую DNS зону. Deployed infrastructure
менять только в явно разрешённом QA scope; переносить прежний manual/container
PASS на endpoint acceptance нельзя.

A6 завершён после standalone Apply/Verify/repeat, обязательных negative/partial
cases, independent review gate и owner acceptance. Реальная Go/Wails/UI приёмка
остаётся в этапах B/C. По [review procedure](../../../../agent-procedures/review.md) этот
контракт требует одного FULL PLAN review; public source/settings/ownership
изменения при реализации требуют independent FULL DIFF review. BLOCK останавливает
работу до решения владельца; бюджет дальнейшей проверки сохраняется.
