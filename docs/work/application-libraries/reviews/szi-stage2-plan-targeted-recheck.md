# SZI-STAGE2 — TARGETED_RECHECK плана

## 1. Вердикт

**APPROVE_WITH_CHANGES — PLAN / TARGETED_RECHECK, SZI-STAGE2.**

Блокирующие **SZI2-P01 и SZI2-P02 устранены на уровне плана**. Неблокирующие
SZI2-P03–04 также исправлены. В непосредственно изменённых batching/lifecycle/
credential-delivery границах новых блокеров не установлено.

Остаются два неблокирующих уточнения: формат результата batch callback и различие
доставки поля через Agent и прав чтения Vault-документа.

Вердикт сформирован независимо. Это оценка плана, не реализации или приёмки.

## 2. Review identity и область

Frozen документ: `docs/work/application-libraries/szi-stage2-technical-plan.md`.

- SHA-256: **`3B359B511D825F9C04C0142D09C27F1243FB302696C04F856E7E274B11AA249C`**.
- Объём: 673 строки.
- Исходная версия кода: `5f6143123b1794e37aa37fe703a3ac8ea05e5baa`.
- HEAD checkout: `327c0b76af5ff315c2a104abb1248de042debe5c`.
- Before-image SHA-256: `0B9A1B168A52275E6FECDE645F5F65718FBC2F04C31F129283996ECF0AA48451`.

Оба хеша проверены непосредственно; revised SHA повторно подтверждён после
исследования. Область ограничена SZI2-P01/P02, исправлениями P03/P04 и непосредственно
изменёнными границами: grouping по провайдерам; provider-ready → groups → clients
→ accounts; полный consumer Vault/Agent; source/delivery client_secret; early/late
fields общего Vault document. Незатронутые разделы FULL не пересматривались.
Исторический FULL BLOCK сохраняется.

## 3. Findings

### SZI2-P01 — BLOCKING — OPEN → RESOLVED

**Сохранение Vault read-paths при disable/removal.**

Исправление: reviewed план352–375, §6.3. Определены аддитивное обновление managed
read-paths, сохранение доступа действующего token, обновление активных credentials,
existing owned policy без второго хранилища, canonical rules/ownership/format guards
и отсутствие запроса отключённого пароля. Исходное противоречие устранено.

Implementation proof: native `postgres + identity → disable/remove identity →
update postgres`, retained read старого token и no-change repeat. QA P12 включает
этот сценарий; proof ещё не выполнен.

### SZI2-P02 — BLOCKING — OPEN → RESOLVED

**Явное общее основание проверки Apply scope.**

Исправление: reviewed план492–510, §7.2. Canonical providedConnectionRef требует
явного включения provider library для выбранного enabled consumer, включая
транзитивные связи. Self-library обслуживается existing instance order. Исключены
анализ Jinja, render history, automatic scope expansion и nginx/СЗИ conditions.
Цена дополнительного идемпотентного Apply явно указана.

Implementation proof: target-free C06 — consumer-only, provider+consumer,
transitive/self references; отсутствие target contact/automatic selection changes.

### SZI2-P03 — NON_BLOCKING — OPEN → RESOLVED

**Единый source административного credential.**

Исправление: reviewed150–157. Bootstrap/admin hooks используют один export source;
source resolution отделён от API readiness, self-reference не создаёт readiness
dependency. Неверный credential existing admin останавливает Apply без reset.
Proof: C07 override/reset, единый source и отсутствие ротации при ошибке.

### SZI2-P04 — NON_BLOCKING — OPEN → RESOLVED

**Canonical Vault source.** Reviewed147 использует vault_ref без нового alias.
Proof: согласованные schema fixtures/examples.

### SZI2-P05 — NON_BLOCKING — OPEN

**Batch output должен соответствовать существующему ограниченному stdout.**

Место: reviewed249–252. Existing package_script/tasks/main.yml task `Require a
bounded machine-readable nonsensitive result` принимает aggregate status/changed
и stdout до2048 символов. План говорит per-request status/changed:100 consumers
легко превысят предел, вызвав отказ успешной группы/ненужное расширение протокола.

Минимальная коррекция: внешний результат остаётся aggregate status/changed,
per-request results — внутренние данные. Success означает все requests завершены;
ошибка блокирует dependent delivery. Публичный список для учёта не нужен.
Proof:100 requests укладываются в stdout contract, partial failure blocks startup/
Vault, repeat идемпотентно доводит batch.

### SZI2-P06 — NON_BLOCKING — OPEN

**secret_bindings ограничивает доставку, не field-level Vault read.**

Место: reviewed443–458, §7.0. PKI и client fields находятся в одном <library>/shared
document. Existing policy выдаёт read целому document; Agent выбирает field.
No binding означает отсутствие автоматической доставки, не field-level ACL
для токена, уже имеющего read. Формулировку «получает только grant-access» можно
ошибочно принять за изоляцию от остальных таких токенов.

Минимальная коррекция: явно обозначить Agent/ENV delivery и document-level ACL.
Новый механизм Vault/незапрошенная изоляция не требуется. Canary проверяет
отсутствие secret в чужом Agent/ENV, но не доказывает невозможность document read.
Это не blocker: отдельного field-level ACL требования владелец не устанавливал.

## 4. Проверка изменённых lifecycle/secret границ

В разрешённой области план задаёт последовательную модель:

1. Infrastructure batches остаются ранними.
2. Application-backed requests заранее группируются по provided source.
3. После readiness/bootstrap публикуется общий endpoint используемого provider.
4. Library provider_prepare hooks предшествуют instance hooks.
5. Accounts выполняются одним batch данного provider.
6. Consumer Vault/Agent получает полный набор после всех его dependencies.
7. Перед startup проверяется результат; provider calls не повторяются по placement.

Client_secret имеет один source до API, без secret output. Shared document делится
на early/late field delta с reread перед late CAS, избегая self bootstrap deadlock
и перезаписи ранних полей устаревшим snapshot. P09–P13 адресуют новые границы;
это запланированные, а не выполненные проверки.

## 5. Scoped overengineering assessment

**Доказанных блокирующих случаев избыточной архитектуры:0.**

| Категория | Оценка / simpler alternative |
| --- | --- |
| Batch lifecycle | Устраняет repeated provider initialization; derived requests/results и existing loops, без persisted queue/DAG |
| provider_prepare | Consumer-owned hooks нужны перед accounts; before_start потребителя нарушил бы порядок |
| Secret persistence | Existing source→private input→API→Vault/Agent; нового store нет |
| Shared readiness | Две existing CAS delta/reread проще отдельной transaction subsystem |
| Scope dependencies | Conservative canonical-ref check проще анализа templates; цена указана |
| Policy retention | Canonical owned rules достаточны, общего HCL merger не требуется |
| DTO/output | Existing aggregate result проще нового per-request публичного output — P05 |
| Преждевременный scope | CRUD registry/generator/daemon/second desired state не добавлены |

## 6. Evidence и ограничения

Непосредственно проверены frozen hashes, corrected sections/bounded diff, current
milestone, existing runner output contract, Vault preflight/policy/CAS boundary
и document-level read/Agent field distinction. Ранее прочитанные root/scoped
instructions/review procedure применены повторно.

Родитель предоставил owner authorization на corrections/один recheck и scope,
а также отсутствие отдельного field-level ACL требования. Tests/targets,
implementation, secrets и generated portable-source не исследовались. Dirty AGP
отдельно; его acceptance не закрывается этим отчётом.

## 7. Валидность и следующее действие

**CURRENT** для reviewed SHA и targeted scope. Изменение batch dispatch, source,
retention, scope authority/endpoint timing требует оценки влияния. P05/P06 не
требуют automatic repeated review. Unresolved blocking: **0**; nonblocking: P05/P06.

Передать revised plan/report владельцу для решения о реализации. Допустимы bounded
documentary corrections P05/P06 без нового automatic review. TARGETED_RECHECK
выполнен один раз; implementation/Apply/Stage1/AGP acceptance этим не разрешены.

## 8. Приложение исполнителя после независимого заключения, 2026-10-22

Это запись внесённых правок, не новый verdict/review. Исторический verdict и
reviewed SHA выше сохранены. В пределах разрешённых nonblocking corrections:

- P05: внешний batch output заменён на aggregate status/changed с лимитом2048;
  внутренние per-request results не публикуются, success подтверждает всю группу;
  QA P09 дополнен100 requests/partial failure/retry.
- P06: явно записан document-level ACL общего Vault document и отсутствие гарантии
  field-level isolation. Уточнена именно доставка client_secret в Agent/ENV grant-access.

Final plan SHA-256 после этих двух documentary corrections:
`AFD92A4B4B030FC78C48442D6B012160FCC99A9ED966901D7CBC5599E04C4E83`.
P05/P06 отмечены исполнителем как addressed; независимого повторного verdict нет.
Бюджет одного TARGETED_RECHECK исчерпан; новых review не запускалось.
