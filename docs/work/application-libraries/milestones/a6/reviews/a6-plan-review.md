# A6 — независимое FULL PLAN review

Дата: 2026-10-11. Ревью выполнил независимый read-only агент
`/root/a6_plan_review` с ролью `architecture-reviewer`. Ниже сохранён его отчёт.
После BLOCK исправления и повторная проверка владельцем пока не разрешены.

## 1. Verdict

**BLOCK — APPLICATION-LIBRARIES-A6, PLAN, FULL.**

Вердикт сформирован независимо. В плане обнаружены два незакрытых риска на
затронутой границе source-owned HAProxy publication: небезопасная фильтрация
соседних fragments по префиксу ID и неоднозначность существующего Host routing
при пересекающихся domains endpoint groups.

## 2. Review identity

Проверено чтением:

- Worktree: `C:\Users\AnufrievEV\.codex\worktrees\application-libraries\platform-installer-v2`.
- HEAD: `540aa05c49ae531b3041da16cbad4771f5ccdd6e`.
- План: `docs/application-libraries/a6-technical-plan.md`.
- SHA-256: `96a863047afe00ef480922f9ce5861e8cc0332d1c62fe81821b423a2266162c8` — совпал при первоначальной и заключительной проверках.
- Scope: standalone A6 settings, application source projection, HAProxy/DNS integration, readiness/publication, Verify, repeat и reconcile. Go/UI, A7/A8, target mutation и посторонние изменения A2 документации исключены.

Ревизии основных контрактов в HEAD:

| Документ | Git blob |
| --- | --- |
| `docs/ansible-core.md` | `d752340b66bb8706f208b19eb143fe5bd3cbb58e` |
| `docs/project-contract.md` | `e81becd6f880a14e774fafbb3272c3c7ff69f29f` |
| `settings.schema.json` | `ac5733266eb1a79e51a0eca3da7bb3ab8b36b32a` |
| `desired-state.schema.json` | `56806e21b75bc49f415439acccfa379368aba232` |
| `docs/endpoint-haproxy-placement-plan.md` | `8cd7bb87744502e12548b57bda8a4d1928f89b14` |
| `docs/application-libraries/execution.md` | `ea67413b972b0e7c20004fb34ba5e65121a93e0f` |

Рабочие `CURRENT_STATE.md` и `implementation-plan.md` содержат незакоммиченные
изменения; их прочитанные редакции зафиксированы SHA-256 соответственно
`4058dca051bdb16b8a7db404564343fdd7d02ddbed9b33b8733b0369884fa4cd` и
`c1b5a3f922408f6f9fecbca1a5df62f8e5438b63064f2046cb28846d0cb993f0`.

Owner decisions использованы из review envelope и текущих документов: standalone
scope, минимальное число действий, один hook на instance, сохранение существующего
provider selection и пользовательского Compose bind address. Отдельная подписанная
ревизия owner envelope не предоставлена.

## 3. Findings

### A6-P01 — BLOCKING — OPEN

**Место:** план §4, §6–7, строки 194–204, 255–258, 300–307;
`services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks/prepare.yml:98`
и `:153`; `.../tasks/activate.yml:25`;
`.../plugins/modules/archive_managed_backends.py:243`.

**Evidence:** существующий partial pipeline исключает прежние fragments через:

```text
startswith('30-backend-' + sourceId + '-')
```

и аналогичный regex. Архиватор затем считает stale все backend files,
отсутствующие в сформированном `candidate_files`.

Например, source `apigateway-sdku` захватывает этим условием fragment соседнего
source `apigateway-sdku-test`. Их IDs, FQDN, backend names и filenames различны,
поэтому заявленная проверка точных collisions такой случай не блокирует.

**Impact:** A6 обещает сохранить соседние источники, но повторное использование
этой фильтрации может исключить соседний fragment из candidate и архивировать
его при публикации выбранного application source. Это предсуществующий механизм,
непосредственно используемый новой application boundary; находка не требует
общего пересмотра HAProxy.

**Smallest correction:** добавить в план обязательное устранение prefix ownership
matching на затронутом partial path. Выбирать точные source-owned filenames по
проверенной source/group mapping, сохраняя legacy filenames и ownership header.
Если точная mapping в текущем механизме недоступна, меньший временный вариант —
target-free BLOCK для неоднозначных source-prefix сочетаний с явно документированным
ограничением.

**Verification required:** production-task negative/partial сценарий с
`apigateway-sdku` и `apigateway-sdku-test`, включая service/application сочетание:
Apply/repeat/retry первого сохраняет файл, содержимое и route второго; архив не
содержит соседний fragment.

### A6-P02 — BLOCKING — OPEN

**Место:** план §4, строки 196–204;
`services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/templates/10-public.cfg.j2:7–9`.

**Evidence:** текущий frontend создаёт suffix ACL для каждой endpoint group и
выбирает backend `<first DNS label>-<group>` в порядке `dictsort`.

При двух groups с одинаковым domain запрос приложения второй группы удовлетворяет
обеим ACL и выбирает первую. При parent/child domains возникает тот же риск,
если широкая group идёт первой. Например, разные instances в groups `a` и `b`
с domain `apps.example.test` имеют разные FQDN и filenames, но запрос второго
instance выбирает `<instance>-a` вместо существующего `<instance>-b`.

План проверяет FQDN/backend/file collisions, в том числе одинаковый domain,
однако не задаёт проверку этой routing ambiguity.

**Impact:** статически допустимая application projection может публиковать fragment,
к которому существующий Host routing не ведёт. Endpoint обнаружит ошибку только
после provider mutation; возможен выбор другого существующего backend.

**Smallest correction:** сохраняя текущий frontend-контракт, добавить target-free
проверку: FQDN каждого enabled application source должен по существующему порядку
ACL однозначно выбирать его endpoint group. Несовместимое сочетание блокировать
до mutation. Менять frontend routing и service semantics для устранения ограничения
без отдельного owner решения не требуется.

**Verification required:** resolver negatives для equal-domain groups и
parent/child suffix overlap; distinct FQDN без точной collision должен блокироваться,
если фактическое первое правило выбирает другую group. Обычная непересекающаяся
конфигурация сохраняет текущий render.

### A6-P03 — NON_BLOCKING — OPEN

**Место:** план §5, строка 227; `docs/endpoint-haproxy-placement-plan.md`, требования;
`service_integration_resolution.py:11`.

**Evidence:** выражение «неоднозначный provider — validation BLOCK» не различает
неоднозначный DNS/address provider и допустимый набор нескольких HAProxy
deployments/provider-host pairs. Существующее owner-approved правило требует
применять ко всем найденным HAProxy парам.

**Impact:** формулировка допускает ошибочную реализацию нового ограничения
единственности HAProxy.

**Smallest correction:** уточнить, что несколько HAProxy providers, возвращённых
существующей выборкой, допустимы; BLOCK относится к конкретной неоднозначности
контракта, например address provider.

**Verification required:** сохранить positive resolver coverage для нескольких
HAProxy deployments и partial host overlap. Повторное архитектурное ревью этой
редакционной рекомендации не требуется.

## 4. Overengineering

**Выявленных избыточных механизмов: 0.**

| Категория | Оценка и более простой механизм |
| --- | --- |
| Новые abstractions/API | Derived typed source необходим для application identity без synthetic `serviceDeployments`. Optional input существующих resolver проще отдельного endpoint framework; план выбирает его. |
| Duplicate contracts/DTO | Shared BackendSettings и отказ от второго nested формата устраняют дублирование. Нужна одна schema definition/generator, как прямо предусмотрено §3.1. |
| Persistence/lifecycle layers | Новых registry, ledger, daemon или desired-state store нет. Используются runtime projection и существующие provider phases. N/A для удаления нового persistence. |
| Premature scope | Go/UI, общий DAG, bundle closure и отсутствующие providers отложены. Full reconcile обеих source kinds необходим сейчас для сохранения уже опубликованных application fragments. |
| Speculative features | Generic CRUD, plugin extension points и произвольные HAProxy directives не предлагаются. HTTP/HTTPS ограничение соответствует текущему frontend. |
| Missed simpler mechanisms | Built-in Ansible merge, templates, candidate validation и BIND update переиспользуются. Коррекции P01/P02 следует выполнить точным matching и bounded validation, без новой транзакционной или миграционной подсистемы. |

## 5. Evidence и ограничения

Непосредственно прочитаны root/scoped instructions, текущий статус, review procedure,
весь A6 план, соответствующие разделы canonical contracts, A6 implementation/execution
scope, settings schemas и targeted resolver/provider code. Проверены Apply/Verify
entrypoints, HAProxy template и prepare/activate publication, BIND source update
и integration probe.

Предоставлены parent: owner decisions, исходная ревизия, scope и описание A1–A5.
Исторические PASS/DONE использованы только как заявленный контекст, не как
доказательство A6.

**Тесты не запускались.** Target hosts не посещались. Secret values и rendered
secret files не читались. Memory lookup не дал релевантных результатов.
UI/mockup comparison не применим к отдельно ограниченному standalone A6 без Go/UI.

## 6. Review validity

**CURRENT** для указанного хэша плана и прочитанных контрактов/source revision.
CURRENT не означает approval.

Изменение плана, source identity/ownership, routing, TLS trust, provider selection
или canonical-state boundary требует оценки применимости этого отчёта к новой
редакции. Локальные тестовые и редакционные исправления сами по себе не требуют
полного повторного ревью.

## 7. Exact unresolved blocking count

**2: A6-P01, A6-P02.**

## 8. Next action

Передать владельцу/parent этот BLOCK, два минимальных исправления и выбор между
точным ownership matching и явно ограничивающей validation для P01. Автоматическую
реализацию и новое ревью не запускать; дальнейшие действия определяет владелец.

## Решение владельца и уточнение 2026-10-11

Владелец принял исправление A6-P01: точный выбор source-owned файлов вместо префикса.
По A6-P02 владелец уточнил: HAProxy deployment относится к одной endpoint group,
выбранной через Keepalived. Выбор providers действительно фильтрует HAProxy по
endpointGroup. Однако текущий 10-public.cfg.j2 строит ACL по всем endpointGroups
из platform_desired_state, поэтому ограничение provider selection само по себе
не устраняет пересечение правил frontend. A6-P02 остаётся открытым для уточнения
минимальной коррекции; повторное ревью и реализация не запускались.

### Последующее принятое решение владельца

Владелец уточнил различие DNS zone и endpoint group и принял минимальную коррекцию
A6-P02: сохранить suffix routing, выводить правила по убыванию длины domain,
блокировать одинаковые нормализованные domains разных групп до mutation,
сохранить уникальность полного FQDN. Ограничение frontend одной группой отвергнуто.
Принятые коррекции P01/P02 внесены в технический план. Исходный FULL PLAN BLOCK
относится к исходному хэшу; исправления не получили независимого recheck.
Реализация и target QA не запускались.

## TARGETED_RECHECK — 2026-10-11

**APPROVE — APPLICATION-LIBRARIES-A6, PLAN, TARGETED_RECHECK.**
Независимый reviewer: `/root/a6_plan_targeted_recheck`. Вердикт сформирован независимо.
HEAD: `540aa05c49ae531b3041da16cbad4771f5ccdd6e`.
Проверенный SHA-256 плана: `b59add886fc15b88ca2b3eb9e2d858bdfb761224644d685275d69a7f349c154e`, совпал до и после чтения.
Scope: только P01/P02 и соседняя ownership/routing boundary; P03/A2/будущие этапы исключены.

- **A6-P01: OPEN → RESOLVED на уровне PLAN.** Точный source/group filename matching во всех partial prepare/activate/archive paths устраняет причину захвата соседнего fragment. Legacy filenames/header сохранены, registry не добавлен. План требует production Apply/repeat/retry для prefix-related service/application IDs с сохранением соседнего файла/route и отсутствием его в архиве.
- **A6-P02: OPEN → RESOLVED на уровне PLAN.** Порядок по убыванию длины нормализованного domain, стабильный tie-break по ID, duplicate domain BLOCK до mutation и уникальность FQDN устраняют неоднозначность dictsort. Parent/child, sibling и duplicate-domain проверки включены. Provider/Keepalived binding не расширяется.

**Overengineering: 0.** Новых abstractions/API, DTO, stores, lifecycle, speculative features или premature scope нет. Equality/set membership и deterministic sorting достаточно; новый registry/router не требуется.

Непосредственно прочитаны инструкции, CURRENT_STATE, review procedure, reviewer configuration, исправления/матрица приемки, исходные findings, relevant canonical contracts, HAProxy prepare/activate/archive/template и Core endpoint/provider selection.
Contract blobs: ansible-core.md `d752340b66bb8706f208b19eb143fe5bd3cbb58e`; project-contract.md `e81becd6f880a14e774fafbb3272c3c7ff69f29f`; endpoint-haproxy-placement-plan.md `8cd7bb87744502e12548b57bda8a4d1928f89b14`.
Тесты не запускались, hosts/secrets не читались. Production код ещё содержит исходные механизмы: закрытие относится к плану, не реализации/QA.

**Validity: CURRENT** для указанного hash/scope. Изменение ownership mapping, routing order/domain validation, provider binding или relevant contracts требует оценки применимости.
**Незакрытых BLOCKING: 0.** Один FULL и один owner-approved TARGETED_RECHECK использованы.
Следующий шаг: решение владельца по реализации; этот отчет не разрешает implementation/target QA.

## Дополнение владельца: универсальный вход hooks

Владелец потребовал единый вход для инфраструктурных сервисов и приложений без
if service / if application в HAProxy, DNS и endpoint orchestration. В план §4
внесено использование существующей runtime endpoint/backend projection; различия
desired inputs разрешает Core до вызова hooks. Отдельные DTO/hooks/stores не вводятся.
TARGETED_RECHECK выше относится к зафиксированному hash и P01/P02; независимое
ревью этого последующего дополнения не заявляется. Новое ревью не запускалось.
