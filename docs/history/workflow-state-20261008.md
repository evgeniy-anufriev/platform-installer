# Historical state snapshot — 2026-10-08

Historical evidence only. Statements such as NEXT, NOT STARTED and DONE below
describe their original checkpoint and may be superseded. Read
[CURRENT_STATE.md](../../CURRENT_STATE.md) for current status and authorization.
Original section text is preserved; relative Markdown destinations are relocated.

## Active-run SSH credential retention (2026-10-07)

`SESSION-RUN-CREDENTIAL-01` implements one Broker slot (`STARTING` →
`RUNNING(runId)`) for the already-approved SSH identity metadata. The slot is
reserved before Start, survives ordinary lease expiry, and is released only
after authoritative terminal state or a proven not-dispatched first attempt.
An uncertain retry is restricted to the same pending plan and relies on the
existing `ExecutionService.pendingStarts` attempt ID. If remote Start was
accepted but local persistence failed, the observer retries and repairs the
PENDING record. Credential replacement/clear and host-key trust changes are
blocked while the slot is occupied. Go tests and vet are passing; real
nonvisual React/Wails expiry-boundary acceptance remains pending. No S11
service plan or target host was changed for this work. The owner approved this
simplified implementation and explicitly declined another review. See
[`docs/session-active-run-credential-plan.md`](../session-active-run-credential-plan.md).

## Execution Order 01 implementation checkpoint (2026-10-07)

Implementation is on `master`; the BIND candidate-selection correction below
is currently uncommitted. The application-config priority list, ordered
BuildDeploymentPlan request and Core per-deployment Apply/Verify projection
are implemented. Core regression on the configured RED OS QA node passed
(487 tests, 19 skipped); `go test ./...` and `go vet ./...` passed. Frontend
typecheck, lint, build and the full suite passed (128 tests).

The DNS resolver supports base-only and selected-source projections. Ordinary
BIND Apply now preserves an existing primary zone and updates only base-owned
A records; explicit full reconcile renders the complete desired zone using the
live SOA serial and a machine-runtime freeze/thaw recovery marker. The source
hook resolves one selected deployment, updates its HAProxy fragment and exact
BIND A record, then probes the endpoint. A defect was found where an existing
zone skipped candidate generation even in explicit full reconcile; that
condition is corrected locally. RED OS BIND tests passed (16/16), including
the isolated `named` dynamic-update/freeze/thaw test and a role-level
`prepare.yml` test: ordinary Apply preserved an existing zone byte-for-byte;
explicit full reconcile rendered a fresh candidate that passed
`named-checkzone`, while the active zone remained unchanged. Follow-up
standalone acceptance found and fixed four runtime defects in exact DNS
A-record updates: Jinja's `item.values` method collision, Ansible stringifying
numeric TTLs, nested loop-variable shadowing, and parsing tab-separated `dig`
output with a whitespace regex. The role now validates and compares DNS answer
fields directly. RED OS BIND tests passed (17/17), and apply/reconcile syntax
checks passed. On node1 and node2, standalone Apply completed, Verify passed,
explicit full reconcile completed, Verify passed again, and final ordinary
Apply returned `changed=0`; both nodes ended with active `named`, valid
`named.conf`, SOA serial 2 and the expected endpoint answer. Node3 was not
touched. Injected interruption/recovery and deletion of a deliberately stale
record remain untested.

No S11 service plan has been run under the new ordering. The source/provider
Core dependency remains fail-closed. Focused node1/node2 standalone
Apply/Verify/reconcile acceptance passed, but injected interruption/recovery,
stale-record deletion and real React/Wails acceptance remain pending; do not
run a service plan under the new ordering yet. The targeted independent
recheck approved the candidate-selection correction with no blocking findings.

Owner-approved BIND behavior for this prerequisite is recorded in ADR-030:
point updates do not delete endpoint records; explicit full reconcile is the
only deletion path. Full reconcile must synchronize/read the live primary SOA
before choosing a validly newer serial and use a machine-runtime recovery
marker plus thaw/authority checks after interruption. These decisions do not
mean the BIND lifecycle is implemented or the order is safe to execute yet.
The one targeted plan recheck for EO01-BIND-01/02/03 found zero remaining
plan blockers (APPROVE_WITH_CHANGES). The primary now uses BIND
`update-policy local`; an exact source A-record task and Core-projected generic
endpoint hook are wired only into Vault, Redis and ClickHouse Apply, whose
manifests declare client endpoint support. The hook reads the selected
deployment's saved endpoint assignment; it does not create one. Kafka and
Docker do not declare endpoint support and have no hook. PostgreSQL remains
excluded by owner decision. No endpoint assignments were added to any project.
Earlier focused endpoint-hook tests passed 13/13; the follow-up BIND suite
passed 17/17 as recorded above. The targeted lifecycle QA changed only node1
and node2; node3 was not touched.

The remaining BIND acceptance gaps are to verify stale desired-state records
are removed by full reconcile and prove injected interruptions recover before
later operations. Apply/Verify, full-reconcile activation, post-reconcile
Verify and ordinary repeat Apply (`changed=0`) have now passed on node1/node2.
The source integration's
endpoint probe and serial/freeze/thaw mechanisms exist and have focused tests,
but their complete role-level sequence and failure boundaries are not yet
proven. Keep the Core source/provider dependency fail-closed until focused and
end-to-end tests pass.

## BROWSER-REMOTE-01/02 — HTTP только для dev; HTTPS в версии 1.0 (2026-10-06)

После проверки реализации выяснилось, что удалённый Linux Browser mode
передаёт учётные данные и содержимое зашифрованных файлов секретов по HTTP;
ограничение подключений по IP не защищает данные в канале. По решению
владельца HTTP-запуск разрешён только для dev и требует явного
`-browser-allow-insecure-dev-http`. Не использовать с production-системами или
данными. HTTPS, настройка внешнего HTTPS origin и проверка защищённой передачи
credentials/secrets остаются на версию 1.0. Локальный Windows Browser mode и
Wails этим ограничением не затронуты.

## RUNTIME-BUNDLE-UX-01A — локальная приёмка перепривязки (2026-10-05)

На странице «Проект» добавлено обнаружение полного проверенного bundle в
`<project>/bundle/` и явная одноразовая кнопка «Привязать». Приложение
публикует его в новый локальный `cache/<digest>/` и меняет lock-пару через
существующий atomic CAS; обычный ProjectWriter по-прежнему не меняет locks.
Старый repository-root `bundle/` читается только как совместимый fallback,
если новый cache ещё пуст. Обнаружение без подтверждения не изменяет проект.

Start теперь до отправки на Execution Node устойчиво сохраняет локальную
операционную запись PENDING для исходного project/node; аварийная отмена
предыдущего run доступна только после проверки исходного узла, host key,
runId и projectIdentity. Подключение к Execution Node отделено от проверки
совместимости project bundle; Core Verify/Prepare/Plan/Start остаются за
прежним runtime gate. Ошибка публикации, удалившая старый cache root,
немедленно сбрасывает недействительную привязку App без CAS проекта.

FULL DIFF review: `RB-DIFF-01` был BLOCK, затем после owner-approved
узкого исправления единственный TARGETED_RECHECK вернул APPROVE, blocking=0.
`go test ./...`, `go vet ./...`, 111 frontend tests, lint, frontend build,
Wails build и `git diff --check` прошли. Windows `go test -race` недоступен
без cgo. Реальный headless React→Wails→Go прогон на одноразовом управляемом
проекте прошёл: preview не писал проект, подтверждение заменило только
`artifactLock.digest` в `project.yml`, inventory остался побайтно прежним.
Целевые серверы не использовались. QA-проекты оставлены в `.runtime/qa/`.
Прямое удаление тестового cache было отклонено политикой среды; вместо него
штатный `publish-bundle` восстановил прежний проверенный digest
`sha256:6eb9d16184caf24f360698df8e626124e5ae0fc35c7d09efef31c676db10eadc`
как единственную запись активного `cache/` и удалил тестовый digest штатной
очисткой. Изменения milestone пока не закоммичены,
общий SI11 installation cycle по-прежнему не завершён.

