# A2 — независимый FULL PLAN review

Дата: 2026-10-10. Reviewer: независимый `architecture-reviewer`,
`/root/a2_full_plan_review`. Первоначальный FULL PLAN: **BLOCK**.
После принятой владельцем коррекции единственный TARGETED_RECHECK: **APPROVE**,
неразрешённых блокеров **0**. Исторический FULL отчёт сохранён ниже;
актуальная проверенная identity и результат — в конце документа.
Статус/разрешение — в [CURRENT_STATE](../../CURRENT_STATE.md).

## Идентичность и scope

- План: [a2-technical-plan.md](a2-technical-plan.md).
- SHA256: `150A02B4B985FCC02722DB7BCD6C766B21692D079B405EE0EB07B5DAA50FAFDC`,
  независимо проверен reviewer до и после чтения.
- Базовый HEAD: `ac4340be8693c3068dc631be91975a22947aab32`.
- Scope: standalone A2/A2.1 — materialization, image delivery, rootless Compose
  Apply/Verify, повторы и ошибки. A3–A8, Go/UI, provider/Vault hooks и включение
  общего execution planner исключены.
- Учтены решения владельца: общий library-host `.env`, наследование base Compose,
  identity из приложения/библиотеки/host ID, несколько Docker-хостов,
  repository-then-offline policy, минимальное использование новых механизмов.
- Канонические основания: root/Core AGENTS, CURRENT_STATE,
  [review procedure](../agent-procedures/review.md), project/Core contracts,
  A1 schemas/code на указанной базе. Несвязанные Redis/Sentinel и SI11 изменения
  не проверялись и сохранены.

## Findings

### A2-P01 — BLOCKING / OPEN: потеря restart после прерывания обновления config

Место: `a2-technical-plan.md:287–291`, §5 фаза 4 и §8 acceptance.

План выбирает restart при изменении bind-mounted config, поскольку содержимое
файла может измениться без изменения Compose hash. Retry должен восстанавливаться
из фактического состояния, но сохраняющийся признак активации не задан.

Контрпример:

1. Ansible записывает новую конфигурацию.
2. Процесс прерывается до restart.
3. Повтор видит правильные bytes и получает `changed=false`.
4. Compose config прежняя, `up` не пересоздаёт container.
5. Приложение продолжает использовать старую конфигурацию, загруженную в память;
   bytes/running/health проверки могут дать ложный PASS.

Воздействие: interrupted recovery и effective configuration Verify не обеспечены;
чистый повтор может маскировать незавершённое обновление.

Наименьшая рекомендуемая коррекция: включить детерминированный digest declared
config files в managed Compose label, использовать обычный recreate при изменении
label. После прерывания desired digest отличается от label работающего контейнера,
и повтор завершает обновление без отдельного activation journal. Tradeoff:
config update заменяет контейнер вместо restart с сохранением ID.

Если restart необходимо сохранить, нужен runtime-only pending/activated
fingerprint с точным порядком записи и readiness-проверки. Это сложнее Compose
reconciliation; выбор должен утвердить владелец.

Проверка: реальное приложение читает config при старте; прерывание после file write
до activation; retry применяет новое значение, соседний instance сохраняет ID;
следующий повтор `changed=0`. Verify до восстановления обнаруживает незавершённую
активацию.

### A2-P02 — NON_BLOCKING / OPEN: standalone assembly image authority

Место: `a2-technical-plan.md:43`, `:52–55`, §3.3 и A2.1.

Текущая `_artifact_source_authorities()` находится в
`module_utils/deployment_plan.py:141`; planner блокирует application libraries
в `:599`. `artifact_source_resolution` ожидает deployment-indexed authority
и выполняет RPM discovery. План предусматривает container branch и сохранение
planner guard, но standalone caller для получения authority не назван.

Риск: дублирование source rules или обход planner guard при реализации.

Минимальное уточнение: standalone preflight вызывает переиспользуемую Core
authority assembly для typed image requirements без `BuildDeploymentPlan`;
existing RPM caller использует тот же механизм. В A2.1 до Apply закрепить version
dispatch, lock location и пример image record. Полная реализация JSON shape в плане
необязательна, но owner/caller должны быть определены.

Проверка: одинаковые locked image/source inputs дают одинаковую authority,
library planner остаётся заблокирован, RPM regression проходит.

### A2-P03 — NON_BLOCKING / OPEN: archive staging и rootless account

Место: `a2-technical-plan.md:234–238`,
`artifact_delivery/tasks/deliver_requirement.yml:27–39`.

Existing delivery создаёт directory `root:root/0700`, archive `root:root/0600`;
выбранный Docker account не прочитает archive для `docker load`.

Минимальное уточнение: сохранить защищённый общий staging и выполнить bounded
copy exact archive в private staging Docker account с повторной проверкой
digest/size и cleanup. Альтернатива — typed owner parameter для image consumer
без изменения RPM defaults. Общий staging не делать общедоступным.

Проверка: offline load под выбранным непривилегированным account, archive не
общедоступен, RPM delivery сохраняет owner/mode.

## Overengineering

Подтверждённых избыточных механизмов: **0**.

- Runtime role и два playbook оправданы standalone Apply/Verify. Дублирование
  tasks в каждом package создаёт повторение security/runtime policy.
- Typed image extension необходим: RPM metadata не выражает registry manifest,
  platform image ID и archive digest; перегрузка RPM name/version нарушает контракт.
- Второго desired store, image catalog/images.lock, scheduler, generic hook DSL
  или преждевременного Go/UI слоя нет.
- Runtime ownership marker и bounded host-local lock защищают объекты и
  конкурирующие Apply; это derived guards, не lifecycle store.
- Built-in template/copy/command и существующий Compose используются обоснованно;
  новая dependency не предлагается.
- Для A2-P01 digest label/Compose reconciliation проще отдельного activation
  journal. Выбор нужно закрепить явно.
- Дублирующие DTO/контракты и преждевременный scope не обнаружены;
  version dispatch должен быть проверен в будущем DIFF.

## Evidence и ограничения

Reviewer непосредственно прочитал план, общий A2 scope, инструкции и canonical
ownership/security contracts, A1 package/settings schemas/application projection,
artifact-source schema/filter/roles, authority assembly/planner guard,
rootless Docker Verify и offline delivery.

Факты merge A1 и excluded dirty scope получены от main agent; HEAD/SHA проверены
независимо. A1 QA — reported baseline, не доказательство A2.
Тесты не запускались, targets не контактировались, файлы не изменялись,
secret material не читался. PLAN review не доказывает remote acceptance.

**Review validity: CURRENT** для указанного SHA и scope. Коррекция A2-P01 требует
проверки changed boundary. Материальное изменение source authority/trust/scope/
ownership требует определения нового review scope. Несвязанные Redis/Sentinel
изменения этот PLAN verdict не инвалидируют.

## Следующее действие

Передать владельцу A2-P01 и выбор коррекции. При BLOCK main останавливает
автоматическую корректировку/реализацию. После решения владельца допустимы
исправление approved blocker и один TARGETED_RECHECK; nonblocking уточнения
не требуют ещё одного FULL review. Бюджет A2 PLAN: initial FULL использован,
TARGETED_RECHECK ещё не разрешён и не выполнен.

## TARGETED_RECHECK A2-P01 — 2026-10-10

**Вердикт: APPROVE. Неразрешённых блокеров: 0.** Независимый reviewer тот же,
FULL gate не переоткрывался. Initial FULL + единственный owner-authorized recheck
использованы; автоматический PLAN review budget исчерпан.

### Идентичность и разрешение

- План SHA256: `446369030D19A871EDA68B12DA8FEAB296D026C13C121ADD43B0150E5DCCC302`,
  проверен reviewer до и после чтения.
- База HEAD: `ac4340be8693c3068dc631be91975a22947aab32`.
- Scope: A2-P01 и непосредственно затронутые config activation, retry, Verify,
  QA evidence boundaries; не повторный FULL.
- Владелец принял automatic digest + Compose recreate, уточнил отсутствие
  пользовательского digest setting и использование ранее собранного QA image.

### Disposition

**A2-P01: OPEN → RESOLVED.** План задаёт автоматически вычисленный digest
детерминированно сериализованных sorted destination/content_sha256 pairs.
User override digest/label запрещён. Compose label сохраняет expected fingerprint;
reconciliation выполняется независимо от changed у template/copy.
После прерывания старый container label отличается, поэтому retry пересоздаёт
exact instance. Verify сравнивает expected/disk/container label; running/healthy
не скрывает mismatch. Tradeoff изменения container ID принят явно.
QA включает interrupted write до up, mismatch до recovery, изоляцию соседнего
instance и следующий clean repeat. Причина блокера устранена на уровне плана;
реальное исполнение остаётся будущими DIFF/QA gates.

**A2-P02: OPEN → RESOLVED, NON_BLOCKING.** Общая Core authority assembly обслуживает
RPM planner и standalone caller без BuildDeploymentPlan; application planner
guard сохранён. Exact version/record закрепляется в A2.1 до Apply.

**A2-P03: OPEN → RESOLVED, NON_BLOCKING.** Existing root staging сохраняет права;
exact archive копируется в private selected-account staging, digest/size повторно
проверяются, load выполняется Docker account, cleanup через always.
Отдельные review gates для этих уточнений не проводились.

### Затронутая QA boundary

Existing probe прямо запускается без штатного Vault Agent entrypoint в A2.
HTTP 503 без credentials доказывает достижимость, а не успешные подключения;
readiness container не объявляется healthcheck coverage. Labels/IDs/checksums
доказывают доставку config и запуск нового процесса. Прикладное чтение значения
в память требует startup-reader fixture; отсутствие отмечено как prerequisite
без ложного PASS или автоматической пересборки. Core не может универсально
доказать внутреннюю интерпретацию приложением каждого параметра. Новый блокер
этой коррекцией не внесён; заявленная application-consumption acceptance остаётся
обязательной открытой проверкой.

### Overengineering, evidence и validity

В коррекции избыточных механизмов **0**: built-in hashing/render + Compose labels
заменяют activation journal, без scheduler/persistence/user digest DTO.
Цена recreate явно принята. Остальные категории FULL не переоткрывались.

Непосредственно прочитаны changed sections плана и bounded probe source/docs,
проверены SHA/HEAD. Image ID — recorded evidence; наличие image на daemon
не проверялось. Tests/targets не запускались, secret material не читался.
APPROVE относится к плану, не реализации или QA.

**Review validity: CURRENT** для нового SHA. Материальное изменение digest
ownership, activation, retry/Verify или acceptance evidence инвалидирует
соответствующую часть ревью. Реализация требует разрешения владельца;
FULL DIFF review и real A2 acceptance остаются обязательными.
