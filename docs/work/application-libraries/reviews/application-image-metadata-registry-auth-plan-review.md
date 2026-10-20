# Ревью runtime credentials registry экземпляра библиотеки

Дата: 2026-10-20. APPLICATION-IMAGE-METADATA-01. Независимый FULL PLAN review
новой owner-requested security/UI редакции выполнен read-only subagent
`architecture-reviewer` по [процедуре](../../../agent-procedures/review.md).
Владелец предложил добавить registry login/password как runtime secrets на уровне
экземпляра библиотеки с применением на целевых узлах. Это новая материальная
редакция, а не автоматическое повторное review прежнего предложения.

## Вердикт и идентичность

**APPROVE. Новых findings: 0. Неразрешённых BLOCKING: 0.**

Проверен полный [план](../application-image-metadata-plan.md), с акцентом на
registry_credentials, session inputs, preparation/execution leases,
target-side auth materialization и Library General UI.

- HEAD: `930d5f71a83e3be99901ea40e2af6464394526f5`.
- SHA-256 frozen плана при FULL review:
  `B859A499CF92A592836FB7DC755A3A33D992B909A85A025C828AC0400113F19F`.
- SHA-256 после редакционного добавления ссылки на этот отчёт и его вердикта,
  без изменения предложенных контрактов:
  `FA4C351EA79E2917E23D8D2037477371CD94761C6B54F840FD6A722219F40580`.

Reviewer повторно подтвердил frozen hash в конце проверки. Review относится
к указанным frozen bytes; финальная редакционная ссылка не является новым
независимым review всей финальной последовательности байтов.

## Findings и закрытие предыдущих уточнений

| ID | Результат независимого reviewer | Основание в frozen плане |
| --- | --- | --- |
| AIM-P01 | RESOLVED | Строки 134–142, 567: offline @digest требует доказуемой manifest/config цепочки; alias не является доказательством; предусмотрен negative test |
| AIM-P02 | RESOLVED | Строки 456–462, 520–525, 578: Create Plan остаётся ограниченным синхронным вызовом без planning job, Cancel API и polling |

Новых блокирующих и неблокирующих замечаний нет. Это закрытие замечаний к
плану; будущие реализация и QA не считаются выполненными.

## Проверенные secret boundaries

Подтверждены refs-only YAML, exact library/registry/hosts binding, запрет
повышения metadata lease до Apply authority и отдельный execution lease.
Явные runtime credentials не обходят node-approved policy и не допускают
скрытого anonymous/другого credential fallback.

Временный target DOCKER_CONFIG использует закрытые права, no_log, always и
recovery cleanup; постоянный Docker login/config не изменяется. Execution Node
обслуживает защищённую передачу runtime inputs, но не требует доступа к registry.

Текущий код не поддерживает предложенные registry/pre-plan purposes автоматически:
descriptor allowlists и application secret admission ограничены прежними
purposes/Apply/Verify, а lease binding требует готовый planFingerprint и
executionManifestDigest. Поэтому versioned расширение existing broker/lease
необходимо; фиктивные plan bindings недопустимы.

## Проверка сложности

Подтверждённых ненужных абстракций, дублирующих contracts/DTO, преждевременной
области, спекулятивных возможностей и упущенных более простых механизмов: **0**.

Расширяются существующие typed descriptors, broker и lease, без отдельного
secret store. Ansible, existing runtime session и временный DOCKER_CONFIG
покрывают задачу без самостоятельной auth-платформы. Постоянный node config
не удовлетворяет изоляции library credentials и отсутствию сохранённых значений.
Vault provisioning, acquisition, registry manager и постоянный Docker login
остаются за scope.

## Evidence и применимость

Непосредственно проверены frozen план, `application_secret_descriptors.go`,
lease `_binding` и application secret admission в `execution_secret_lease.py`,
transport types/limits в `credential_lease.go`, существующий
`ApplicationSecretInputs`, ранее изученные plan/runtime/source/UI границы.

Новый Library General блок явно описан как изменение текущего design/mockup
по предложению владельца. Реализация, тесты и real React/Wails/target acceptance
не выполнялись; секретные значения и target hosts не читались.

Вывод требует пересмотра затронутой границы при изменении auth precedence,
lease bindings/permissions, target materialization/cleanup, trust/source policy
или planning lifecycle. Review не заменяет утверждение владельца,
HIGH-RISK DIFF review и QA. Следующий шаг — утверждение этой редакции плана;
реализация, acquisition, bundle publication и установка не разрешены отчётом.
