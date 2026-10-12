# A4 — независимое FULL DIFF ревью

Дата 2026-10-10. Reviewer `/root/a4_full_diff_review`, architecture-reviewer,
read-only. Verdict **BLOCK**, CURRENT. Один blocker OPEN. Первое FULL DIFF A4;
TARGETED_RECHECK не выполнялся и требует согласия владельца после исправлений.

## Идентичность

Ветка codex/application-libraries, HEAD/base
c7dba6b1d80beab78fe797a792f94f4ed4fec298. 38 source files Core/schema/Vault
provider/Agent private delivery/PostgreSQL credential map.
Fingerprint `4df862f3cd99d163d914d799f9d72fe651e8720a305bf12447182c838087d279`:
sortedUnique lowercase-fileSHA256 + two spaces + relativepath, UTF-8 without BOM,
LF including terminal LF. Plan hash at review:
`200fb9f3c14b8c04ef889eecc47a753a1849fe959b3e4160a5f16230a636ae51`.

Учтены owner decisions: existing Go age import → typed runtime token;
standalone explicit token/plaintext bootstrap custody без age CLI;
endpoint https://fqdn implicit443; /24+localhost;
library actions before instance; Go/UI/A5–A7 вне scope.

## A4-D01 — BLOCKING, OPEN

План §11 требует обязательную native-приёмку, а QA journal явно оставляет
непроверенными endpoint-first, два Docker placements, expiry/re-auth,
live CAS conflict, missing field и unsafe path. Текущий успешный fixture
использует один Docker-хост и direct Vault address. Unit URL test не доказывает
работу через HAProxy, union CIDR и shared RoleID не доказаны двумя placements.

Влияние: нельзя подтвердить все эксплуатационные границы A4 или объявить COMPLETE.
Это пробел обязательной evidence; дефект реализации им не доказан.

Минимальные owner-approved проверки в существующем fixture, без benchmark/framework:

- Реальный HTTPS endpoint443 и отказ без direct fallback.
- Два placements с одним logical RoleID/account/document.
- Короткий max TTL, истечение и автоматическая повторная авторизация Agent.
- Один реальный CAS conflict, сохранение соседних полей.
- Missing field и unsafe private path: fail closed без раскрытия значений.

## A4-D02 — NON_BLOCKING, OPEN

Вступление §3.1 плана (строки143–147 на reviewed revision) ещё описывает
отменённые admin-token.age file/password fields; ниже текст и schema уже содержат
новое решение. Минимальная правка — согласовать вступление. Re-review только этой
документационной правки не требуется. После BLOCK правка автоматически не выполнена.

## Overengineering

Блокирующих случаев 0. Projection/action/module нужны для target-free jobs,
protected credentials и фактического rootless UID mapping. Builtin uri/copy/include_role
переиспользованы. Shared file guard используется PostgreSQL; второго secret store
или desired-state DTO нет. Generic hook engine/daemon/queue/transaction framework
и преждевременная Go/UI реализация отсутствуют. Closed Agent profile ограничивает
exec/sinks; произвольный HCL был бы проще формально, но ослабляет проверяемую границу.

## Evidence и ограничения

Reviewer изучил source/contracts/schema/provider sequence/no_log/TLS/no-redirect,
CAS delta/ownership/private RoleID/PKCS12/cleanup, не читал runtime secrets,
не опрашивал targets и не запускал тесты. Executor evidence — [journal](../evidence/a4-test-journal.md).
56Core+12Vaultprovider+25PGcontract+2HBA PASS, syntax PASS,29Vaultrole PASS;
latest native e7676355d0be4cb7b99ca6ddc8b783fd exit0, actual standalone explicittoken
и plaintextbootstrap custody PASS, Apply/Verify/repeat changed0,
scope/CIDR/renew/restart/wrongPGpassword/readonlyKV/foreignowner PASS.
Earlier broad522PASS19skip. No complete A4/UI acceptance implied.

После BLOCK автоматические доработки/новые acceptance cases остановлены.
Исполнитель рекомендует согласовать ограниченные проверки A4-D01 и исправление
A4-D02, после чего один TARGETED_RECHECK по A4-D01. Решение владельца ещё не получено.