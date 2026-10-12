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
Разделение смешанных документов и устранение содержательных дублей ещё не выполнено.
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

## Случаи для отдельного разбора

| Материал | Что проверить до разделения или архивирования |
| --- | --- |
| [UI-BE-04](work/ui-backend/ui-be-04.md) | Ownership, протокол, fingerprint и lifecycle отделить от implementation audit и submilestone gates; сохранить ссылки на конкретные разделы |
| [Docker rootless](work/docker/service-docker-rootless-architecture.md) | Runtime/network/service contract отделить от SI10 acceptance evidence |
| [Service install acceptance](work/services/service-install-acceptance.md) | Общие правила приёмки отделить от датированных результатов отдельных сервисов |
| [Application server types](work/application-config/application-config-server-types.md) | Planned contract, текущие правила и implementation/verification различить по подтверждённой версии |
| [Application libraries](work/application-libraries/README.md) | Предложения будущих этапов отделять от реализованных контрактов подэтапов; актуальность проверять по текущему состоянию |
| [Roadmap](roadmap.md) | Сохранить последовательность и критерии этапов; дубли текущих статусов и подробные runs заменить ссылками после сверки |
| [Owner decisions](open-questions.md) | Разрешённые решения сверить с ADR; открытые вопросы не переносить в историю только по возрасту |
| [Endpoint draft](work/endpoint-placement/endpoint-haproxy-placement-draft.md) | Сопоставить draft, plan и ADR-033; перенос в историю допустим после подтверждения замены |
| `core-*`, `net-*`, `ui-*`, `service-install-*` | Наличие milestone в имени не доказывает устаревание контракта; проверить нормативные разделы перед архивированием |

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
Core, bundle и целевые хосты не изменялись. Коммит не создавался.

Следующий проход — содержательный разбор смешанных документов и дублей из
таблицы выше. Наличие выполненного переноса не означает завершение этого разбора.

## Полная карта файлов исходного снимка

Имена в первом столбце сохраняют исходный путь снимка; ссылки ведут к файлам
после переноса. Третий столбец содержит фактический путь относительно `docs`.
`Сохранить` — прежний путь сохранён. `Перенести` — группировка выполнена.
`Проверить содержание` — документ также перенесён целиком, но контракт и историю
нужно проверить перед разделением; архивирование этой отметкой не разрешается.

| Исходный файл (ссылка на текущий путь) | Назначение | Текущий путь (относительно docs) | Классификация первого прохода |
| --- | --- | --- | --- |
| [agent-context-maintenance.md](agent-context-maintenance.md) | Канонический документ / навигация | `agent-context-maintenance.md` | Сохранить |
| [agent-index.md](agent-index.md) | Канонический документ / навигация | `agent-index.md` | Сохранить |
| [agent-procedures/qa.md](agent-procedures/qa.md) | Обязательная процедура | `agent-procedures/qa.md` | Сохранить |
| [agent-procedures/review.md](agent-procedures/review.md) | Обязательная процедура | `agent-procedures/review.md` | Сохранить |
| [agent-procedures/runtime-bundle.md](agent-procedures/runtime-bundle.md) | Обязательная процедура | `agent-procedures/runtime-bundle.md` | Сохранить |
| [agent-procedures/si11.md](agent-procedures/si11.md) | Обязательная процедура | `agent-procedures/si11.md` | Сохранить |
| [ansible-core.md](ansible-core.md) | Канонический документ / навигация | `ansible-core.md` | Сохранить |
| [ansible-playbooks/README.md](guides/ansible-playbooks/README.md) | Руководство | `guides/ansible-playbooks/README.md` | Перенести |
| [application-config-server-types.md](work/application-config/application-config-server-types.md) | План / контракт / история реализации | `work/application-config/application-config-server-types.md` | Проверить содержание |
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
| [application-libraries/architecture.md](work/application-libraries/architecture.md) | План / контракт / история реализации | `work/application-libraries/architecture.md` | Проверить содержание |
| [application-libraries/configuration.md](work/application-libraries/configuration.md) | План / контракт / история реализации | `work/application-libraries/configuration.md` | Проверить содержание |
| [application-libraries/execution.md](work/application-libraries/execution.md) | План / контракт / история реализации | `work/application-libraries/execution.md` | Проверить содержание |
| [application-libraries/implementation-plan.md](work/application-libraries/implementation-plan.md) | План | `work/application-libraries/implementation-plan.md` | Перенести |
| [application-libraries/lightweight-verify-test-journal.md](work/application-libraries/milestones/lightweight-verify/evidence/lightweight-verify-test-journal.md) | Evidence / журнал / аудит | `work/application-libraries/milestones/lightweight-verify/evidence/lightweight-verify-test-journal.md` | Перенести |
| [application-libraries/plan-review.md](work/application-libraries/reviews/plan-review.md) | Review | `work/application-libraries/reviews/plan-review.md` | Перенести |
| [application-libraries/README.md](work/application-libraries/README.md) | Тематическая навигация | `work/application-libraries/README.md` | Перенести |
| [application-libraries/secrets.md](work/application-libraries/secrets.md) | План / контракт / история реализации | `work/application-libraries/secrets.md` | Проверить содержание |
| [application-libraries/ui.md](work/application-libraries/ui.md) | План / контракт / история реализации | `work/application-libraries/ui.md` | Проверить содержание |
| [architecture-decisions.md](architecture-decisions.md) | Канонический документ / навигация | `architecture-decisions.md` | Сохранить |
| [architecture.md](architecture.md) | Канонический документ / навигация | `architecture.md` | Сохранить |
| [backend-and-ui.md](backend-and-ui.md) | Канонический документ / навигация | `backend-and-ui.md` | Сохранить |
| [browser-mode-local-plan.md](work/browser/browser-mode-local-plan.md) | План | `work/browser/browser-mode-local-plan.md` | Перенести |
| [browser-mode-remote-plan.md](work/browser/browser-mode-remote-plan.md) | План | `work/browser/browser-mode-remote-plan.md` | Перенести |
| [core-01.md](work/core/core-01.md) | План / контракт / история реализации | `work/core/core-01.md` | Проверить содержание |
| [core-03.md](work/core/core-03.md) | План / контракт / история реализации | `work/core/core-03.md` | Проверить содержание |
| [core-04.md](work/core/core-04.md) | План / контракт / история реализации | `work/core/core-04.md` | Проверить содержание |
| [core-05.md](work/core/core-05.md) | План / контракт / история реализации | `work/core/core-05.md` | Проверить содержание |
| [core-06.md](work/core/core-06.md) | План / контракт / история реализации | `work/core/core-06.md` | Проверить содержание |
| [core-07.md](work/core/core-07.md) | План / контракт / история реализации | `work/core/core-07.md` | Проверить содержание |
| [core-07a.md](work/core/core-07a.md) | План / контракт / история реализации | `work/core/core-07a.md` | Проверить содержание |
| [devx-01.md](work/development/devx-01.md) | План / контракт / история реализации | `work/development/devx-01.md` | Проверить содержание |
| [endpoint-haproxy-placement-draft.md](work/endpoint-placement/endpoint-haproxy-placement-draft.md) | Предложение; проверить замену | `work/endpoint-placement/endpoint-haproxy-placement-draft.md` | Проверить содержание |
| [endpoint-haproxy-placement-plan-review.md](work/endpoint-placement/reviews/endpoint-haproxy-placement-plan-review.md) | Review | `work/endpoint-placement/reviews/endpoint-haproxy-placement-plan-review.md` | Перенести |
| [endpoint-haproxy-placement-plan.md](work/endpoint-placement/endpoint-haproxy-placement-plan.md) | План | `work/endpoint-placement/endpoint-haproxy-placement-plan.md` | Перенести |
| [exec-01a-source-audit.md](work/execution/evidence/exec-01a-source-audit.md) | Evidence / журнал / аудит | `work/execution/evidence/exec-01a-source-audit.md` | Перенести |
| [exec-01a.md](work/execution/exec-01a.md) | План / контракт / история реализации | `work/execution/exec-01a.md` | Проверить содержание |
| [exec-generated-state.md](work/execution/exec-generated-state.md) | План / контракт / история реализации | `work/execution/exec-generated-state.md` | Проверить содержание |
| [exec-obs-01.md](work/execution/exec-obs-01.md) | План / контракт / история реализации | `work/execution/exec-obs-01.md` | Проверить содержание |
| [execution-failure-diagnostics.md](guides/execution-failure-diagnostics.md) | Руководство / инструкция QA | `guides/execution-failure-diagnostics.md` | Перенести |
| [execution-node-password-auth-plan.md](work/execution-node-password-auth/execution-node-password-auth-plan.md) | План | `work/execution-node-password-auth/execution-node-password-auth-plan.md` | Перенести |
| [execution-node-password-auth-review.md](work/execution-node-password-auth/reviews/execution-node-password-auth-review.md) | Review | `work/execution-node-password-auth/reviews/execution-node-password-auth-review.md` | Перенести |
| [execution-order-01-plan.md](work/execution-order/execution-order-01-plan.md) | План | `work/execution-order/execution-order-01-plan.md` | Перенести |
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
| [net-01.md](work/network/net-01.md) | План / контракт / история реализации | `work/network/net-01.md` | Проверить содержание |
| [net-02.md](work/network/net-02.md) | План / контракт / история реализации | `work/network/net-02.md` | Проверить содержание |
| [net-03-1.md](work/network/net-03-1.md) | План / контракт / история реализации | `work/network/net-03-1.md` | Проверить содержание |
| [net-03.md](work/network/net-03.md) | План / контракт / история реализации | `work/network/net-03.md` | Проверить содержание |
| [net-04-1.md](work/network/net-04-1.md) | План / контракт / история реализации | `work/network/net-04-1.md` | Проверить содержание |
| [net-04-2.md](work/network/net-04-2.md) | План / контракт / история реализации | `work/network/net-04-2.md` | Проверить содержание |
| [net-04.md](work/network/net-04.md) | План / контракт / история реализации | `work/network/net-04.md` | Проверить содержание |
| [open-questions.md](open-questions.md) | Канонический документ / навигация | `open-questions.md` | Сохранить |
| [pki-01.md](work/pki/pki-01.md) | План / контракт / история реализации | `work/pki/pki-01.md` | Проверить содержание |
| [pki-platform-shared-tls-usages-plan.md](work/pki/pki-platform-shared-tls-usages-plan.md) | План | `work/pki/pki-platform-shared-tls-usages-plan.md` | Перенести |
| [pki-service-scope-optimization-plan.md](work/pki/pki-service-scope-optimization-plan.md) | План | `work/pki/pki-service-scope-optimization-plan.md` | Перенести |
| [pki-single-pass-review.md](work/pki/reviews/pki-single-pass-review.md) | Review | `work/pki/reviews/pki-single-pass-review.md` | Перенести |
| [pki-single-pass.md](work/pki/pki-single-pass.md) | План / контракт / история реализации | `work/pki/pki-single-pass.md` | Проверить содержание |
| [pki-store-password-recovery-01.md](work/pki/pki-store-password-recovery-01.md) | План / контракт / история реализации | `work/pki/pki-store-password-recovery-01.md` | Проверить содержание |
| [postgres-01.md](work/postgresql/postgres-01.md) | План / контракт / история реализации | `work/postgresql/postgres-01.md` | Проверить содержание |
| [project-contract.md](project-contract.md) | Канонический документ / навигация | `project-contract.md` | Сохранить |
| [project-export-display-name-plan.md](work/project-lifecycle/project-export-display-name-plan.md) | План | `work/project-lifecycle/project-export-display-name-plan.md` | Перенести |
| [project-global-path-and-prefix-plan.md](work/project-lifecycle/project-global-path-and-prefix-plan.md) | План | `work/project-lifecycle/project-global-path-and-prefix-plan.md` | Перенести |
| [project-verification-password-fix-plan.md](work/project-lifecycle/project-verification-password-fix-plan.md) | План | `work/project-lifecycle/project-verification-password-fix-plan.md` | Перенести |
| [qa-react-wails.md](guides/qa-react-wails.md) | Руководство / инструкция QA | `guides/qa-react-wails.md` | Перенести |
| [qa-runtime-promotion.md](guides/qa-runtime-promotion.md) | Руководство / инструкция QA | `guides/qa-runtime-promotion.md` | Перенести |
| [roadmap.md](roadmap.md) | Канонический документ / навигация | `roadmap.md` | Сохранить |
| [runtime-bundle-project-rebind-plan.md](work/runtime-bundle/runtime-bundle-project-rebind-plan.md) | План | `work/runtime-bundle/runtime-bundle-project-rebind-plan.md` | Перенести |
| [server-information-check-plan.md](work/server-information/server-information-check-plan.md) | План | `work/server-information/server-information-check-plan.md` | Перенести |
| [service-02a.md](work/services/service-02a.md) | План / контракт / история реализации | `work/services/service-02a.md` | Проверить содержание |
| [service-docker-rootless-architecture.md](work/docker/service-docker-rootless-architecture.md) | План / контракт / история реализации | `work/docker/service-docker-rootless-architecture.md` | Проверить содержание |
| [service-install-01-go-edit-architecture.md](work/services/service-install-01-go-edit-architecture.md) | План / контракт / история реализации | `work/services/service-install-01-go-edit-architecture.md` | Проверить содержание |
| [service-install-06-postgresql.md](work/postgresql/service-install-06-postgresql.md) | План / контракт / история реализации | `work/postgresql/service-install-06-postgresql.md` | Проверить содержание |
| [service-install-07-redis-sentinel-architecture.md](work/redis/service-install-07-redis-sentinel-architecture.md) | План / контракт / история реализации | `work/redis/service-install-07-redis-sentinel-architecture.md` | Проверить содержание |
| [service-install-08-vault-architecture.md](work/vault/service-install-08-vault-architecture.md) | План / контракт / история реализации | `work/vault/service-install-08-vault-architecture.md` | Проверить содержание |
| [service-install-08a-secret-contracts.md](work/vault/service-install-08a-secret-contracts.md) | План / контракт / история реализации | `work/vault/service-install-08a-secret-contracts.md` | Проверить содержание |
| [service-install-08a.md](work/vault/service-install-08a.md) | План / контракт / история реализации | `work/vault/service-install-08a.md` | Проверить содержание |
| [service-install-08b.md](work/vault/service-install-08b.md) | План / контракт / история реализации | `work/vault/service-install-08b.md` | Проверить содержание |
| [service-install-08c.md](work/vault/service-install-08c.md) | План / контракт / история реализации | `work/vault/service-install-08c.md` | Проверить содержание |
| [service-install-08d-review.md](work/vault/reviews/service-install-08d-review.md) | Review | `work/vault/reviews/service-install-08d-review.md` | Перенести |
| [service-install-08d.md](work/vault/service-install-08d.md) | План / контракт / история реализации | `work/vault/service-install-08d.md` | Проверить содержание |
| [service-install-08e-bootstrap-correction.md](work/vault/service-install-08e-bootstrap-correction.md) | План / контракт / история реализации | `work/vault/service-install-08e-bootstrap-correction.md` | Проверить содержание |
| [service-install-08e-clear-evidence.md](work/vault/evidence/service-install-08e-clear-evidence.md) | Evidence / журнал / аудит | `work/vault/evidence/service-install-08e-clear-evidence.md` | Перенести |
| [service-install-08e-clear.md](work/vault/service-install-08e-clear.md) | План / контракт / история реализации | `work/vault/service-install-08e-clear.md` | Проверить содержание |
| [service-install-08e-follower-unseal-fix.md](work/vault/service-install-08e-follower-unseal-fix.md) | План / контракт / история реализации | `work/vault/service-install-08e-follower-unseal-fix.md` | Проверить содержание |
| [service-install-08e.md](work/vault/service-install-08e.md) | План / контракт / история реализации | `work/vault/service-install-08e.md` | Проверить содержание |
| [service-install-08f-vault-endpoint-ha.md](work/vault/service-install-08f-vault-endpoint-ha.md) | План / контракт / история реализации | `work/vault/service-install-08f-vault-endpoint-ha.md` | Проверить содержание |
| [service-install-09-clickhouse-architecture.md](work/clickhouse/service-install-09-clickhouse-architecture.md) | План / контракт / история реализации | `work/clickhouse/service-install-09-clickhouse-architecture.md` | Проверить содержание |
| [service-install-11-cleanup.md](work/service-install-11/service-install-11-cleanup.md) | План / контракт / история реализации | `work/service-install-11/service-install-11-cleanup.md` | Проверить содержание |
| [service-install-11-test-journal.md](work/service-install-11/evidence/service-install-11-test-journal.md) | Evidence / журнал / аудит | `work/service-install-11/evidence/service-install-11-test-journal.md` | Перенести |
| [service-install-11-ui-test-cases.md](work/service-install-11/service-install-11-ui-test-cases.md) | Критерии и сценарии приёмки | `work/service-install-11/service-install-11-ui-test-cases.md` | Перенести |
| [service-install-acceptance.md](work/services/service-install-acceptance.md) | План / контракт / история реализации | `work/services/service-install-acceptance.md` | Проверить содержание |
| [service-runtime-optimization.md](work/services/service-runtime-optimization.md) | План / контракт / история реализации | `work/services/service-runtime-optimization.md` | Проверить содержание |
| [service-unit-naming-plan.md](work/service-unit-naming/service-unit-naming-plan.md) | План | `work/service-unit-naming/service-unit-naming-plan.md` | Перенести |
| [session-active-run-credential-plan.md](work/execution/session-active-run-credential-plan.md) | План | `work/execution/session-active-run-credential-plan.md` | Перенести |
| [si08-output-run-delivery-decoupling.md](work/vault/si08-output-run-delivery-decoupling.md) | План / контракт / история реализации | `work/vault/si08-output-run-delivery-decoupling.md` | Проверить содержание |
| [si11-ansible-role-defaults-plan.md](work/service-install-11/si11-ansible-role-defaults-plan.md) | План | `work/service-install-11/si11-ansible-role-defaults-plan.md` | Перенести |
| [si11-s06-inherited-settings-plan.md](work/service-install-11/si11-s06-inherited-settings-plan.md) | План | `work/service-install-11/si11-s06-inherited-settings-plan.md` | Перенести |
| [si11-target-host-trust-plan.md](work/service-install-11/si11-target-host-trust-plan.md) | План | `work/service-install-11/si11-target-host-trust-plan.md` | Перенести |
| [si11-v02-trusted-binding-plan.md](work/service-install-11/si11-v02-trusted-binding-plan.md) | План | `work/service-install-11/si11-v02-trusted-binding-plan.md` | Перенести |
| [ui-01.md](work/ui-01/ui-01.md) | План / контракт / история реализации | `work/ui-01/ui-01.md` | Проверить содержание |
| [ui-01a-contract-freeze.md](work/ui-01/ui-01a-contract-freeze.md) | План / контракт / история реализации | `work/ui-01/ui-01a-contract-freeze.md` | Проверить содержание |
| [ui-01a-mockup-reconciliation.md](work/ui-01/evidence/ui-01a-mockup-reconciliation.md) | Evidence / журнал / аудит | `work/ui-01/evidence/ui-01a-mockup-reconciliation.md` | Перенести |
| [ui-01a-qa.md](work/ui-01/evidence/ui-01a-qa.md) | Evidence / журнал / аудит | `work/ui-01/evidence/ui-01a-qa.md` | Перенести |
| [ui-01a-review.md](work/ui-01/reviews/ui-01a-review.md) | Review | `work/ui-01/reviews/ui-01a-review.md` | Перенести |
| [ui-01a-toolchain.md](work/ui-01/ui-01a-toolchain.md) | План / контракт / история реализации | `work/ui-01/ui-01a-toolchain.md` | Проверить содержание |
| [ui-01a.md](work/ui-01/ui-01a.md) | План / контракт / история реализации | `work/ui-01/ui-01a.md` | Проверить содержание |
| [ui-01b-review.md](work/ui-01/reviews/ui-01b-review.md) | Review | `work/ui-01/reviews/ui-01b-review.md` | Перенести |
| [ui-01b.md](work/ui-01/ui-01b.md) | План / контракт / история реализации | `work/ui-01/ui-01b.md` | Проверить содержание |
| [ui-01c.md](work/ui-01/ui-01c.md) | План / контракт / история реализации | `work/ui-01/ui-01c.md` | Проверить содержание |
| [ui-01d-architecture.md](work/ui-01/ui-01d-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01d-architecture.md` | Проверить содержание |
| [ui-01d.md](work/ui-01/ui-01d.md) | План / контракт / история реализации | `work/ui-01/ui-01d.md` | Проверить содержание |
| [ui-01e1-architecture.md](work/ui-01/ui-01e1-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e1-architecture.md` | Проверить содержание |
| [ui-01e2-architecture.md](work/ui-01/ui-01e2-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e2-architecture.md` | Проверить содержание |
| [ui-01e3-architecture.md](work/ui-01/ui-01e3-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e3-architecture.md` | Проверить содержание |
| [ui-01e3.md](work/ui-01/ui-01e3.md) | План / контракт / история реализации | `work/ui-01/ui-01e3.md` | Проверить содержание |
| [ui-01e4-architecture.md](work/ui-01/ui-01e4-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e4-architecture.md` | Проверить содержание |
| [ui-01e5-architecture.md](work/ui-01/ui-01e5-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01e5-architecture.md` | Проверить содержание |
| [ui-01e6.md](work/ui-01/ui-01e6.md) | План / контракт / история реализации | `work/ui-01/ui-01e6.md` | Проверить содержание |
| [ui-01f-architecture.md](work/ui-01/ui-01f-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f-architecture.md` | Проверить содержание |
| [ui-01f1-architecture-review.md](work/ui-01/reviews/ui-01f1-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f1-architecture-review.md` | Перенести |
| [ui-01f1-architecture.md](work/ui-01/ui-01f1-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f1-architecture.md` | Проверить содержание |
| [ui-01f2-architecture-review.md](work/ui-01/reviews/ui-01f2-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f2-architecture-review.md` | Перенести |
| [ui-01f2-architecture.md](work/ui-01/ui-01f2-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f2-architecture.md` | Проверить содержание |
| [ui-01f3-architecture-review.md](work/ui-01/reviews/ui-01f3-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f3-architecture-review.md` | Перенести |
| [ui-01f3-architecture.md](work/ui-01/ui-01f3-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f3-architecture.md` | Проверить содержание |
| [ui-01f4-architecture-review.md](work/ui-01/reviews/ui-01f4-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f4-architecture-review.md` | Перенести |
| [ui-01f4-architecture.md](work/ui-01/ui-01f4-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f4-architecture.md` | Проверить содержание |
| [ui-01f5-architecture-review.md](work/ui-01/reviews/ui-01f5-architecture-review.md) | Review | `work/ui-01/reviews/ui-01f5-architecture-review.md` | Перенести |
| [ui-01f5-architecture.md](work/ui-01/ui-01f5-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01f5-architecture.md` | Проверить содержание |
| [ui-01f6.md](work/ui-01/ui-01f6.md) | План / контракт / история реализации | `work/ui-01/ui-01f6.md` | Проверить содержание |
| [ui-01g-architecture.md](work/ui-01/ui-01g-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01g-architecture.md` | Проверить содержание |
| [ui-01g1.md](work/ui-01/ui-01g1.md) | План / контракт / история реализации | `work/ui-01/ui-01g1.md` | Проверить содержание |
| [ui-01g2.md](work/ui-01/ui-01g2.md) | План / контракт / история реализации | `work/ui-01/ui-01g2.md` | Проверить содержание |
| [ui-01g3.md](work/ui-01/ui-01g3.md) | План / контракт / история реализации | `work/ui-01/ui-01g3.md` | Проверить содержание |
| [ui-01g4.md](work/ui-01/ui-01g4.md) | План / контракт / история реализации | `work/ui-01/ui-01g4.md` | Проверить содержание |
| [ui-01h-architecture-review.md](work/ui-01/reviews/ui-01h-architecture-review.md) | Review | `work/ui-01/reviews/ui-01h-architecture-review.md` | Перенести |
| [ui-01h-architecture.md](work/ui-01/ui-01h-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01h-architecture.md` | Проверить содержание |
| [ui-01h1.md](work/ui-01/ui-01h1.md) | План / контракт / история реализации | `work/ui-01/ui-01h1.md` | Проверить содержание |
| [ui-01h2-architecture.md](work/ui-01/ui-01h2-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01h2-architecture.md` | Проверить содержание |
| [ui-01h2.md](work/ui-01/ui-01h2.md) | План / контракт / история реализации | `work/ui-01/ui-01h2.md` | Проверить содержание |
| [ui-01h3-architecture.md](work/ui-01/ui-01h3-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01h3-architecture.md` | Проверить содержание |
| [ui-01h3.md](work/ui-01/ui-01h3.md) | План / контракт / история реализации | `work/ui-01/ui-01h3.md` | Проверить содержание |
| [ui-01h4.md](work/ui-01/ui-01h4.md) | План / контракт / история реализации | `work/ui-01/ui-01h4.md` | Проверить содержание |
| [ui-01i-architecture-review.md](work/ui-01/reviews/ui-01i-architecture-review.md) | Review | `work/ui-01/reviews/ui-01i-architecture-review.md` | Перенести |
| [ui-01i-architecture-targeted-recheck.md](work/ui-01/reviews/ui-01i-architecture-targeted-recheck.md) | Review | `work/ui-01/reviews/ui-01i-architecture-targeted-recheck.md` | Перенести |
| [ui-01i-architecture.md](work/ui-01/ui-01i-architecture.md) | План / контракт / история реализации | `work/ui-01/ui-01i-architecture.md` | Проверить содержание |
| [ui-01i.md](work/ui-01/ui-01i.md) | План / контракт / история реализации | `work/ui-01/ui-01i.md` | Проверить содержание |
| [ui-01j.md](work/ui-01/ui-01j.md) | План / контракт / история реализации | `work/ui-01/ui-01j.md` | Проверить содержание |
| [ui-02-architecture.md](work/ui-02/ui-02-architecture.md) | План / контракт / история реализации | `work/ui-02/ui-02-architecture.md` | Проверить содержание |
| [ui-02a.md](work/ui-02/ui-02a.md) | План / контракт / история реализации | `work/ui-02/ui-02a.md` | Проверить содержание |
| [ui-02b.md](work/ui-02/ui-02b.md) | План / контракт / история реализации | `work/ui-02/ui-02b.md` | Проверить содержание |
| [ui-02c.md](work/ui-02/ui-02c.md) | План / контракт / история реализации | `work/ui-02/ui-02c.md` | Проверить содержание |
| [ui-02d.md](work/ui-02/ui-02d.md) | План / контракт / история реализации | `work/ui-02/ui-02d.md` | Проверить содержание |
| [ui-02e-pki-runtime-secret-transport.md](work/ui-02/ui-02e-pki-runtime-secret-transport.md) | План / контракт / история реализации | `work/ui-02/ui-02e-pki-runtime-secret-transport.md` | Проверить содержание |
| [ui-02f-runtime-service-secret-transport.md](work/ui-02/ui-02f-runtime-service-secret-transport.md) | План / контракт / история реализации | `work/ui-02/ui-02f-runtime-service-secret-transport.md` | Проверить содержание |
| [ui-be-01.md](work/ui-backend/ui-be-01.md) | План / контракт / история реализации | `work/ui-backend/ui-be-01.md` | Проверить содержание |
| [ui-be-02.md](work/ui-backend/ui-be-02.md) | План / контракт / история реализации | `work/ui-backend/ui-be-02.md` | Проверить содержание |
| [ui-be-03.md](work/ui-backend/ui-be-03.md) | План / контракт / история реализации | `work/ui-backend/ui-be-03.md` | Проверить содержание |
| [ui-be-04.md](work/ui-backend/ui-be-04.md) | План / контракт / история реализации | `work/ui-backend/ui-be-04.md` | Проверить содержание |
| [ui-design-01-mockups.html](design/ui-design-01-mockups.html) | UI-дизайн / предложение | `design/ui-design-01-mockups.html` | Перенести |
| [ui-design-01.md](design/ui-design-01.md) | UI-дизайн / предложение | `design/ui-design-01.md` | Перенести |
| [ui-logs-01-plan.md](work/ui-lifecycle/ui-logs-01-plan.md) | План | `work/ui-lifecycle/ui-logs-01-plan.md` | Перенести |
| [ui-net-01-architecture.md](work/ui-network/ui-net-01-architecture.md) | План / контракт / история реализации | `work/ui-network/ui-net-01-architecture.md` | Проверить содержание |
| [ui-net-01.md](work/ui-network/ui-net-01.md) | План / контракт / история реализации | `work/ui-network/ui-net-01.md` | Проверить содержание |
| [ui-project-creation-design.md](design/ui-project-creation-design.md) | UI-дизайн / предложение | `design/ui-project-creation-design.md` | Перенести |
| [ui-save-verify-architecture.md](work/ui-lifecycle/ui-save-verify-architecture.md) | План / контракт / история реализации | `work/ui-lifecycle/ui-save-verify-architecture.md` | Проверить содержание |
| [ui-ux-01-proposals.md](design/ui-ux-01-proposals.md) | UI-дизайн / предложение | `design/ui-ux-01-proposals.md` | Перенести |
| [v1-reference-audit.md](work/development/v1-reference-audit.md) | План / контракт / история реализации | `work/development/v1-reference-audit.md` | Проверить содержание |
