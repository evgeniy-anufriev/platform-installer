# Библиотеки: маршруты к контрактам и границы scope

Этот индекс различает подэтапы и не утверждает их текущий статус. Источник
статуса и разрешений — [CURRENT_STATE](../../../CURRENT_STATE.md).
Реализованные требования ищите в техническом плане конкретного подэтапа вместе
с его corrections/review и QA-журналом. Общие проектные документы не заменяют
versioned schemas, service packages или accepted substage scope.

| Подэтап | Предмет контракта | Материалы |
| --- | --- | --- |
| A1 | Пакеты, vars/defaults, slots и read-only resolve | [План](milestones/a1/a1-technical-plan.md) · [review](milestones/a1/reviews/) · [журнал](milestones/a1/evidence/a1-test-journal.md) |
| A2 | Материализация, доставка образов, rootless Compose и readiness | [План](milestones/a2/a2-technical-plan.md) · [review](milestones/a2/reviews/) · [журнал](milestones/a2/evidence/a2-test-journal.md) |
| A3 | PostgreSQL resources/accounts/grants | [План](milestones/a3/a3-technical-plan.md) · [review](milestones/a3/reviews/) · [журнал](milestones/a3/evidence/a3-test-journal.md) |
| A4 | Vault provisioning, Agent и общие PKI-секреты | [План](milestones/a4/a4-technical-plan.md) · [review](milestones/a4/reviews/) · [журнал](milestones/a4/evidence/a4-test-journal.md) |
| A5 | Redis/Sentinel, ClickHouse и выбранный Kafka SSL-only scope | [План](milestones/a5/a5-technical-plan.md) · [review](milestones/a5/reviews/) · [журнал](milestones/a5/evidence/a5-test-journal.md) |

Последующие A6–A9, Go и UI описываются в [общем плане](implementation-plan.md).
Kafka SASL/principal/ACL является отдельным security scope; SSL-only probe
не доказывает authenticated access.

## Проектные предложения и уточнения

| Документ | Назначение |
| --- | --- |
| [architecture.md](architecture.md) | Сущности, хранение и ownership |
| [configuration.md](configuration.md) | Пакеты, defaults, экземпляры и Compose |
| [execution.md](execution.md) | Provider hooks, порядок и будущая интеграция |
| [secrets.md](secrets.md) | Secret bindings, Vault и Agent |
| [ui.md](ui.md) | Предложение интерфейса |

Эти документы консолидируют обсуждение и уточнения разных этапов. Их примеры
могут относиться к будущему scope; они не являются самостоятельным доказательством
реализации. Для конкретного поля или flow выбирайте соответствующий подэтап
и его versioned contract.

[Навигация](README.md) · [Общий план](implementation-plan.md)
