# Инвентаризация и карта упорядочивания документации

## Границы первого прохода

Снимок каталога `docs` от 2026-10-12: 205 файлов до добавления этой карты
и `README.md`; 153 файла в корне, 32 в `application-libraries`, 11 изображений,
4 процедуры, 4 исторических снимка и 1 руководство в `ansible-playbooks`.
Карта перечисляет все файлы снимка, включая HTML и изображения.

На первом проходе добавлена навигация. На втором проходе перенесены 177 файлов
по карте ниже: 75 с однозначным назначением и 102 смешанных материала целиком.
28 файлов сохранены на прежних путях. Целевые пути теперь являются фактическими.
Классификация предварительная: основана на путях, назначении и заголовках;
она не утверждает актуальность всех утверждений внутри каждого документа.
Содержательный разбор выполняется пакетами; результаты приведены ниже.
Организация документов и выделение исторических результатов выполнены пакетами ниже.
Полная проверка старых версий контрактов по текущему коду не входит в реорганизацию.
Текущий статус и разрешения остаются в [CURRENT_STATE.md](../CURRENT_STATE.md).

## Целевая организация

| Каталог | Назначение |
| --- | --- |
| Корень `docs` | Короткая навигация и основные канонические документы на стабильных путях |
| `agent-procedures/` | Обязательные процедуры; сохраняются на текущих путях |
| `guides/` | Руководства эксплуатации, разработки и диагностики |
| `design/` | UI-дизайн, mockups и предложения по интерфейсу |
| `contracts/` | Подробные действующие контракты, выделенные из смешанных материалов после проверки |
| `work/<тема>/` | Планы и материалы реализации; внутри темы `reviews/` и `evidence/` |
| `history/` | Существующие исторические снимки; заменённые документы только после проверки |
| `images/` | Существующие изображения; пока сохраняются, чтобы избежать лишних переносов |

На втором проходе исходные имена сохраняются внутри тематических папок:
это облегчает проверку происхождения и исключает потерю идентификаторов.
Для новых самостоятельных этапов допустимы `plan.md`, `test-cases.md`,
`reviews/` и `evidence/test-journal.md`, если идентификатор однозначно задан папкой.
Переименование старых файлов в такие имена требует отдельной карты без коллизий.

Основные канонические файлы, roadmap, agent-index и процедуры остаются на месте.
Перенос в `work/` обозначает принадлежность к теме, а не отмену контракта:
смешанные документы сохраняют содержание до отдельного разбора.

## Случаи, определённые при первоначальной инвентаризации

| Материал | Что проверить до разделения или архивирования |
| --- | --- |
| [UI-BE-04](work/ui-backend/ui-be-04.md) | Ownership, протокол, fingerprint и lifecycle отделить от implementation audit и submilestone gates; сохранить ссылки на конкретные разделы |
| [Docker rootless](work/docker/service-docker-rootless-architecture.md) | Runtime/network/service contract отделить от SI10 acceptance evidence |
| [Service install acceptance](work/services/service-install-acceptance.md) | Общие правила приёмки отделить от датированных результатов отдельных сервисов |
| [Application server types](work/application-config/application-config-server-types.md) | Planned contract, текущие правила и implementation/verification различить по подтверждённой версии |
| [Application libraries](work/application-libraries/README.md) | Предложения будущих этапов отделять от реализованных контрактов подэтапов; актуальность проверять по текущему состоянию |
| [Roadmap](roadmap.md) | Сохранить последовательность и критерии этапов; дубли текущих статусов и подробные runs заменить ссылками после сверки |
| [Owner decisions](open-questions.md) | Контекст/evidence разделены |
| [Endpoint draft](work/endpoint-placement/endpoint-haproxy-placement-draft.md) | Исторический draft; узкий scope в плане |
| `core-*`, `net-*`, `ui-*`, `service-install-*` | Наличие milestone в имени не доказывает устаревание контракта; проверить нормативные разделы перед архивированием |

Результаты разбора этих случаев приведены в последующих пакетах ниже.

Никакие FAIL/BLOCK, review findings или владельческие решения не переписываются
в успешные результаты. Решение владельца и вердикт reviewer сохраняются раздельно.
Review и evidence связываются с исходным scope/revision; перемещение не расширяет
их применимость. Runtime-секреты и артефакты исполнения в `docs` не добавляются.

## Порядок переноса и последующего разбора

1. Перед переносом сверить снимок с текущими файлами и сохранить посторонние
   изменения. Найти потребителей точных путей в README, CURRENT_STATE, AGENTS,
   навыках, документах, коде и скриптах, исключая vendor, runtime и V1.
2. Переносить тематическими группами без редактирования утверждений. Обновить
   Markdown/HTML-ссылки и ссылки с якорями, включая ссылки из переносимых файлов
   наружу. Сравнить содержание с исходным после учёта замен адресов ссылок.
3. Разбирать смешанные материалы отдельно: выделить действующий контракт,
   оставить review/evidence с происхождением, подтвердить замену перед архивом.
   Добавить небольшие тематические README там, где они помогают маршруту чтения.

Критерии приёмки: каждый исходный файл учтён ровно один раз; нет коллизий
целевых путей; локальные ссылки и якоря изменённых файлов разрешаются;
обязательные процедуры достижимы из AGENTS и индекса; статус не дублируется;
точные evidence IDs и исходные вердикты сохранены. Проверить маршруты:
UI → дизайн/экран/QA; Core → контракт/процедура; milestone → план/review/evidence.
Проверки документации не требуют запуска Core, Wails или мутации target hosts.

## Результат второго прохода — 2026-10-12

- Перенесены все 177 файлов с изменённым целевым путём; 28 файлов снимка
  сохранены на месте. Смешанные материалы перенесены без разделения и архивирования.
- В корне `docs` осталось 11 файлов вместо 153, включая новые README и карту.
  Дополнительная навигация добавлена в `work`, `guides`, `design` и SI11.
- До переноса сохранены точные рабочие версии документов, включая существующие
  незакоммиченные правки CURRENT_STATE и журнала SI11. SHA-256 и обратное применение
  замен подтвердили сохранность 194 текстовых документов исходного снимка
  и 54 документов вне `docs`; изменения в них ограничены путями ссылок.
  11 изображений остались на месте. Новые навигационные страницы проверены отдельно.
- При переносе выполнены 625 замен адресов в 91 документе. Потребители в AGENTS,
  CURRENT_STATE, корневом README, README Core/services и исторических снимках обновлены.
  Ссылки внутри перенесённых файлов пересчитаны относительно нового расположения.
- Проверены 747 локальных ссылок и якорей в итоговых документах; для исходного
  снимка дополнительно проверена 661 ссылка. Сломанных ссылок и новых ошибок нет.
  Обязательные процедуры остаются на стабильных путях; UI/Core/SI11 маршруты
  доступны из README и agent-index. `git diff --check` проходит.

Старые пути в подписях ссылок и указателях на строки проверенной review-версии
сохранены как происхождение evidence. Они не используются как адреса навигации;
переходы ведут к текущим файлам, а исходное расположение отражено в полной карте.

Локальные снимки, скрипты и отчёт находятся в игнорируемом каталоге
`.runtime/qa/documentation-20261012/`. Это вспомогательные материалы проверки,
  не runtime-зависимость и не дополнительный источник статусов. Код продукта,
Core, bundle и целевые хосты не изменялись. Второй проход закреплён коммитом
`85d4567` и отправлен в `origin/master`. Прежние изменения статуса и журнала
SI11 сохранены вне этого коммита. В двух review-файлах пять Markdown hard breaks
нормализованы из двух конечных пробелов в обратную косую черту, без изменения текста.

Наличие выполненного переноса не означает завершение содержательного разбора.

## Третий проход: первый содержательный пакет — 2026-10-12

Разобраны три смешанных документа; исходные утверждения перенесены без изменения:

| Исходный материал | Контракт / общие правила | Evidence |
| --- | --- | --- |
| UI-BE-04 | [Execution contract](contracts/execution-planning-and-events.md) | [Implementation audit](work/ui-backend/evidence/ui-be-04-implementation-audit.md) |
| Docker SI10 | [Docker contract](contracts/docker-rootless.md) | [SI10 acceptance](work/docker/evidence/si10-acceptance.md) |
| Общая приёмка сервисов | [Повторяемые условия](agent-procedures/service-acceptance.md) | [Исторические статусы и runs](work/services/evidence/service-install-initial-evidence.md) |

Планы сохраняют scope, gates и сценарии; бывшие нормативные разделы содержат
ссылки на выделенные правила вместо копии текста. Заголовки и прежние якоря
сохранены. Датированные статусные строки перенесены в evidence с явной пометкой
исторического снимка. Выделение контракта не расширяет scope, не утверждает
будущие возможности и не заменяет текущий статус или решения владельца.

По уточнению владельца завершённый SI11 объединён с общими материалами
`work/services`: семь исходных материалов и навигация перенесены из отдельной
папки, отдельная тема SI11 убрана из индекса. Журнал, case verdicts и прежние
незакоммиченные изменения сохранены. Историческая процедура SI11 остаётся
доступной для соответствующих сценариев; новое исполнение не разрешается.

Снимки и проверка: `.runtime/qa/documentation-content-20261012/`.
Все 25 выделенных фрагментов сопоставлены с исходным текстом после обратного
пересчёта относительных ссылок; остальные исходные документы проверены на
сохранность текста. Проверены локальные ссылки и якоря всей документации,
ошибок нет. Это первый пакет содержательного разбора, а не завершение всех
102 предварительно отмеченных смешанных материалов. Их разбор продолжается
отдельными пакетами; объём следующего пакета описан ниже.

## Третий проход: второй содержательный пакет — 2026-10-12

- Foundation типов серверов разделён на [version-scoped contract](contracts/application-config-foundation.md),
  [план](work/application-config/application-config-server-types.md) и
  [исторический audit/acceptance](work/application-config/evidence/foundation-acceptance.md).
  Формулировки относятся к application-config v1alpha1 и исходным project-edit
  v1alpha2/v1alpha3. Они не объявляют v1alpha3 текущей версией всех новых sessions
  и не отменяют поздние версии или общий контракт проекта.
- Из roadmap вынесены 45 записей об исходной реализации, acceptance и тогдашнем
  состоянии в [исторический снимок](history/roadmap-checkpoints-20261012.md).
  Старая запись SI11 NOT STARTED сохранена только как история; закрытие этапа
  владельцем определяется CURRENT_STATE. Roadmap сохраняет scope, последовательность
  и критерии выхода; нет повторного актуального ledger DONE/NEXT.
- В libraries добавлен [индекс контрактов и scope](work/application-libraries/contract-index.md):
  A1–A5 → технический план/review/журнал; дальнейшие A6–A9, Go/UI → общий план.
  Общие architecture/configuration/execution/secrets/UI помечены как консолидированные
  проектные предложения с уточнениями этапов. Их примеры не являются acceptance.
- README libraries стал навигацией без копии текущих статусов и reviewer verdicts.
  Прежняя навигация, FULL PLAN и A5 checkpoint сохранены в
  [снимке обсуждения](work/application-libraries/evidence/documentation-checkpoints-20261012.md).
  Из заголовка A5 общего плана убран текущий статус; прежний якорь сохранён.
  Kafka security/SASL scope не объявлен выполненным.

Проверка и исходные рабочие версии: `.runtime/qa/documentation-next-20261012/`.
55 новых вынесенных фрагментов сопоставлены с исходным содержанием после
обратного пересчёта ссылок; 25 фрагментов предыдущего пакета также сохранены.
Текст незатронутых документов и все оставшиеся блоки roadmap проверены отдельно.
Итог: 955 локальных ссылок и якорей разрешаются, 248 незатронутых документов
совпадают с рабочим снимком; 173 оставшихся блока roadmap сохранены. Roadmap
сокращён с 1074 до 754 строк при сохранении исходных критериев и ограничений.
`git diff --check` проходит. Код продукта и целевые среды не изменялись.
Вынесенные статусы не являются новым доказательством реализации или разрешением QA.
Новые изменения этого прохода пока не закоммичены; существующие owner corrections
CURRENT_STATE и журнала установки сервисов не изменялись содержательно.

## Третий проход: Core, сеть и UI — 2026-10-12

Обработаны 50 документов исходных этапов Core, NET, UI-01, UI-02 и UI-BE.
29 разделов с фактически выполненными проверками и историческим audit,
57 явных абзацев статуса и один вердикт в заголовке вынесены в пять сводных
файлов evidence. Разделы Acceptance criteria, QA plan, Required evidence
и другие будущие требования не классифицировались как выполненная проверка.

| Тема | Навигация | Исходные статусы и результаты |
| --- | --- | --- |
| Core | [README](work/core/README.md) | [Checkpoint](work/core/evidence/documentation-checkpoints-20261012.md) |
| Сеть | [README](work/network/README.md) | [Checkpoint](work/network/evidence/documentation-checkpoints-20261012.md) |
| UI-01 | [README](work/ui-01/README.md) | [Checkpoint](work/ui-01/evidence/documentation-checkpoints-20261012.md) |
| UI-02 | [README](work/ui-02/README.md) | [Checkpoint](work/ui-02/evidence/documentation-checkpoints-20261012.md) |
| Backend | [README](work/ui-backend/README.md) | [Checkpoint](work/ui-backend/evidence/documentation-checkpoints-20261012.md) |

Scope исходных этапов отмечен явно: формулировка старого implementation audit
не является утверждением о последней версии продукта. При удалении статуса
сохранены независимые предложения о scope и ограничениях. Заголовки вынесенных
разделов остались точками входа, старый якорь изменённого заголовка сохранён.
Внутренние ссылки архивируемых фрагментов ведут к исходному контексту.
Review verdicts, owner exceptions и точные тестовые значения не переписаны.

Снимки и проверка: `.runtime/qa/documentation-core-ui-20261012/`.
87 вынесенных фрагментов сверены с исходником после обратного пересчёта ссылок,
80 фрагментов двух предыдущих пакетов также сохранены. Проверка реконструкции
50 исходных документов подтверждает отсутствие изменений вне объявленных
переносов и scope-пометок; остальные документы сравнивались с точным рабочим
снимком. Локальные ссылки и якоря проверены без Markdown-примеров внутри code fences.
Итог: 1259 локальных ссылок и якорей разрешаются; 214 незатронутых документов
совпадают с рабочим снимком. `git diff --check` проходит.
Код, targets и runtime bundles не изменялись; новое выполнение или acceptance
этот документационный пакет не разрешает. Изменения пока не закоммичены.

## Полная карта файлов исходного снимка

Имена в первом столбце сохраняют исходный путь снимка; ссылки ведут к файлам
после переноса. Третий столбец содержит фактический путь относительно `docs`.
`Сохранить` — прежний путь сохранён. `Перенести` — группировка выполнена.
`Проверить содержание` — документ также перенесён целиком, но контракт и историю
нужно проверить перед разделением; архивирование этой отметкой не разрешается.
`Контекст/evidence разделены` — явные исторические блоки отделены от scope;
это не означает ревью всех нормативных утверждений или изменение их версии.

| Исходный файл (ссылка на текущий путь) | Назначение | Текущий путь (относительно docs) | Обработка / оставшаяся проверка |
| --- | --- | --- | --- |
| [agent-context-maintenance.md](agent-context-maintenance.md) | Канонический документ / навигация | `agent-context-maintenance.md` | Сохранить |
| [agent-index.md](agent-index.md) | Канонический документ / навигация | `agent-index.md` | Сохранить |
| [agent-procedures/qa.md](agent-procedures/qa.md) | Обязательная процедура | `agent-procedures/qa.md` | Сохранить |
| [agent-procedures/review.md](agent-procedures/review.md) | Обязательная процедура | `agent-procedures/review.md` | Сохранить |
| [agent-procedures/runtime-bundle.md](agent-procedures/runtime-bundle.md) | Обязательная процедура | `agent-procedures/runtime-bundle.md` | Сохранить |
| [agent-procedures/si11.md](agent-procedures/si11.md) | Обязательная процедура | `agent-procedures/si11.md` | Сохранить |
| [ansible-core.md](ansible-core.md) | Канонический документ / навигация | `ansible-core.md` | Сохранить |
| [ansible-playbooks/README.md](guides/ansible-playbooks/README.md) | Руководство | `guides/ansible-playbooks/README.md` | Перенести |
| [application-config-server-types.md](work/application-config/application-config-server-types.md) | План; version-scoped contract и acceptance выделены | `work/application-config/application-config-server-types.md` | Разделён |
| [application-libraries/a1-a2-speed-review.md](work/application-libraries/milestones/a1-a2-speed/reviews/a1-a2-speed-review.md) | Review | `work/application-libraries/milestones/a1-a2-speed/reviews/a1-a2-speed-review.md` | Перенести |
| [application-libraries/a1-a2-speed-test-journal.md](work/application-libraries/milestones/a1-a2-speed/evidence/a1-a2-speed-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/a1-a2-speed/evidence/a1-a2-speed-test-journal.md` | Перенести |
| [application-libraries/a1-diff-review.md](work/application-libraries/milestones/a1/reviews/a1-diff-review.md) | Review | `work/application-libraries/milestones/a1/reviews/a1-diff-review.md` | Перенести |
| [application-libraries/a1-plan-review.md](work/application-libraries/milestones/a1/reviews/a1-plan-review.md) | Review | `work/application-libraries/milestones/a1/reviews/a1-plan-review.md` | Перенести |
| [application-libraries/a1-technical-plan.md](work/application-libraries/milestones/a1/a1-technical-plan.md) | План | `work/application-libraries/milestones/a1/a1-technical-plan.md` | Перенести |
| [application-libraries/a1-test-journal.md](work/application-libraries/milestones/a1/evidence/a1-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/a1/evidence/a1-test-journal.md` | Перенести |
| [application-libraries/a2-diff-review.md](work/application-libraries/milestones/a2/reviews/a2-diff-review.md) | Review | `work/application-libraries/milestones/a2/reviews/a2-diff-review.md` | Перенести |
| [application-libraries/a2-plan-review.md](work/application-libraries/milestones/a2/reviews/a2-plan-review.md) | Review | `work/application-libraries/milestones/a2/reviews/a2-plan-review.md` | Перенести |
| [application-libraries/a2-technical-plan.md](work/application-libraries/milestones/a2/a2-technical-plan.md) | План | `work/application-libraries/milestones/a2/a2-technical-plan.md` | Перенести |
| [application-libraries/a2-test-journal.md](work/application-libraries/milestones/a2/evidence/a2-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/a2/evidence/a2-test-journal.md` | Перенести |
| [application-libraries/a3-diff-review.md](work/application-libraries/milestones/a3/reviews/a3-diff-review.md) | Review | `work/application-libraries/milestones/a3/reviews/a3-diff-review.md` | Перенести |
| [application-libraries/a3-plan-review.md](work/application-libraries/milestones/a3/reviews/a3-plan-review.md) | Review | `work/application-libraries/milestones/a3/reviews/a3-plan-review.md` | Перенести |
| [application-libraries/a3-technical-plan.md](work/application-libraries/milestones/a3/a3-technical-plan.md) | План | `work/application-libraries/milestones/a3/a3-technical-plan.md` | Перенести |
| [application-libraries/a3-test-journal.md](work/application-libraries/milestones/a3/evidence/a3-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/a3/evidence/a3-test-journal.md` | Перенести |
| [application-libraries/a4-diff-review.md](work/application-libraries/milestones/a4/reviews/a4-diff-review.md) | Review | `work/application-libraries/milestones/a4/reviews/a4-diff-review.md` | Перенести |
| [application-libraries/a4-plan-review.md](work/application-libraries/milestones/a4/reviews/a4-plan-review.md) | Review | `work/application-libraries/milestones/a4/reviews/a4-plan-review.md` | Перенести |
| [application-libraries/a4-technical-plan.md](work/application-libraries/milestones/a4/a4-technical-plan.md) | План | `work/application-libraries/milestones/a4/a4-technical-plan.md` | Перенести |
| [application-libraries/a4-test-journal.md](work/application-libraries/milestones/a4/evidence/a4-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/a4/evidence/a4-test-journal.md` | Перенести |
| [application-libraries/a5-cluster-plan-review.md](work/application-libraries/milestones/a5/reviews/a5-cluster-plan-review.md) | Review | `work/application-libraries/milestones/a5/reviews/a5-cluster-plan-review.md` | Перенести |
| [application-libraries/a5-diff-review.md](work/application-libraries/milestones/a5/reviews/a5-diff-review.md) | Review | `work/application-libraries/milestones/a5/reviews/a5-diff-review.md` | Перенести |
| [application-libraries/a5-plan-review.md](work/application-libraries/milestones/a5/reviews/a5-plan-review.md) | Review | `work/application-libraries/milestones/a5/reviews/a5-plan-review.md` | Перенести |
| [application-libraries/a5-technical-plan.md](work/application-libraries/milestones/a5/a5-technical-plan.md) | План | `work/application-libraries/milestones/a5/a5-technical-plan.md` | Перенести |
| [application-libraries/a5-test-journal.md](work/application-libraries/milestones/a5/evidence/a5-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/a5/evidence/a5-test-journal.md` | Перенести |
| [application-libraries/architecture.md](work/application-libraries/architecture.md) | План / контракт / история реализации | `work/application-libraries/architecture.md` | Предложение; scope уточнён индексом контрактов |
| [application-libraries/configuration.md](work/application-libraries/configuration.md) | План / контракт / история реализации | `work/application-libraries/configuration.md` | Предложение; scope уточнён индексом контрактов |
| [application-libraries/execution.md](work/application-libraries/execution.md) | План / контракт / история реализации | `work/application-libraries/execution.md` | Предложение; scope уточнён индексом контрактов |
| [application-libraries/implementation-plan.md](work/application-libraries/implementation-plan.md) | План | `work/application-libraries/implementation-plan.md` | Перенести |
| [application-libraries/lightweight-verify-test-journal.md](work/application-libraries/milestones/lightweight-verify/evidence/lightweight-verify-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/lightweight-verify/evidence/lightweight-verify-test-journal.md` | Перенести |
| [application-libraries/plan-review.md](work/application-libraries/reviews/plan-review.md) | Review | `work/application-libraries/reviews/plan-review.md` | Перенести |
| [application-libraries/README.md](work/application-libraries/README.md) | Тематическая навигация | `work/application-libraries/README.md` | Перенести |
| [application-libraries/secrets.md](work/application-libraries/secrets.md) | План / контракт / история реализации | `work/application-libraries/secrets.md` | Предложение; scope уточнён индексом контрактов |
| [application-libraries/ui.md](work/application-libraries/ui.md) | План / контракт / история реализации | `work/application-libraries/ui.md` | Предложение; scope уточнён индексом контрактов |
| [architecture-decisions.md](architecture-decisions.md) | Канонический документ / навигация | `architecture-decisions.md` | Сохранить |
| [architecture.md](architecture.md) | Канонический документ / навигация | `architecture.md` | Сохранить |
| [backend-and-ui.md](backend-and-ui.md) | Канонический документ / навигация | `backend-and-ui.md` | Сохранить |
| [browser-mode-local-plan.md](work/browser/browser-mode-local-plan.md) | План | `work/browser/browser-mode-local-plan.md` | Контекст/evidence разделены |
| [browser-mode-remote-plan.md](work/browser/browser-mode-remote-plan.md) | План | `work/browser/browser-mode-remote-plan.md` | Контекст/evidence разделены |
| [core-01.md](work/core/core-01.md) | План / контракт / история реализации | `work/core/core-01.md` | Контекст/evidence разделены |
| [core-03.md](work/core/core-03.md) | План / контракт / история реализации | `work/core/core-03.md` | Контракт этапа; сохранён целиком |
| [core-04.md](work/core/core-04.md) | План / контракт / история реализации | `work/core/core-04.md` | Контракт этапа; сохранён целиком |
| [core-05.md](work/core/core-05.md) | План / контракт / история реализации | `work/core/core-05.md` | Контракт этапа; сохранён целиком |
| [core-06.md](work/core/core-06.md) | План / контракт / история реализации | `work/core/core-06.md` | Контекст/evidence разделены |
| [core-07.md](work/core/core-07.md) | План / контракт / история реализации | `work/core/core-07.md` | Контракт этапа; сохранён целиком |
| [core-07a.md](work/core/core-07a.md) | План / контракт / история реализации | `work/core/core-07a.md` | Контракт этапа; сохранён целиком |
| [devx-01.md](work/development/devx-01.md) | План / контракт / история реализации | `work/development/devx-01.md` | Контекст/evidence разделены |
| [endpoint-haproxy-placement-draft.md](work/endpoint-placement/endpoint-haproxy-placement-draft.md) | Предложение; проверить замену | `work/endpoint-placement/endpoint-haproxy-placement-draft.md` | Исторический draft; узкий scope в плане |
| [endpoint-haproxy-placement-plan-review.md](work/endpoint-placement/reviews/endpoint-haproxy-placement-plan-review.md) | Review | `work/endpoint-placement/reviews/endpoint-haproxy-placement-plan-review.md` | Перенести |
| [endpoint-haproxy-placement-plan.md](work/endpoint-placement/endpoint-haproxy-placement-plan.md) | План | `work/endpoint-placement/endpoint-haproxy-placement-plan.md` | Контекст/evidence разделены |
| [exec-01a-source-audit.md](work/execution/evidence/exec-01a-source-audit.md) | Evidence / журнал / аудит | `work/execution/evidence/exec-01a-source-audit.md` | Перенести |
| [exec-01a.md](work/execution/exec-01a.md) | План / контракт / история реализации | `work/execution/exec-01a.md` | Контекст/evidence разделены |
| [exec-generated-state.md](work/execution/exec-generated-state.md) | План / контракт / история реализации | `work/execution/exec-generated-state.md` | Контракт этапа; сохранён целиком |
| [exec-obs-01.md](work/execution/exec-obs-01.md) | План / контракт / история реализации | `work/execution/exec-obs-01.md` | Контекст/evidence разделены |
| [execution-failure-diagnostics.md](guides/execution-failure-diagnostics.md) | Руководство / инструкция QA | `guides/execution-failure-diagnostics.md` | Перенести |
| [execution-node-password-auth-plan.md](work/execution-node-password-auth/execution-node-password-auth-plan.md) | План | `work/execution-node-password-auth/execution-node-password-auth-plan.md` | Контекст/evidence разделены |
| [execution-node-password-auth-review.md](work/execution-node-password-auth/reviews/execution-node-password-auth-review.md) | Review | `work/execution-node-password-auth/reviews/execution-node-password-auth-review.md` | Перенести |
| [execution-order-01-plan.md](work/execution-order/execution-order-01-plan.md) | План | `work/execution-order/execution-order-01-plan.md` | Контекст/evidence разделены |
| [history/milestones-state-20261008.md](history/milestones-state-20261008.md) | Исторический снимок | `history/milestones-state-20261008.md` | Сохранить |
| [history/si11-state-20261008.md](history/si11-state-20261008.md) | Исторический снимок | `history/si11-state-20261008.md` | Сохранить |
| [history/vault-state-20261008.md](history/vault-state-20261008.md) | Исторический снимок | `history/vault-state-20261008.md` | Сохранить |
| [history/workflow-state-20261008.md](history/workflow-state-20261008.md) | Исторический снимок | `history/workflow-state-20261008.md` | Сохранить |
| [images/installer-engineer-guide/certificates-pki.png](images/installer-engineer-guide/certificates-pki.png) | Изображение руководства | `images/installer-engineer-guide/certificates-pki.png` | Сохранить |
| [images/installer-engineer-guide/execution-terminal-failed.png](images/installer-engineer-guide/execution-terminal-failed.png) | Изображение руководства | `images/installer-engineer-guide/execution-terminal-failed.png` | Сохранить |
| [images/installer-engineer-guide/installation-plan-preparation.png](images/installer-engineer-guide/installation-plan-preparation.png) | Изображение руководства | `images/installer-engineer-guide/installation-plan-preparation.png` | Сохранить |
| [images/installer-engineer-guide/installation-plan-stages.png](images/installer-engineer-guide/installation-plan-stages.png) | Изображение руководства | `images/installer-engineer-guide/installation-plan-stages.png` | Сохранить |
| [images/installer-engineer-guide/installation-result.png](images/installer-engineer-guide/installation-result.png) | Изображение руководства | `images/installer-engineer-guide/installation-result.png` | Сохранить |
| [images/installer-engineer-guide/installation-success.png](images/installer-engineer-guide/installation-success.png) | Изображение руководства | `images/installer-engineer-guide/installation-success.png` | Сохранить |
| [images/installer-engineer-guide/persistent-header.png](images/installer-engineer-guide/persistent-header.png) | Изображение руководства | `images/installer-engineer-guide/persistent-header.png` | Сохранить |
| [images/installer-engineer-guide/project-overview.png](images/installer-engineer-guide/project-overview.png) | Изображение руководства | `images/installer-engineer-guide/project-overview.png` | Сохранить |
| [images/installer-engineer-guide/servers-and-execution-node.png](images/installer-engineer-guide/servers-and-execution-node.png) | Изображение руководства | `images/installer-engineer-guide/servers-and-execution-node.png` | Сохранить |
| [images/installer-engineer-guide/service-settings.png](images/installer-engineer-guide/service-settings.png) | Изображение руководства | `images/installer-engineer-guide/service-settings.png` | Сохранить |
| [images/installer-engineer-guide/topology-deployment.png](images/installer-engineer-guide/topology-deployment.png) | Изображение руководства | `images/installer-engineer-guide/topology-deployment.png` | Сохранить |
| [installer-engineer-guide.md](guides/installer-engineer-guide.md) | Руководство / инструкция QA | `guides/installer-engineer-guide.md` | Перенести |
| [net-01.md](work/network/net-01.md) | План / контракт / история реализации | `work/network/net-01.md` | Контракт этапа; сохранён целиком |
| [net-02.md](work/network/net-02.md) | План / контракт / история реализации | `work/network/net-02.md` | Контекст/evidence разделены |
| [net-03-1.md](work/network/net-03-1.md) | План / контракт / история реализации | `work/network/net-03-1.md` | Контекст/evidence разделены |
| [net-03.md](work/network/net-03.md) | План / контракт / история реализации | `work/network/net-03.md` | Контекст/evidence разделены |
| [net-04-1.md](work/network/net-04-1.md) | План / контракт / история реализации | `work/network/net-04-1.md` | Контекст/evidence разделены |
| [net-04-2.md](work/network/net-04-2.md) | План / контракт / история реализации | `work/network/net-04-2.md` | Контекст/evidence разделены |
| [net-04.md](work/network/net-04.md) | План / контракт / история реализации | `work/network/net-04.md` | Контекст/evidence разделены |
| [open-questions.md](open-questions.md) | Канонический документ / навигация | `open-questions.md` | Контекст/evidence разделены |
| [pki-01.md](work/pki/pki-01.md) | План / контракт / история реализации | `work/pki/pki-01.md` | Контракт этапа; сохранён целиком |
| [pki-platform-shared-tls-usages-plan.md](work/pki/pki-platform-shared-tls-usages-plan.md) | План | `work/pki/pki-platform-shared-tls-usages-plan.md` | Контекст/evidence разделены |
| [pki-service-scope-optimization-plan.md](work/pki/pki-service-scope-optimization-plan.md) | План | `work/pki/pki-service-scope-optimization-plan.md` | Перенести |
| [pki-single-pass-review.md](work/pki/reviews/pki-single-pass-review.md) | Review | `work/pki/reviews/pki-single-pass-review.md` | Перенести |
| [pki-single-pass.md](work/pki/pki-single-pass.md) | План / контракт / история реализации | `work/pki/pki-single-pass.md` | Контекст/evidence разделены |
| [pki-store-password-recovery-01.md](work/pki/pki-store-password-recovery-01.md) | План / контракт / история реализации | `work/pki/pki-store-password-recovery-01.md` | Контекст/evidence разделены |
| [postgres-01.md](work/postgresql/postgres-01.md) | План / контракт / история реализации | `work/postgresql/postgres-01.md` | Контекст/evidence разделены |
| [project-contract.md](project-contract.md) | Канонический документ / навигация | `project-contract.md` | Сохранить |
| [project-export-display-name-plan.md](work/project-lifecycle/project-export-display-name-plan.md) | План | `work/project-lifecycle/project-export-display-name-plan.md` | Перенести |
| [project-global-path-and-prefix-plan.md](work/project-lifecycle/project-global-path-and-prefix-plan.md) | План | `work/project-lifecycle/project-global-path-and-prefix-plan.md` | Перенести |
| [project-verification-password-fix-plan.md](work/project-lifecycle/project-verification-password-fix-plan.md) | План | `work/project-lifecycle/project-verification-password-fix-plan.md` | Перенести |
| [qa-react-wails.md](guides/qa-react-wails.md) | Руководство / инструкция QA | `guides/qa-react-wails.md` | Перенести |
| [qa-runtime-promotion.md](guides/qa-runtime-promotion.md) | Руководство / инструкция QA | `guides/qa-runtime-promotion.md` | Перенести |
| [roadmap.md](roadmap.md) | Scope и критерии; исторические checkpoints выделены | `roadmap.md` | Сохранить |
| [runtime-bundle-project-rebind-plan.md](work/runtime-bundle/runtime-bundle-project-rebind-plan.md) | План | `work/runtime-bundle/runtime-bundle-project-rebind-plan.md` | Контекст/evidence разделены |
| [server-information-check-plan.md](work/server-information/server-information-check-plan.md) | План | `work/server-information/server-information-check-plan.md` | Контекст/evidence разделены |
| [service-02a.md](work/services/service-02a.md) | План / контракт / история реализации | `work/services/service-02a.md` | Контекст/evidence разделены |
| [service-docker-rootless-architecture.md](work/docker/service-docker-rootless-architecture.md) | План; контракт и evidence выделены | `work/docker/service-docker-rootless-architecture.md` | Разделён |
| [service-install-01-go-edit-architecture.md](work/services/service-install-01-go-edit-architecture.md) | План / контракт / история реализации | `work/services/service-install-01-go-edit-architecture.md` | Контекст/evidence разделены |
| [service-install-06-postgresql.md](work/postgresql/service-install-06-postgresql.md) | План / контракт / история реализации | `work/postgresql/service-install-06-postgresql.md` | Контекст/evidence разделены |
| [service-install-07-redis-sentinel-architecture.md](work/redis/service-install-07-redis-sentinel-architecture.md) | План / контракт / история реализации | `work/redis/service-install-07-redis-sentinel-architecture.md` | Контекст/evidence разделены |
| [service-install-08-vault-architecture.md](work/vault/service-install-08-vault-architecture.md) | План / контракт / история реализации | `work/vault/service-install-08-vault-architecture.md` | Контекст/evidence разделены |
| [service-install-08a-secret-contracts.md](work/vault/service-install-08a-secret-contracts.md) | План / контракт / история реализации | `work/vault/service-install-08a-secret-contracts.md` | Контракт этапа; сохранён целиком |
| [service-install-08a.md](work/vault/service-install-08a.md) | План / контракт / история реализации | `work/vault/service-install-08a.md` | Контекст/evidence разделены |
| [service-install-08b.md](work/vault/service-install-08b.md) | План / контракт / история реализации | `work/vault/service-install-08b.md` | Контекст/evidence разделены |
| [service-install-08c.md](work/vault/service-install-08c.md) | План / контракт / история реализации | `work/vault/service-install-08c.md` | Контекст/evidence разделены |
| [service-install-08d-review.md](work/vault/reviews/service-install-08d-review.md) | Review | `work/vault/reviews/service-install-08d-review.md` | Перенести |
| [service-install-08d.md](work/vault/service-install-08d.md) | План / контракт / история реализации | `work/vault/service-install-08d.md` | Контекст/evidence разделены |
| [service-install-08e-bootstrap-correction.md](work/vault/service-install-08e-bootstrap-correction.md) | План / контракт / история реализации | `work/vault/service-install-08e-bootstrap-correction.md` | Контекст/evidence разделены |
| [service-install-08e-clear-evidence.md](work/vault/evidence/service-install-08e-clear-evidence.md) | Evidence / журнал / аудит | `work/vault/evidence/service-install-08e-clear-evidence.md` | Перенести |
| [service-install-08e-clear.md](work/vault/service-install-08e-clear.md) | План / контракт / история реализации | `work/vault/service-install-08e-clear.md` | Контекст/evidence разделены |
| [service-install-08e-follower-unseal-fix.md](work/vault/service-install-08e-follower-unseal-fix.md) | План / контракт / история реализации | `work/vault/service-install-08e-follower-unseal-fix.md` | Контекст/evidence разделены |
| [service-install-08e.md](work/vault/service-install-08e.md) | План / контракт / история реализации | `work/vault/service-install-08e.md` | Исторический журнал / аудит; сохранён целиком |
| [service-install-08f-vault-endpoint-ha.md](work/vault/service-install-08f-vault-endpoint-ha.md) | План / контракт / история реализации | `work/vault/service-install-08f-vault-endpoint-ha.md` | Контекст/evidence разделены |
| [service-install-09-clickhouse-architecture.md](work/clickhouse/service-install-09-clickhouse-architecture.md) | План / контракт / история реализации | `work/clickhouse/service-install-09-clickhouse-architecture.md` | Контекст/evidence разделены |
| [service-install-11-cleanup.md](work/services/service-install-11-cleanup.md) | План / контракт / история реализации | `work/services/service-install-11-cleanup.md` | Исторический журнал / аудит; сохранён целиком |
| [service-install-11-test-journal.md](work/services/evidence/service-install-11-test-journal.md) | Evidence / журнал / аудит | `work/services/evidence/service-install-11-test-journal.md` | Перенести |
| [service-install-11-ui-test-cases.md](work/services/service-install-11-ui-test-cases.md) | Критерии и сценарии приёмки | `work/services/service-install-11-ui-test-cases.md` | Перенести |
| [service-install-acceptance.md](work/services/service-install-acceptance.md) | План; условия и evidence выделены | `work/services/service-install-acceptance.md` | Разделён |
| [service-runtime-optimization.md](work/services/service-runtime-optimization.md) | План / контракт / история реализации | `work/services/service-runtime-optimization.md` | Контекст/evidence разделены |
| [service-unit-naming-plan.md](work/service-unit-naming/service-unit-naming-plan.md) | План | `work/service-unit-naming/service-unit-naming-plan.md` | Перенести |
| [session-active-run-credential-plan.md](work/execution/session-active-run-credential-plan.md) | План | `work/execution/session-active-run-credential-plan.md` | Перенести |
| [si08-output-run-delivery-decoupling.md](work/vault/si08-output-run-delivery-decoupling.md) | План / контракт / история реализации | `work/vault/si08-output-run-delivery-decoupling.md` | Контекст/evidence разделены |
| [si11-ansible-role-defaults-plan.md](work/services/si11-ansible-role-defaults-plan.md) | План | `work/services/si11-ansible-role-defaults-plan.md` | Контекст/evidence разделены |
| [si11-s06-inherited-settings-plan.md](work/services/si11-s06-inherited-settings-plan.md) | План | `work/services/si11-s06-inherited-settings-plan.md` | Контекст/evidence разделены |
| [si11-target-host-trust-plan.md](work/services/si11-target-host-trust-plan.md) | План | `work/services/si11-target-host-trust-plan.md` | Перенести |
| [si11-v02-trusted-binding-plan.md](work/services/si11-v02-trusted-binding-plan.md) | План | `work/services/si11-v02-trusted-binding-plan.md` | Контекст/evidence разделены |
| [ui-01.md](work/ui-01/ui-01.md) | План / контракт / история реализации | `work/ui-01/ui-01.md` | Контекст/evidence разделены |
| [ui-01a-contract-freeze.md](work/ui-01/ui-01a-contract-freeze.md) | План / контракт / история реализации | `work/ui-01/ui-01a-contract-freeze.md` | Контекст/evidence разделены |
| [ui-01a-mockup-reconciliation.md](work/ui-01/evidence/ui-01a-mockup-reconciliation.md) | Evidence / журнал / аудит | `work/ui-01/evidence/ui-01a-mockup-reconciliation.md` | Перенести |
| [ui-01a-qa.md](work/ui-01/evidence/ui-01a-qa.md) | Evidence / журнал / аудит | `work/ui-01/evidence/ui-01a-qa.md` | Перенести |
| [ui-01a-review.md](work/ui-01/reviews/ui-01a-review.md) | Review | `work/ui-01/reviews/ui-01a-review.md` | Перенести |
| [ui-01a-toolchain.md](work/ui-01/ui-01a-toolchain.md) | План / контракт / история реализации | `work/ui-01/ui-01a-toolchain.md` | Контекст/evidence разделены |
| [ui-01a.md](work/ui-01/ui-01a.md) | План / контракт / история реализации | `work/ui-01/ui-01a.md` | Контекст/evidence разделены |
| [ui-01b-review.md](work/ui-01/reviews/ui-01b-review.md) | Review | `work/ui-01/reviews/ui-01b-review.md` | Перенести |
| [ui-01b.md](work/ui-01/ui-01b.md) | План / контракт / история реализации | `work/ui-01/ui-01b.md` | Контекст/evidence разделены |
| [ui-01c.md](work/ui-01/ui-01c.md) | План / контракт / история реализации | `work/ui-01/ui-01c.md` | Контекст/evidence разделены |
| [ui-01d-architecture.md](work/ui-01/ui-01d-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01d-architecture.md` | Контекст/evidence разделены |
| [ui-01d.md](work/ui-01/ui-01d.md) | План / контракт / история реализации | `work/ui-01/ui-01d.md` | Контекст/evidence разделены |
| [ui-01e1-architecture.md](work/ui-01/ui-01e1-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e1-architecture.md` | Контекст/evidence разделены |
| [ui-01e2-architecture.md](work/ui-01/ui-01e2-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e2-architecture.md` | Контекст/evidence разделены |
| [ui-01e3-architecture.md](work/ui-01/ui-01e3-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e3-architecture.md` | Контекст/evidence разделены |
| [ui-01e3.md](work/ui-01/ui-01e3.md) | План / контракт / история реализации | `work/ui-01/ui-01e3.md` | Контекст/evidence разделены |
| [ui-01e4-architecture.md](work/ui-01/ui-01e4-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e4-architecture.md` | Контекст/evidence разделены |
| [ui-01e5-architecture.md](work/ui-01/ui-01e5-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e5-architecture.md` | Контекст/evidence разделены |
| [ui-01e6.md](work/ui-01/ui-01e6.md) | План / контракт / история реализации | `work/ui-01/ui-01e6.md` | Контекст/evidence разделены |
| [ui-01f-architecture.md](work/ui-01/ui-01f-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f-architecture.md` | Контекст/evidence разделены |
| [ui-01f1-architecture-review.md](work/ui-01/reviews/ui-01f1-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f1-architecture-review.md` | Перенести |
| [ui-01f1-architecture.md](work/ui-01/ui-01f1-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f1-architecture.md` | Контекст/evidence разделены |
| [ui-01f2-architecture-review.md](work/ui-01/reviews/ui-01f2-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f2-architecture-review.md` | Перенести |
| [ui-01f2-architecture.md](work/ui-01/ui-01f2-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f2-architecture.md` | Контекст/evidence разделены |
| [ui-01f3-architecture-review.md](work/ui-01/reviews/ui-01f3-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f3-architecture-review.md` | Перенести |
| [ui-01f3-architecture.md](work/ui-01/ui-01f3-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f3-architecture.md` | Контекст/evidence разделены |
| [ui-01f4-architecture-review.md](work/ui-01/reviews/ui-01f4-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f4-architecture-review.md` | Перенести |
| [ui-01f4-architecture.md](work/ui-01/ui-01f4-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f4-architecture.md` | Контекст/evidence разделены |
| [ui-01f5-architecture-review.md](work/ui-01/reviews/ui-01f5-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f5-architecture-review.md` | Перенести |
| [ui-01f5-architecture.md](work/ui-01/ui-01f5-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f5-architecture.md` | Контекст/evidence разделены |
| [ui-01f6.md](work/ui-01/ui-01f6.md) | План / контракт / история реализации | `work/ui-01/ui-01f6.md` | Контекст/evidence разделены |
| [ui-01g-architecture.md](work/ui-01/ui-01g-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01g-architecture.md` | Контекст/evidence разделены |
| [ui-01g1.md](work/ui-01/ui-01g1.md) | План / контракт / история реализации | `work/ui-01/ui-01g1.md` | Контекст/evidence разделены |
| [ui-01g2.md](work/ui-01/ui-01g2.md) | План / контракт / история реализации | `work/ui-01/ui-01g2.md` | Контекст/evidence разделены |
| [ui-01g3.md](work/ui-01/ui-01g3.md) | План / контракт / история реализации | `work/ui-01/ui-01g3.md` | Контекст/evidence разделены |
| [ui-01g4.md](work/ui-01/ui-01g4.md) | План / контракт / история реализации | `work/ui-01/ui-01g4.md` | Контекст/evidence разделены |
| [ui-01h-architecture-review.md](work/ui-01/reviews/ui-01h-architecture-review.md) | Review | `work/ui-01/reviews/ui-01h-architecture-review.md` | Перенести |
| [ui-01h-architecture.md](work/ui-01/ui-01h-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01h-architecture.md` | Контекст/evidence разделены |
| [ui-01h1.md](work/ui-01/ui-01h1.md) | План / контракт / история реализации | `work/ui-01/ui-01h1.md` | Контекст/evidence разделены |
| [ui-01h2-architecture.md](work/ui-01/ui-01h2-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01h2-architecture.md` | Контекст/evidence разделены |
| [ui-01h2.md](work/ui-01/ui-01h2.md) | План / контракт / история реализации | `work/ui-01/ui-01h2.md` | Контекст/evidence разделены |
| [ui-01h3-architecture.md](work/ui-01/ui-01h3-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01h3-architecture.md` | Контекст/evidence разделены |
| [ui-01h3.md](work/ui-01/ui-01h3.md) | План / контракт / история реализации | `work/ui-01/ui-01h3.md` | Контекст/evidence разделены |
| [ui-01h4.md](work/ui-01/ui-01h4.md) | План / контракт / история реализации | `work/ui-01/ui-01h4.md` | Контекст/evidence разделены |
| [ui-01i-architecture-review.md](work/ui-01/reviews/ui-01i-architecture-review.md) | Review | `work/ui-01/reviews/ui-01i-architecture-review.md` | Перенести |
| [ui-01i-architecture-targeted-recheck.md](work/ui-01/reviews/ui-01i-architecture-targeted-recheck.md) | Review | `work/ui-01/reviews/ui-01i-architecture-targeted-recheck.md` | Перенести |
| [ui-01i-architecture.md](work/ui-01/ui-01i-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01i-architecture.md` | Контекст/evidence разделены |
| [ui-01i.md](work/ui-01/ui-01i.md) | План / контракт / история реализации | `work/ui-01/ui-01i.md` | Контекст/evidence разделены |
| [ui-01j.md](work/ui-01/ui-01j.md) | План / контракт / история реализации | `work/ui-01/ui-01j.md` | Контекст/evidence разделены |
| [ui-02-architecture.md](work/ui-02/ui-02-architecture.md) | План / контракт / история реализации | `work/ui-02/ui-02-architecture.md` | Контекст/evidence разделены |
| [ui-02a.md](work/ui-02/ui-02a.md) | План / контракт / история реализации | `work/ui-02/ui-02a.md` | Контекст/evidence разделены |
| [ui-02b.md](work/ui-02/ui-02b.md) | План / контракт / история реализации | `work/ui-02/ui-02b.md` | Контекст/evidence разделены |
| [ui-02c.md](work/ui-02/ui-02c.md) | План / контракт / история реализации | `work/ui-02/ui-02c.md` | Контекст/evidence разделены |
| [ui-02d.md](work/ui-02/ui-02d.md) | План / контракт / история реализации | `work/ui-02/ui-02d.md` | Контекст/evidence разделены |
| [ui-02e-pki-runtime-secret-transport.md](work/ui-02/ui-02e-pki-runtime-secret-transport.md) | План / контракт / история реализации | `work/ui-02/ui-02e-pki-runtime-secret-transport.md` | Контекст/evidence разделены |
| [ui-02f-runtime-service-secret-transport.md](work/ui-02/ui-02f-runtime-service-secret-transport.md) | План / контракт / история реализации | `work/ui-02/ui-02f-runtime-service-secret-transport.md` | Контекст/evidence разделены |
| [ui-be-01.md](work/ui-backend/ui-be-01.md) | План / контракт / история реализации | `work/ui-backend/ui-be-01.md` | Контекст/evidence разделены |
| [ui-be-02.md](work/ui-backend/ui-be-02.md) | План / контракт / история реализации | `work/ui-backend/ui-be-02.md` | Контекст/evidence разделены |
| [ui-be-03.md](work/ui-backend/ui-be-03.md) | План / контракт / история реализации | `work/ui-backend/ui-be-03.md` | Контекст/evidence разделены |
| [ui-be-04.md](work/ui-backend/ui-be-04.md) | План; контракт и audit выделены | `work/ui-backend/ui-be-04.md` | Разделён |
| [ui-design-01-mockups.html](design/ui-design-01-mockups.html) | UI-дизайн / предложение | `design/ui-design-01-mockups.html` | Перенести |
| [ui-design-01.md](design/ui-design-01.md) | UI-дизайн / предложение | `design/ui-design-01.md` | Перенести |
| [ui-logs-01-plan.md](work/ui-lifecycle/ui-logs-01-plan.md) | План | `work/ui-lifecycle/ui-logs-01-plan.md` | Контекст/evidence разделены |
| [ui-net-01-architecture.md](work/ui-network/ui-net-01-architecture.md) | План / контракт / история реализации | `work/ui-network/ui-net-01-architecture.md` | Контекст/evidence разделены |
| [ui-net-01.md](work/ui-network/ui-net-01.md) | План / контракт / история реализации | `work/ui-network/ui-net-01.md` | Контекст/evidence разделены |
| [ui-project-creation-design.md](design/ui-project-creation-design.md) | UI-дизайн / предложение | `design/ui-project-creation-design.md` | Перенести |
| [ui-save-verify-architecture.md](work/ui-lifecycle/ui-save-verify-architecture.md) | План / контракт / история реализации | `work/ui-lifecycle/ui-save-verify-architecture.md` | Контекст/evidence разделены |
| [ui-ux-01-proposals.md](design/ui-ux-01-proposals.md) | UI-дизайн / предложение | `design/ui-ux-01-proposals.md` | Перенести |
| [v1-reference-audit.md](work/development/v1-reference-audit.md) | План / контракт / история реализации | `work/development/v1-reference-audit.md` | Исторический журнал / аудит; сохранён целиком |

## Execution, PKI и сервисы: исторические checkpoints — 2026-10-12

В 22 документах отделены 13 разделов результатов проверок и 14 явно
обозначенных статусных записей. Исходные заголовки и якоря сохранены;
нормативные разделы, решения владельца, scope и acceptance criteria остаются
в исходных планах. Результаты собраны в `evidence` семи тем:
execution, PKI, PostgreSQL, Vault, Redis, ClickHouse и общая установка сервисов.

Добавлена навигация по execution, PKI и Vault. Смешанные разделы с решениями
владельца и требованиями не перенесены целиком; полный журнал SI08-E
сохранён и обозначен как исторический журнал в навигации Vault.
Завершённый SI11 остаётся в общей теме установки сервисов.

Проверены 1385 локальных ссылок и якорей: ошибок нет. Все 27 новых
фрагментов и 167 ранее выделенных фрагментов сохранены. Обратное
восстановление 22 исходных документов подтвердило отсутствие изменений
в оставшихся требованиях; 251 прочий документ совпадает со снимком.
`git diff --check` проходит. Локальные proof-материалы находятся в
`.runtime/qa/documentation-services-execution-20261012/`. Продуктовый код,
runtime bundle и targets не изменялись.

## Остаточный разбор и уточнение карты — 2026-10-12

В browser, runtime bundle, SSH auth, execution order, endpoint placement,
UI lifecycle/network, server information и development обработаны 13 документов:
отделены 20 фрагментов checkpoint/evidence. Дополнительно в пяти документах
сети и UI-01D отделены пять фрагментов. Старые якоря DONE-подэтапов сохранены.

DEV-only HTTP browser остаётся явной security boundary; статусная метка
заменена на описание ограничения без изменения текста. Исходный Endpoint
draft явно обозначен как исторический scope обсуждения; узкий план остаётся
точкой входа. Черновик сохранён для прослеживаемости владельческих решений.
Ограничение общего Start при rebind, правила dependency ordering и условие
QA NetworkManager fallback сохранены в исходных документах.

Уточнена классификация исходных контрактов без отдельного статусного раздела,
предложений libraries со scope-index и цельных журналов. Отметка о сохранении
контракта не является проверкой соответствия текущему коду.

### Остаточные пункты на момент предыдущего пакета

- Смешанные исторические/нормативные разделы DEVX-01, SI08-A, Vault clear,
  service runtime optimization, UI-BE-03 и Save/Verify: извлечение возможно
  только после точной сверки повторяемых правил с каноническими документами.
- Различия между контрактами отдельных версий и каноническими документами:
  не унифицировать автоматически DTO, security boundaries или owner decisions.
- Open questions и ADR: возраст записи не доказывает её закрытие.

Физическая организация и маршруты чтения готовы. Остаточные пункты относятся
к актуализации содержания; они не препятствуют использованию новой структуры.
Содержательные пакеты после `85d4567` фиксируются отдельным коммитом
реорганизации. Предшествовавшие правки текущих статусов и журнала сохраняются
в рабочей копии отдельно.

Итоговая проверка: 1467 локальных ссылок и якорей без ошибок;
сохранены все 219 выделенных фрагментов. Для двух последних пакетов
проверено обратное восстановление 13 и пяти исходных документов,
не затрагивая оставшиеся требования. `git diff --check` проходит.

При проверке индекса Git нормализованы пустые строки в конце 29 новых
Markdown-файлов и конечные пробелы в перенесённых исторических строках.
Markdown hard breaks сохранены обратной косой чертой. Исходные фрагменты
сохранены в локальных proof-снимках; итоговая проверка всех 219 фрагментов
учитывает только эти изменения форматирования.

## Завершение разбора смешанных разделов — 2026-10-12

В DEVX-01, SI08-A, Vault clear, service runtime optimization, UI-BE-03
и Save/Verify исторические результаты отделены от оставшихся ограничений.
Исходные правила mount-защиты, protocol attestation, no-target-contact,
nonroot QA identity, рамки SI08-A и лицензирования остаются в исходных
документах. Review verdicts, digest и результаты QA сохранены без замены
в существующих тематических файлах evidence.

Повторяемые owner decisions в [open questions](open-questions.md) заменены
на навигацию к ADR-011/012/013/014/018/019. Полный исходный текст сохранён в
[снимке](history/owner-decisions-20261012.md). Deferred signature вопрос явно
ограничен исходными Core milestones; актуальная trust boundary выбирается
по последующим ADR и процедуре bundle, без объявления вопроса закрытым.

### Итог и граница выполненного

Реорганизация документации завершена: файлы разнесены по назначению,
маршруты чтения доступны, контракты отделены от исторических статусов и
результатов там, где это не разрывает их исходную границу. Цельные журналы
и аудиты явно обозначены; каждый файл первоначального снимка учтён.
В карте больше нет необработанных отметок «Проверить содержание».

Дальнейшая актуализация старых DTO/контрактов по коду, проверка полноты
текущих ADR и переоценка открытых product-policy вопросов — самостоятельные
задачи, а не незавершённый перенос документации. Старые версии контрактов
не объявлены автоматически действующей спецификацией. Код продукта,
Core, bundle и целевые хосты этим разбором не изменялись.

Проверка завершения: 1511 локальных ссылок и якорей без ошибок;
сохранены 230 выделенных фрагментов, включая 11 новых. Обратное
восстановление семи документов подтверждает учтённые изменения;
242 прочих файла совпадают со снимком. Предыдущие evidence сохраняются
без изменений; новые записи добавлены в существующие тематические файлы.
`git diff --check` проходит. Proof-материалы:
`.runtime/qa/documentation-mixed-20261012/`.

## Сверка маршрута Save / Verify с backend — 2026-10-12

ADR-027 и owner-change документ сверены с текущим backend без выполнения
Core или установки. `ReviewStructuralEditSession` использует
`ReviewStructural` → `PlanStructuralSave` и хранит план с `LocalOnly`;
`CommitStructuralEditPlan` использует guarded transaction, а её local-only
ветка завершается до Core snapshot. `VerifyProject` отдельно читает сохранённую
ревизию и проверяет runtime evidence; fresh installation plan проверяется
по project/runtime binding. Старый desktop `CommitEditPlan` возвращает
`EDIT_CONTRACT_SUPERSEDED`.

Уточнены точки входа в docs README, contracts README, agent-index и темах UI:
для нового Save сначала читать ADR-027/owner-change, а UI-BE-03 и раннюю
UI-01D архитектуру — в их исходном writer/compatibility scope. Исходные
нормативные разделы не переписаны; новые DTO, правила и статусы не вводились.

Точки проверки: [desktop App](../internal/desktop/app.go),
[local Save](../internal/installer/local_save.go),
[edit session](../internal/installer/session.go),
[transaction](../internal/installer/transaction.go),
[installation plan](../internal/desktop/installation_plan.go) и
[Start](../internal/desktop/installation_execution.go). Это сверка исходников
и маршрутов документации, не новая UI/Core acceptance или независимый review.

Проверка пакета: 1527 локальных ссылок и якорей без ошибок; все 230
выделенных фрагментов сохранены. Нормативные разделы UI-BE-03 совпадают
с предыдущей версией; добавлена только scope-пометка. `git diff --check`
проходит. Proof-снимки: `.runtime/qa/documentation-current-save-20261012/`.

## Сверка версий execution-контрактов — 2026-10-12

В [таблицу схем](../contracts/README.md) добавлены существующие, ранее
пропущенные `plan/v1alpha3` и `execution-capabilities/v1alpha5/v1alpha6`.
В [execution contract](contracts/execution-planning-and-events.md) добавлено
различие между исходным планом эволюции v1alpha1 и стандартным Core output
v1alpha2, отдельным selected-source schema v1alpha3 и credentialed Start v1alpha2.
Схема не объявлена доказательством активного runtime или полной приёмки flow.

Проверены исходники [Core planner](../ansible-core/collections/ansible_collections/platform/core/plugins/module_utils/deployment_plan.py),
[fixed protocol](../ansible-core/tools/execution_protocol.py),
[Go ExecutionService](../internal/executionnode/execution_service.go) и
[credentialed Start](../internal/executionnode/credential_lease.go).
Approve требует EXECUTABLE и точных acknowledgements; Start проверяет approval,
TTL и consumed state. В документации сохранены исходные normative sections,
JSON schemas и production code не изменены. Это source/schema сверка,
не real UI/Core acceptance и не независимый architecture review.

Проверка: 1540 локальных ссылок/якорей без ошибок, 45 путей опубликованных
схем существуют и содержат корректный JSON; 230 выделенных фрагментов
сохранены. Исходные execution sections не изменены; `git diff --check`
проходит. Proof-снимки: `.runtime/qa/documentation-execution-versions-20261012/`.
