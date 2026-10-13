# A8. Библиотеки в общем плане выполнения

Дата: 2026-10-13. Ветка: `codex/application-libraries`.
Статус: технический план; реализация требует принятия владельцем после PLAN review.

## 1. Результат и границы

Один Core BuildDeploymentPlan формирует инфраструктурные действия и последнюю
фазу библиотек. Один approved manifest, run ID, runtime lease, журнал и Cancel
обслуживают весь запуск. Первая mutation библиотеки допускается только после
успешного Apply/Verify всех инфраструктурных deployments этого плана.

А7 реализовал target-free модель, plan/v1alpha4, secret descriptors/v1alpha3 и
две фиксированные операции APPLICATION_LIBRARIES_APPLY/VERIFY. Сейчас наличие
библиотек намеренно даёт APPLICATION_COMMON_PLAN_INTEGRATION_REQUIRED и null
executable manifest. А8 заменяет этот временный запрет проверяемой интеграцией.

В scope: Core план, private manifest, существующий execution protocol/controller,
защищённые runtime inputs/outputs, адреса/SSH trust и наблюдение выполнения.
Go backend, React/Wails, selective install, resume/checkpoint scheduler,
автоматический rollback, Kafka ACL и полная приёмка A9 не входят в A8.
Standalone без Installer остаётся обязательным. UI acceptance относится к B/C.

## 2. Минимальный граф

```text
existing preflight / PKI / infrastructure phases
  apply:postgres -> verify:postgres
  apply:vault    -> verify:vault
  apply:docker   -> verify:docker
  apply:other    -> verify:other
                    |
                    | все infrastructure Verify успешны
                    v
  applications:apply -> applications:verify
```

Добавить одну последнюю фазу с двумя уже существующими действиями А7.
`applications:apply.dependsOn` содержит отсортированные ID ВСЕХ SERVICE_VERIFY
общего плана; `applications:verify.dependsOn = [applications:apply]`.
Сохранить действующие PKI/service dependencies и последовательность исполнения.
Барьер — зависимости плюс последовательный fail-fast controller, без отдельного
Ansible play, сетевой проверки или нового operation type.

Пустой список Verify не доказывает готовность infrastructure. Для общего плана
с библиотеками отсутствие необходимых infrastructure actions блокирует execution;
ручной standalone запуск с существующими providers сохраняет свои preflight.
Сбой даже инфраструктурного сервиса, не используемого первой библиотекой,
останавливает переход. Cancel проверяется перед каждой операцией, в том числе
между последним Verify и applications:apply. Уже выполненные mutations сохраняются.

Внутри applications:apply повторно используются A1–A6: ресурсы библиотеки,
аккаунты/grants, Vault, materialization, image delivery, запуск/readiness,
endpoint hooks. Один batch ресурсов на библиотеку и один вызов аккаунтов на
экземпляр сохраняются. Не разбивать их на отдельные controller processes.

## 3. A8.1 — authoritative planning

Основные точки: `module_utils/deployment_plan.py`, `application_plan.py`,
action `build_deployment_plan.py`, `playbooks/deployment-plan-machine.yml`.

1. Проверить resolved bindings, provider capabilities, Docker placements и
   closure инфраструктуры существующим Core resolution; Go правил не добавлять.
2. Убрать временный A7 finding только когда построены корректные infrastructure
   actions и application actions, а остальные findings не блокируют execution.
3. Включить application actions в итоговые phases и их fingerprint до создания
   manifest. Public plan и private manifest обязаны описывать один порядок.
4. Проверить уникальность ID, существование dependencies, отсутствие цикла и
   расположение каждой dependency раньше dependent operation. Использовать
   существующие проверки графа; не вводить отдельный DAG engine.
5. Не выбирать live источник образа в target-free Build. Requirement/digest/lock
   и node-scoped policy связываются с планом; registry/offline выбор делает A2.
6. Infrastructure-only и пустые libraries сохраняют прежние версии/семантику,
   включая plan fingerprints при неизменных исходных inputs.

Контрольные сценарии: несколько libraries, несколько placements, providers без
непосредственной связи с приложением, неизвестный ref, отсутствующий Docker,
неполный image lock, один и тот же host у приложения и provider.

## 4. A8.2 — private manifest и protocol capabilities

А7 имеет закрытую schema отдельной application operation под
`contracts/execution-manifest/v1alpha2/`. А8 завершает schema полного manifest
для mixed run: существующие service/PKI operations плюс две application operations.
Не переиспользовать номер уже выпущенного контракта с несовместимой семантикой.
Сохранить v1alpha1 infrastructure path; завершение нового v1alpha2 документировать
в contracts README и execution contract.

Private manifest включает applicationLibraries, applicationSemanticFingerprint,
applicationSecretRequirements и существующие runtime release/project bindings.
Поля нельзя передать как произвольный executable/argv/playbook: controller
по-прежнему выбирает два фиксированных standalone entrypoints.

Собрать manifest из финальных phases в одном месте. Не хранить отдельный
исполняемый applicationExecution рядом с approved manifest. Если промежуточная
А7 projection нужна для построения, она остаётся внутренней derived моделью.
Связать application descriptors с существующим descriptor-set fingerprint,
approval identity, manifest digest и проверкой lease. Не менять authority inputs.

Protocol capabilities рекламируют mixed application execution только после
поддержки schema, lease и controller. Старый consumer не получает новый contract
молча: unsupported version блокируется штатной negotiation. Go/UI ещё не
объявляются совместимыми и не получают обход version checks.

## 5. A8.3 — targets и защищённые inputs

Точные targets: Docker placements плюс hosts инфраструктуры, которые существующие
provider/endpoint hooks реально могут контактировать. Учитывать discovery primary
PostgreSQL, HA ClickHouse, Redis/Sentinel, Vault, HAProxy/BIND по текущим resolved
проекциям. Не включать весь inventory только потому, что А7 использовал широкий
список snapshot hosts. Не изобретать второй topology resolver.

Один и тот же scope используется для public approval targets, requiredCredentials,
targetConnections, known_hosts и operation runtime projection. Execution Node
учитывается существующим контрактом отдельно от удалённых targets. Перед Apply
и Verify приложений выполнить штатную проверку target trust, как для services.

Runtime secrets поступают через уже реализованный typed lease. Credentials не
пишутся в portable vars, public plan, command line или events. Run-owned protected
files имеют существующие права и очищаются на SUCCESS/FAILED/CANCELLED.
Application-specific files выдаются только соответствующим операциям.

Проверить два источника Vault admin token:

- explicit application runtime input для уже установленного Vault;
- bootstrap output Vault, установленного раньше в ЭТОМ общем run.

Принятая владельцем коррекция A8-P01: использовать уже сохраняемые защищённые
файлы на Execution Node. Новый storage/custody механизм не создавать.
Источник закрепить в digest-bound private descriptor: `RUNTIME_INPUT` либо
`CURRENT_RUN_BOOTSTRAP`, с точным Vault deploymentRef. Это source runtime input,
а не дополнительный пользовательский параметр библиотеки.

Для первого bootstrap Vault выбрать CURRENT_RUN_BOOTSTRAP: admin token не входит
в обязательные operator lease values. До infrastructure dispatch проверить
объявление output/provider и привязку к manifest, но не требовать ещё не созданный
файл. После успешного Verify всей инфраструктуры, до application mutation,
прочитать admin-token из защищённых файлов именно текущего run и этого provider,
используя существующие проверки файлов и custody. Затем материализовать
application input существующим механизмом. Terminal capture/delivery outputs
сохранить для выдачи оператору; не ждать его для application hook.

Для ранее установленного Vault использовать RUNTIME_INPUT через существующий
typed lease. Повтор после успешного bootstrap относится к этому варианту:
оператор предоставляет существующий token штатным runtime input, старый run и
global latest token автоматически не искать. Если свежесть Vault нельзя доказать
target-free при Build, preflight исходного плана может обнаружить уже
инициализированный Vault и потребовать новый Build с RUNTIME_INPUT до mutations.
В пределах утверждённого run не переключать источник автоматически.

При двух заявленных источниках отклонить неоднозначность до mutations. Отсутствие
нужного output после барьера, чужой provider/run или небезопасный файл блокируют
application mutation. Промежуточный token доступен только нужной операции и
очищается штатно; durable bootstrap outputs сохраняют существующую политику
хранения и terminal delivery. Unseal shares приложению не выдаются.
Go decrypt/upload остаётся последующим B.

Аналогично проверить доступность общего PKI password/material и image credentials
через существующие run inputs. Изменение требуемого secret scope аннулирует lease
и approval по текущему контракту. Независимые runtime файлы могут готовиться до
барьера без Vault API/provider mutations. Application projection с
CURRENT_RUN_BOOTSTRAP готовится после барьера; application lease resolver не
должен требовать его как заранее предоставленное значение.

## 6. A8.4 — execution, события и ошибки

`execution_controller.py` исполняет один manifest по порядку. До dispatch проверить
целостность application suffix и infrastructure dependencies; при ошибке manifest
не начинать mutations. Запуск каждого application operation использует текущие
SSH credentials, runtime vars и trusted release. Не запускать вложенный controller,
новый run или повторную установку provider.

Существующие ACTION_STARTED/TASK_STARTED/ACTION_COMPLETED показывают phaseId и
actionId библиотек. Сохранить callback и безопасные bounded diagnostics;
serviceDeployment не заполнять фиктивным library ID. Если schema требует source
identity, использовать существующие application fields либо минимальное расширение
контракта, согласованное с plan version. Не создавать отдельный журнал приложений.

Ошибка application Apply завершает run FAILED, Verify не запускается. Ошибка
Verify тоже FAILED. Повтор — новый authoritative Build/approval/run с обычной
идемпотентностью A1–A6; skip по старому SUCCESS и автоматический resume не добавлять.
Cancel сохраняет уже созданные resources/containers и штатно убирает runtime
credentials. Общая infra установка не ждёт будущие application endpoints: их
публикация выполняется consumer hooks после readiness во втором этапе.

## 7. Скорость и простота

Две application controller операции на весь выбранный scope. Барьер добавляет
нулевое число Ansible tasks и внешних запросов. Не дублировать snapshots/preflight,
которые уже нужны существующему standalone entrypoint для exact fingerprint.
Обычный Verify контейнера сохраняет один docker inspect, затем уже реализованные
содержательные connection/endpoint checks. Не возвращать file/hash Compose audit.
Не выполнять новые benchmark серии; время двух операций записать из обычного QA.

## 8. QA и приёмка A8

Python/Ansible только RED OS из текущей ветки через qa-sync, по QA procedure.
Основной агент запускает affected tests; independent FULL DIFF review обязателен
из-за manifest/secret/lifecycle boundaries. PLAN review — один FULL; после BLOCK
остановка, targeted recheck только по отдельному решению владельца.

| Проверка | Ожидаемый результат |
| --- | --- |
| Empty libraries / infra-only | Прежний executable plan/protocol; actual Start/Verify и Cancel regression |
| Target-free mixed Build | Ни одного SSH/registry/Vault запроса, deterministic fingerprints |
| All-infrastructure barrier | Каждая SERVICE_VERIFY dependency раньше application Apply |
| Unrelated infra failure | Ни одной library mutation и ни одного application ACTION_STARTED |
| Missing/reordered/duplicate operation | Manifest rejected до mutations |
| Cancel на границе | Applications не стартуют; terminal CANCELLED и cleanup |
| Apply failure | Application Verify не выполняется; FAILED, safe diagnostics |
| Secret scope/version drift | Lease/manifest validation reject до mutations |
| Target trust scope | Все реальные provider/placement hosts покрыты; чужие hosts не требуются |
| Fresh Vault bootstrap | Нет admin token в operator lease; файл текущего run доступен hook после барьера |
| Bootstrap output missing / чужой provider/run | Application mutation не начинается |
| Repeat с уже инициализированным Vault | Явный RUNTIME_INPUT; нет автоматического чтения старого run |
| Existing Vault | Explicit runtime token проходит тот же hook path |
| Mixed real run + repeat | Infra Verify → application Apply/Verify; SUCCESS, repeat changed=0 |

Реальный mixed QA: один ограниченный проект с существующим rootless Docker,
Vault и минимум одним account provider, плюс библиотека с digest-pinned
`docker/application-connection-probe`. Использовать готовый проверенный образ;
если недоступен — зафиксировать prerequisite, не скачивать автоматически.
Endpoint и подключения использовать как содержательную проверку готового A1–A6
пути, не повторять полную security матрицу A4/A5. Отдельно проверить свежий Vault
bootstrap в изолированном разрешённом fixture: не переустанавливать общий Vault.
Точный mutable QA scope записать до запуска. Failure/cancel тесты максимально
проводить bounded fixtures; реальные проверки не должны ломать общий full-services.

Запуск через production Core protocol: Build → protected lease/trust preparation
→ Start → events/Get → terminal. Не редактировать approved manifest для приёмки.
Записать revision, fingerprints, run IDs, sequence действий, changed, cleanup и
safe events в evidence/a8-test-journal.md. Не выдавать standalone PASS за UI PASS.
После QA удалить временные source workspaces/identities; общие deployments,
approved images и authoritative audit не удалять без отдельного scope.

## 9. Порядок реализации и документы

1. A8.1: phases/dependencies/fingerprints и target-free tests.
2. A8.2: complete manifest schema и protocol negotiation.
3. A8.3: exact targets, trust и существующий secret custody для mixed run.
4. A8.4: controller guards, events и cancel/failure tests.
5. Focused RED OS regression, реальные bounded mixed/infra-only проверки.
6. Один FULL DIFF review; owner-approved corrections/recheck при необходимости.
7. Обновить execution contract, общий план, contract index, QA journal и
   CURRENT_STATE по фактическим результатам. A9 не начинать автоматически.

Критерий завершения: production mixed Core plan EXECUTABLE, один manifest/run,
доказанный all-infrastructure Verify barrier, реальные successful/repeat и
cancel/failure evidence, сохранённый infrastructure-only путь, zero открытых
блокеров по review. Коммит и master synchronization — по отдельному запросу.
