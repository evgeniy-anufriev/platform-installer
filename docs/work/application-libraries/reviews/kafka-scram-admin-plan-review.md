# Kafka SCRAM admin — FULL PLAN review

Дата: 2026-10-20. Независимый read-only reviewer:
`/root/scram_compatibility_plan_review`, роль `architecture-reviewer`.
Вердикт: **BLOCK**. Открытых blocking findings: **2**.

Проверен [план](../kafka-scram-plan.md), SHA-256
`B00C47DBF8AC18675B99B5E38A19BFB6C6029F8312C5B4AADA2EFE2FFF24CE73`;
HEAD `930d5f71a83e3be99901ea40e2af6464394526f5`, dirty tree.
Scope: весь план, особенно обязательный admin SecretRef, временный mTLS
bootstrap, admin-only finalization, anonymous data ACL и existing Agent ENV.
Частичная реализация использована как evidence; DIFF verdict не выдавался.

## KS-P04 — runtime privileges после прерывания

План §6:228–245; `authorization_inputs.yml:33–61`, `main.yml:437–451`.
Finalized/bootstrap определяется по строке `super.users=User:admin` в файлах.
Прерывание после финальной записи до restart оставляет работающий процесс с
certificate superusers. Повтор видит финальные файлы, config change отсутствует,
и может завершиться без удаления временных runtime privileges.

Минимальное исправление: доказать фактически загруженную конфигурацию каждого
member либо его запуск с финальной конфигурацией; при несовпадении restart и
повторная проверка до SUCCESS. Новый persistence store не требуется.
Проверки: interruption после записи до restart, повтор Apply, read-only Verify
в таком состоянии и interruption после restart одного из трёх members.

## KS-P05 — collision обязательного requirementRef

План §6:217–222; `services/kafka/service.yml:49–62`;
`deployment_plan.py:343–350`; `docs/project-contract.md:110–127`.
Generic service secret planner копирует manifest requirementRef без deployment
namespace и блокирует duplicates. Два Kafka deployments с обязательным
`kafka-admin-password` получают `RUNTIME_SECRET_REQUIREMENT_DUPLICATE`.
Это сужает canonical поддержку независимых deployments одного service type.

Минимальное исправление: deployment-bound public requirement identity через
существующий `_secret_input_requirement_ref()`, сохраняя логическое имя в manifest
и единственный существующий Broker/lease channel. Kafka-specific Go resolver
не требуется. Проверки: два deployments с независимыми inputs; отсутствующий
input блокирует соответствующий deployment; transport сохраняет привязку.

## Остальные выводы и ограничения

KS-P01 RESOLVED по явному порядку, новый recovery defect вынесен в KS-P04.
KS-P02 остаётся RESOLVED: existing Agent env_template без file wrapper.
KS-P03 RESOLVED: автоматические права только exact member identities.
Overengineering findings: 0. Existing Broker/lease, provider jobs и fixed JAAS
formatter соответствуют задаче; temporary bootstrap обоснован первым admin.

Reviewer проверил план, инструкции, deployment identity, metadata, secret planner,
authorization tasks, account flow, member config и Vault formatter. Runtime/JAR
аудит независимо не повторялся; тесты и targets не запускались, значения секретов
не читались, файлы reviewer не изменял. SCRAM acceptance отсутствует.

Следующий шаг по процедуре: вернуть владельцу KS-P04/KS-P05, влияние и минимальные
коррекции. Работу по заблокированным границам остановить. Повторный review этим
отчётом не разрешён. Предложение исполнителя находится в §10 плана.
