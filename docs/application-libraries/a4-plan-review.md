# A4 — независимый FULL PLAN review

Вердикт: **BLOCK**. Проверенная редакция `a4-technical-plan.md` SHA-256:
`93f38805c6a6cc2c0be68ae45f5be8c22ad2c5638badbd707f05ba1069575e66`.
База: `c7dba6b1d80beab78fe797a792f94f4ed4fec298`, codex/application-libraries.
Reviewer: независимый architecture-reviewer `/root/a4_plan_review`.
Scope: standalone Vault hook, источники, AppRole/CIDR, endpoint, shared PKI и Agent.
Реализации A4 и target QA нет. FULL budget использован; TARGETED_RECHECK допускается
только после owner-approved исправлений. Самостоятельные исправления блокеров
после этого отчёта и автоматический повтор review не выполнялись.

## A4-P01 — BLOCKING, OPEN

Endpoint и client CIDR остаются неопределённым архитектурным выбором.
План §5 требует фактический client IP через endpoint, но выбор доверенного
forwarding механизма отложен. Текущий Vault listener template не задаёт trusted
XFF/PROXY protocol; проверенные HAProxy templates не устанавливают доверенный XFF.
Обычный proxy endpoint меняет видимый Vault адрес; Docker-host CIDR не разрешит
login. Расширение роли до proxy IP нарушает границу доступа.

Минимальная коррекция: выбрать конкретный поддерживаемый путь. Для HTTP proxy
HAProxy перезаписывает клиентский XFF, Vault доверяет только resolved proxy
addresses; явно определены hops и прямое подключение без заголовка. Это narrow
инфраструктурное изменение требует согласования scope. Альтернатива: поддержать
только endpoint, уже достоверно сохраняющий client IP, с явным prerequisite.

Проверка: настоящий Agent login и последующий KV read через endpoint; spoofed XFF
и чужой client отклоняются; direct-port допускается только без configured endpoint.
Первичный контракт: [Vault TCP listener](https://developer.hashicorp.com/vault/docs/configuration/listener/tcp).

## A4-P02 — BLOCKING, OPEN

Библиотечный vault_ref не имеет конкретной связи с account credential.
План §4 учитывает последнее решение владельца, но не показывает canonical YAML:
как library binding/mount/document/field становится source конкретного
accounts.postgres.credentials.password. Сейчас vault_ref расположен в credential
source schema, а A3 принимает password только runtime_secret_ref. secret_bindings
связывает переменную Agent с account/field либо library_secret; это не выбор
источника пароля для account hook.

Минимальная коррекция: один точный library YAML и минимальное schema/resolver
изменение для именованной ссылки account credential на библиотечный source.
Vault deployment выбирается библиотекой; account-specific secret может иметь
собственный document/field. Переиспользовать existing shared-secret/source,
если они покрывают сценарий, без второго secret registry.

Проверка: два credentials с различными fields/documents в одном Vault binding,
shared-only, missing reference, read-only original document и отсутствие plaintext
в projection.

## A4-P03 — NON_BLOCKING, OPEN

Rootless delivery: конкретизировать A4.1 discovery result — container UID/GID →
host UID/GID, ownership родительских директорий, безопасная проверка читаемости
до запуска. A2 Docker account ownership недостаточно для nonzero container UID.
Проверить restart. Отдельный повтор review не требуется.

## Overengineering и ограничения доказательств

Блокирующих замечаний по усложнению нет. Узкая Vault provider role с uri loops и
optional agent_template оправданы. Generic engine, второй secret store, daemon,
queue и provider-wide mutations не предлагаются. Generated passwords/rotation
отложены. Один hook не означает один HTTP request.

Проверены scoped contracts, schema, A2 runtime guards, A3 password source guard,
Vault listener и HAProxy templates. Тесты/обращения к targets не выполнялись;
A3 PASS не доказывает A4. Validity CURRENT для указанного plan SHA-256.

Рекомендация implementer: сначала согласовать минимальные решения P01/P02,
затем конкретизировать план и выполнить один owner-approved TARGETED_RECHECK.
Незакрытых блокеров: **2**.

## Owner-approved corrections и единственный TARGETED_RECHECK

Владелец согласовал P01: IPv4 /24 Docker hosts и дополнительно 127.0.0.1/32;
подтвердил, что Vault видит source внутри этих /24 даже через proxy. P02:
библиотечный выбор Vault deployment отделён от account-specific source defaults.
Исправленный plan SHA-256:
`bba6aacb35723a959ea588ebbc0a85337f7322b7336a93407db4648743792258`.

Независимый `/root/a4_plan_review`, TARGETED_RECHECK A4-P01/P02:
**APPROVE_WITH_CHANGES**, ноль открытых blockers.
- P01 RESOLVED: явная subnet policy, endpoint-first, login и KV read обязательны;
  trusted forwarding не требуется в принятом scope.
- P02 RESOLVED: concrete canonical YAML использует existing source/bindings,
  не вводит новый DTO и не подменяет source при доставке A3 credentials.
- P03 NON_BLOCKING: private rootless mapping должен быть доказан реализацией A4.1.
- Неблокирующая синхронизация secrets.md и implementation-plan.md с новой CIDR
  политикой выполнена; отдельный re-review не требуется.

Target QA и implementation не выполнялись. Network prerequisite пока подтверждён
владельцем, а не runtime evidence. Verdict CURRENT для указанной редакции плана.
Бюджет A4 PLAN FULL + TARGETED_RECHECK исчерпан. Реализация требует owner request.

## Последующее уточнение владельца: admin-token.age input

После TARGETED_RECHECK владелец задал библиотечный vault_ref с пользовательским
путём к admin-token.age и runtime secret reference для encryption password.
План дополнен §3.1: typed library credential input, Execution Node path,
protected existing age decrypt, no plaintext и shared invocation resolution.
Это изменение публичного credential input контракта; предыдущий verdict не
проверяет новую часть. FULL + TARGETED_RECHECK budget исчерпан, дополнительный
review без явного owner request не запускается. P01/P02 остаются закрытыми
в пределах ранее проверенной редакции; актуальная добавленная граница не reviewed.

Последующее уточнение UI: переиспользовать existing Vault file import
(ServicesPage chooseSecretFile → backend ReadVaultInput → pending SERVICE_ADMIN_TOKEN
broker → runtime-secret lease). Локальный file path в Core не передаётся.
Standalone file/ref source остаётся optional парой; typed input имеет приоритет.
План §3.1 дополнен; это не review новой credential-input части и не UI acceptance.

Последующее решение владельца заменяет standalone age file/ref контракт:
существующие platform_vault_admin_token или protected bootstrap admin-token.
Installer использует existing Go age import и runtime inputs. Также все endpoint
используют HTTPS 443 без явного порта в URL. Это owner-approved текущая редакция;
предыдущий PLAN verdict не объявляется review этих изменений. DIFF review отдельно.
