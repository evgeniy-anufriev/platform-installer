# UI-01A — contract preflight для редактора проекта

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01a-checkpoint-001).

Accepted artifacts: [contract freeze](ui-01a-contract-freeze.md),
[toolchain](ui-01a-toolchain.md), [mockup reconciliation](evidence/ui-01a-mockup-reconciliation.md),
[reviews](reviews/ui-01a-review.md) and [QA](evidence/ui-01a-qa.md).

## 1. Цель

Устранить контрактную неопределённость до первого production UI-кода. Результат
должен позволить выполнить UI-01B–UI-01J без скрытого изменения архитектуры,
обхода Core или появления второго desired-state store.

UI-01A отвечает на семь вопросов:

1. Какие данные и команды уже реально предоставляет backend каждому экрану?
2. Как создать и повторно открыть намеренно пустой проект без `inventory`,
   `host_vars` и `group_vars`?
3. Как первый полный draft превращается в Core-valid staged Ansible project и
   атомарно публикуется только после review?
4. Какими файлами inventory может владеть Installer, не получая права менять
   произвольный human-owned `inventory/hosts.yml`?
5. Какие typed команды отсутствуют для Серверов, Топологии, Сертификатов и
   Сервисов?
6. Как editor использует READY Execution Node для Core query/validation, не
   реализуя UI-02 preparation/execution?
7. Какой минимальный Wails/React toolchain поддерживается и воспроизводимо
   собирается в текущем репозитории?

## 2. Обязательные входы и границы исследования

Перед началом прочитать и зафиксировать revisions/digests:

- `AGENTS.md`, `CURRENT_STATE.md`, `docs/work/ui-01/ui-01.md`;
- `docs/design/ui-design-01-mockups.html`, `docs/design/ui-design-01.md`,
  `docs/design/ui-project-creation-design.md`;
- `docs/project-contract.md`, `docs/backend-and-ui.md`;
- `docs/work/ui-backend/ui-be-01.md`–`docs/work/ui-backend/ui-be-04.md`, `docs/work/pki/pki-01.md`;
- project/snapshot/edit-plan schemas и фактические Go interfaces/types.

Пройти в макете три сценария:

1. Create → Servers → Topology → Certificates → Services → Review.
2. Topology → выбранный deployment → Service editor → возврат в Topology.
3. Existing project → read-only/unsupported state → безопасное отсутствие save.

В стартовом отчёте перечислить расхождения макета и реализованных контрактов.
Демонстрационные PASS, планы и результаты не считать backend-возможностями.

Не входят: создание frontend subtree, Wails scaffold, project mutation,
изменение Core/Ansible, подготовка Execution Node, target SSH, apply/verify,
runtime PKI materialization и перенос UI-02 в UI-01A.

## 3. Исходные подтверждённые факты

- `coreadapter.Adapter` сейчас имеет только `BuildSnapshot`.
- `installer.Backend` реализует `PlanEdit`, `CommitEditPlan` и discard поверх
  существующего Core-loadable проекта; Create/Open/session API отсутствуют.
- Writer владеет только
  `inventory/group_vars/all/platform-installer.yml` и
  `inventory/host_vars/<host>/platform-installer.yml` с managed header.
- `inventory/hosts.yml` считается canonical revision input, но не writable
  Installer-owned документом.
- Current `EditCommand` покрывает deployment/configuration/endpoint/HAProxy/
  placement operations, но не server inventory и не PKI authority/profile CRUD.
- `ProjectSnapshot` уже содержит hosts, catalog, deployments, effective config,
  topology, endpoints, integrations, PKI, findings и document ownership.
- Snapshot считает отсутствующий inventory fatal open error. Existing empty Core
  fixture создаёт `inventory/hosts.yml` с localhost, поэтому не доказывает
  требуемый metadata-only create flow.
- `project.yml` schema требует не только `metadata.id`, но также
  `desiredStateContract`, `catalogLock` и `artifactLock`; `desiredState` optional.
- Wails/React/frontend subtree и зависимости в репозитории отсутствуют.

Эти факты нужно подтвердить повторно текущим working tree при старте UI-01A.

## 4. Work packages

### UI-01A.1 — screen-to-contract inventory

Создать таблицу для каждого экрана/действия:

| Поле | Содержание |
| --- | --- |
| Screen/action | Например, Projects/Create, Servers/Add, PKI profile/Edit |
| Query source | Реальный Go method и versioned contract либо `MISSING` |
| Command source | Реальный semantic command либо `MISSING` |
| Authority | Go application / Core / project file / runtime secret broker |
| Files | Читаемые и потенциально изменяемые logical paths |
| Execution Node | none / query required / validation required |
| Target contact | Должно быть `NO` для всего UI-01 editor path |
| Failure states | Typed findings/timeouts/conflicts/read-only reason |
| Owning milestone | B–I |

Проверить не только объявленные в документах интерфейсы, но их реализацию и
тесты. Любой design-only DTO пометить `PROPOSED`, не `AVAILABLE`.

Отдельно составить reuse map: `ProjectSnapshot`, `EditCommand`, `EditPlan`,
`EditCommitResult`, Execution Node binding и secret-reference primitives.
Новый DTO допускается только для новой прикладной операции, которую нельзя
выразить существующим контрактом без потери семантики.

### UI-01A.2 — empty-project lifecycle decision

Зафиксировать versioned `CreateProjectRequest/Result` либо доказать возможность
переиспользовать существующий контракт. Решение должно определить:

- нормализацию display name и генерацию стабильного `metadata.id`;
- источник initial `catalogLock` и `artifactLock`, их совместимость и поведение,
  когда approved bundle/catalog отсутствует;
- точный byte-level initial file set: требование владельца — нет `inventory`,
  `host_vars`, `group_vars`; никакого implicit service или localhost target;
- явный признак Installer-created metadata-only state внутри portable contract,
  если он нужен, без SQLite/config JSON authority;
- различие `EMPTY_MANAGED_PROJECT` и повреждённого/неполного imported project;
- atomic create, destination collision, path containment, symlink/reparse-point,
  permissions, cancellation, crash cleanup и recent-project publication;
- reopen после process restart и обновления Installer/Core.

Рекомендуемая развилка для решения: либо schema-compatible `project.yml` с
обязательными locks является единственным первоначальным файлом, либо контракт
пустого проекта расширяется явно. Нельзя считать папку «новой» только потому,
что inventory отсутствует, и нельзя создавать скрытый desired-state marker.

Deliverable: decision record с JSON/YAML examples, typed findings и state
transition diagram `ABSENT → CREATING → EMPTY_MANAGED → CONFIGURED`.

### UI-01A.3 — first-write and inventory ownership decision

Определить транзакцию первого save:

```text
metadata-only canonical project
        + backend-owned transient draft
        ↓
temporary complete candidate project
        ↓
Core BuildSnapshot/Validate on Execution Node, no target contact
        ↓ READY only
review plan with semantic and document changes
        ↓ approved commit
atomic publication of inventory + managed variable documents
```

Нужно выбрать один inventory contract, включая logical path, managed marker,
serialization, migration и read-only coexistence. Рассмотреть минимум:

- Installer-owned deterministic `inventory/hosts.yml` только для проектов,
  созданных Installer;
- отдельный Installer-owned inventory source, подключённый `ansible.cfg`, если
  Core и обычный `ansible-playbook` сохраняют однозначную authority;
- запрет server editing для opened human projects до отдельного adoption flow.

Выбор должен сохранять standalone Ansible, inventory precedence, unknown files,
human-owned inputs и current revision calculation. Не допускаются YAML mutation
без ownership, merge Ansible vars в Go или временный validation bypass.

Определить bounded draft/session contract: session ID, project/root identity,
base revision, ordered semantic commands, expiration, navigation, review,
discard и process-exit behavior. Draft может быть только transient application
state; после restart он не является сохранённой конфигурацией.

Deliverable: transaction/ownership decision, required extensions to
`EditCommand`/writer/Core adapter, failure table и mapping в UI-01C–UI-01F.

### UI-01A.4 — topology, PKI and service command gap

Для порядка Topology → Certificates → Services проверить:

- catalog-driven type/mode/member/role/placement metadata;
- endpoint group, dependency and integration edits;
- certificate authority, certificate profile и TLS profile CRUD;
- scope (`HOST`/`MEMBER`/`DEPLOYMENT`), references и safe policy fields;
- service setting schema, origin, override/reset и `tlsProfile` reference;
- Core-derived consumers, SAN and reissue findings.

Результат должен отделять желаемый PKI intent от runtime materialization.
`CERTIFICATE_REISSUE_REQUIRED` остаётся blocking runtime finding; UI-01A не
определяет кнопку обхода. Secret values и private material не входят ни в один
editor DTO.

Для каждого missing operation указать минимальное изменение существующего
`EditCommand/v1alpha1` либо обоснованную новую версию. Не создавать service-type
branches в Go/React и не принимать `ProjectSnapshot` обратно как mutation.

Deliverable: command gap matrix и точный scope UI-01F/G/H.

### UI-01A.5 — editor Core/Execution Node boundary

Зафиксировать, как workstation backend получает authoritative snapshot и staged
proof через уже READY Execution Node:

- stable node binding and capability/version check;
- transfer только required project/candidate inputs;
- timeout/cancellation/error/redaction semantics;
- immutable bundle/catalog used for lock resolution;
- no target inventory contact during snapshot/validation;
- behavior без node: metadata create/open допускается там, где это безопасно;
  validate/review/commit, требующий Core proof, явно блокируется;
- stale node/catalog/bundle и reconnect не дают false READY.

Переиспользовать UI-BE-04/EXEC-01 transport primitives, но не использовать
execution lifecycle как generic remote shell. Если текущий `CommandAdapter`
локальный, указать минимальный adapter composition milestone и tests.

Deliverable: sequence diagram и typed failure mapping в UI-01B/D.

### UI-01A.6 — Wails/React toolchain decision

Проверить актуальные официальные requirements и совместимость с текущим Go,
Windows/WebView2 и offline build policy. Зафиксировать:

- Wails major/minor policy, React и TypeScript versions/ranges;
- package manager и lockfile; Node LTS policy;
- Vite/build/test/lint/typecheck tooling;
- generated Wails bindings как единственный frontend transport;
- dependency licensing/SBOM и offline-cache strategy;
- directory boundaries, generated files, Git rules and CI commands;
- native development/build prerequisites и понятную диагностику их отсутствия.

Не добавлять зависимости и scaffold в UI-01A. Versions подтверждать по
официальной документации в момент выполнения, а не копировать из V1.

Deliverable: toolchain ADR и воспроизводимые planned commands для UI-01B.

### UI-01A.7 — reconciliation, reviews and handoff

Свести решения в один dependency-ordered implementation map UI-01B–UI-01J.
Обновить `docs/work/ui-01/ui-01.md`, mockup/design только если решения меняют UX, roadmap,
CURRENT_STATE и relevant architecture decision records.

Провести `core-contract-reviewer` и `safety-reviewer`. Blocking finding должен
быть либо устранён в документах, либо оставить UI-01A неготовым; перенос
неразрешённого архитектурного вопроса в реализацию недопустим.

## 5. Обязательные deliverables

UI-01A должен оставить reviewable пакет:

1. `docs/ui-01a-contract-matrix.md` — screen/query/command/authority/gap matrix.
2. Decision record empty-project lifecycle и initial lock provenance.
3. Decision record first-write, inventory ownership и transient edit session.
4. Command gap matrix для Servers/Topology/Certificates/Services.
5. Editor-to-Execution-Node sequence/failure model.
6. Wails/React toolchain ADR.
7. Focused QA matrix и negative cases для каждого последующего milestone.
8. Обновлённые UI-01 plan, roadmap, CURRENT_STATE и mockup reconciliation log.
9. Два review reports, каждый с 0 blocking findings.

Имена отдельных ADR-файлов можно уточнить при выполнении, но содержимое и
трассировка решений обязательны. Один огромный speculative schema не является
допустимой заменой этим deliverables.

## 6. QA plan

### Test scope

UI-01A проверяет непротиворечивость документации, contracts и planned API.
Production behavior не добавляется, поэтому full Core/service regression и
target lifecycle tests не требуются.

### Required positive scenarios

- каждый элемент согласованных экранов имеет query/command/owner или явно
  отложен с disabled/read-only UX;
- metadata-only create/reopen и first-write имеют полные state transitions;
- linked batch server + deployment + placement + PKI + setting достигает Core
  proof только как complete staged candidate;
- non-TLS service path не требует PKI profile;
- открытый human-owned project остаётся read-only там, где ownership нет;
- service editor entry из Topology использует ту же deployment identity.

### Negative and boundary scenarios

- existing/empty/non-empty destination, inaccessible path, symlink/reparse point;
- absent/incompatible catalog or artifact lock source;
- missing inventory в imported project не принят за new managed project;
- missing/unavailable/stale Execution Node, timeout and cancellation;
- blocked/partial Core snapshot, stale project revision, plan expiry/conflict;
- unknown/reserved service setting and unsupported catalog version;
- dangling host/deployment/endpoint/PKI references;
- secret-like values and private PKI material rejected/redacted;
- external edits and process restart with transient draft;
- UI navigation does not silently persist, apply or discard draft.

### Contract/schema scenarios

- all examples validate against existing or explicitly proposed versioned schemas;
- no unversioned map crosses Wails for project mutations;
- project metadata/locks, snapshot, edit-plan/result and findings retain their
  current authority and redaction rules;
- catalog/schema reproducibility commands remain identified for later gates;
- proposed changes preserve ordinary standalone `ansible-playbook` consumption.

### Regression risks

- making `project.yml` mandatory for standalone Ansible projects;
- classifying arbitrary inventory as Installer-owned;
- validating a synthetic model different from committed files;
- storing draft/project configuration in SQLite or frontend persistence;
- duplicating catalog/PKI defaults in Go/React;
- using execution protocol as unrestricted SSH/RPC;
- treating missing Execution Node as successful validation;
- merging UI-02 apply/result semantics into editor save.

### Environment requirements

- Windows: Git, Go, Node/toolchain discovery, WebView2/Wails requirement audit;
- RED OS Execution Node: read-only current-tree Core contract probes only if a
  documented question cannot be resolved statically;
- no service target contact and no shared Kafka deployment mutation;
- external web lookup only for current official Wails/React/Node requirements.

### Not testable locally in UI-01A

Native Wails build, generated binding behavior, real first-write transaction,
Core-mediated commit and GUI E2E remain acceptance of later milestones. UI-01A
must specify their commands and fixtures but must not report them PASS.

## 7. Exit criteria

UI-01A is DONE only when:

- all seven work packages and nine deliverables complete;
- every gap has owning milestone and acceptance test;
- empty project, lock provenance, inventory ownership, first-write and PKI edits
  have one accepted solution each, without unresolved alternatives in code path;
- Wails/frontend stack is selected from current official evidence;
- mockup reconciliation completed before and after the work;
- no production code/dependencies/scaffold were introduced;
- secret audit and `git diff --check` pass;
- both reviews report 0 blocking findings;
- docs/roadmap/CURRENT_STATE agree and one focused documentation commit is made;
- worktree is clean except unrelated pre-existing user changes.

После UI-01A не начинать UI-01B автоматически.
