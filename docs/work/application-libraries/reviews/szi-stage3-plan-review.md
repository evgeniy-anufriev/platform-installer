# SZI-STAGE3 — независимый FULL PLAN review

Дата: 2026-10-24. Reviewer: `/root/szi_stage3_plan_review`, роль architecture-reviewer.
Режим: FULL PLAN. Вердикт: **APPROVE_WITH_CHANGES**. Unresolved BLOCKING: **0**.
Вердикт сформирован независимо. Implementation/DIFF review и target QA не выполнялись.

## Идентичность

- База/HEAD: `24e24f9594b38b484682d27e433bc25b572935b5`.
- План: `docs/work/application-libraries/szi-stage3-technical-plan.md`.
- Проверенный SHA-256 до и после review:
  `6BB79EFE13D484957E448885112B0356557BA75E49D91CC4DBA06C85467BA884`.
- Scope: весь этап3 — standalone selection, providers, credentials, images,
  endpoints, hooks/nginx, Go/UI и acceptance SDKU/CSPA.
- Во время review изменёнными были только план и CURRENT_STATE.md.

## Findings независимого reviewer

### SZI3-P01 — NON_BLOCKING / OPEN на проверенной редакции

Место: §6, §9/SZI3-05. Явно ограничить также прежнюю генерацию маршрутов
выбранными потребителями.

Доказательство: `examples/szi/application-packages/nginx/1.0.0/assets/routes.requested.json.j2`
обходит все библиотеки full snapshot. Сохраняемый before_start вызывает
prepare-routes.sh, который читает этот файл и делает additive upsert. Фильтрация
runtime jobs по A сама по себе не фильтрует содержимое Jinja.

Влияние: устанавливаемый nginx может обновить route пропущенной consumer library,
нарушив scope C, даже при корректном новом integration_apply hook.

Минимальная коррекция: обе точки получения requested routes используют одну
фильтрованную проекцию; собственные маршруты устанавливаемой provider library
сохраняются, невыбранные внешние потребители только retained.

Проверка: nginx/provider и SDKU входят A, CSPA входит S; изменение desired endpoint
CSPA не меняет existing route. Отдельно S=[] и first install.

### SZI3-P02 — NON_BLOCKING / OPEN на проверенной редакции

Место: §4, §6. Явно определить compatibility package script schema.

Доказательство: `contracts/application-libraries/v1alpha1/package.schema.json`,
`$defs.script`, содержит закрытые enum phase/argv.valueFrom; run_on=execution_node
разрешён только для трёх существующих callback phases. Старый валидатор не понимает
новую optional phase/argv source. Стратегия версии package contract была неявной.

Минимальная коррекция: зафиксировать package API/schema version либо явное
capability-gated additive extension и import/resolve gate. Старый runtime должен
отклонять новый hook до target mutations; старые пакеты сохраняют поведение.
Явно определить phase/run_on/execution restrictions.

Проверка: old package/new runtime; new package/unsupported runtime; target
once/each_target; execution_node once; несовместимые комбинации.

### SZI3-P03 — NON_BLOCKING / OPEN на проверенной редакции

Место: §9, абзац после таблицы. Убрать двусмысленность обязательного DIFF gate.

Доказательство: «Новая production DIFF review — только ... отдельному owner
решению» допускает необязательность review при обычной реализации. Изменяются
public versioned contracts, execution scope и credential custody — HIGH-RISK
по `docs/agent-procedures/review.md`.

Минимальная коррекция: текущий запрос разрешает только PLAN review и не запускает
DIFF сейчас; после разрешения реализации обязательный независимый HIGH-RISK
DIFF gate выполняется по процедуре до acceptance/promotion с implementation identity.
Неблокирующие уточнения не требуют ещё одного PLAN review.

## Обязательная оценка overengineering

Подтверждённых ненужных абстракций, дублирующих DTO/contracts, новой persistence,
преждевременного scope или блокирующих speculative extension points: **0**.

Pure Core scope helper нужен для единой A/C/P projection; Go/UI filter не даёт
нужных гарантий. Canonical selection definition и pass-through Go не дублируют
Core. Нет нового installation registry, ready markers, scheduler, discovery,
удаления или UI групп.

integration_apply и typed consumer projection имеют конкретного потребителя:
nginx на placements, которые не обязаны совпадать с API provider placements.
Прямой reuse before_start требует lifecycle, а provider_prepare адресуется
connection provider target. Более простой механизм с теми же гарантиями не найден.
Новая phase допустима при сохранении прежнего runner и отсутствии второго executor;
цена расширения schemas/scheduling отражена в плане.

## Evidence и ограничения review

Reviewer прочёл root/scoped AGENTS, CURRENT_STATE, review procedure,
ansible-core-review criteria, весь план, применимые project/Core/architecture
contracts, scripts schema, Installation B4/mockup, provider batching и ordered tasks,
endpoint publication, nginx scripts/Lua/template и SZI provided connection defaults.

Подтверждено по коду: provider-script зависит от preflight job; batch привязан
к точному export; routes template читает full snapshot; runner и product API разделены.

Тесты не запускались. Stage2 PASS — baseline evidence, не Stage3 acceptance.
Secrets/private credential files не читались, сети/target contacts, мутаций и
других агентов reviewer не использовал. Review validity: CURRENT для проверенного
SHA и базы. Материальные изменения границ оцениваются по процедуре.

## Неблокирующие уточнения автора после review

Внесены без нового review, как разрешено FULL verdict:

| Finding | Уточнение в текущем плане | Состояние |
|---|---|---|
| P01 | единая фильтрация legacy before_start и нового route hook; добавлен P15 | ADDRESSED_BY_AUTHOR, независимо не перепроверялось |
| P02 | manifest API/application-libraries package schema v1alpha2; old schema не меняет enum; explicit import/resolve capability gate и restrictions | ADDRESSED_BY_AUTHOR, независимо не перепроверялось |
| P03 | текущий запрос PLAN-only; mandatory HIGH-RISK DIFF после разрешения реализации | ADDRESSED_BY_AUTHOR, независимо не перепроверялось |

SHA-256 текущего уточнённого плана:
`4DE51E6D62E5EB71FE62B57DEF88D8E703B4507DBD46D93EC237F16EAF87BBEA`.
Это не новый независимый verdict на изменённый hash. Исходный FULL verdict сохранён.
Unresolved blockers остаётся0. Второй review не запрашивался.

Следующее действие: решение владельца о реализации, включая предложенные
integration_apply/integration_consumers и package API v1alpha2. До этого никаких
implementation, runtime publication или target actions.
