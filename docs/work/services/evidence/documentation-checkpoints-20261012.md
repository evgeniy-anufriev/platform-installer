# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## si11-v02-trusted-binding-plan.md

Source document: [si11-v02-trusted-binding-plan.md](../si11-v02-trusted-binding-plan.md).

<a id="si11-v02-trusted-binding-plan-checkpoint-001"></a>

## Реальная приёмка V02 (01.10.2026)

После S11-00 первый WebView Verify был заблокирован отдельным Go staging-дефектом:
фиксированный родитель `/var/tmp/platform-installer/execution-plan` отсутствовал.
По разрешению владельца `stageProjectArchive` теперь готовит только этот
фиксированный каталог с проверкой типа/владельца и режимом `0700`, сохраняя
исключительное `mkdir` для run-каталога. Регрессионный тест, полный `go test
./...`, `go vet ./...`, Wails build и `git diff --check` прошли. Нового
архитектурного review не было: бюджет D01/D02 исчерпан, исправление не меняет
утверждённую границу.

Реальный `.exe` без аргументов (SHA-256
`5C0AFEEF51A39A8F57C7BB07E89B1BD43F8FA6C9F55F7868D35D0F094A9345E5`)
через Windows UI Automation открыл сохранённый проект, принял сеансовый PEM,
показал ранее независимо сверенный SSH-отпечаток node1, получил явное
подтверждение, показал READY и завершил Project Verify состоянием «Проверено».
Файлы проекта не изменились; staging-каталог на Execution Node после операции
пуст. Сервисы и план установки не запускались. V02 — ПРОЙДЕН; весь SI11 этим
не завершён.



## si11-s06-inherited-settings-plan.md

Source document: [si11-s06-inherited-settings-plan.md](../si11-s06-inherited-settings-plan.md).

<a id="si11-s06-inherited-settings-plan-checkpoint-001"></a>

Status: owner-approved behavior; architecture and implementation in progress.


## si11-ansible-role-defaults-plan.md

Source document: [si11-ansible-role-defaults-plan.md](../si11-ansible-role-defaults-plan.md).

<a id="si11-ansible-role-defaults-plan-checkpoint-001"></a>

Status: owner-directed correction before the next SI11 full-plan run.


## service-install-01-go-edit-architecture.md

Source document: [service-install-01-go-edit-architecture.md](../service-install-01-go-edit-architecture.md).

<a id="service-install-01-go-edit-architecture-checkpoint-001"></a>

## SERVICE-INSTALL-01 acceptance update

The Keepalived acceptance fixture will be constructed as follows:

1. the Wails placement dialog is exercised against the public EditSession
   backend: it rejects an incomplete priority, accepts explicit values, and
   saves/reopens the same direct-owned placement through Review/Save;
2. the public Wails `CreateProject` flow creates the controlled, Git-ignored
   cumulative QA root from the fixed immutable bundle source; Go reopens and
   accepts only its `EMPTY_MANAGED_PROJECT` state;
3. one v1alpha9 Go `EditSession` with three `CreateServer` intents, one
   `CreateServiceDeployment`, one `CreateEndpointGroup`, one
   `ReconcileHostScopedDeploymentPlacement` with priorities 150/120/100, and
   one `ReconcileEndpointProvider` for VRID 61 / VIP `192.168.56.121`;
4. `ReviewStructural` and the existing guarded local Commit;
5. reopen and assert the owned servers, placement priorities and provider
   tuple without Core or target contact;
6. run the existing Go `CreatePlan → ApprovePlan → Start → observe → Sync`
   lifecycle twice against the three RED OS targets, retaining the resulting
   canonical project as the sole input to SERVICE-INSTALL-02.

The first milestone fails closed when the cumulative root already exists;
replacement is a separate, reviewed cleanup operation and is never an
implicit local reset. Each later milestone must open the same root, verify its
saved revision before appending its own commands, and prove its additions do
not rewrite previous service state. The final milestone builds one fresh plan
from that same accumulated revision. The test retains the existing
deployment-scoped cleanup/isolation rule. It must not reset hosts or touch
active Kafka units. Core remains responsible for the final target-free project
validation, deployment plan, apply and verify.




## service-02a.md

Source document: [service-02a.md](../service-02a.md).

<a id="service-02a-checkpoint-001"></a>

Status: DONE.
