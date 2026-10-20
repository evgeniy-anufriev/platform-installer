# Kafka SCRAM — KS-D01 TARGETED_RECHECK

Дата: 2026-10-20. Независимый read-only reviewer
`/root/scram_compatibility_plan_review`, роль architecture-reviewer.
Вердикт: **APPROVE в scope KS-D01**, unresolved BLOCKING в scope **0**.
Это не общий APPROVE всего Kafka SCRAM DIFF.

База: `930d5f71a83e3be99901ea40e2af6464394526f5`.
[Scope](kafka-scram-d01-recheck-scope.json) SHA256:
`05839E1A6DD0C18C1E42D7962A6DE5C03B6AC21F051DA5F3219781F2F5DE11FE`.
Все 11/11 fingerprints совпали, включая повторную проверку.
Предыдущий FULL scope:
`B2180611562B78362006A6A65A9D358827A3009484DAA8907F053DDCC20EAEF3`.
Исторический FULL BLOCK не переписывается.

## KS-D01 — BLOCKING, OPEN → RESOLVED

Проверены application_providers.py:131–185: отдельные adminCandidates разрешаются
existing resolve_connection независимо от первого library client selector;
неоднозначный admin listener блокируется. prepare_application_providers.py:35–48
привязывает exact PKI plans по host/profile и Kafka consumer request.
application_accounts.yml:6–24 требует SASL admin candidates/admin requirement и
выбирает административный candidate. application_accounts_scope.yml сохраняет
protected admin configuration и cleanup. Application authentication продолжает
использовать собственные account candidates.

Legacy SSL библиотека больше не определяет transport для SCRAM user/ACL
provisioning другой библиотеки. Тестовые случаи покрывают оба порядка библиотек,
managed/existing и отказ при неправильном PKI request. Новых blocking regressions
в непосредственно затронутой границе не выявлено.

## Остальные findings и overengineering

KS-D02 не пересматривался. OWNER_REJECTED — прямое решение владельца отклонить
ограничение конфигурации; это не техническое RESOLVED и не reviewer-resolution.
Новых guards или повторного review KS-D02 не предлагается. KS-D03 вне scope;
его исправление/native результаты этим review не подтверждаются.

Overengineering findings: 0. adminCandidates необходимо для разных data/admin
connections. Замена общего candidates потеряла бы library client selection.
Существующие resolver/PKI loop переиспользованы, нового framework, persistence,
secret transport или lifecycle layer нет.

## Evidence и пределы

Reviewer непосредственно проверил исходники, tests и fingerprints. Parent сообщил
provider23 PASS и action fixture4 PASS с восемью subcases; reviewer тесты не
запускал. Повтор target-free snapshot, syntax и native checks на момент envelope
ещё не имели нового подтверждённого PASS.

Установка, SERVICE_APPLY, startup приложений, bundle publication и real acceptance
не выполнялись. Секретные значения не читались; reviewer файлы не изменял.
Отчёт сохранён parent по тексту независимого reviewer.

Review validity: CURRENT для указанной revision и KS-D01. Изменения admin
selector, PKI binding или account hook могут инвалидировать соответствующую часть.
Общий unresolved count не обнуляется: вне scope KS-D02 не получает resolution.
Новый review не запускается; запрет стендовых установок сохраняется.