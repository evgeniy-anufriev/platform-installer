# A4 — журнал standalone QA

Дата: 2026-10-10. Ветка `codex/application-libraries`, база
`c7dba6b1d80beab78fe797a792f94f4ed4fec298`. Незакоммиченные изменения A4.
Core/Python выполнялись только на RED OS node1 через platform-automation,
persistent EXEC-01 key, IdentitiesOnly=yes, sudo -n. Benchmark не проводился.

## Scope и решения владельца

Vault hook: library shared secrets, instance account documents/policy/AppRole;
Agent в том же контейнере, private RoleID volume и PKCS12 delivery.
AppRole bind_secret_id=false; union source IPv4 /24 плюс 127.0.0.1/32.
Один библиотечный batch и один instance hook, не provider-wide mutation batch.
Go/UI/A5/A6/A7 не реализованы и не считаются принятыми.
Installer использует existing Go age import → SERVICE_ADMIN_TOKEN lease;
standalone — platform_vault_admin_token или private bootstrap admin-token.
age CLI/Python decrypt удалены. Unseal остаётся ответственностью Vault install role.
Owner endpoint rule: https://<fqdn>, implicit 443; direct access uses resolved port.

## Выполненные проверки

- Current source e7676355d0be4cb7b99ca6ddc8b783fd: 56 application Core tests PASS,
  12 Vault provider tests PASS, 25 PostgreSQL contract tests PASS.
- Source 66f15bda5aba47f8b12fbb1e07558fc1: 29 existing Vault role tests PASS.
- Source f7dbaa981b3d4c09bd0f78f0d0bb389e: native full Apply/Verify/repeat PASS.
- Source 66f15bda5aba47f8b12fbb1e07558fc1 after credential revision:
  native full Apply/Verify/repeat PASS.
- Native status: PostgreSQL, PKCS12 truststore, PKCS12 client keystore,
  Vault Agent all `ok`. Rootless UID1000 delivery proven, daemon UID1002.
- Clean repeat changed=0, stable RoleID/container identity, unchanged KV version.
- Existing KV source is read-only; temporary derived password file cleaned.
- Existing PG password mismatch blocks before publication; no password rotation.
- Foreign document owner blocks without KV write; neighbor fields preserved.
- Allowed KV paths readable, other path denied; outside accepted CIDRs cannot
  read secrets. renew-self/revoke-self and container restart checked.
- Agent template alias correction tested: two variables bound to the same KV
  field receive distinct no-output template comments; all required env values exist.
- Protected files/symlink/schema/CAS delta/CIDR normalization covered by unit tests.
- Earlier broad bounded Core run: 541 executed, 522 passed, 19 skipped;
  16 unchanged native PKI recovery cases excluded. This predates final bounded
  credential/endpoint edits, which have focused rechecks above.

Native fixture uses isolated PostgreSQL port28432 and temporary TLS Vault server,
not deployed full-services infrastructure. Reuses existing prepared image
platform-application-connection-probe:qa,
sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb.
No image download/build. Overall /status may return503 because A5 providers are
absent; the four A4 checks must be ok. Fixtures/protected credential values do
not appear in source/project/Compose/safe output.

## Acceptance snapshot before owner-directed continuation

Fixture e7676355d0be4cb7b99ca6ddc8b783fd passed standalone token and plaintext
bootstrap custody through full Core Apply/Verify. At that point HAProxy endpoint
routing, multi-host placement, expiry reauthentication, live CAS retry, and native
missing-field/unsafe-path cases were still open. The later two-host run below
closed the endpoint, placement, renewal, scope/CIDR and restart checks.

No React/Wails acceptance is claimed; those layers are outside A4 implementation.
Independent [FULL DIFF](../reviews/a4-diff-review.md) recorded A4-D01 BLOCK pending native
evidence; the owner authorized its bounded closure and one targeted recheck.
Independent reviewer source identity: 38 paths, sortedUnique UTF-8 without BOM,
lowerSHA256 + two spaces + relativepath, LF including terminal LF:
`4df862f3cd99d163d914d799f9d72fe651e8720a305bf12447182c838087d279`.
Apply/Verify syntax PASS. Two PostgreSQL HBA tests PASS.

Native A3 resources/accounts/verify/repeat regression PASS (one functional case).
No comparison or benchmark series performed; built-in fixture timing output is not
used as speed acceptance evidence.

## Native A4-D01 acceptance — owner-directed continuation

Дата: 2026-10-10. Существующий ограниченный native fixture завершился успешно
(`Ran 1 test in 518.078s`, exit 0) на двух RED OS Docker hosts с rootless Docker.
Результат fixture: `A4_MULT_HOST_ENDPOINT_AND_APPROLE_RENEWAL_PASS`
(hosts=node1,node2; Vault endpoint HTTPS/443), `A4_STATUS_STATES`
(PKCS12 truststore/client keystore, PostgreSQL и Vault Agent — `ok`),
`A4_NATIVE_APPLY_VERIFY_REPEAT_PASS`, `A4_SCOPE_CIDR_RENEW_RESTART_PASS`,
`A4_WRONG_PASSWORD_AND_READONLY_SOURCE_PASS`,
`A4_FOREIGN_DOCUMENT_BLOCK_PASS` и
`A4_STANDALONE_TOKEN_AND_BOOTSTRAP_PASS`. Стенд проверил endpoint-маршрут,
размещение на двух хостах, renewal/restart, scope/CIDR, отрицательный пароль
PostgreSQL, read-only source, foreign document и standalone token/bootstrap.

Повторный точечный прогон текущих Core application tests на RED OS: 15 PASS;
`apply.yml`/`verify.yml` syntax PASS. В текущей Compose-проверке адрес bind
(`127.0.0.1` и `0.0.0.0`) и пользовательские поля принимаются; тест отвергает
подмену Core-образа и опубликованного порта. Полный native fixture выполнялся
до возврата этой сокращённой Core-only Compose-проверки; поэтому его результат
не заявляется как интеграционное подтверждение именно этой последней версии
валидатора. Ее контракт покрыт текущим focused test.

После QA удалены оба временных `/var/tmp/platform-installer-qa-*` workspace,
временный protected log на node1 и QA helper на node2/node3. Временные ключи и
файлы учётных данных не включены в журнал.

На момент этого прогона live CAS conflict и native negative cases для missing
field/unsafe path ещё не были проверены; поэтому A4-D01 оставался открытым.
Результаты их последующей проверки записаны ниже. Benchmark не выполнялся.

## A4-D01 CAS and fail-closed continuation

Дата: 2026-10-11. Текущий worktree на ветке `codex/application-libraries`.
RED OS node1, current working-tree sync, persistent EXEC-01 key and `sudo -n`.
Один native fixture завершился `Ran 1 test in 265.467s`, exit 0.

Проверка создала реальный KV v2 CAS конфликт: параллельный PATCH сохранил
соседнее поле, устаревшая запись получила 400, hook перечитал документ и повторил
только свой delta. Итоговый маркер:
`A4_LIVE_CAS_CONFLICT_RETRY_PASS neighbor=preserved`. Поле пароля совпало с
ожидаемым, соседнее `qa_cas_neighbor` осталось `preserved`.
В том же fixture прошли `A4_MISSING_FIELD_AND_UNSAFE_PATH_FAIL_CLOSED_PASS`,
неверный PostgreSQL пароль, read-only KV source, foreign-owner защита, полный
Apply/Verify/repeat и standalone token/bootstrap checks.

Причина прежнего провала была в границе Ansible `include_tasks`: переменная
`application_vault_cas_retry: true`, заданная в vars самого include, затеняла
переменную, которой его условие пыталось ограничить повтор. Повтор был постоянно
skipped. Теперь первая запись и единичная повторная попытка разделены на
`document.yml` и `document_retry.yml`: retry выполняется только на CAS marker,
перечитывает текущую версию, а второй конфликт завершает операцию fail-closed.
Обычный путь не делает дополнительного сетевого запроса.

Vault provider unit tests: 12 PASS. Apply syntax-check PASS. Отдельная
Compose/Core-валидация не менялась в ходе этого исправления. QA teardown теперь
удаляет только точную detached Compose network текущего fixture; 29 накопленных
сетей с префиксом `a4entry-` были проверены как принадлежащие этому QA fixture и
удалены. После полного прогона тестовых сетей `a4entry-*` не осталось.

Документ §3.1 синхронизирован с принятым owner решением: Installer расшифровывает
.age через существующий Go механизм, standalone получает runtime token или
plaintext bootstrap custody. Актуальный код и предшествующие два-host endpoint/
renewal evidence переданы на ограниченный TARGETED_RECHECK только по A4-D01.

## Owner confirmation — A4-D01 maxTTL reauthentication

Дата: 2026-10-11. Владелец подтвердил, что лично проверил автоматическую
повторную авторизацию Vault Agent по AppRole после истечения `maxTTL`; поведение
работает. По решению владельца оставшийся блокер A4-D01 снят. Это owner-verified
acceptance, а не новый запуск исполнителем и не изменение evidence, проверенного
независимым reviewer: его TARGETED_RECHECK остаётся BLOCK для зафиксированной
ревизии/набора evidence. Значения токенов и секретов не записывались.
