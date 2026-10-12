# Application libraries documentation checkpoints

Source snapshot from 2026-10-12 before navigation cleanup. Statements describe
their reviewed versions and stages; they are not a current status ledger.
The owner decision remains distinct from independent review verdicts.
Current status: [CURRENT_STATE](../../../../CURRENT_STATE.md).

## Original navigation and discussion context

# Пользовательские библиотеки приложений

Документация функциональности, реализуемой по подэтапам. Архитектурные разделы
и примеры будущих этапов описывают проектные предложения; реализованные контракты
и доказательства проверок находятся в технических планах и журналах соответствующих
подэтапов. Текущий статус остаётся в [CURRENT_STATE](../../../../CURRENT_STATE.md).

Владелец завершил обсуждение и вернул стандартную процедуру ревью.
Проведён [FULL PLAN review](../reviews/plan-review.md): APPROVE_WITH_CHANGES, ноль blockers.
Его проверенная версия предшествовала уточнению о размещении библиотеки на
нескольких Docker-хостах; для этой части прежний вердикт не переносится автоматически.
Это не разрешение реализации всех этапов; следующий ограниченный scope утверждает владелец.
Этот раздел консолидирует обсуждение, включая более поздние уточнения про
Compose-наследование, идентичность экземпляров и общие PKI-секреты. Ранние
review черновика не считаются review этого расширенного предложения.

## Навигация

| Документ | Содержание |
| --- | --- |
| [FULL PLAN review](../reviews/plan-review.md) | Независимый отчёт, идентичность проверенной версии и неблокирующие корректировки |
| [Общий план реализации](../implementation-plan.md) | Подэтапы standalone Ansible + Core → Go backend → UI, критерии выхода и переиспользование механизмов |
| [Технический план A1](../milestones/a1/a1-technical-plan.md) | Контракт vars/packages, slot mapping, read-only resolve, Core extension points, fixtures и QA gates |
| [Ревью A1](../milestones/a1/reviews/a1-plan-review.md) | Независимый FULL PLAN review технического плана и bounded correction |
| [Технический план A2](../milestones/a2/a2-technical-plan.md) | Standalone materialization, общий env/base Compose, registry/bundle image delivery, rootless Apply/Verify и QA |
| [Ревью A2](../milestones/a2/reviews/a2-plan-review.md) | Независимый FULL PLAN review, blocker interrupted config activation и уточнения image authority/staging |
| [DIFF ревью A2](../milestones/a2/reviews/a2-diff-review.md) | FULL BLOCK, согласованные исправления D01/D02 и единственный TARGETED_RECHECK |
| [Журнал A2](../milestones/a2/evidence/a2-test-journal.md) | Проверки standalone runtime, публичного образа, повтора и ограничения доказательств |
| [Технический план A3](../milestones/a3/a3-technical-plan.md) | Общий PostgreSQL hook: ресурсы библиотеки, accounts/grants, ownership/retry и минимальная стоимость выполнения |
| [Технический план A4](../milestones/a4/a4-technical-plan.md) | Vault endpoint/client port, KV v2, AppRole, shared PKI secrets, private Agent delivery и standalone QA |
| [Технический план A5](../milestones/a5/a5-technical-plan.md) | Redis/Sentinel ACL, ClickHouse resources/accounts/grants и выбранный Kafka SSL-only scope; реализация и текущие проверки завершены |
| [PLAN review A5](../milestones/a5/reviews/a5-plan-review.md) | APPROVE_WITH_CHANGES, ноль blockers; уточнены shared locks, Sentinel roles и optional bindings |
| [Cluster revision review A5](../milestones/a5/reviews/a5-cluster-plan-review.md) | Исторический BLOCK A5-C01; риск принят владельцем, специальная обработка исключена |
| [DIFF review A5](../milestones/a5/reviews/a5-diff-review.md) | Initial FULL BLOCK по D01/D02; единственный owner-approved targeted recheck APPROVE, оба finding закрыты |
| [QA journal A5](../milestones/a5/evidence/a5-test-journal.md) | Сквозные A4/A5 и native Redis/Sentinel/ClickHouse проверки на RED OS; ограничения Keeper перечислены |
| [PLAN review A4](../milestones/a4/reviews/a4-plan-review.md) | FULL PLAN BLOCK → owner-approved TARGETED_RECHECK APPROVE_WITH_CHANGES, ноль blockers |
| [DIFF review A3](../milestones/a3/reviews/a3-diff-review.md) | FULL DIFF findings and owner-approved targeted recheck |
| [QA journal A3](../milestones/a3/evidence/a3-test-journal.md) | Functional standalone/Core/PostgreSQL evidence; no benchmark |
| [Ревью плана A3](../milestones/a3/reviews/a3-plan-review.md) | FULL PLAN APPROVE_WITH_CHANGES, ноль blockers, bounded уточнение application privilege scope |
| [Ревью скорости A1/A2](../milestones/a1-a2-speed/reviews/a1-a2-speed-review.md) | Независимый FULL DIFF оптимизаций; operation-local reuse и сохранение guards |
| [Журнал скорости A1/A2](../milestones/a1-a2-speed/evidence/a1-a2-speed-test-journal.md) | Сопоставимый before/after benchmark, focused/native проверки и ограничения |
| [Архитектура](../architecture.md) | Сущности, хранение, границы Core/Ansible/Go/UI |
| [Конфигурация](../configuration.md) | Defaults, group_vars, ID экземпляра, base Compose, HAProxy |
| [Установка](../execution.md) | Ресурсы библиотеки, общие provider hooks, порядок, повтор и сбои |
| [Секреты](../secrets.md) | Vault Agent, AppRole, привязки переменных, общие PKI-секреты |
| [UI](../ui.md) | Предлагаемая страница «Приложения» и существующий цикл установки |

## Основания и границы

- [Project contract](../../../project-contract.md), [Ansible Core](../../../ansible-core.md)
  и [architecture](../../../architecture.md) сохраняют силу. Эти черновики их не заменяют.
- [Docker runtime](../../docker/service-docker-rootless-architecture.md) даёт существующую
  основу; установка приложений является расширением.
- Общая endpoint-интеграция: [playbook](../../../../services/integrations/playbooks/apply-endpoint.yml)
  и [placement contract](../../endpoint-placement/endpoint-haproxy-placement-plan.md).
- До UI реализации нужно согласовать расширение
  [UI design](../../../design/ui-design-01.md) и [mockups](../../../design/ui-design-01-mockups.html).
- Продуктовый код, targets, bundles и secrets этой документацией не изменяются.

## Дальнейшая детализация

Порядок и критерии подэтапов собраны в [общем плане](../implementation-plan.md).
Он не разрешает начать следующие milestone; перечисленные ниже вопросы
закрываются в соответствующих подэтапах до зависимой реализации.

Открытые вопросы:

1. Точные versioned schemas и mapping к существующим переменным и backend settings.
2. Материализация нескольких экземпляров одного Compose-пакета: имена service,
   области `.env`, пути, container names и отсутствие конфликтов на одном Docker.
3. Provider-native ownership УЗ/ресурсов, восстановление после interrupted create,
   rotation и изменения grants; никаких takeover по совпадению имени.
4. AppRole bootstrap при перезапуске, expiry, повторной авторизации и потере identity.
5. Ссылка общего секрета на точный PKI credential/material revision и rotation.
6. App endpoint identity/FQDN, совместимость старых service endpoints и
   protocol-specific probes; текущее поведение missing-provider сохраняется.
7. Поддержка новых provider capabilities. В частности, SASL в текущем
   [Kafka manifest](../../../../services/kafka/service.yml) обозначен unsupported;
   сценарий с Kafka username/password требует отдельного расширения.
8. Безопасное доверие пакетам, writer/import/export и offline image closure.

При последующей формализации синхронизировать канонические контракты, ADR и roadmap.
Подробные результаты будущей QA вести отдельно от архитектурного описания.

A4 standalone: COMPLETE by owner acceptance. See [QA journal](../milestones/a4/evidence/a4-test-journal.md)
for native evidence and the owner-confirmed AppRole reauthentication after
`maxTTL`; the independent [review report](../milestones/a4/reviews/a4-diff-review.md) records its verdict
against the evidence snapshot it inspected.

## Implementation-plan review checkpoint

Результат FULL PLAN: [APPROVE_WITH_CHANGES](../reviews/plan-review.md), ноль блокирующих замечаний.

## A5 implementation-plan checkpoint

Текущий Redis/Sentinel, ClickHouse и Kafka SSL-only scope реализован и прошёл
обязательный review/QA; см. [FULL DIFF и targeted recheck](../milestones/a5/reviews/a5-diff-review.md)
и [журнал](../milestones/a5/evidence/a5-test-journal.md). C02 Keeper production access/retention proof
остаётся неблокирующим ограничением. Kafka SASL/principal/ACL по-прежнему требует
отдельного security scope.

## Original A5 heading

### A5. Остальные providers по тому же образцу — текущий scope выполнен
