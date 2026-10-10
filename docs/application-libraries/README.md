# Пользовательские библиотеки приложений

Документация функциональности, реализуемой по подэтапам. Архитектурные разделы
и примеры будущих этапов описывают проектные предложения; реализованные контракты
и доказательства проверок находятся в технических планах и журналах соответствующих
подэтапов. Текущий статус остаётся в [CURRENT_STATE](../../CURRENT_STATE.md).

Владелец завершил обсуждение и вернул стандартную процедуру ревью.
Проведён [FULL PLAN review](plan-review.md): APPROVE_WITH_CHANGES, ноль blockers.
Его проверенная версия предшествовала уточнению о размещении библиотеки на
нескольких Docker-хостах; для этой части прежний вердикт не переносится автоматически.
Это не разрешение реализации всех этапов; следующий ограниченный scope утверждает владелец.
Этот раздел консолидирует обсуждение, включая более поздние уточнения про
Compose-наследование, идентичность экземпляров и общие PKI-секреты. Ранние
review черновика не считаются review этого расширенного предложения.

## Навигация

| Документ | Содержание |
| --- | --- |
| [FULL PLAN review](plan-review.md) | Независимый отчёт, идентичность проверенной версии и неблокирующие корректировки |
| [Общий план реализации](implementation-plan.md) | Подэтапы standalone Ansible + Core → Go backend → UI, критерии выхода и переиспользование механизмов |
| [Технический план A1](a1-technical-plan.md) | Контракт vars/packages, slot mapping, read-only resolve, Core extension points, fixtures и QA gates |
| [Ревью A1](a1-plan-review.md) | Независимый FULL PLAN review технического плана и bounded correction |
| [Технический план A2](a2-technical-plan.md) | Standalone materialization, общий env/base Compose, registry/bundle image delivery, rootless Apply/Verify и QA |
| [Ревью A2](a2-plan-review.md) | Независимый FULL PLAN review, blocker interrupted config activation и уточнения image authority/staging |
| [DIFF ревью A2](a2-diff-review.md) | FULL BLOCK, согласованные исправления D01/D02 и единственный TARGETED_RECHECK |
| [Журнал A2](a2-test-journal.md) | Проверки standalone runtime, публичного образа, повтора и ограничения доказательств |
| [Ревью скорости A1/A2](a1-a2-speed-review.md) | Независимый FULL DIFF оптимизаций; operation-local reuse и сохранение guards |
| [Журнал скорости A1/A2](a1-a2-speed-test-journal.md) | Сопоставимый before/after benchmark, focused/native проверки и ограничения |
| [Архитектура](architecture.md) | Сущности, хранение, границы Core/Ansible/Go/UI |
| [Конфигурация](configuration.md) | Defaults, group_vars, ID экземпляра, base Compose, HAProxy |
| [Установка](execution.md) | Ресурсы библиотеки, общие provider hooks, порядок, повтор и сбои |
| [Секреты](secrets.md) | Vault Agent, AppRole, привязки переменных, общие PKI-секреты |
| [UI](ui.md) | Предлагаемая страница «Приложения» и существующий цикл установки |

## Основания и границы

- [Project contract](../project-contract.md), [Ansible Core](../ansible-core.md)
  и [architecture](../architecture.md) сохраняют силу. Эти черновики их не заменяют.
- [Docker runtime](../service-docker-rootless-architecture.md) даёт существующую
  основу; установка приложений является расширением.
- Общая endpoint-интеграция: [playbook](../../services/integrations/playbooks/apply-endpoint.yml)
  и [placement contract](../endpoint-haproxy-placement-plan.md).
- До UI реализации нужно согласовать расширение
  [UI design](../ui-design-01.md) и [mockups](../ui-design-01-mockups.html).
- Продуктовый код, targets, bundles и secrets этой документацией не изменяются.

## Дальнейшая детализация

Порядок и критерии подэтапов собраны в [общем плане](implementation-plan.md).
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
   [Kafka manifest](../../services/kafka/service.yml) обозначен unsupported;
   сценарий с Kafka username/password требует отдельного расширения.
8. Безопасное доверие пакетам, writer/import/export и offline image closure.

При последующей формализации синхронизировать канонические контракты, ADR и roadmap.
Подробные результаты будущей QA вести отдельно от архитектурного описания.
