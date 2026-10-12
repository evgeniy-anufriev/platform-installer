# Подробные контракты

Подробные правила и сохранённые версии контрактов этапов. Это дополнение к
[архитектуре](../architecture.md), [контракту проекта](../project-contract.md)
и [Ansible Core](../ansible-core.md). Разделение документов не меняет правила
или статус приёмки; текущий статус находится в [CURRENT_STATE](../../CURRENT_STATE.md).

| Контракт | Связанные материалы |
| --- | --- |
| [Save, Project Verify и DeploymentPlan](../work/ui-lifecycle/ui-save-verify-architecture.md) | [ADR-027](../architecture-decisions.md#adr-027-save-project-verify-and-deploymentplan-are-separate-operations); новый Save локален, Verify и execution plan — отдельные операции |
| [Планирование, протокол и события](execution-planning-and-events.md) | [UI-BE-04 план](../work/ui-backend/ui-be-04.md), [implementation audit](../work/ui-backend/evidence/ui-be-04-implementation-audit.md) |
| [Docker rootless и Compose](docker-rootless.md) | [SI10 план и gates](../work/docker/service-docker-rootless-architecture.md), [acceptance evidence](../work/docker/evidence/si10-acceptance.md) |
| [Application config / server types: foundation scope](application-config-foundation.md) | [План](../work/application-config/application-config-server-types.md), [audit и acceptance](../work/application-config/evidence/foundation-acceptance.md); сохранён исходный scope v1alpha1/v1alpha2/v1alpha3, поздние версии не переопределяются |

Сохранённый контракт этапа не является спецификацией всех поздних версий.
Для Save начинайте с ADR-027 и связанного owner-change документа; старые
Core-backed Review/EditPlan остаются источником writer/transaction mechanics
и compatibility history. Текущий UI не использует их для разрешения нового Save.

[Карта документации](../README.md)
