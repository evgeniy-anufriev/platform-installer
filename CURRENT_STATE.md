# Current state

## SI11 Keepalived participant-scoped apply guard (2026-10-06)

The Keepalived Apply playbook now conditions each prepare, activate and
reconcile role invocation on membership in the participant list already used
by the two cluster barriers. Unassigned hosts that remain in
`platform_targets` should therefore not execute service-role tasks. The
existing contract assertion was updated to require all three guards. No test,
RED OS acceptance or Wails run has been performed for this correction; SI11
I05 remains **ПРОВАЛ** until the selected participants pass both barriers and
an unassigned host is proven untouched. The full plan remains blocked by four
`ARTIFACT_SOURCE_OFFLINE_REQUIRED` findings (Kafka and ClickHouse); the active
bundle/cache was not changed, and no server or plan was touched.

## SI11 offline payload candidate prepared (2026-10-06)

The required Kafka archive and three ClickHouse RPMs were already present in
the local DEV artifact input and their SHA-256 values matched the service
artifact declarations. A separate candidate bundle was built from the current
verified runtime plus those exact files and passed the product CLI
`validate-bundle` check. Candidate digest:
`sha256:61c914e6c102c28f3ab08edaa3c4da4d812314dae8cd0fe5357f97bba7587c25`.
It is retained under `.runtime/qa/si11-bundle-candidate-20261006`; the active
cache and project lock remain on
`sha256:6eb9d16184caf24f360698df8e626124e5ae0fc35c7d09efef31c676db10eadc`.
The candidate was imported through the Wails «Проект» screen and explicitly
bound. The UI displayed the old/new digests and matching catalog before the
action, then reported «Набор уже привязан»; the saved project lock now points
to the candidate digest and the active cache contains that digest. The former
project import bundle was preserved as
`.runtime/qa/si11-recovered-20261002/bundle.previous-20261006`. The UI still
shows Execution Node `node1` as not prepared and session credentials as not
set. Preparation, Verify, plan creation and service installation have not
been run with the new bundle; I02/I04 remain in progress.

## SI11 Project Verify diagnostic — prerequisite identified (2026-10-06)

The Project Verify UI now displays the bounded diagnostic code returned by
`VerifyProject` instead of collapsing unknown errors into one message. Go
publishes only structured or explicitly recognized codes; arbitrary transport
and process error text is reduced to `PROJECT_VERIFY_FAILED`. The saved project
is not changed by Verify. Go tests, frontend tests/lint/build, Wails build and
`git diff --check` passed. The earlier failing Verify response was not present
in retained logs. A new read-only Wails Verify on the recovered ten-deployment
S11 project returned `EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED`. The Servers page
showed selected node1 as not prepared and session credentials as absent; this
attempt stopped before Core. The UI now explains the runtime-binding
prerequisite. This does not establish the cause of any earlier READY-node
Verify failure and does not change SI11 acceptance status.

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

## SI11 Vault clean bootstrap reset (2026-10-05, latest)

The Vault role now starts and unseals each follower before querying its
initialized state, and retries the safe readiness GET up to 30 times at two
second intervals. Static names for `no_log` tasks are forwarded as safe event
labels without task output, arguments or results. Focused RED OS checks passed:
event observability 25 tests (4 opt-in skipped), Vault role contract 27 tests,
and Vault Apply syntax-check. A direct standalone Ansible 3/3 Apply and Verify
also completed successfully on all three members (zero failed/unreachable).
This is role evidence only, not the required Wails acceptance.

At the owner's request, the exact three-member Vault deployment was reset with
the standalone `services/vault/playbooks/clear.yml`. Its check-mode preflight
passed against all three trusted SSH host keys. The real clear completed with
`failed=0`, `unreachable=0`; the three exact Vault units are now inactive and
disabled, and each Raft data directory retains only its ownership marker. The
Vault package, configuration, certificates, audit/custody data and other
services were preserved. Swap remains disabled on node1–node3. The temporary
SSH identity used by the controller was removed immediately after verification.

The current immutable bundle `sha256:80fa875772f49ef7869c98a93b0033ca611ddd9c5ae36d668457a2259d71d3ef`
was validated, published and activated on node1 through the real Wails
preparation flow. The isolated Vault project passed verification and a fresh
three-action plan was approved. Wails run
`installer-63fd6a29f7a1287d92c0aa2398019475` reached terminal FAILED during
Vault Verify after PKI and Apply succeeded. The reported failing task on node1
is `Require an explicit or project-root-derived standalone output path`.
The runtime projection contained the correct absolute output path. The Vault
read-only output-path assertion had invalid YAML/Jinja backslash escaping; a
read-only Jinja compilation of the active bundle reproduced `TemplateSyntaxError`.
The one-line guard correction passed 28 Vault role tests and Verify syntax-check
on RED OS. New immutable bundle
`sha256:6eb9d16184caf24f360698df8e626124e5ae0fc35c7d09efef31c676db10eadc`
was validated and published; the isolated Vault project was rebound by the
narrow artifact-lock CAS API. The Vault members were cleared again with the
owned `clear.yml` (`failed=0`, `unreachable=0`), and Wails was restarted so it
could rediscover the newly published bundle. In the real Wails UI the node1
SSH fingerprint was confirmed, the Execution Node reached READY/PREPARED, and
Core verified the new project revision. The fresh three-action plan for
revision `sha256:22d12783505819c11642e8b09c2908fe3b97769e27aa5ad4d1ddc804b8361fe1`
was approved. Run `installer-45c8036f6ec6330cdc5710e8f6b004b7` completed
`SUCCEEDED`/100%: PKI, Vault Apply and Vault Verify passed on node1–node3.
The installer workstation received `admin-token.age`, `unseal-shares.age` and
`complete` under the project `secrets/qa-vault-consumer/`. The receipt names
this exact run, and both ciphertext SHA-256 values match the receipt. Secret
contents were not opened. Isolated Vault Wails acceptance is PASS; the wider
SI11 all-services plan remains in progress.

## SI11 isolated Vault retry after swap removal (2026-10-05)

Owner-authorized QA host preparation disabled disk/zram swap on node1–node3;
the generated `dev-zram0.swap` unit was masked with `--runtime` so systemd
would not reactivate it during the run. `/proc/swaps` was empty on all three
nodes. Through the real Wails UI, the isolated Vault project produced a fresh
three-action PKI/Apply/Verify plan, target SSH keys were confirmed, and run
`installer-397c2f2e9ab0e44711341fc3d9691210` started. PKI completed, but
Vault Apply terminated **FAILED** at sequence 1348 (first failed task 1340).
The seed on node1 and first follower service on node2 were started; node3 was
not reached. The follower wait at task 1339 exhausted retries: node2 Vault
reported `waiting for unseal keys to be supplied`, while the role waits for
follower `/v1/sys/init` to report initialized before it invokes follower
unseal. This is a separate Ansible bootstrap-order blocker, not the earlier
swap preflight. No further run or host reset was attempted. The current run's
bootstrap outputs were delivered to the workstation project as encrypted
`admin-token.age` and `unseal-shares.age`; no secret content was inspected.
Vault acceptance and cumulative S11 remain **BLOCKED** pending owner decision
on the narrow Ansible correction and recovery path. The UI event-name fix is
in the worktree but not yet in the running Wails binary.

## SI11 isolated Vault blocker (2026-10-04)

The isolated Vault project `si11-vault-isolated-20261004` was reopened and
verified through the real Wails UI. Execution Node preparation initially
failed during bundle staging because a previous privileged Python invocation
left root-owned `__pycache__` in the digest-specific staging directory. The
activation command now uses `PYTHONDONTWRITEBYTECODE=1`; the three stale QA
bytecode files were removed, and Wails preparation subsequently passed.
The fresh plan for `qa-vault-consumer` contained only PKI, Vault Apply and
Vault Verify on node1–node3. The owner started run
`installer-e682505fb9474442971ed10522936204` through Wails. It terminated
**FAILED**: Vault Raft preflight `Require host swap disabled for Vault Raft`
failed on all three nodes at events 996–998. Both zram and disk swap are
active on each target; node1 had about 561 MiB of used zram. Vault acceptance
is **BLOCKED**, not DONE. No retry or host swap mutation is authorized yet;
decide how to prepare the QA hosts before another run. The cumulative
all-services S11 plan remains pending. The UI task-list omission of
`task.name` was a separate presentation defect: Core emitted the bounded
field and Go carried it, but the old React list rendered only `safeMessage`.
The merged UI/UX branch now renders `task.name` where present; live WebView
verification of the new build is still pending.

## SI11 reusable PKI project template (2026-10-04)

Through the real Wails UI, created and locally saved a three-server project
(`node1`–`node3`) with portable PKI desired state: managed CA
`qa-isolated-ca`, certificate profile `qa-isolated-server-client` with both
`serverAuth` and `clientAuth`, and TLS profile `qa-isolated-tls` referencing
`runtime:pki-store-password`. Wails exported the project to the ignored QA
template directory
`.runtime/qa/templates/si11-pki-template-20261004`; its export preview listed
four files / 3805 bytes and explicitly excluded session credentials and
runtime data. The exported template was reopened through Wails and the three
PKI entities were confirmed visible. No plaintext password or generated
private key was placed in the project template.

This is reusable PKI **desired state**, not issued certificates. Actual PKI
materialization belongs to a service plan with real TLS consumers. After
opening the export, session credentials were cleared; the approved PEM was
re-entered through Wails and its independently matched host key reconfirmed.
The original bundle `sha256:f1da…c4f6b8c` was superseded for this QA project by
the corrected immutable bundle
`sha256:decb2ada165efeed058e6373a645de09ae3e15e94b6abf0313e92b316e5f0606`.
It was acquired on the trusted RED OS node from the current worktree, passed
the normal validator, and its embedded `deployment_plan.py` matched the
corrected source. The standard publisher placed it in the active bundle cache.
With owner authorization, the CAS-safe `UpdateArtifactLock` API changed only
this project's digest; reopening verified project revision
`sha256:beace1012fd6a2b9f25ee44ba7f3b978835207f4b0788e00d0b7b97f0c0901ea`.
Wails was restarted to load the active bundle; node1 was rebound and prepared
through the UI, and target-free Verify returned `Проверено`. No plaintext
secret was logged. The same project was then used for an isolated Keepalived
plan: deployment
`qa-keepalived-isolated` was saved with node1 and node2 placements. The first
plan was blocked because the provider tuple was absent. Its
`SERVICE_TARGETS_UNAVAILABLE` finding was secondary: blocked topology omitted
`placementsByHost` from the snapshot consumed by the planner. The group and
provider tuple were then copied from the S11 all-services project through the
Wails UI, and a fresh target-free Verify passed. The fresh plan has no findings
and lists node1,node2 for both Apply and Verify; it was approved through Wails.
Start attempts on the old runtime were blocked before run creation by the
target-host trust scope mismatch. Core now scopes private `targetConnections`
to the union of exact action targets; focused planner/trust tests passed and
the authorized targeted independent recheck returned APPROVE. A fresh Wails
plan for revision `beace…01ea` had no findings and listed only node1,node2 for
Apply and Verify. Their SSH fingerprints matched workstation `known_hosts` and
were approved through Wails. Node3 was not probed or approved. Start created
run `installer-94b7b6c9851f03d81fd98df01ae45435`; the Wails Result view reached
`Успешно завершено` after event 279 (`Execution controller completed`). This
is the first successful isolated Keepalived apply+verify run; repeat
`changed=0` is not yet tested. The project is now a working QA project, not a
pristine PKI-only template. **PKI-TEMPLATE-03
is PASSED for bundle availability and target-free Core Verify; certificate
issuance remains unverified.** The earlier generic UI error was resolved by
publishing the already-built bundle and preparing the Execution Node. Detailed
evidence is in the [S11 test journal](docs/service-install-11-test-journal.md).

## SI11 latest Wails run and revised test order (2026-10-04)

The latest all-services run `installer-185fe62605213a283e75eb904172e290`
ended authoritatively **FAILED** at `08:12:33Z` / sequence 3393; this is not
just a stale progress label. PKI, BIND, ClickHouse, DNS client, Docker,
HAProxy and Kafka completed. Keepalived failed at Barrier A
`Assert every participant produced a passing candidate`; PostgreSQL, Redis and
Vault were not reached. The Wails Execution and Result views failed to reflect
the durable terminal result. A host-scope mismatch was found and corrected in
the uncommitted Keepalived playbook: inventory `platform_targets` contains
node1, node2 and node3, while the exact `qa-keepalived` plan action targets
only node1 and node2. Both barriers now share a participant list derived from
the selected deployment's host placement; standalone Ansible derives it from
all Keepalived deployments in the project. A three-host RED OS preflight test
confirmed node1/node2 selected and unassigned node3 skipped in both modes;
13 focused tests and apply-playbook syntax check passed. The correction is now
in the verified `f1da…` immutable bundle, and that runtime is prepared on the
Execution Node. The first isolated Keepalived plan through Wails was blocked
because the provider tuple was absent. After copying the S11 endpoint group
and provider values into this project, saving, reconfirming the Execution Node
binding and verifying again, a fresh plan passed with Apply/Verify targets
node1,node2 and no findings. The plan was approved through Wails; Start was
attempted twice and safely blocked before run creation by the plan-vs-manifest
host-trust scope mismatch described above. Core now fixes the mismatch; the
corrected runtime still needs Wails preparation and a UI Start retry. The initial
historical event does not identify the first
failed loop item, and `failed_when: false` means native-validation SUCCESS
events do not reveal the original validator return codes; a separate
historical validation failure cannot be ruled out.

Owner changed the S11 order: before another full-plan run, test Keepalived,
PostgreSQL, Redis and Vault through separate real Wails plans; then run a new
cumulative all-services plan. Isolated Keepalived now has terminal Wails PASS
for Apply+Verify on node1,node2; repeat `changed=0` is not yet tested.
PostgreSQL is marked successful by the owner after a post-correction runtime
check: node2 primary/node3 secondary, monitor-origin TLS probes to both, and
`pg_autoctl` state without `!`. The historical failed run is preserved; no new
Wails plan was run for the narrow health-check correction by owner decision.
The Redis isolated project has now been rebound through the standard QA runtime
publisher to artifact `sha256:77c1d067dd8d13d1732d91556fd6b21af83826ffffb3f88ec3dd8c0b30880ca5`
and catalog `sha256:2fffcf55c1fda97afa1f712f7b31893f8b81e8ccd1f6909a3666ecfe5bb5cf8b`;
node1 preparation passed. Redis and Vault Wails plans remain outstanding.
Do not start the cumulative plan until they are complete.
Details and acceptance evidence are in the [S11 test journal](docs/service-install-11-test-journal.md).

The owner authorized CLI acquisition as preparation for Wails acceptance. The
corrected bundle was built on the trusted RED OS acquisition node from the
current worktree and initially published to a separate QA cache as
`sha256:f1da6df3aeb4385ed94a499a6f5a0e07fc7213bf96fa0566da767c475c4f6b8c`.
Its Keepalived `apply.yml` SHA-256 exactly matches the corrected worktree file;
the previous bundle/cache was preserved at acquisition time. The exact bundle
has since been verified and published into the active `bundle/` cache using the
standard publisher. Wails prepared the Execution Node against it and target-free
Core Verify passed. A Keepalived deployment was added to the existing project
(no servers were recreated). The initial plan's endpoint findings were fixed
through Wails using the existing S11 all-services values: group
`qa-shared-endpoint` (`qa-renamed.example.internal`), VIP
`192.168.56.111` on `enp0s8`, VRID `42`. After local Save, project Verify first
reported unavailable because the selected node had lost its trusted binding;
the UI explained that node1 was only an untrusted candidate. Its SSH
fingerprint was matched against the existing `known_hosts`, confirmation and
readiness check were repeated through Wails, and Verify then passed. The new
plan for revision `sha256:2d598763478061c15753f08d96a5ef06baef17fc2d3820b062b544e48ba217b1`
has no findings; Apply and Verify targets are exactly node1,node2. It awaits
owner approval and was not started. No service-side changes occurred.

## SI11 role defaults and override precedence (2026-10-04)

The defaults regression observed in failed run
`installer-3c61c99fe1fd0d1bd4988c42837d86b5` is corrected in the active
uncommitted worktree. Core no longer promotes role-default-only values into
the higher-priority runtime `set_fact` map. Kafka only projects explicit
deployment values; absent values use role defaults or ordinary inventory
precedence. The same conditional private-map adapter now preserves standalone
Vault/Redis/PostgreSQL playbooks, and Keepalived advert interval 1 is a role
default. RED OS checks passed: Core 477 tests (19 skipped), Kafka 29, Keepalived
12, Kafka's real Ansible default/inventory/project precedence fixture and
affected playbook syntax. I05 remains **ПРОВАЛ** until a new immutable runtime
is exercised through a fresh real Wails full-plan run; the failed historical
run is not relabeled as passed. Details: [S11 test journal](docs/service-install-11-test-journal.md).

## SI11 PKI reissue implementation gate (2026-10-03)

The owner-approved UI-triggered PKI reissue implementation is uncommitted in
the active SI11 worktree. The five FULL DIFF blockers PKI-DIFF-01 through
PKI-DIFF-05 were corrected under the owner's decision. The one permitted
independent TARGETED_RECHECK returned **PASS** for all five. The corrected
RED OS Core suite passed (473 tests, 19 skipped), as did focused real Ansible
reissue/CA/missing-store tests, Go tests/vet and affected race tests, frontend
lint/tests/build (104 tests), catalog reproducibility and playbook syntax.
The Wails build had passed before these Core-only blocker corrections; no
frontend/backend binding changed in them. No new runtime bundle or S11 run
has been published after this review. Real Wails reissue acceptance and I05
remain open; passing code gates does not mark S11 installation successful.
See [S11 test journal](docs/service-install-11-test-journal.md).

## SI11 restart attempt (2026-10-03)

Owner requested restarting S11 with TLS Server + Client enabled. The saved
`qa-server-profile` was updated and reopened through the real Wails UI; both
usages are enabled. The owner then explicitly chose to reuse the existing QA
servers without clearing them. No server cleanup was performed in this retry.

SSH access was restored: the established persistent EXEC key was found in the
main checkout, and a separate unencrypted PEM QA key was created in the active
worktree's ignored `.runtime/secrets/` and its public key authorized on
node1–node3. All three connections and `sudo -n` were checked. The new key's
fingerprint matched the prior node fingerprints in workstation `known_hosts`;
host-key approval for all project targets and explicit Execution Node binding
were completed through Wails. node1 returned READY.

A fresh Wails plan was built for saved revision
`sha256:ca56a24669eaee851b6b73c2f0a578d71d362d27e48ba9c2de0d96142f057255`,
containing all ten deployments on node1–node3, with no findings, and approved.
PKCS#12 and protected-output passwords plus required ClickHouse, PostgreSQL,
Redis/Sentinel and Docker runtime secrets were supplied through Wails; new QA
values are stored only in ignored DPAPI files under `.runtime/secrets/`.
Start was invoked exactly once through Wails, without cleaning any server. Run
`installer-d471170dcf7d8e11d2325e9596b0364b` reached **FAILED** after 80 events.
The authoritative safe journal on node1 identifies the failure: PKI action
`pki:apply`, task `platform.core.pki_materialize : Require explicit
authorization for certificate reissue`, event 78. Events 79–80 report
`ANSIBLE_OPERATION_FAILED (ANSIBLE_FAILURE_UNCLASSIFIED)` and
`EXECUTION_OPERATION_FAILED`. No service apply action started. The run stopped
at the existing PKI reissue safety guard because the Server+Client profile
changed the certificate-request fingerprint but the plan supplied no explicit
reissue request authorization. No retry was started. I05 remains **ПРОВАЛ**;
the existing reissue operation is not exposed by the Wails plan flow.
See the live [S11 test journal](docs/service-install-11-test-journal.md).

## SI11 latest continuation (2026-10-03)

After QA nodes were cleared and the Windows route conflict was fixed, the
temporary `/32` routes through VirtualBox Host-Only restored SSH. A fresh
approved ten-deployment plan was started through the real Wails UI as run
`installer-3153a7c00ae8b2488cf429fda6a6ce3b`. It ended **FAILED**: event 1435
`Ansible operation failed`, event 1436 `Trusted operation failed before
completion`. Read-only inspection of the retained safe task journal identified
the failing task on all three nodes: `Require HA Keeper TLS listener or skip it
for standalone`, waiting approximately 32 seconds for TCP port 9281. Keeper
units and listeners were active after the run. Their logs repeatedly report
`certificate verify failed` during Raft communication. The node certificates
have valid chains and matching node SANs, but OpenSSL reports `SSL server: Yes`,
`SSL client: No`; client-purpose verification fails as `unsuitable certificate
purpose`. The Keeper configuration presents the same certificate/key as both
server and client TLS identity. Thus the confirmed PKI defect is that a
server-only certificate is reused as the Raft mutual-TLS client identity. The
Wails Result tab still hides the failed task identity and shows only generic
terminal events. No files on the QA nodes were changed during diagnosis and no
retry was started. The correction path is an owner decision: issue a Keeper
certificate with both required TLS usages, or define a separate client
certificate, then regenerate PKI and restart the whole plan. I05 remains
**FAILED**; evidence is in the [S11 test journal](docs/service-install-11-test-journal.md).

The owner-requested one-hour lifetimes are implemented and verified. Focused
Go tests, `go test ./...`, `go vet ./...`, and `wails build -nopackage -clean`
pass. In the rebuilt real Wails app, the session SSH credential showed expiry
`2026-10-03T12:16:35Z`; a newly created and approved ten-deployment plan showed
`2026-10-03T12:19:38Z`, exactly one hour after creation. After target SSH trust
was reapproved through the UI and session-only output, PKI, and eight service
secrets were supplied through their UI forms, Start created run
`installer-a8a85c7eb298a122d1df7803d85e11e1`. It ended **FAILED** with 136 UI
events: event 135 `Ansible operation failed`, event 136
`Trusted operation failed before completion`. The bounded WebView event list
does not identify the failed task, so the cause is unknown; no further run was
started. The earlier `RUNTIME_SECRET_VALUES_UNAVAILABLE` did not recur before
this run, but the failed run does not prove the overall secret/PKI recovery
path passed. I05 remains **FAILED** pending owner direction on diagnosis.

## SERVICE-INSTALL-11 S11-00 DONE — Installer-free QA baseline (2026-10-01)

SI11 is **IN PROGRESS / BLOCKED after the first all-services Start**, not DONE. The
real no-argument Wails UI produced an approved plan for revision
`sha256:5b52f5beec7314555395d363cdb5bf700e2580cf376dcbd613a567b811293ddb`
with ten deployments and node1/node2/node3 as targets, but Start returned a
misleading `PKI_STORE_PASSWORD_UNAVAILABLE` before any run ID. The owner
authorized continued diagnosis. Go now distinguishes missing PKI and service
passwords; React displays the failed Start. The UI secret form was corrected
to include a catalog-required username, and Go now recognizes the saved
two-field reference. Focused and full Go/frontend tests and Wails build pass.
Continuation 2026-10-02: one WebView attempt initially could not renew the
expired SSH credential session because the selected key was OpenSSH format
(`BEGIN OPENSSH PRIVATE KEY`), while the credential field requires an
unencrypted PEM key parsed as PKCS#8, RSA PKCS#1 or EC SEC1. That rejection
explains the resulting `BINDING_REQUIRED`; it was not evidence of a Go/Wails
defect. On a later WebView retry, a compatible PEM credential was accepted,
`node1`'s SSH fingerprint matched workstation `known_hosts`, UI Check reported
READY, and the preparation flow completed its confirmation path. This still
does not prove clean-host runtime delivery because node1 had already received
runtime via separate QA activation. H06/H07 remain in progress for their
uncovered cases; the durable PEM/session preflight is recorded in [AGENTS.md](AGENTS.md)
and the S11 [test cases](docs/service-install-11-ui-test-cases.md). See the live
[test journal](docs/service-install-11-test-journal.md).
Later in the same WebView session, H06 switched from node1 to node2 and back.
Node2 initially required preparation; after in-UI fingerprint approval, the
Preparation plan/confirmation completed, and a fresh Check returned READY.
Returning to node1 required a fresh fingerprint confirmation and Check before
READY was shown again. A narrow exact-prompt UIA handler was added for the
WebView Preparation confirmation. H06/H07 remain partial: the eligibility of
an unprobed server, cancellation, and bootstrap on a separately proven clean
Execution Node have not been covered. In a later WebView run, node3's fingerprint
matched workstation `known_hosts`; read-only Check returned «Требуется
подготовка». The owner-authorized UI preparation completed, and a fresh Check
returned READY. node3 is not a proven clean-host baseline because earlier QA
may have touched it.
H08 now PASSES through the real WebView: ten visible server rows were produced
only as unsaved TEST-NET intents, independently scrolled in both directions
through the UIA scroll-item pattern, and the Execution Node panel heading stayed
at the same screen position. Configuration pages remained available while the
selected draft node was NOT READY, Installation was gated, and Installation
returned when node1 was READY. All temporary server intents were discarded and
are absent from the project.
Seven Docker/PostgreSQL/Redis secret references were saved through UI, while
their values remain runtime-only. A pre-full-plan audit is recorded in the
[Russian test journal](docs/service-install-11-test-journal.md). An attempted
ClickHouse endpoint on an unserved QA group correctly blocked Core planning
and was removed through UI. A later fresh plan reached `PLAN_REVIEW` without
that `SERVICE_SECRET_INPUT_PLACEMENT_INVALID` finding. A pre-I Wails C03 retest found a
verification-status regression: an added runtime-digest lookup revalidated the
dynamic READY binding during an open draft and erased saved-revision evidence.
The lookup is now guarded against active EditSession; focused/full Go tests,
vet and Wails build pass, and real Wails Verify → Review/Save showed
`VERIFIED → STALE`. A second real Wails case changed Certificate Scope's
explicit DNS name and saved; the Certificates screen showed STALE without
presenting the old SAN preview as current. Its initial fallback incorrectly
said "not verified" for STALE; the React status projection and test were
corrected, and the rebuilt Wails retest passed. The test DNS value was
reverted through UI to the original revision, which remains STALE until a
new Verify. C03 now PASSES. The Russian S11 journal includes a description
column for every test case. A fresh Wails plan on the current revision again
reached `PLAN_REVIEW`; eight service passwords plus output/PKI passwords were
submitted through the real UI. The late-created UI Execution Node binding
initially lacked its credential-lease provider; after the narrow Go fix,
Start created authoritative run
`installer-313e1f3cfe2c0c31350871d6915a1df4`. That run ended `FAILED`
at PKI target-directory preparation on node1/node2/node3, before service
installation. During event polling the Windows UI repeatedly opened and
closed console windows, stealing focus; the user closed the app manually.
SSH/host-key child processes now request no Windows console window; Go tests,
vet and Wails build pass, but real UI retest remains pending. I05 remains
FAILED. The run's PKI task failure (`ANSIBLE_FAILURE_UNCLASSIFIED`) is a
separate blocker; no all-services installation has passed.
Read-only follow-up localized the likely cause to private-key target transport:
the lease accepts a private key, but the controller passes only password-mode
credentials to Ansible. The Execution Node has no default SSH private key for
`platform-automation`; node1→node1 without an explicit key returned
`AUTH_DENIED`. The owner authorized a narrow runtime-only leased-PEM adapter.
The first independent DIFF review found `S11-KEY-01` in Cancel cleanup.
After an owner-authorized correction, targeted recheck still BLOCKS: a failed
`systemctl stop` can leave an active controller, while a subsequent
`GetExecution` recovery removes its temporary key from a terminal
`CANCELLED` journal without confirming unit inactivity. The additional
owner-authorized correction to the unit-status query passed 438 Core tests
(19 skipped) on RED OS. A further owner-authorized change now retains
temporary connection files in terminal recovery until unit inactivity is
confirmed. A final owner-authorized narrow correction moved attached lease
cleanup behind the same confirmed-inactive check; the regression now uses a
real attached test lease. The targeted recheck resolved `S11-KEY-01` with
zero blocking findings, and 439 Core tests pass (19 skipped) on RED OS. No
The exact correction was published as a new immutable runtime release
`sha256:79fb40d447c870f0d86d09322489630381e5261325eae6bf6d8c076e9bc6c192`
and activated on node1 through the supported QA path. The real no-argument
Wails app reopened the QA project, confirmed node1 READY, built and approved
a fresh ten-deployment plan for saved revision
`sha256:a964eba760c607e641a03c07c0d90610667abb8b588fd12d246df81e3d52be49`.
Output, PKI and eight deployment secrets were supplied through the UI in
session memory. One Start created authoritative run
`installer-322051a844b4ed5ffc23e4c2594fe76a`, which ended `FAILED`.
The real UI shows task-event pairs only as generic start/completed labels for
`localhost`, then event 135 `Ansible operation failed` and event 136
`Trusted operation failed before completion`. I05 remains FAILED, and no
repeat was started. Narrow safe journal inspection places the failure in
PKI `keytool -list` verification of dedicated PKCS12 stores; its task name is
redacted by `no_log`. A newly generated QA PKI password may not match stores
from the earlier run; this is a hypothesis, not a confirmed product defect.
Password/state diagnosis and another Wails run await owner direction.
After owner authorization, a fresh Wails plan used the existing protected QA
PKI password and produced run `installer-f7d80d6b2d587fc222773a39a528e416`.
PKCS12 verification no longer failed, but the run ended `FAILED` at
`Prepare deployment-owned PKI target directory` on node1/node2/node3.
Read-only diagnosis found that the Execution Node has no
`/var/lib/platform-installer/execution/known_hosts`, while the controller
requires that file with `StrictHostKeyChecking=yes` for target SSH. The same
QA PEM reaches all three targets from Windows; this does not establish
controller-side host trust. No third run was started. I05 remains FAILED;
target host-trust provisioning needs an owner-approved supported path, not
disabled host-key checking.

The owner-approved target host-trust handoff is implemented, but I05 remains
FAILED. The original ignored `.runtime` SI11 project was lost with the archived
worktree; its exact seven-file portable project was recovered from run
`installer-f7d80d6b2d587fc222773a39a528e416` into
`.runtime/qa/si11-recovered-20261002`. Wails confirmed its original revision
`sha256:a964eba760c607e641a03c07c0d90610667abb8b588fd12d246df81e3d52be49`
and three correct target addresses. A bounded Core fix now accepts both
decimal staging IDs and authoritative 32-character hex run IDs when verifying
run-local target `known_hosts`; its focused RED OS regression passed. New
immutable runtime `sha256:ca9a38b1fa0943482633809241726833db218a7df557630531e7713797aef1da`
is active on node1, and the recovered project's lock-set revision is
`sha256:0371f510d8e7c5f8b3e1fe04019595d93630f31795c6194aeca8ef7ecff678d2`.
The real Wails WebView confirmed READY node1, independently matched and
approved SSH host keys for node1/node2/node3, built a clean ten-deployment
`PLAN_REVIEW`, stored a session-only output password and approved the plan.
Start was not pressed: the old SI11 DPAPI credential files were ignored runtime
inputs and did not survive worktree archival. A different older local PKI
password was safely checked against the existing node1 PKCS12 keystore and
returned `MISMATCH`; its temporary remote copy was removed. Recover the
original PKI and service secrets or agree on safe QA PKI/service reset before
another WebView Start. The [test journal](docs/service-install-11-test-journal.md)
records the evidence. No new run ID or installation success is claimed.

The independent DIFF blocker `S11-DIFF-01` is now RESOLVED: the Core private
connection projection rejects `ansible_ssh_host` and `ansible_ssh_port` before
target trust staging can authorize Start. Targeted recheck APPROVED with zero
remaining findings in scope. Core (447 tests, 19 skipped), Go, affected race,
frontend (102 tests), Wails build, catalog/schema reproducibility and scoped
security/diff checks passed. I05 remains FAILED because a real Start with the
new immutable runtime has not yet completed.

The owner replaced the clean-OS snapshot/reinstall requirement with bounded
removal of Installer, Execution Node and QA-installed service state on the
dedicated node1/node2/node3 VMs (`192.168.56.101`–`.103`). This is an
**Installer-free QA baseline**, not a claim of a freshly installed OS.
S11-00 targeted cleanup and final absence audit passed on all three VMs:
QA units/packages/accounts and confirmed service/runtime data were removed;
`/etc/hosts` matches its pre-Installer backup; SSH, passwordless sudo,
systemd-resolved and enabled repositories remain available. The four failed
OS/VirtualBox units are unrelated to Installer services. This is not a claim
that OS settings were restored to a pristine image; see the retained-state
exceptions in the [cleanup record](docs/service-install-11-cleanup.md).
The original S11-00 baseline did not include an installation run; the first
all-services run is now recorded above. [Roadmap boundary](docs/roadmap.md).
SI11 UI test case V02 now PASSES through the real no-argument Wails WebView:
the saved project opened, the session PEM and independently matched SSH host
key were approved, node1 reported READY, and Project Verify reported
`Проверено`. The owner-approved Go staging correction creates the fixed
`/var/tmp/platform-installer/execution-plan` parent safely before the unique
run child. The parent is owned by `platform-automation`, mode `0700`, and
contains no leftover run directories after Verify. Four canonical project file
digests remained unchanged. Focused/full Go tests, vet, Wails production build
and diff check passed. D01/D02 targeted DIFF review had previously passed with
zero blockers; it was not repeated for this bounded staging correction. No
service installation was performed. V02 UI preparation restored the Execution
Node runtime on node1, so its current state is no longer the original
Installer-free S11-00 baseline; a strict fresh S11 restart must re-establish
that baseline first.
[V02 plan](docs/si11-v02-trusted-binding-plan.md) and
[test journal](docs/service-install-11-test-journal.md).
SI11 V03 Verify→Save status correction is now accepted through real Wails UI.
The first run had wrongly displayed `UNVERIFIED` after a committed change.
The owner-approved narrow fix preserves prior verification as `STALE` without
old findings/identity previews, and prevents read-only node/plan status
refreshes during a draft from revoking that evidence. In the rebuilt `.exe`,
Verify showed «Проверено»; a Save changing only disposable
`node2.desiredHostname` changed canonical `inventory/hosts.yml` from SHA-256
`20273344…177129` to `135BFA52…2E7977E` and displayed «Проверка устарела».
Installation remained disabled. The full V03 case now PASSES: a real Wails
repeat showed that an old approved plan cannot Start with an unsaved draft or
after Save changes the project revision. React checks current InstallationState,
plan identity and saved revision before enabling Approve/Start. No service was
installed.
Details are in the test journal.
SI11 V04 now PASSES through the real Wails WebView. Sixteen endpoint-group
intents reached the shared draft limit; a seventeenth action was disabled,
Discard left canonical files unchanged, and reopen showed no QA draft data.
The entry-points page initially omitted remaining command capacity; a bounded
React label now shows the shared used/remaining count. The rebuilt `.exe`
showed `16` used and `0` remaining before repeat Discard. Frontend 80/80,
lint/build, Wails build and diff check passed. No service was installed.
2026-10-03 S11 continuation: real WebView review of Installation tabs found
the internal `READY_TO_PLAN` enum exposed as the summary badge. React now maps
known Installation/plan/run/output statuses to Russian labels and hides unknown
enum values behind safe generic text. Focused InstallationPage tests 13/13,
full frontend tests 103/103, lint/build and Wails `-nopackage -clean` pass;
new executable SHA-256 is
`6D1484DCC7FA2E090C6A00B63A83A8545AEBCC24A0E9C6006609A71FD9A49730`.
The rebuilt no-argument app was opened through the actual WebView flow; the
existing project was selected with its native Wails folder picker. The
Execution Node session was restored through the UI, node1 fingerprint was
matched to the existing `known_hosts` entry and confirmed, and read-only Check
returned READY. The Installation summary then showed «Готов к построению
плана» and no longer exposed `READY_TO_PLAN` (**this narrow localization
check passes**). No project files were changed, no plan was created and Start
was not pressed. Overall L01 remains failed because catalog labels and other
forms still contain English text. The owner has now authorized recreation of
the QA PKI after the prior PKCS12 password mismatch. The only existing reset
path is `ansible-core/playbooks/pki-reissue.yml`; it is not exposed through
Wails and reissues selected leaf requests while retaining the managed CA. SI11
acceptance forbids direct Ansible/Core invocation, so no reset was performed;
owner direction is required on whether this one-time pre-test reset may use the
existing playbook outside acceptance. Full-plan acceptance itself remains
Wails-only.
After `S11-00` is verified, the SI11 installation test must operate
exclusively through the real Wails/React UI. QA scripts that directly call
Wails Go bindings, Go, Ansible or Core, or replace UI/native-dialog behavior,
are forbidden for acceptance. The user-visible interface must support and
show the complete project-to-terminal flow; missing UI capability blocks SI11
instead of triggering a backend bypass. Read-only logs can corroborate, not
replace, the UI result.
The staged, not-yet-executed coverage matrix for **implemented UI actions** is
[SI11 UI test cases](docs/service-install-11-ui-test-cases.md). A hypothetical
project-delete action is not required; it was only an example, not a feature
request. SI11 UI test cases are in progress; the all-services installation
cycle remains NOT STARTED.
S01 navigation now PASSES after a real Wails reopen: all ten structurally
saved deployments open in their own settings from the service list and
Topology. Their install-ready configuration remains S05 work.
S02 now PASSES in real Wails: Vault
`vault-1` port `8301 → 8311 → 8312` stayed off disk until Save, reopened as
`8312`, then was restored through UI to `8301` with exact original project,
group-vars and node1 host-vars hashes. In a separate disposable imported
fixture, editing Keepalived `advertInterval` through the same UI Save preserved
a pre-existing unsupported `advancedConfig` value; reopen showed its presence
but did not reveal raw YAML. The fixture was removed afterward. This is UI
editor acceptance, not install-ready service configuration.
In a separate disposable QA copy, S11 S01 now has ten structurally saved
deployments; the seven newly added service pages opened through the real
Wails UI, but installation topology/settings are unfinished. S11 S06 is in
progress. A disposable QA copy now opens in the real Wails WebView with
immutable bundled defaults visible in input fields and source labels;
unchanged values do not enable «Применить». A new immutable runtime with
target-free Core preview is active on QA node1. The owner also approved
amending one already-applied service-setting command before Save; the real
Wails WebView passed `8443 → 8444 → 8445 → Reset 8443` with one draft command
and no canonical file changes. The subsequent S06 continuation found a Go
blocker: withdrawing the final command left an empty EditSession active.
The owner-authorized narrow Go/React fix now closes that session. A real Wails
repeat confirmed that the draft disappears and node1 host-key/readiness flow
is usable again. The QA topology was then completed enough to expose a Core
member-setting defect: snapshot materialization replaced inventory-owned
member configuration with topology-only members. The owner-authorized narrow
Core fix keeps verified topology identity and member configuration together.
All 426 RED OS Core tests passed; a new immutable runtime
`sha256:821c5a158c58acec79948060b9d3a5674ea442f9e58d56351a20493326f7bb3f`
was published/activated and the disposable QA project's runtime lock set was
CAS-updated. Real Wails reopen and READY node1 then showed the distinct Vault
3-on-1 values `8301`/`8302`/`8303` as member overrides, while deployment
`8300` remained separate and project status remained UNVERIFIED. A real UI
ClickHouse `8443 → 8444 → Save → Reset → Save` test invalidated Core preview
at draft/Save, preserved the UNVERIFIED state, and restored exact original
`project.yml` and group-vars file digests. The draft-only inherited label was
corrected from «Сохранено» to «Задано» and checked in a rebuilt Wails WebView;
the verification draft was discarded without changing canonical bytes.
That repeat exposed a React-only discard defect: after the shared EditSession
was discarded, the service form retained an unapplied input. The form now
resets with the shared draft lifecycle. A fresh Wails WebView run passed
ClickHouse `8443 → 8444` Apply → local `8445` → Discard → `8443` with Apply
and Reset disabled; the canonical project and group-vars SHA-256 values stayed
unchanged. Frontend tests 97/97, lint/build and Wails build passed.
Further real Wails S11 checks passed for Vault member amend/discard, Kafka
enum edit/discard, Docker bounded-string 32/33-character Review boundary,
and BIND Zone pattern admission; all test drafts were discarded and checked
canonical hashes remained unchanged. The first ClickHouse Secrets action
created only SecretRef draft intents and requested a project Save before
session-value entry; that draft was discarded. Its one-time QA value was not
found in any of the seven portable project files, but the full two-step
session-secret acceptance remains open.
The subsequent real WebView two-step ClickHouse test saved only a
`passwordSecretRef` through Review/Save in managed group-vars and then accepted
a fresh session-only value with no new draft. Neither one-time QA value was
found in the seven portable project files; the UI now describes only the
saved reference, not availability of a session value. Real Wails native-file
dialogs rejected a non-Vault JSON and accepted separate synthetic valid-format
JSON inputs for both Vault file requirements without changing canonical
project hashes. The synthetic files are not real Vault credentials and were
not used for installation. Encrypted-file input and event/journal non-leakage
remain unverified, so S04 and S06 are not DONE.
S06 is **IN PROGRESS**: other configuration and secret-safety cases remain.
No installation was started.
The separate S07 navigation correction now lists member-to-host placements
in Topology by services and opens the existing member editor from both
Topology tabs. S07 navigation now PASSES in real Wails after reopening the
saved QA project: all three Vault members on node1 opened their distinct
settings from both tabs, and host-scoped DNS client opened deployment
settings without a synthetic member. No project bytes changed. See the Russian
[SI11 test journal](docs/service-install-11-test-journal.md).
The original disposable QA project has `serviceDeployments: {}`. Its plan has
empty apply/verify phases, not service-installation actions. The UI now
explains empty action lists and displays `serviceDeployment` when present;
the empty-state text passed a real Wails WebView check. A separate future,
nonblocking [UI-UX-01 production-ready design audit](docs/ui-ux-01-proposals.md) covers
the entire interface, including layout density and excessive whitespace.
In a separate disposable QA copy with Kafka, Keepalived and Vault, a real
target-free Wails plan showed all three deployment IDs and the Russian phase
labels. Its incomplete topology correctly left planning blocked; no Start was
attempted. The plan's observed English Core `safeMessage` findings and the
session output-password mismatch error now have bounded Russian React display
text, confirmed in the rebuilt WebView. The broad L01 localization case remains
FAILED because catalog labels and other forms are still open. SI11 I01 now
PASSES, including all four Installation tabs, stale-plan gating and real
deployment IDs in a nonempty target-free plan. I02 remains in progress after
negative and positive session-password UI checks; the application was closed
to clear that session. See the live test journal.

On 2026-10-02, the current Wails retry reopened the recovered ten-deployment
project and selected `node1` through the UI. The PEM session credential and
SSH host fingerprint were handled in WebView; the fingerprint matched the
workstation's existing `known_hosts`. UI Check reported READY. The UI
Preparation plan required confirmation; the confirmation action completed and
the WebView reported `Подготовлен` (project Verify: `Проверено`). An earlier
QA runtime activation on node1 had happened outside WebView and is not counted
as user-flow evidence; the UI preparation result is recorded separately.
A fresh UI plan for revision
`sha256:85b69051d9e86d17c4eb2e2f81afe007ff43d8023a7050f416f0d0a2cb6baad9`
reached `PLAN_REVIEW` for ten deployments targeting node1/node2/node3 with no
Core findings. The missing Docker QA password was generated after owner
authorization, stored only as DPAPI CurrentUser under ignored
`.runtime/secrets/`, and submitted through the `qa-docker` Secrets dialog.
The existing DPAPI output-encryption password was also entered through the UI;
the plan was approved. Start remains disabled pending the PKI store password.
The older candidate PKI password was previously proven MISMATCH against the
existing node1 keystore, so it will not be submitted and no replacement PKI
password will be guessed. No Start was pressed and no new run ID exists. I05
remains failed from the prior run and is blocked before Start pending safe
recovery of the matching original PKI password or an owner-approved QA PKI
reset. L01 remains failed because ClickHouse catalog labels and other strings
are still English. The UI automation pre-action tone remains Windows
`Asterisk` with a three-second warning.

## SERVICE-INSTALL-10 Docker rootless + Compose DONE (2026-10-01)

Owner reassigned SI10 to Docker rootless + Compose; the all-services single-plan
cycle is SI11, now in progress. [SI10 architecture and evidence](docs/service-docker-rootless-architecture.md).
Autonomous RED OS Ansible existing-user/create-user apply, verify and strict
repeat passed (`changed=0`). The two owner-approved DIFF blockers were
corrected and the single targeted recheck passed with zero blockers. Docker's
rootless-extras RPM is `noarch`; its exact manifest requirement was corrected
without weakening the generic source policy. The immutable QA runtime digest
is `sha256:46fbb7be6578c5e5c004188e7ad6b8b4945ab8519365a820374d4d61e8770165`.
Real nonvisual React/Wails -> Go -> READY Execution Node plan/start produced
`installer-b37382a3d07ccc3ce4472f2d251274db` SUCCEEDED and a strict repeat
`installer-5c5f5df7fa464a1f7ace36eae87209dc` SUCCEEDED. The repeat had
PKI/Docker apply/verify SUCCESS, zero CHANGED/FAILED tasks and terminal state
observed through the Wails binding. The selected rootless systemd target,
bridge and user service stopped on LXC stop, rejected manual start before
readiness, restored on late LXC start and recovered automatically after QA
reboot. Compose and mutual-TLS API positive/negative probes passed; rootful
Docker service/socket stayed inactive. Full RED OS Core suite passed 419 tests
(19 skipped), focused Docker tests 2/2 and playbook syntax passed. Go full
test/vet, affected RED OS race tests, frontend lint/67 tests/build, Wails
production build, catalog/schema reproducibility, focused secret audit and
`git diff --check` passed. This is completed SI10 Docker evidence, not proof
that Docker has been installed in the current SI11 all-services cycle.

## SERVICE-INSTALL-09 ClickHouse PARTIAL ACCEPTANCE, NOT DONE (2026-09-29)

Owner requested the next service: ClickHouse 1/1 standalone without Keeper,
then 3/1 and 3/3 with one paired server+Keeper member per replica, TLS on all
enabled protocols and an HTTPS endpoint. The all-services one-plan final
acceptance was subsequently assigned to SI11. Architecture plan:
[SI09](docs/service-install-09-clickhouse-architecture.md). The first FULL
PLAN review identified source-authenticity and HTTPS-authentication gaps; the
owner approved signed upstream repository metadata plus exact RPM checksums,
and the standard ClickHouse `default` password supplied through Installer
Secrets. The single allowed targeted recheck APPROVED both findings with zero
blockers. Four exact `26.8.14.3` LTS RPMs were acquired through the signed
official repository metadata and rehashed after copy into ignored DEV import.
The temporary RED OS acquisition workspace was removed. The ClickHouse service
manifest, generated configuration schema/catalog, and TLS-only Ansible role
were implemented. A RED OS target-free topology/secret
contract test passed for standalone 1/1 and paired HA 3/1; read-only package,
path, unit and listener preflight passed on node1. Apply/verify syntax-check
passed. Direct standalone 1/1 Ansible apply and authenticated HTTPS verify now
PASS on node1; repeat apply PASS with `changed=0`. The standalone run neither
installed the Keeper RPM nor created a Keeper unit; its server unit is active.
The first apply exposed non-traversable shared Execution Node directories, so
the role now uses dedicated ClickHouse roots. A service-start race and a
systemd template newline defect were corrected before the passing repeat.
An immutable ClickHouse runtime is published. The terminal real-bridge
acceptance remains incomplete as detailed below.
The first direct HA 3/1 attempt stopped during package installation: the
official Keeper RPM conflicts with the official server RPM on the same host.
The installed pinned server RPM already owns a working Keeper executable.
The service package closure was narrowed to common-static,
server and client; HA now checks the Keeper binary's RPM owner before
starting distinct Keeper units.
Direct Ansible HA 3/1 now PASS on node3: three server plus three Keeper units,
one row replicated across all three authenticated HTTPS members, and repeat
apply `changed=0`. Direct Ansible HA 3/3 also PASS on nodes1–3: one paired
member per host, a row written on node1 visible from all three, and per-host
repeat apply `changed=0`. With only the owned node3 server+Keeper units stopped,
nodes1–2 committed and read a second row; after restoring those exact units,
node3 read both rows. A strict `interserver_https_host` value from each member
address was required for verified interserver TLS. This is direct-Ansible
evidence. The corrected immutable QA release
`sha256:e0665a237c99ae18c3501ec088abaafcdc12a033e0d7b17dabee9983c01d76b1`
is activated READY on node1. The cumulative saved project revision is
`sha256:5afa228cea02912cc07351e1864fce9a89fea435dbc6bfa40785c0deb2a002b5`.
Real nonvisual React/Wails built and approved plan
`plan-4a9a1b6e6ede9da9d358a8ce`, then started
`installer-f1c76b8b08a861e5cd10257ddc679809`. This cumulative full-plan
run terminated FAILED at `apply:service-install-04-haproxy`, after ClickHouse
apply SUCCEEDED. The HAProxy TLS probe had supplied empty stdin to
`openssl s_client`, which could wait until timeout despite valid TLS. The
bounded fix supplies `Q`; focused RED OS tests and syntax-check pass. The
corrected HAProxy direct apply passed on all three nodes after an exact
active-to-temporary-candidate recovery of the failed prior attempt. This
manual QA recovery is not a general production recovery fix.
The earlier full-plan run `installer-f477972a2d8afd831e67e2f07f119963`
FAILED at Vault audit-space preflight: node1 had ~0.8 GiB free against its
1.6 GiB requirement. Twelve old inactive QA runtime releases were removed
after checking active release and terminal run state; node1 then had ~3.1 GiB
free. This failed run is not acceptance. The SI09-DIFF-01 targeted recheck
APPROVED the bounded ClickHouse path-safety correction, zero blockers.
ClickHouse direct 3/3 verify passed on immutable release
`sha256:4c87562e21981f4cc5ec742dacf1d6f010ea89cf8da2175665aa5c55d48fcec0`
(READY on node1), saved revision
`sha256:4f969e072089c76579be1c22be2193ff287516559f13f1158cdf6d7a74b82536`:
node1/node2/node3 each `ok=67 changed=0 failed=0`. A strict direct repeat
ClickHouse apply passed with `changed=0` on all three nodes (156 OK per host).
The canonical server and Keeper units are active on each node. BIND on all
three nodes resolves the ClickHouse name to VIP `192.168.56.121`; each HAProxy
has the ClickHouse 3-member backend with CA and hostname verification, and an
HTTPS `/ping` through DNS/VIP/HAProxy returned 200. This is isolated service
and endpoint evidence, not a terminal PASS of the full UI lifecycle.

The owner explicitly declined another cumulative full-plan run and requested
partial acceptance. Therefore the required real React/Wails -> Go -> Execution
Node terminal PASS is absent: SI09 remains NOT DONE. The next formal gate is a
new terminal PASS and strict repeat through the real bridge, if later
authorized. SI10 is Docker acceptance as recorded above; SI11 is now in
progress, with no all-services installation run yet.
Owner deferred generic scoped endpoint-provider execution to the separate
NOT STARTED `EXEC-PLAN-SCOPE-01` milestone after SI09 functional QA. Current
full-plan execution must not be misreported as selective provider reconcile.

## SI08-F Vault endpoint HA technical acceptance DONE (2026-09-29)

New managed 3-host project `project-e74f53b99dd648d4` pinned to immutable
runtime `sha256:9b0beb40e91b1a1beb20d14096ecd6a45c09274053b6f0bdf412a8424e7a6e3c`.
Canonical project revision stayed
`sha256:5e9c6fc52f0c760a15083b797831f4122ca87d17426f14c277dea07f0a65e6cb`.
Real nonvisual React/Wails opened the project, imported protected Vault inputs,
built/approved plan `plan-7ef0fd3def229115d95c955f`, started and observed
both runs through the supported Wails Go methods. Initial run
`installer-56f9aa6637457b0bcf119b6b3abfa0f4` SUCCEEDED in 35m55s;
strict repeat `installer-06510ac6068d9b7a695599d14850d32e` SUCCEEDED
in 40m54s, with all nine actions SUCCESS, 0 CHANGED, 0 FAILED and no event
sequence gaps. Repeat task counts: 1564 SUCCESS, 427 SKIPPED.

Post-initial-run audit found that new project BIND serial 1 equaled the old
served zone's serial 1; secondaries had not transferred the new content. The
explicit audited `recover_dns_lifecycle` operation used prior fingerprint and
three observed SOA serials to advance the persistent new-project serial to 2.
All three DNS nodes then answered the endpoint FQDN with VIP 192.168.56.121,
SOA serial 2. No manual zone file edit or automatic cross-project state
adoption was used. This is an explicit QA migration, not normal apply behavior.

Three current Vault units are active and unsealed. HAProxy has identical
three-target backend fragments on all nodes, validates with `haproxy -c`,
and uses `ssl verify required` with endpoint `verifyhost`. File audit, KV v2,
userpass, three Raft voters, authenticated KV through DNS/VIP, leader
step-down, active-node loss, marker continuity and restored/unsealed 3/3
cluster all PASS. Core full 416 OK (19 skips); affected BIND/HAProxy/Vault,
Windows Go/vet/frontend/Wails, RED OS affected race, catalog/schema and
secret-event audit PASS. Six exact remote QA workspaces removed. Full evidence:
[SI08-F](docs/service-install-08f-vault-endpoint-ha.md). SI09 has NOT started.
The SI08-F source, runtime, Installer and QA changes are recorded in focused
commits `f23fb9a`, `d1c0612`, `d1df02d`, `c6f066b`, `2b67ed8` and
`9773413`. SI09 still requires a separate owner request.

## SI08-E Vault technical acceptance PASS (2026-09-28)

Initial real React/Wails 3/3 run installer-810aa4cf27d26af17702df266bcf9959
FAILED after 1674s, terminal sequence 1040. PKI PASS; bootstrap started three
members, but cluster-wide file audit enable ran concurrently on three hosts.
One POST succeeded and two FAILED at task sequence 1000/1002 after all three
had read the mount as absent. No Raft reset or data deletion occurred.
The failed-run bootstrap package was delivered/ACKed encrypted through real
React/Wails into secrets/vault-qa-ha33/ and retained for safe recovery.

Owner-authorized bounded correction: configure.yml admission now runs only on
the canonical seed inventory host under the existing deployment lock. No new
cluster state model, protocol or TLS bypass. Fresh RED OS Vault suite 22 PASS
(3.078s), including real Ansible Conditional 1/1 and 3/3 host gating.
Catalog/schema reproducibility, verifier syntax, Go full suite/vet PASS;
helper QA workspace cleaned. Immutable release qa-si08-vault-20260928-16
published/activated READY with digest
sha256:fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4;
catalog unchanged. HA 3/3 project advanced through guarded CAS, revision
sha256:78e13c9ebc0663e13ad59cb38af108300e917a5276cf185e95effc8be3d77b7e.
Fresh real React/Wails READY/encrypted imports/plan/approval/Start:
plan-a15dd43ccacbf164e776c818,
run installer-d47eaabb277d6ae029eaa4bcd45a1d79 SUCCEEDED in 1879s
(31m19s), terminal sequence 1366. PKI/apply/verify SUCCESS at 175/1057/1365.
Task journal: 697 SUCCESS, 163 SKIPPED, 0 CHANGED, 0 FAILED, no sequence
gaps or observability degradation. Cluster-wide configure ran on seed only;
followers skipped it. No new bootstrap package. Validated TLS health on
.101/.102/.103: initialized and unsealed, one active/two standbys, same
cluster ID; authorized API shows file audit, KV v2, userpass and 3/3 Raft
voters. A distinct fresh React/Wails strict-repeat run
installer-bc5136d6f92f24e8b28ab57ea25dff4a SUCCEEDED in 2335s
(38m55s), terminal sequence 1366. PKI/apply/verify SUCCESS at 175/1057/1365;
697 SUCCESS, 163 SKIPPED, 0 CHANGED, 0 FAILED, no sequence gaps or
observability degradation. Result NO_NEW_PACKAGE.

Protected installer-side token was used transiently for bounded TLS QA. File
audit, KV v2, userpass and 3/3 voters PASS. Fixed nonsecret KV marker was
written/read, leader stepped down from node1 to node2 via Vault API (HTTP 204),
and marker remained readable. Exact node1 vault-hb-1 unit restarted; health
observed initialized/sealed HTTP 503. Two protected shares explicitly unsealed
it (progress 1 then sealed false). All three returned unsealed/healthy, node2
active and node1/node3 standby; marker persisted, including read via restarted
node1; 3/3 voters remained. No other Vault deployment unit was restarted.

Temporary QA SSH admission removed exactly once on .101/.102/.103; owned
Wails/Vite stopped. Windows Go suite/vet, frontend 67/lint/build, production
Wails build, RED OS Vault role 22, catalog/schema reproducibility and standalone
Ansible apply/verify syntax-check PASS. Full RED OS Core suite 397 OK with 19
skips (458.414s). Journal allow-list audit for both 3/3 runs and 3/1 repeat:
0 forbidden fields. Initial parallel Core/race attempt overloaded .101;
sequential race still hit OOM (test process killed at ~1.65 GiB RSS with
other services active). A `GOMEMLIMIT=512MiB`, `GOGC=20`, one-worker retry
also reached only 36 MiB host memory available and was explicitly stopped
before another OOM. Focused RED OS race for Vault input parsing PASS;
`internal/runtimesecret` and `internal/executionnode` race PASS. The single
highest-memory age test also OOM-killed on .101 (~1.67 GiB RSS), confirming
that node cannot safely run the package while neighboring services stay active.
The current-source `internal/secretfiles` race binary was built on .101 with
`CGO_ENABLED=1 go test -c -race`, transferred as one ELF artifact to .103,
and SHA-256 matched before execution. Both nodes are RED OS 8.0.3 x86_64;
.103 had 3.2 GiB available and no Go/toolchain install was needed there.
The complete package test binary ran on .103 with `-test.count=1` and the race
detector enabled: PASS, exit 0. This closes the full affected RED OS race gate
without touching other deployments, enabling swap or waiving any test.
Both exact temporary QA workspaces were removed. Post-test TLS health still
shows the HA node on .103 initialized/unsealed/standby. SI08-E technical
acceptance is DONE. Pre-existing unrelated worktree changes remain; do not
claim a clean repository or start SI09 automatically. Runtime swap masks on
QA hosts remain only until reboot to keep active Vault nodes compliant; no
permanent host policy change was made.

## SI08-E HA 3/1 strict repeat PASS (2026-09-28)

Fresh real React/Wails plan/approval/Start/observe/result run
installer-6bc5e5fccb90d4eb458c926decc8026b SUCCEEDED in 2081s (34m41s),
terminal sequence 942. Saved revision and release -15 unchanged.
PKI/apply/verify action SUCCESS at 149/761/941. Authoritative task journal:
361 SUCCESS, 105 SKIPPED, 0 CHANGED, 0 FAILED; zero sequence gaps and no task
observability degradation. Result READY/NO_NEW_PACKAGE. No reset/reinit.
HA 3/1 strict repeat acceptance is closed. HA 3/3 and final failover/restart,
service/full regression gates remain pending; SI08-E overall is NOT DONE.

## SI08-E follower recursion corrected; HA 3/1 resumed (2026-09-28)

Owner-approved narrow correction removes the redundant self-referential
vault_member vars mapping in bootstrap_follower.yml; nested unseal inherits
the existing outer loop member. RED OS Vault role suite 21 PASS (2.535s),
including real Ansible Templar identity/endpoint checks for co-located and
distributed followers. Catalog/schema reproducibility and verifier syntax PASS.
Go full suite/vet PASS; helper QA workspace cleaned; diff check PASS.
New immutable release qa-si08-vault-20260928-15 published/activated READY:
sha256:c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03.
Catalog unchanged. HA 3/1 lock advanced through guarded promotion CAS;
saved revision sha256:ddf3f1e2c8248810ae69c30b08a963f3b00a7061f71a72d89fa434a9004f70e4.
Previous failed-run bootstrap package delivered/ACKed through real React/Wails
into secrets/vault-qa-ha31/ as encrypted admin-token.age/unseal-shares.age.
Both files imported through actual React handlers into the runtime-only session.
Fresh plan plan-c0ccd228d15b7c1481d0b0f1 approved; real React/Wails Start:
installer-1fc2dacbcb428c7ebf2375f981086e12 SUCCEEDED in 2160s (36m),
terminal sequence 942. PKI/apply/verify SUCCESS at 149/761/941.
Task counts 367 SUCCESS, 98 SKIPPED, 1 CHANGED, 0 FAILED; no sequence gaps
or observability degradation. Single change starts previously unstarted follower.
Three HA units ACTIVE; TLS health initialized/unsealed, one leader/two standbys,
same cluster identity. Standalone remains ACTIVE. No reset/reinit.
Result READY/NO_NEW_PACKAGE. Correction evidence:
docs/service-install-08e-follower-unseal-fix.md. Strict changed=0 repeat and
HA 3/3 still pending. Narrow correction committed as a3e58ab. Owned dev/harness
stopped and temporary session RSA admission removed. Other existing worktree
changes remain outside that focused commit; no overall clean/DONE claim.

## SI08-E HA 3/1 retry blocked by recursive follower variable (2026-09-28)

Owner-authorized swapoff alone did not persist even within the boot:
systemd reactivated dev-zram0.swap on all three QA hosts. Applied reversible
runtime masks for dev-zram0.swap, systemd-zram-setup@zram0.service and
dev-sda3.swap, then swapoff; /proc/swaps header-only verified on all hosts.
No fstab/vendor zram configuration change; reboot removes runtime masks.
First retry bridge was missing explicit bundle binding; no run was created.
Relaunched with the established trusted QA binding and immutable release -14.
Actual React/Wails READY/fresh plan/approval/Start accepted:
run installer-10817d1d0930fd2a6836bd49f7083c00 FAILED after 1757s,
plan-f42ff4c2a085d32a8102c50b, revision unchanged from the HA 3/1 project.
PKI stage complete; swap preflight SUCCESS at sequence 464. Follower start
and initialized join check passed; first nested unseal task FAILED at 684,
terminal sequence 690. bootstrap_follower.yml passes a self-referential
vars mapping vault_member: "{{ vault_member }}" into unseal_member.yml.
Real RED OS Ansible Templar reproduced AnsibleError/recursive=True for that
mapping. Narrow proposed fix: remove the redundant mapping and inherit the
existing outer loop variable. No production correction made during acceptance.
No terminal HA PASS claimed. Seed initialized; first follower started;
data/bootstrap custody and committed run evidence preserved, no reset/reinit.
Owned Vite/Wails/harness stopped; temporary session RSA admission removed.
HA 3/3 remains NOT STARTED pending this role defect correction and HA 3/1 PASS.

## SI08-E HA 3/1 blocked by host swap; HA 3/3 prepared (2026-09-27)

Owner authorized sequential HA 3 nodes/1 server, then 3 nodes/3 servers.
Separate managed QA projects preserve the accepted standalone deployment.
HA 3/1 project project-216b2b909b937158 uses vault-ha-1..3 on node1 and
API/cluster ports 8300..8305. Real React/Wails fresh plan approval/Start:
plan-f42ff4c2a085d32a8102c50b, saved revision
sha256:4cd738232e51d472a1aa5530501bf9926c4aecc04ee013d691db40c48790ac14,
run installer-6b3a3e1ee1ffac82ee36167cc207bde9 FAILED after 639s,
terminal sequence 470. Vault preflight task failed at sequence 464:
VAULT_SWAP_ENABLED; node1 has active /dev/zram0 and /dev/sda3 swap.
Release -14 remains unchanged. No HA PASS claimed; no bootstrap occurred.
HA 3/3 project project-62473d1453874107 prepared through the existing local
EditSession/writer, Core plan plan-a2396817cf2a0cff99520cfc EXECUTABLE.
It uses vault-hb-1..3 on node1..3 and API/cluster base ports 8500/8501.
HA 3/3 execution NOT STARTED; waits for HA 3/1 acceptance.
All three QA hosts accessible with the established execution identity.
Temporary session RSA admission removed; owned Vite/Wails dev processes stopped.
Standalone unit remains ACTIVE. No standalone clear/reset or host swap change.
Owner authorized disabling swap on all three QA hosts. Executed swapoff -a
on .101/.102/.103; /proc/swaps header-only and Swap=0 verified on each host.
Available memory after disabling: approximately 1899/2337/3293 MiB.
This is current-boot state only: fstab/zram boot configuration is unchanged,
so reboot can reactivate swap. HA retry remains pending; no preflight bypass.

## SI08-E standalone repeat full plan PASS, changed=0 (2026-09-27)

Owner-approved transient lock recap correction real-proven. Actual React/Wails
run installer-d58d310393ae11ca56d6ff26c7dbd619 SUCCEEDED after 1508s
(25m08s), terminal sequence 902. Fresh plan plan-6240efc2d7659001c91933c5;
saved revision sha256:63dc5e487a0406782b37457cf5955393cbba3e0088504d56b5b8c0a1f573c21d.
Immutable release qa-si08-vault-20260927-14:
sha256:e80e44d23c8c61a1be3f6a2e970e6d7da218bb1aed917fddb75774fe2174c325.
PKI/apply/verify SUCCESS at sequences 149/721/901; task journal has 341 SUCCESS,
105 SKIPPED, 0 CHANGED, 0 FAILED. Hold/release now SUCCESS, lock readiness and
always-release still execute. No active transient Vault lock holder remains.
Vault ACTIVE/initialized/unsealed/leader, health HTTP 200; no reinit or data reset.
Result output list READY/NO_NEW_PACKAGE, appropriate for initialized repeat;
original encrypted custody preserved. Owned dev/harness stopped, temporary RSA
removed. Helper QA workspace cleaned. Standalone repeat gate is closed;
SI08-E overall still pending HA 3/1, HA 3/3/failover and final acceptance gates.

## SI08-E owner-approved lock recap correction under acceptance (2026-09-27)

Only transient lock hold/release now reports changed_when:false; ownership,
readiness/contention, fail-closed admission and always release unchanged.
Persistent directories/config/PKI/packages/data keep real change reporting.
Fresh RED OS role suite 20 PASS (2.061s); real isolated lock contention,
ordinary release and failed-holder recovery PASS, exact test artifacts cleaned.
Apply syntax/catalog/schema PASS, helper QA workspace cleaned.
New immutable release qa-si08-vault-20260927-14 activated:
sha256:e80e44d23c8c61a1be3f6a2e970e6d7da218bb1aed917fddb75774fe2174c325.
Saved revision sha256:63dc5e487a0406782b37457cf5955393cbba3e0088504d56b5b8c0a1f573c21d.
Fresh full React/Wails repeat underway; changed=0 not claimed until terminal.

## SI08-E standalone full React/Wails plan SUCCEEDED (2026-09-27)

Exact PKI verify correction real-proven: Vault verify imports existing shared
Core pki-verify.yml, reconstructs derived PKI requests/plans in its own process,
checks chain/fingerprint read-only, then verifies Vault TLS health/audit/KV2/auth.
Run installer-a31ff651ccf90db5d83d5acbb75494f8 SUCCEEDED after 1312s,
terminal sequence 902. Plan plan-1229e0c17b8d70e3ca1c8e6f; saved revision
sha256:57a71854492b2f7e23fe9b718996692e9d99a0c5159eb5fddef108f7ebdb9612.
Release qa-si08-vault-20260927-13:
sha256:31ef6e223a6c76330b179cc7629094232f6b7e15807ee33090caf1d686c92569.
PKI/apply/verify action SUCCESS at sequences 149/721/901. Real React flow:
open -> READY -> encrypted input import -> fresh plan -> approve -> Start ->
observe -> Result/output list READY, NO_NEW_PACKAGE for initialized repeat.
Task results: 339 SUCCESS, 105 SKIPPED, 2 CHANGED, 0 FAILED. CHANGED only
transient lock hold/release (372/712); strict repeat changed=0 NOT achieved.
Vault ACTIVE, initialized/unsealed/leader, health HTTP 200. No reinit/data reset,
TLS bypass or new evidence persistence; existing custody preserved.
Owned dev/harness stopped; exact temporary RSA removed, helper QA workspace
cleaned. Full SI08-E remains incomplete: lock recap semantics, fresh repeat,
HA 3/1 and 3/3/failover, remaining final acceptance gates. No overall DONE claim.

## SI08-E shared read-only PKI verify import correction (2026-09-27)

Vault verify missed the existing pki-verify.yml import used by Kafka/PostgreSQL.
Added that shared import after validate.yml, before Vault verify-only role.
Core resolves PKI requests/plans anew on the controller and verifies target
chain/fingerprint read-only; no new persistence, transport or Go-derived paths.
Fresh RED OS: 19 Vault tests PASS (1.859s), 3 consumer selection tests PASS
(8.255s), 12 PKI resolver tests PASS (0.048s); verify syntax/catalog/schema PASS.
Exact helper workspace cleaned. Supported immutable release -13 activated:
sha256:31ef6e223a6c76330b179cc7629094232f6b7e15807ee33090caf1d686c92569.
Saved revision sha256:57a71854492b2f7e23fe9b718996692e9d99a0c5159eb5fddef108f7ebdb9612.
Real React/Wails READY/encrypted imports accepted; full plan retry underway.
Terminal success and strict repeat/HA acceptance not yet claimed.

## SI08-E audit fix proven; separate verify PKI selector blocker (2026-09-27)

Run installer-5f3974b945758ad381f9dee706351b7d on release -12 completed
FAILED after 1309s, terminal sequence 826. Plan plan-519730a358b82c118cda6130;
saved revision sha256:00c1bc110338d41c79c16a672d9887e00f32c344369fdd69b92de60e7a5a2cd8.
PKI action SUCCESS, Vault apply action SUCCESS (sequence 721), including
existing audit admission and in-apply health/audit/KV2/userpass verification.
Owner-requested log_raw representation defect is corrected and real-proven.
Separate verify action fails selecting exact materialized PKI consumer plan:
select_consumer_plan.yml Require one exact PKI consumer plan FAILED at 824.
No TLS bypass/path guessing introduced; next correction must use existing
Core-owned PKI evidence in read-only verify across independent action processes.
Changed-task evidence is 2, both transient lock hold/release, not changed=0.
No unrelated idempotency fix made as part of log_raw correction.
Owned dev/harness stopped, exact temporary RSA removed; data/custody preserved.
Full standalone/repeat/HA acceptance remains blocked; no DONE/clean/commit claim.

## SI08-E audit false representation correction validated (2026-09-27)

Owner-authorized narrow fix: new audit requests use string 'false'; configure
and verify accept only false/'false' (existing case folding) or legacy '0',
preserving absent-option default. Unknown/true/null/collection values rejected;
no broad bool coercion, no existing audit rewrite or disable/re-enable.
Fresh RED OS role suite 18 PASS (2.347s), including 40 real Ansible conditional
positive/negative cases; apply/static verify syntax and catalog/schema PASS.
Go full suite/vet PASS, helper QA workspace cleaned. Supported immutable release
qa-si08-vault-20260927-12 published/activated:
sha256:1fbe82af9044d93cc68a898e7be8bda84b351f2ca671173bec5dcb0ecbcc98b6.
Saved revision sha256:00c1bc110338d41c79c16a672d9887e00f32c344369fdd69b92de60e7a5a2cd8.
Real React/Wails READY/encrypted imports PASS; new acceptance underway.
Full terminal apply/verify/repeat/HA success remains pending.

## SI08-E existing audit-option representation blocker (2026-09-27)

Fresh actual React/Wails run installer-bd14ba46f1db62f80dbba808cb45988e
FAILED after 921s, terminal sequence 690. Same current saved revision/runtime;
READY, encrypted imports, fresh plan/approval/Start all accepted.
Existing Vault unseal after reboot SUCCESS; no reinitialization. PKI tasks
SUCCESS. Configure read SUCCESS, incompatible-existing-configuration assert
FAILED (redacted ANSIBLE_TASK_FAILED at sequence 684). Bounded read-only API
proves file audit expected path, KV2, userpass; audit options.log_raw is string
"0", not "false". Current configure/verify guards accept only textual "false".
Exact representation mismatch blocks apply; do not weaken to arbitrary bool
coercion or silently mutate existing audit. Need bounded producer/read-back
parity correction and positive/negative proof before another acceptance run.
Normal always cleanup released this run's transient lock. Health HTTP 200,
initialized/unsealed/leader, canonical unit ACTIVE. Full verification not DONE.

## SI08-E QA node restored after power loss (2026-09-27)

.101 SSH restored. Actual React/Wails observer returned INTERRUPTED:102 for
installer-be9d767e41344a215fc2c9ef54877945 after 564s. No successful terminal
apply/verify claimed. Vault canonical unit ACTIVE, initialized=true, sealed=true
(Shamir restart behavior), health HTTP 503. Existing encrypted token/shares
preserved; next fresh plan uses them to unseal, never reinitialize.
Restarted owned Wails dev process to replenish bounded file-selection queue.
Full standalone/repeat/HA acceptance remains pending.

## SI08-E QA Execution Node powered off during acceptance (2026-09-27)

Supported immutable release qa-si08-vault-20260927-11 published/activated:
sha256:41c8d8a6e287dc69da063cba2f4dacfe081832ee38a6d02c52b4715f1cf6701d.
Saved revision sha256:0632608cc975dda517e1d7dfa3da12fad0fd9332194542962a577a6c17def598.
Real React/Wails READY, both encrypted inputs STORED, fresh plan
plan-d773b7fc52a8168128fad5c4 approved; Start returned STARTED for
installer-be9d767e41344a215fc2c9ef54877945. Last authoritative observation:
RUNNING, sequence 101, persistent PKI directory preparation.
QA VM RedOS-8.3-1 (.101) powered off at 2026-09-27 17:58:17 UTC;
VirtualBox confirms poweroff, TCP/22 unavailable, peer .102 cannot reach it.
.102/.103 remain SSH-accessible. Terminal result cannot currently be observed;
do not classify this run as PASS/FAILED from the transport failure.
Read-only API before outage confirmed file audit, KV2 and userpass enabled;
audit log_raw=false was NOT confirmed and needs exact safe inspection.
No data reset/reinitialization, journal cleanup or duplicate Start performed.
Full standalone/repeat/HA verification remains pending. SI08-E is not DONE.

## SI08-E dynamic verify parse defect corrected (2026-09-27)

Run installer-faf5ea3d4b99ee18aefb692fa25d27a2 FAILED after 1618s. Corrected
token/API configure tasks all SUCCESS; next dynamic include of verify failed
before any verifier task event. Exact source defect: verify.yml had fail_msg as
a task action sibling instead of an ansible.builtin.assert argument. Fixed that
indentation only; added static import_role tasks_from=verify syntax playbook and
focused module-shape regression. Fresh RED OS static verifier syntax PASS,
16 role-contract tests PASS (1.179s). No infrastructure rule/schema redesign.
Parser abort left a transient lock-holder. Exact unit ownership proved by failed
run state, event timestamps, active-enter time and fixed flock path/command;
only that helper stopped. Canonical Vault ACTIVE/unsealed/health HTTP 200,
no reset/reinit or data loss. Harness/dev stopped, temporary RSA removed.
New immutable runtime promotion/retry underway; full verification still pending.

## SI08-E full verification resumed (2026-09-27)

Supported QA promotion built/published/activated qa-si08-vault-20260927-10:
sha256:3cc0a48f9722f344fd14103b199dd1137b482c1bfa56a723fbf46d09a53af9d5.
Catalog unchanged: sha256:a460d77a38b7134f9a1639871eeb925a3ce8d673df3bfa5dcc1a40a22ada86d3.
Guarded lock-set update of the isolated QA project produced saved revision
sha256:46c94b17520915df19939b6661b8a108295bff67131ae15617464e0f51d34e9c.
Actual React/Wails: READY, corrected token/original shares STORED, fresh plan
plan-705a4c74638ef4e22f497d86 approved, Start STARTED;
run installer-faf5ea3d4b99ee18aefb692fa25d27a2 currently RUNNING.
No terminal apply/verify/repeat success yet. Known Wails dev overlay exception
persists; not clean UI acceptance. Read-only SSH to .102/.103 succeeds, no loaded
Vault units observed there. No reset/reinit or target cleanup performed.

## SI08-E header-token defect corrected (2026-09-27)

Cause proven: producer appended LF to admin-token; raw import preserved it and
HTTP header construction failed before requests. Read-only exact-LF control
returned HTTP 200 for sys/audit, sys/mounts and sys/auth. Owner-authorized fix:
Ansible writes exact token bytes without LF; raw/JSON/age import rejects CR/LF
without trimming or normalization. Existing custody no-overwrite/no_log retained.
Explicit QA correction created secrets/vault-qa-standalone/admin-token-corrected.age,
removed exactly one trailing LF in memory, verified encryption/readback and
unchanged original admin-token.age. Original receipt/ciphertext not overwritten.
Corrected-file API probe: all three HTTP 200, no CR/LF; actual React/Wails import
of corrected token and original shares STORED, READY PASS. No new Start in probe.
Full Go/vet/diff check, production Wails build (13.813s), catalog/schema
reproducibility, Vault apply syntax-check PASS. RED OS bootstrap/recovery:
6 tests PASS (367.718s); Vault role contracts 15 PASS (1.104s).
Independent scoped DIFF APPROVE, 0 blocking/overengineering;
fingerprint 14af436a811bf8e8f37a780d3e07290e56b3b01119d953541adb95f286dcbcaa.
Affected RED OS CGO race PASS (internal/secretfiles, 238.390s); exact temporary
QA workspace removed through qa-sync cleanup.
Dev/harness stopped, temporary RSA removed (QA_KEY_REMOVED). Known dev ipc.js
error persists; clean UI acceptance not claimed. Active immutable runtime remains
unchanged; producer fix needs a new immutable release for future new deployments.
SI08-E apply/verify/repeat/HA acceptance remains pending, not DONE. No commit or
clean-worktree claim; previous unrelated changes preserved.

## SI08-E new blocker after successful unseal (2026-09-27)

Real React/Wails run installer-f53a30142211d7456a8a4b76c28937b3 terminal FAILED.
Former pending-secret Start blocker is fixed and tested. Seed unseal and exact
cluster identity checks succeeded. Failure is sequence 682, first protected task
in configure.yml: read sys/audit, sys/mounts, sys/auth before any configuration
mutation. Diagnostic ANSIBLE_OPERATION_FAILED (ANSIBLE_FAILURE_REDACTED) does not
retain the HTTP/TLS/module detail; token failure is NOT established.
Safe read-only post-run probe: HTTP 200, initialized=true, sealed=false,
standby=false, cluster identity present, exact canonical unit ACTIVE.
Deployment lock release succeeded. No reset/reinit, key/custody removal or secret
disclosure. New minimal prerequisite: bounded read-only API diagnosis through
existing protected credential flow, outputting only endpoint/status/error class,
before another apply. Do not disable no_log or print response bodies/tokens.
Owned harness/dev servers stopped; exact temporary RSA removal QA_KEY_REMOVED.
QA race workspace cleaned. Journals/custody/canonical project preserved.
SI08-E BLOCKED; verify/repeat/HA/final gates not PASS, no milestone commit/clean claim.

## SI08-E broker correction: real Start admitted (2026-09-27)

Owner-authorized narrow correction separates pending password consumption from
typed input binding in the existing Broker. Empty password promotion no longer
rejects a typed-only bucket; successful password promotion preserves typed inputs
for exact Core descriptor binding. No new store, protocol, guard bypass or reset.
Focused broker tests cover typed-only/mixed inputs and descriptor rejection;
App regression covers clearing/non-clearing descriptor refresh in Start order.
Focused tests, full Go suite and vet PASS. Current-source RED OS CGO race PASS:
broker 1.208s, App 1.323s. Scoped independent DIFF APPROVE_WITH_CHANGES,
0 blocking/overengineering; PBT-01 nonblocking test hardening applied and focused
PASS (TTL/generation unchanged, consumed password and expired typed buffers wiped).
Actual React/Wails: READY, both ciphertext inputs STORED, fresh plan approved,
Start STARTED -> installer-f53a30142211d7456a8a4b76c28937b3, now terminal FAILED
on the new configuration API blocker documented above.
Saved revision remains sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b.
This supersedes the Start blocker below, not full Vault acceptance: terminal
apply/verify/repeat and HA acceptance remain pending; dev ipc.js error remains.
Initialized Vault/custody/history preserved. No SI08-E DONE or clean-worktree claim.

## SI08-E Start blocked by pending-secret promotion (2026-09-27)

Actual React/Wails retry: READY, both encrypted files STORED, fresh plan
plan-a09964168cc5a40c97429e9d rendered/approved, output password and PKI password
PRESENT. Revision sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b.
Start returned BLOCKED / RUNTIME_SECRET_DESCRIPTORS_STALE, no runId returned.
Subsequent real target-free GetRuntimeSecretDescriptors returned UNAVAILABLE /
RUNTIME_SECRET_INPUT_INVALID. Concrete broker defect: the shared pending bucket
contains typed token/shares but an empty password values map; password promotion
requires a nonempty map, and its success path clears the entire pending bucket
before the following BindPendingServiceSecretInputs can bind typed inputs.
App invokes password promotion before typed binding; Start wraps descriptor
failure as STALE. No guard bypass, new run, target apply or reinitialization.
Smallest correction pending owner direction: separate consumption of password
entries from typed entries in the existing bucket, allow empty password promotion
without dropping typed inputs, and prove the combined App/Start sequence in tests.
Owned dev/harness stopped, exact QA RSA removal confirmed QA_KEY_REMOVED.
Custody/canonical files and historical run journals retained; SI08-E BLOCKED.

## Dev-only path selection seam: real encrypted import PASS (2026-09-27)

Owner approved nonvisual React/Wails selection substitution. A private picker
function defaults to native OpenFileDialog; dev-only startup configuration
accepts a bounded finite queue of absolute paths. Production !dev ignores it.
No new Wails method, plaintext/payload transport or alternate import path.
Descriptor authorization, bounded handle reader, age parsing/decryption, final
binding recheck and session broker remain the existing implementation.
Real React Services/Secrets -> existing Wails method: admin-token.age STORED,
unseal-shares.age STORED; REAL_REACT_WAILS_SECRET_IMPORT=PASS, READY PASS.
No native dialog/Computer Use, new Start or Vault mutation in this focused probe.
Known dev ipc.js renderer exception remains; this is not clean UI/full Vault
acceptance. SI08-E apply/verify/repeat/HA gates still pending.
Focused production/dev tests, full normal-build Go suite and vet normal/dev PASS.
Wails production build PASS (8.592s) after owned dev server stopped.
Temporary QA RSA admission removed with confirmation. Independent scoped DIFF
review APPROVE_WITH_CHANGES, 0 blocking; NFS-01 nonblocking production isolation
test strengthened with callable sentinel for valid/malformed env, focused PASS.
RED OS normal-build CGO race PASS (1.119s). RED OS dev-build race UNAVAILABLE:
GTK3/WebKit2GTK development packages absent; no host packages installed to bypass
this prerequisite. Windows dev unit tests and real bridge import PASS are separate.
Earlier unrelated dirty work retained; SI08-E not DONE and no clean-worktree claim.

## Continued Vault import blocked by Computer Use input (2026-09-27)

Real React/Wails retry: credential PRESENT, READY PASS; native secret picker
opened as a separate returned Window with the headless-owner helper. No Wails
focus crash occurred. Computer Use set_value failed with UIA cache-property error
(0x80070057). Fresh focus observations after activation, Alt+n, Ctrl+l and Tab
did not change from the search field. No filename was typed blindly and no
encrypted-file import success or new Start was observed. This is an automation
input blocker, not Vault execution or secret validation. The initialized Vault,
ciphertext custody files and committed journals remain untouched.
Harness and owned dev servers stopped; temporary RSA removal confirmed
QA_KEY_REMOVED. Dev-server output also contains WebView2 ProcessFailed kind 6
and the existing ipc.js renderer exception; do not claim clean WebView acceptance.
SI08-E remains BLOCKED pending reliable native-dialog input; no DONE claim.

## Native dialog headless-owner workaround verified (2026-09-27)

QA helper scripts/qa-native-dialog.cjs uses supported Wails WindowHide before
the real native action and WindowShow in finally. This exposes an actual
independently targetable dialog without changing production Go, dependencies,
native import validation or credential semantics. Three helper tests PASS.
Real secret-free ChooseProject cancellation returns NO_PROJECT; a subsequent
real GetApplicationConfig returns READY. No WebView2 process exit in this probe.
The previous missing-modal limitation is therefore avoidable in headless QA.
Vault harness now wraps its real React file-selection handler in this helper.
First continued acceptance attempt timed out waiting for rendered READY; fresh
SSH probe succeeded and real CheckExecutionNode returned READY. Retry in progress;
no new import/Start or overall SI08-E success claimed at this point.

## Native dialog targeting cannot be completed through current CUA API (2026-09-27)

Owner-authorized QA-only correction: refuse native-dialog input unless exactly
one actual returned Window matches both Installer app identity and dialog title;
never fall back to its disabled main-window owner or fabricate a modal handle.
Runtime-only helper and two focused tests exercise this guard.
A real Wails ChooseProject folder-dialog probe, without secrets or targets,
confirmed both list_windows and list_apps expose only the main Installer window.
Accessibility confirms that owner is disabled and the folder modal is a nested
element, not a returned independently targetable Window. No activation/input was
sent to that disabled owner. Native import acceptance remains BLOCKED by this
Computer Use targeting limitation; the guard prevents repeating the unsafe
automation action but is not a completed file-import fix. No production or
dependency change, no secret import, no Start or Vault mutation.

## SI08-E native secret picker / WebView2 blocker (2026-09-27)

Continued real React/Wails flow after the DTO correction: project opened,
session credential PRESENT, Execution Node READY, Vault Secrets form rendered.
First native admin-token.age picker opened. Computer Use returned its actual
accessibility tree. Setting the filename failed to activate the captured window;
Wails logged WebView2 `The parameter is incorrect` in Chromium.Focus/onFocus,
then the application process disappeared and bridge port 34115 closed.
One unchanged supported dev restart restored the bridge and READY; the repeated
React file-selection action did not expose a usable native dialog. No import
success, new Start/run, init/reset/unseal or deployment was observed.
SI08-E remains BLOCKED on the desktop native-file-input boundary; this is not
evidence of a Vault failure. No dependency or production bypass was introduced.
Both attempt harnesses and dev servers stopped; exact temporary RSA admission
removal confirmed QA_KEY_REMOVED. Existing custody and run journals preserved.
Next bounded action: diagnose native dialog ownership/focus in the supported
Wails bridge before retrying the already-initialized Vault with retained custody.

## Secrets descriptor wire correction verified (2026-09-27)

Owner-authorized bounded correction adds explicit lower-camel JSON tags to
RuntimeSecretDescriptorOperation/View, preserving existing descriptor semantics.
Generated Wails models refreshed/formatted; two focused wire tests prove exact
field names, round-trip data and safe unavailable response.
Actual React Services -> vault-qa-standalone -> Secrets, through real Wails Go
methods, returns READY with two descriptors and renders two file-input controls.
No secret file import, new Start, init/reset/unseal or target deployment was
performed by this focused probe. This closes the descriptor wire blocker only;
SI08-E full Vault acceptance remains pending, not DONE.
Focused Go tests PASS; go test ./... and go vet ./... PASS; frontend lint,
67 tests and build PASS; wails build -nopackage -clean PASS (11.257s).
RED OS CGO race tests for descriptors, pending-output list and concurrent
binding guards PASS (1.080s), using current qa-sync source.
SSH recovered; exact temporary QA RSA key removal confirmed QA_KEY_REMOVED.
Previous pending workspace cleanup completed via qa-sync. Earlier unrelated
uncommitted changes remain preserved; no clean-worktree or milestone claim.

## Output list guard fixed; real delivery PASS; Secrets DTO blocker (2026-09-27)

Cleanup caveat: after local dev servers stopped, RED OS race SSH connection
closed; a fresh bounded SSH probe timed out during banner exchange. Race is NOT
PASS. Removal of this attempt's temporary RSA admission was issued but completion
was not confirmed; do not report the key removed. qa-sync workspace
/var/tmp/platform-installer-qa-fa6f3340b14d40e69747697502478238 remains pending cleanup.
Restore SSH access before confirming exact-key removal and workspace cleanup;
do not reboot targets or delete custody as a workaround.

Owner-authorized ListPendingSecretOutputs guard now re-resolves the existing
private binding and checks binding/node/runtime/READY plus project/generation.
External selection remains free of a synthetic SelectedHostID. Existing positive
test uses real external context; 9 deterministic concurrent-change cases reject
the response. Focused Go, full Go tests/vet and diff check PASS.
Real React/Wails Result recovery: READY package
805b1d37fb4b8c901369d2901dc8f41d from run
installer-6989b0f2fb6c2609515170ece9c9eeb7 delivered/encrypted successfully.
Local secrets/vault-qa-standalone contains admin-token.age, unseal-shares.age and
complete receipt; no plaintext file/content exposed.
Subsequent real Services/Secrets import blocked before native picker: Wails
GetPendingRuntimeSecretDescriptors returns uppercase Status/Descriptors while
React expects lowercase status/descriptors. RuntimeSecretDescriptorOperation
and RuntimeSecretDescriptorView lack JSON tags (app.go). No new Start/init/reset.
This separate wire-shape correction is proposed, not implemented here.
SI08-E remains BLOCKED; earlier changes preserved; no overall DONE claim.

## SI08-E recovery blocked by external-node list guard (2026-09-27)

Corrected unseal runtime published/activated through supported promotion:
sha256:169d75bc64933c0f871efe26f2da36652776025bf9c1e4a9b72b8d8961c7735d.
Isolated revision sha256:a75031b7d1fb1d54273c8781fc5e4ceb100443f1c72f2038ac56f920e646e73b;
catalog unchanged. No target reset/init/unseal or new Start was performed.
Actual React/Wails recovery flow opens project, proves READY, sets session-only
output encryption password and invokes Result/ListPending. Repeated real binding
calls return PROJECT_CHANGED with unchanged EXPLICIT_EXTERNAL/READY selection.
Concrete defect: app.go ListPendingSecretOutputs post-call guard compares
SelectedHostID to binding.node.ID; external selection deliberately has no
SelectedHostID (execution_node_context.go selectInitial). Existing private
binding resolver correctly checks external.hostID instead. Do not weaken guard
or substitute a mock/direct secret export. Smallest proposed correction: recheck
the current supported private binding identity after the remote call together
with existing project/generation guards; add external-selection and race tests.
No Go correction made without owner direction. Custody/journals retained,
dev servers stopped. SI08-E remains BLOCKED; no output delivery/import claimed.

## Seed identity ordering correction implemented (2026-09-27)

Owner authorized bounded fix of the SI08-E unseal blocker. unseal_member.yml
now captures seed cluster_id only from confirmed initialized/unsealed health,
after requiring a nonempty string identity. Followers still compare their own
post-unseal identity to the seed; no pre-unseal cluster_id is required.
No init/custody/protocol change; no_log retained. No target reset or unseal run.
Current-source RED OS: 4 new real-Ansible synthetic boundary tests PASS (9.358s),
in both native modes; Vault contract 15 PASS (0.425s); apply/verify syntax and
catalog/schema reproducibility PASS. Full Go tests/vet/diff check PASS.
QA workspace cleaned. Correction remains uncommitted/unpublished; real
React/Wails acceptance remains pending and SI08-E is not DONE. Next run must
use retained admin-token/unseal-shares through the supported secret-input flow,
not reinitialize the now-initialized seed. Previous dirty changes preserved.

## SI08-E new blocker: seed identity read before unseal (2026-09-27)

Diagnostic runtime sha256:9752977101218636e21af54fc8ca38fc2689b6b04218cf598a2258874b1bd0db
published/activated; isolated revision
sha256:1b5ac63e9dec173990ef8b063df15c9540d8e18e3a50318d957590fc8fb13c79.
Real React/Wails fresh plan/approval/Start run
installer-6989b0f2fb6c2609515170ece9c9eeb7 FAILED, sequence 670.
Original audit task SUCCESS; init custody files exist, recovery record absent.
Unseal include starts at sequence 659; initial health succeeds, then capture
seed cluster identity fails. Safe read-only health proof: HTTP 503,
initialized=true, sealed=true, cluster_id absent. No token/shares inspected.
New classifier emitted ANSIBLE_FAILURE_REDACTED for the no_log failure, as required.
Smallest proposed correction: capture seed identity after confirmed unseal,
then retain exact follower identity guard. No correction/reset/retry performed.
Core 393 total / 374 PASS / 19 SKIP; privileged clear 18 PASS; reproducibility PASS.
QA workspace/RSA admission cleaned; dev servers stopped; custody/journals retained.
SI08-E remains BLOCKED pending owner authorization of this bounded service fix.

## Bounded failure diagnostics implemented; runtime acceptance pending (2026-09-27)

Owner-authorized isolated audit-directory task PASS changed=false (5.724s),
with mountpoint identity, inactive Vault unit and committed journal unchanged.
Original failure did not reproduce; removed temporary QA key was not reinstated.
Controller now derives a closed coarse diagnostic class from the final ordinary
Ansible failure record when no explicit Core error_code exists. Raw output stays
bounded/in-memory; no_log/censored results stay opaque. No service/retry semantics
or public protocol change. Details: docs/execution-failure-diagnostics.md.
Current-source RED OS: 6 new tests PASS, observability 21 PASS / 4 opt-in SKIP,
lifecycle 39 PASS. Full Go tests/vet and diff check PASS; qa-sync workspace cleaned.
New runtime publication and real React/Wails acceptance remain pending; no full
Apply or bootstrap was run. SI08-E remains BLOCKED; earlier dirty work preserved.

## SI08-E real React/Wails retry: new provisioning blocker (2026-09-27)

Guarded Vault clear committed as 72a199143df4c7acb50d0ce77cf439398b32ada6.
Exact owned QA reset passed (changed=4); member root/marker, config, PKI,
audit/unit identities and committed journal bytes were retained. No active run
or deployment lock existed before reset.
Bootstrap correction received independent FULL DIFF APPROVE, zero blockers;
reviewed fingerprint 49bb289d7427879f45cc3dcfe3d01f13efcc3bc51f8b6a3cac440277b66a0571.
Supported immutable publication/activation produced runtime
sha256:e53df4e66364ebbb7fde8653219da12dc77bff92ea527d347a02ed5205291531.
Only the isolated QA project's guarded lock was promoted; catalog unchanged.
Real React/Wails readiness, fresh plan, approval and Start proceeded, but run
installer-c77432c312f53ac251fc5635ff559915 became FAILED at sequence 570.
First failed task: Create the fixed audit mountpoint used inside each unit
namespace (/var/log/platform-vault-audit), before init/unseal.
Read-only inspection proves root:root 0755, no immutable flag, adequate disk
and inode capacity, selected unit inactive. Separate elevated local Ansible
check-mode inspection passes changed=0; it is not production-run acceptance.
Exact production task error/cause is not yet established; do not guess or
retry the full plan. SI08-E remains BLOCKED, not DONE. Temporary QA public-key
admission was removed; prior unrelated worktree changes remain preserved.

## Vault explicit clear corrections complete; targeted DIFF PASS (2026-09-27)

Owner authorized exact SI08-CLEAR-DIFF-02/03 corrections. Process guard now
matches both exact config forms independently of argv[0]. Vault-only no-follow
fd traversal checks opened inode identity and Linux mnt_id before each descent;
missing/malformed mount evidence blocks clear. No generic framework or normal
Apply/Verify change.
Focused RED OS clear 18 PASS (1.839s), Vault contract 15 PASS (0.515s), syntax
PASS; independent full Core 387 total / 383 PASS / 4 opt-in SKIP / 0 errors
(174.730s), catalog/schema, full Go tests/vet and diff check PASS. Tested source
hashes match the reviewed revision.
One independent targeted recheck APPROVE: DIFF-01 remains RESOLVED, DIFF-02/03
OPEN -> RESOLVED, zero blocking/overengineering findings. Reviewed ordinal
fingerprint `1f30018aa7b9db71f591dfe54b28117608b38e73bc50bb359163301a7baead5a`.
QA source workspace was cleaned. Actual reset and SI08-E acceptance are still
not claimed; subsequent reset requires fresh exact identity/no-active-run proof.
Evidence: docs/service-install-08e-clear-evidence.md. Earlier unrelated
uncommitted work is preserved; clear is a separate focused implementation.

## Vault clear resumed FULL DIFF: two safety blockers (2026-09-27)

Owner authorized commit/continuation. Resumed SAME incomplete FULL DIFF on
unchanged fingerprint `86df9179819d462aaa11813072c70ec9645be9a643a522b7e8e7ef3a872f37e3`.
SI08-CLEAR-DIFF-01 envelope mismatch is reviewer-verified RESOLVED. Review now
completed with BLOCK: SI08-CLEAR-DIFF-02 process admission relies on argv[0],
and SI08-CLEAR-DIFF-03 one-shot mount admission does not exclude later movement
of a directory containing an inherited mount into the deletion subtree.
The second finding is a static counterexample, not an experimentally reproduced
deletion. Smallest corrections: exact config-argument guard independent of
argv[0], and descriptor mount-identity checks before each directory descent,
with focused real-process and synchronized mount-movement tests.
No automatic correction/re-review, commit or destructive execution. Owner
decision on these two bounded safety corrections is required. Existing tests
remain regression PASS but do not prove the missing cases. QA identity chain
project/run/operation/member/unit/config/data was read-only rechecked PASS;
active Installer runs and Vault lock holders were zero at inspection.

## Vault explicit clear implemented; DIFF revision-envelope blocker (2026-09-27)

Owner approved the concrete clear plan. Added standalone clear playbook,
clear_entry/clear tasks, exact confirmation default and narrow held-descriptor
Vault member helper. Apply/Verify are unchanged; actual Raft data has not been
cleared and no service was stopped. Current owned unit passed read-only helper
inspection (`inspect_only=true`, changed=false).

RED OS focused clear 15 PASS, Vault contract 15 PASS, standalone clear syntax
PASS; independent full Core 384 total / 380 PASS / 4 opt-in SKIP / 0 errors,
177.032s; catalog/schema reproducibility PASS; full Go tests/vet and diff check
PASS. Seven tested source file hashes match the local implementation.

FULL DIFF reviewer returned BLOCK, SI08-CLEAR-DIFF-01: supplied fingerprint
used PowerShell cultural sorting instead of the stated ordinal sorting.
Read-only reconciliation confirms unchanged file hashes; corrected ordinal
fingerprint matches reviewer exactly:
`86df9179819d462aaa11813072c70ec9645be9a643a522b7e8e7ef3a872f37e3`.
No automatic review rerun or destructive execution. The safety review is not
complete; owner authorization is needed for review continuation/recheck with
the corrected identity. Evidence: docs/service-install-08e-clear-evidence.md.
No commit; unrelated existing worktree changes are preserved. SI08-E acceptance
remains BLOCKED.

## SI08-E QA reset authorized; safe mechanism prerequisite unresolved (2026-09-27)

Owner authorized reset of the owned QA Vault instance. Read-only recheck on
.101 confirms Vault is initialized, while `init-response.json`, `admin-token`
and `unseal-shares` are absent from the exact failed run's output package.
Scoped inspection found no existing suitable identity-safe Vault data reset or
quarantine mechanism. Existing project publication rename helpers do not prove
the identity of a Vault source directory and are not reused as a reset tool.
The approved bootstrap correction plan explicitly requires stopping on this
mechanism gap. No unit was stopped, no data was deleted/moved, no journal or
output package was changed, and no new runtime or acceptance run was started.
SI08-E remains BLOCKED pending an owner-approved bounded reset mechanism.

Owner requested analogous Kafka/PostgreSQL Ansible clear tasks. Concrete plan:
`docs/service-install-08e-clear.md`, explicit standalone playbook, exact
deployment acknowledgement and existing flock; a narrow Vault-only held-fd
reset preserves member root/marker, config, TLS, audit and controller custody.
Independent FULL PLAN review APPROVE_WITH_CHANGES, zero blocking findings;
two nonblocking mount/revalidation clarifications were incorporated. Concrete
helper design was subsequently approved and implemented (see latest entry).
No destructive target mutation has occurred.

## SI08-E acceptance preparation started (2026-09-27)

Owner authorized SI08-E after C/D commit `3e1f711`. Required preserved
prerequisite work was restored from stash (stash retained). New immutable QA
runtime `sha256:d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d`
is activated on .101 and READY. Standalone QA project
`.runtime/qa/vault-qa-standalone-20260927` has saved inventory/PKI/Vault desired
state; fresh Go/Core plan is EXECUTABLE. Native UI import of the prepared
project was confirmed by the owner. Visual/manual UI acceptance is waived;
nonvisual React/Wails integration through real backend bindings is now mandatory
for all services and affected application flows (see AGENTS/common acceptance).
The imported project now includes unplaced Kafka `asd`, preserved unchanged.
Isolated Vault QA project `project-76b046511af5faed` has an EXECUTABLE plan.
Start was blocked by the Go PKI capability gate requiring legacy payload v2
from a v4-only runtime. Owner-approved bounded correction and focused tests
are implemented; focused/full Go tests, vet, diff check and production Wails
build PASS. The real React/Wails automation prerequisite is resolved via the
standard loopback Wails dev server and headless Edge; no production debug
endpoint or dependency edits. React session credentials/readiness PASS and
fresh Plan reaches PLAN_REVIEW. Owner-approved Plan presentation correction
now serializes empty Targets/DependsOn as arrays; JSON regression/full Go/vet
PASS and actual React Plan rendering/approval/PKI input PASS. Real React Start
previously returned BLOCKED / LEASE_PAYLOAD_INVALID before run creation. The
owner-approved typed nil-map correction now serializes runtimeSecretValues as
{}, with focused/full Go tests, vet and diff check PASS. Actual React/Wails
retry passes lease admission but returns EXECUTION_MANIFEST_INVALID before run
creation. Active runtime proof: Core emits displayLabel in private
runtimeSecretInputs; the closed consumer rejects that field. The same bounded
descriptor without displayLabel is accepted. SI08-E is BLOCKED on this new
producer/consumer mismatch was then corrected with owner authorization: private
displayLabel omitted, public label preserved, real consumer regression PASS.
Core 351 PASS/4 skips, Go full suite/vet and catalog/schema checks PASS.
New immutable runtime sha256:a668dca34624ba39bc289efbe577b6b1665488d9e7ce416c8c910d65d0139c96
activated; only isolated Vault QA project locks advanced through guarded API.
Real React/Wails Start admitted run installer-7c88e83cb1124ca91cfce021861d4b01,
then terminal INTERRUPTED at sequence 2. Controller reports OUTPUT_ACCESS_DENIED:
execution root is mode 0700 owned by UID 1001, detached controller runs as UID 0;
output storage requires owner == effective UID. SI08-E is BLOCKED on this new
ownership mismatch before Ansible Apply was corrected with owner authorization.
Supported activation now creates/verifies private execution storage through the
existing no-follow output directory helper under sudo; foreign owner fails closed.
QA root alone was corrected by fchown on its opened directory after no active runs
were confirmed; descendants/journals/leases were untouched. Startup projection
failure after verified durable identity now records FAILED with lease cleanup.
Core 353 PASS/4 skips, lifecycle 39, output storage 25, Go suite/vet, frontend
67/lint/build and catalog/schema checks PASS. Runtime
sha256:c1727d16eca98bcb054bbe4665275776df5d0adc8ecbd202961346143455de09
activated; React/Wails admitted run installer-95d2c1f3ad92343e09ae8da684a1ef78.
It reached RUNNING and PKI Apply completed. Terminal FAILED at sequence 338:
Vault closed-input assertion rejects apiPort type after generic
runtime_role_variables set_fact. Manifest apiPort is an integer; local-only
Ansible reproduction of the same set_fact conversion fails assertion index 6
(platform_vault_api_port is integer). SI08-E is BLOCKED on this new typed
Core-to-Ansible boundary defect; no type/safety check was weakened.
Owner authorized a narrow generic correction. Local-only RED OS experiment
proved mapping args preserve numeric types, but Ansible set_fact with native mode
disabled still converts string "false" to boolean. New focused real-Ansible
regression: native=True PASS; native=False BLOCK on string identity; empty and
malformed/missing-host guards PASS. The experimental production task change was
reverted; regression retained. No new runtime publication or Vault retry.
A fully typed correction now requires an explicit choice of a narrowly scoped
fact action adapter versus global native-mode policy; the latter was not changed.
Owner approved the narrow adapter. platform.core.apply_runtime_role_variables
now copies only current-host platform_* values into facts without scalar
templating/coercion, target transport, or file writes. Existing mapping guards
and no_log retained; arguments/invalid names rejected. Real Ansible regression
PASS in native=False/True, including numeric and boolean-shaped strings,
list/map/null, empty mapping and malformed/missing host. Focused tests 3 and
service/PKI contracts 11 PASS; Go suite/vet PASS; full Core 356 PASS/4 skips,
catalog/schema reproducibility PASS. Runtime
sha256:0c0248c19a457d647a060c8c72b1ca1fa5999099f02a0e43b55239b563b15f1a
activated; only isolated QA project lock updated. React/Wails run
installer-2e83aa4e51d88886abc0827217e6abae reached PKI/apply and passed the
previously failing Vault typed-input guard. Pinned Vault repository installation
completed; terminal FAILED at sequence 586 on changed-member restart tracking.
provision.yml used loop_var vault_member for configuration/systemd templates,
while tracking expected item.item.id. Owner authorized retaining item.item.id:
template loops now use default item with task-local vault_member alias.
Real local-only Ansible regression PASS: three-member first render, unchanged
repeat, and single-member change track the exact expected identities without
duplicates. Target now has
partial package/account/PKI/config provisioning; no active Vault units observed.
No Vault init/unseal, verify or output-delivery success is claimed. SI08-E is
BLOCKED on a new independent service-directory access defect after this
owner-authorized loop correction passed real acceptance. Core 357 PASS/4 skips,
Go suite/vet, catalog/schema and diff check PASS. Immutable runtime
sha256:66ed3423ed150cb8fa46af19c0bdcd120a4066a4ffcd78c3367d28b76ac24e67
activated. React/Wails run installer-ff1844b73c5fd429dbf4c7b0c9243cbe passed both
tracking tasks and started the seed; terminal FAILED at sequence 600.
Vault auto-restarts (exit 1, permission denied). Deployment parent directory
/etc/platform-vault/vault is root:root 0750; service-owned member config 0600
cannot be read as platform-vault because parent traversal is denied. No new
permission correction was made. QA source workspace/key and local automation
were cleaned; original imported project and unrelated services unchanged.
Owner authorized the next bounded permission correction: deployment parents
now retain root owner/0750 with platform_vault_group. Private member/file modes
and no-follow/owner guards are unchanged. Focused root/local Ansible 2 PASS,
including service read/no-parent-write and repeat changed=0; Vault 15 PASS,
Core 358 PASS/5 skips; Go suite/vet, catalog/schema and diff check PASS.
Runtime sha256:c8952a109ac1774cc896e5d195a5908e95d371f385ec5891317436eef38789df
activated. React/Wails run installer-b095002168ac83f7fb1aa9289f7120cb proves
configuration readable and Vault ACTIVE, closing the permission blocker.
Terminal FAILED at sequence 612 on a new bootstrap response validation defect:
dictionary .keys resolves a method rather than the Shamir shares collection.
Synthetic active-task proof fails; ['keys'] variant passes. Production bootstrap
was not changed. TLS API confirms initialized=true; exact custody package has
no init-response.json/admin-token/unseal-shares (existence-only proof).
SI08-E remains BLOCKED. No blind retry or QA state reset was performed; required
next actions are explicit dictionary indexing correction and owner-authorized
reset of only the exact owned initialized QA member before repeat acceptance.
QA source workspace/key and local automation cleaned; no other service mutation.
Owner accepted the bootstrap plan correction. Revision 2 is in
docs/service-install-08e-bootstrap-correction.md: immediate minimal recovery
copy, explicit readback/sync durability, strict validation and confirmed durable
pair before recovery deletion. Independent single targeted recheck APPROVE:
SI08-E-PLAN-01 RESOLVED (PLAN), zero blocking/overengineering findings.
SI08-E-PLAN-02 remains the separate reset identity/mechanism prerequisite.
This closes only the plan gate; production bootstrap implementation, fault
injection and real retry have not been performed. No QA reset occurred.
Owner subsequently authorized implementation. bootstrap.yml now uses explicit
keys indexing, immediate minimal recovery copy, metadata/readback/sync checks,
strict validation and pre-publication conflict checks, synchronized pair and
directory synchronization after recovery cleanup. Native modes/interruption/
reopen/partial pair/malformed/conflict/sync/cleanup regression: focused 6 PASS
(213.153s), Vault contracts 15 PASS. Independent QA full Core 364 PASS/5 skips
(369 total, 238.129s); Go suite/vet, catalog/schema, standalone syntax and diff
check PASS. QA source workspaces/logs cleaned; no actual secret reads.
No runtime promotion or real retry in this correction; no QA reset. Existing
initialized seed without custody still blocks SI08-E acceptance. PLAN-02 exact
ownership reconciliation, safe reset/quarantine mechanism and separate owner
authorization remain required. Implementation uncommitted; SI08-E not DONE.
See docs/qa-react-wails.md and SI08-E evidence. No mock substitute is used.
Vault Apply partially completed and seed init occurred as above; unseal, verify,
protected delivery and repeat acceptance have not passed. See
`docs/service-install-08e.md`. Earlier NOT STARTED statements below describe
the historical C/D gate, not the current E authorization.

## SERVICE-INSTALL-08 Vault implementation started (2026-09-26)

SI08-D owner clarification: the common output encryption password is entered
on Installation → Plan. No folder selection is provided. The workstation
uses `<project-root>/secrets/<deploymentId>/` automatically. This behavior is
implemented with safe opened-directory publication and tests for the default
path, no overwrite, symlink rejection and exclusion from Core staging/revision.
Go full test/vet, frontend 67 tests/lint/build and Windows Wails build PASS.
Initial FULL DIFF review returned BLOCK with six findings SI08-D-DIFF-01–06.
The owner accepted all six blocking and two nonblocking corrections. Final QA
PASS: Core 341 PASS/4 opt-in skips, contracts 31 PASS, Vault role 15 PASS,
Windows full Go/vet, frontend 67/lint/build, Wails and affected RED OS race PASS.
The single targeted recheck resolved DIFF-01–05 but returned BLOCK on DIFF-06:
protected pre-publication packages lacked reservation/terminal recovery handling.
The owner subsequently authorized this exact correction. DIFF-06 is now
RESOLVED BY OWNER-AUTHORIZED EXACT CORRECTION, with private durable reservations,
full-pair terminal publication, empty completion/next-run admission and explicit
partial-material recovery status. No further architecture review was run;
the automatic review budget remains exhausted. Final current-source offline
QA: lifecycle 38 PASS, storage 24 PASS, Core 351 PASS/4 opt-in skips,
contracts 31 PASS, Vault role 15 PASS, catalog/schema checks PASS; affected
Go race, Windows full Go/vet and frontend 67/lint/build PASS.
SI08-C/D are recorded in a focused implementation commit; unrelated work remains
outside it. No Vault execution occurred. See `docs/service-install-08d.md` and
`docs/service-install-08d-review.md`. SI08-E remains NOT STARTED.

SI08-B is DONE. SI08-C implementation and QA gates PASS in the current
worktree and are recorded with SI08-D in a focused implementation commit.
Unrelated in-progress changes remain outside it. SI08-D is implemented; SI08-E
remains NOT STARTED. D has implemented the workstation age file crypto base at
`internal/secretfiles`, pinned to filippo.io/age v1.3.2, Scrypt work factor 18,
and the approved encrypted-file size bound. It also strictly extracts only the
approved Vault token/share fields and projects closed `x-secretInputs` from the
locked catalog as safe metadata. Focused tests, `go test ./...` and `go vet
./...` pass. D now includes no-follow selected-file reading, broker/lease
integration, output delivery and generic Secrets/Plan UI in the worktree.
The DIFF-06 reservation/recovery correction is implemented and tested; real
Vault service acceptance remains SI08-E. The mockup shows the common Plan encryption
password and fixed default output path. The SI08-C implementation and QA evidence are recorded in
[`docs/service-install-08c.md`](docs/service-install-08c.md). It adds Core
typed-secret descriptors and manifest binding, Execution Node capability and
lease admission, scoped Ansible forwarding, and interruption-safe cleanup of
temporary typed-input files. Vault unseal shares are Apply-only; the admin token
is available to Apply and Verify. The immutable runtime was not published or
activated, and no Vault deployment or target mutation occurred.

SI08-B is DONE. The owner-authorized targeted recheck passed SI08-B-DIFF-01 and
SI08-B-DIFF-03 after the lock/path execution evidence was supplied;
SI08-B-DIFF-02 is resolved by the owner decision to match
the established services' two-mode artifact-source behavior: authority/resolved
source mode uses the common gate; direct Ansible-only mode without those inputs
continues using the configured package repository without a new mandatory gate.
All three B findings are resolved with zero blocking and zero overengineering
findings. No real Vault deployment or target mutation occurred.

Latest focused evidence on RED OS: Vault role contract 14 PASS; lock contention
proved exactly one READY holder and reacquisition after normal stop and failed
holder; seven symlink cases across config/data/log deployment/member and config
PKI boundaries rejected before outside writes; standalone, 3-member/1-host and
3-member/3-host role validation plus read-only preflight and apply/verify syntax
checks PASS. The prior B Core suite had 322 tests PASS, 4 skipped. Latest C
regression: Core 337 PASS, 4 skipped; contracts 31 PASS; Vault role 15 PASS;
catalog and service schema reproducibility, apply syntax-check and
`git diff --check` PASS. No Vault package, init, or target data mutation has
been performed.

Owner authorized implementation after the exact SI08-PLAN-02 terminal-evidence
correction. SI08-A is DONE; pinned artifact acquisition blocker is resolved.
The architecture is
`docs/service-install-08-vault-architecture.md`: standalone and three-member
Raft (1/1, 3/1, 3/3), API TLS and Vault cluster TLS, audit, KV v2, userpass
enabled without managed accounts; configurable unseal defaults 2-of-3.
Workstation encryption uses its session password; protected temporary
plaintext on Execution Node is retained until confirmed delivery.

Initial additive SecretOutputDelivery/v1alpha1 request/control-response/safe
metadata schemas and a bounded Go Fetch-frame decoder are implemented but not
wired into an active runtime or advertised. Existing published execution
contracts are unchanged. Closed Go control-request decoder and Python
request/Fetch codec are added; neither performs target contact or storage.
RED OS contract suite: 21 PASS; Python codec: 3 PASS; `go test ./...` and
`go vet ./...` PASS. Owner-authorized DEV acquisition of
`vault-1.21.2-1.red80.x86_64` from RED OS `updates` completed. RPM signature and
repository/remote/local SHA-256 equality PASS:
`sha256:11db853f514625835ed4516876311057b7021fbaf39a53040e5e13d111bc41dd`.
Artifact is Git-ignored under `.runtime/artifacts/vault/`; extracted binary
reports Vault v1.21.2. No Vault package has been installed.
Private Linux protected package publication/Fetch foundation is implemented,
not wired or advertised: no-follow held descriptors, restricted ownership/modes,
durable exact binding, no overwrite and READY publication after entry flush.
RED OS storage tests 10 PASS; Core suite 320 tests, OK (4 skipped).
SI08-D exact DIFF-06 correction and focused/regression gates are complete in
the focused C/D implementation commit. SI08-E
owns real Vault deployment acceptance. SI08-B and SI08-C status/evidence are
recorded above.
Redis completion must not be inferred from this entry.
Artifact metadata license BUSL-1.1; intended distribution/license notices must
be addressed before offline publication. No runtime release was published or
activated. Exact artifact evidence and remaining A contract gates are recorded
in `docs/service-install-08a.md`.

Initial implementation DIFF review: BLOCK, one blocking finding. Canonical
deployment IDs containing dots/underscores are rejected by output identity
admission (SI08-A-DIFF-01). Exact metadata-key case is NON_BLOCKING
(SI08-A-DIFF-02). Callback error leakage is RESOLVED (SI08-A-DIFF-03), with
independent focused QA PASS. Latest full Go test/vet and RED OS wire race PASS;
contracts 31 PASS, Core 320 tests OK (4 skipped), reproducibility/offline PASS.
This initial BLOCK is historical. Owner-approved corrections passed the one
TARGETED_RECHECK: DIFF-01/02 RESOLVED, DIFF-03 remains RESOLVED, 0 blocking
and 0 overengineering findings. Final Windows Go test/vet PASS; RED OS Core
321 tests OK (4 skipped), contracts 31 PASS, wire race and reproducibility
PASS; diff-check PASS. SI08-A contract foundation is DONE, not runtime or
Vault deployment acceptance. New additive input/output contracts are defined
but not advertised; existing published contracts are unchanged.

## Application config and server type foundation (2026-09-14)

`OWNER-APP-CONFIG-01/02` is implemented. Repository development configuration
is the versioned `config/application.yml`; it currently declares `infra`,
`app` and `db`. New Installer sessions emit additive
`project-edit/v1alpha3`, whose `CreateServer` requires one grammar-valid type;
absence from the local configured list is warning-only.
Published v1alpha2 remains unchanged and both versions use the same Go
`EditCommand` model.

Canonical projects store only the grammar-valid ID as optional-on-legacy-read
`platform_host.type`. Core projects it through the existing
`ProjectSnapshot.hosts` object. Missing legacy and locally unknown valid types
are preserved without backfill; unknown configured types produce only a
nonblocking Installer diagnostic and do not alter Core status, validation or
fingerprint. Type has no service, topology, placement, Execution Node or source
selection semantics. UI-01E1 through UI-01E6 and UI-01F1 through UI-01F3 are
DONE; UI-01F4, UI-01F5 and UI-01F6 are DONE. UI-01F overall is DONE; UI-NET-01 is DONE (evidence: `docs/ui-net-01.md`), UI-01G1 through UI-01G4 are DONE (evidence: `docs/ui-01g1.md`, `docs/ui-01g2.md`, `docs/ui-01g3.md`, `docs/ui-01g4.md`), UI-01G overall is DONE, and UI-01H overall is DONE (evidence: `docs/ui-01h4.md`); UI-01I is DONE (evidence: `docs/ui-01i.md`); UI-01J is DONE (evidence: `docs/ui-01j.md`); UI-01 overall is DONE.

## UI-01 implementation status (2026-09-07)

UI-01A through UI-01D are DONE. UI-01D was accepted by the owner without a
final revision-bound review. UI-01 overall is DONE; UI-01E1 through
UI-01E6 and UI-01F1 through UI-01F6 are DONE; UI-01F overall is DONE and UI-NET-01 is DONE while UI-01G overall and UI-01H overall are DONE; UI-01I and UI-01J are DONE, and UI-01 overall is DONE. UI-01B adds only the Wails/React read-only
shell and fixed `BuildProjectSnapshot` protocol operation; it adds no writer,
edit/session, candidate, save or apply path.

ADR-027 is implemented pre-UI-01E5 without changing milestone statuses. New
Installer sessions use local structural review and the existing guarded writer;
Save requires no Execution Node/Core call and returns a locally projected saved
revision. Reopen without a node reads only directly Installer-owned canonical
server fields. Explicit Project Verify runs the existing target-free
`BuildProjectSnapshot` operation, binds derived in-memory evidence to the saved
revision/attested active-runtime identity, and never mutates project files. A semantic Save
makes the new revision `UNVERIFIED`. Fresh `BuildDeploymentPlan` remains mandatory
before execution. UI-01E5 is DONE: readiness/preparation and navigation gating
use only the startup trusted binding, with explicit Prepare confirmation and
fresh post-Prepare Verify evidence. UI-01E6 is DONE: real Wails creation,
READY/navigation acceptance, target-free Core proof and RED OS regression
passed without service or target mutation; see `docs/ui-01e6.md`.

The 2026-09-05 accepted freeze is `docs/ui-01a-contract-freeze.md`; toolchain, mockup
reconciliation, reviews and QA are recorded in the adjacent `ui-01a-*`
documents. It fixed the one-file empty project (`project.yml` only), exact lock
provenance, first-save ownership, then-current complete-candidate Core proof,
project-edit v1alpha2 evolution, missing server/topology/PKI commands, and
runtime-only session credentials. ADR-027 supersedes only its Core-before-Save
requirement; its ownership and transaction protections remain. Historical
Core-contract and safety reviews reported 0 blocking findings.

The implementation sequence remains `docs/ui-01.md` (UI-01B through UI-01J).
Every milestone requires pre-start and acceptance mockup/contract checks.
Editor order is Servers → Topology → Certificates (PKI intent) → Service
settings. UI-02 execution/task-stream UI and target secret lease transport
remain separate.

## UI-02 installation workflow (2026-09-22)

UI-02A is DONE. It adds the closed local `InstallationState` Wails projection
and the read-only Summary → Plan → Execution → Result Installation surface.
It performs no Core, Execution Node or target call and has no plan creation,
approval, Start, cancellation or secret path. UI-02B is DONE: it adds fresh
target-free planning, closed plan projection and exact acknowledgement approval
for the current saved revision/runtime binding, with no Start, cancellation,
secret or target-contact path. UI-02C is DONE: `ExecutionService` uses only
the closed v1alpha2 credential-lease/Start lifecycle, while the Execution Node
creates the authoritative run ID and durably binds attempt, run and lease
before controller launch. Focused Windows and RED OS gates passed without a UI
Start path, runtime activation or target contact. UI-02D is DONE: the App
wires the runtime-only broker to the existing credentialed Start seam, projects
only closed execution event/result DTOs, and owns bounded local observer
subscriptions that detach without remote cancellation. Its generation-bound
publication prevents an old asynchronous Start/Subscribe result from binding
to a replacement project or Execution Node. UI-02E is DONE: the immutable
release `sha256:6d85afb53c6994f2f1b152e29b39a329ed35a9af7ed3e9c802be0e888993dca0`
completed two production-shaped one-host/three-member Kafka lifecycle cycles
through `CreatePlan -> ApprovePlan -> Start`. Runs
`installer-a21c3eed1d053ac7ef073e13214349a6` (12m16s) and
`installer-a3a4bba6fb97f41b21080ae22c00bcbb` (12m42s) both returned
`SUCCEEDED`; the repeat apply returned `changed=0`. PKI/Kafka apply and verify,
local Go/frontend/Wails gates, RED OS Core/race gates, reproducibility and
hygiene passed. UI-02F is DONE: it adds bounded Core-derived service-secret
descriptors, descriptor-bound session-only values, v1alpha3 lease admission
and the generic Services-page Secrets dialog without secret persistence or
projection. RED OS Core full suite (292 PASS, 4 skipped), lifecycle suite
(31 PASS), Go/frontend/Wails gates and catalog reproducibility passed. UI-02
overall is DONE. Evidence: `docs/ui-02a.md`,
`docs/ui-02b.md`, `docs/ui-02c.md`, `docs/ui-02d.md`,
`docs/ui-02e-pki-runtime-secret-transport.md` and
`docs/ui-02-architecture.md`.

## Next acceptance sequence (2026-09-23)

SERVICE-INSTALL-01 Keepalived is DONE: two production-shaped lifecycle runs
through the cumulative QA project completed `SUCCEEDED`; the repeat applied
`changed=0`. The current VIP owner is node2. SERVICE-INSTALL-02 BIND is DONE:
two production-shaped lifecycle runs completed `SUCCEEDED`; the first wrote
machine-owned generated state once and the fresh repeat applied `changed=0`
after reading the same project-identity-bound state outside its run workspace.
SERVICE-INSTALL-03 dns-client is DONE: two fresh production-shaped lifecycle
runs completed `SUCCEEDED` through the cumulative project; both recorded
`changed=0` after the corrected DNS-client verify task. SERVICE-INSTALL-04
HAProxy is DONE: two fresh Go-mediated lifecycle runs completed `SUCCEEDED`;
the second full cumulative plan recorded `changed=0`, and `haproxy.service`
is active on node1, node2 and node3. SERVICE-INSTALL-05 Kafka is DONE: the
canonical three-member deployment was accepted on three distinct target hosts;
the historical one-target QA deployment is not current deployment evidence.
SERVICE-INSTALL-06 PostgreSQL/pg_auto_failover is DONE (2026-09-24): the
isolated three-host Go lifecycle accepted a monitor on node1 and database
members on node2/node3. First run
`installer-45943379628ebee4a28716d85b571916` reached `SUCCEEDED` in 17m45s
with 65 changes; repeat run `installer-4fcc0cd5afc8689509aea2e2a49935e6`
reached `SUCCEEDED` in 17m9s with `changed=0`; both PostgreSQL verify actions
passed. By owner decision, SERVICE-INSTALL-07 is active: implement and accept
Redis `standalone` on one host and Redis/Sentinel HA with three paired members
on one host by default, with distributed three-host placement also required;
both use mandatory TLS through standalone Ansible, Core, Go
and Wails/React. Its plan is
`docs/service-install-07-redis-sentinel-architecture.md`; implementation and
acceptance are in progress. The standalone Go lifecycle passed twice:
`installer-a641eec3e9ac20867bde45bccd36dec9` succeeded with 17 changes and
`installer-679e49f37f791802b19fe3b1b07025ca` succeeded with `changed=0`.
The Sentinel 3-member/1-host deployment was added to the cumulative project;
its first full plan, `installer-8d2639ea1adaca620772383631a8a534`, failed before
Redis apply in PostgreSQL TLS resolution because several deployments shared a
TLS profile and the role selected only by host/profile. The working-tree fix
passes focused selector/lifecycle tests, all 307 Core tests, and syntax checks
for PostgreSQL, Redis, HAProxy and Kafka playbooks. A fresh immutable runtime
release must be activated before retrying the cumulative plan; Sentinel
3-member/3-host acceptance remains pending. Owner decision: at most one Redis deployment per project;
standalone QA uses an isolated project and Sentinel HA is the sole Redis
deployment in the cumulative project. Owner-approved Secrets UX for SI07:
the service dialog accepts bounded runtime-only passwords from a trusted local
catalog without Execution Node readiness; Core reconciles requirements and
the mandatory fresh plan at the installation gate, before Start. Local format
checks run immediately. The architecture-only Secrets review returned
APPROVE_WITH_CHANGES with no blocking findings; its two wording/lifecycle
clarifications are incorporated in the SI07 plan. SERVICE-INSTALL-08 is the
subsequent one-plan acceptance for all
seven services from one shared project and one approved plan, followed by
verify and a fresh repeat plan proving `changed=0`. Deployment-scoped cleanup
and before/after isolation checks must preserve other QA deployments. Exact
target addresses and resource ownership must be established before execution.
Ordered milestones: SERVICE-INSTALL-01 Keepalived, 02 BIND, 03 dns-client,
04 HAProxy, 05 Kafka (three targets), 06 PostgreSQL/pg_auto_failover DONE, 07
Redis standalone plus Sentinel HA ACTIVE, 08 one plan for all seven NEXT. Conditions: `docs/service-install-acceptance.md` and
`docs/roadmap.md`, "Post-UI-02 service installation acceptance".

## EXEC-OBS-01 completion (2026-09-05)

EXEC-OBS-01A through 01D are DONE. Managed Ansible task events use the existing
ExecutionEvent contract and authoritative Execution Node journal. Go
RunObserver provides pagination, replay, bounded typed subscriptions and the
derived Installer-side `.runtime/executions/<runId>/events.jsonl` mirror.
CLI `-command execution-watch -run-id <id>` prints the exact node/run/path,
follows until terminal and detaches on Ctrl+C without cancelling execution.

Real three-node Kafka runs `installer-1788591717613836600` (11m56s) and
`installer-1788592474776987100` (9m07s) both completed SUCCEEDED with PKI apply,
Kafka apply/verify, repeat changed=0, and 1,723 events each. Local mirror,
typed subscriber and remote stream matched. Live client/CLI restart and
Get-Content -Wait were proven. Real no_log/failure/degradation tests, Core,
Kafka/PKI, Go/race/vet, reproducibility, offline validation and secret audits
passed; both reviews have 0 blocking findings. See `docs/exec-obs-01.md` for
exact commands, test counts, durations and performance measurement limits.

UI-01A is the completed documentation freeze. UI-01B is DONE: its native
Windows Wails shell opens an existing project read-only through a READY
Execution Node and Core's fixed target-free ProjectSnapshot operation. UI-01C is
DONE: metadata-only local creation publishes one managed `project.yml`, and
empty-project reopen remains local without a Core snapshot. UI-01D is DONE by
owner acceptance without final revision-bound review: the Go-owned bounded
transient session, negotiated remote complete-candidate Core proof, guarded
first write and narrow Wails review/save shell passed Windows and RED OS
acceptance. UI-01E1 is DONE: new sessions use v1alpha4 server CRUD intents;
Core projects desired hostname, normalized SSH port and generic host references;
the staged Core-backed review/commit lifecycle is retained as historical
acceptance evidence, while ADR-027 defines the new local Save target. UI-01E2
Servers UI, UI-01E3 shared runtime session credentials, UI-01E4 Execution Node selection, UI-01E5 readiness/preparation and UI-01E6 cross-platform acceptance are DONE. UI-01F1 is DONE: lock-bound catalog and managed local topology reads passed. UI-01F2 is DONE: additive v1alpha5 topology intents, both placement forms, the final-state reducer and existing guarded local Save/reopen path passed Windows and RED OS gates with zero blocking review findings. UI-01F3 is DONE: the catalog-driven deployment editor, shared structural draft, local Review/Save and node-free reopen passed Windows and regression gates. UI-01F4 is DONE: shared member- and host-scoped placement editors use the existing session/review/local Save lifecycle; deterministic Wails frontend acceptance covers Save/reopen/clear without Core, Execution Node or target contact. UI-01F5 is DONE: Entry points reuses the five v1alpha5 endpoint intents; strict typed/bounded Go projection keeps raw Core endpoint/provider maps out of React, and INVALID exposes findings only. UI-01F6 is DONE: built Windows desktop, deterministic web-view, RED OS target-free/race and reproducibility acceptance passed. UI-01F overall is DONE; evidence is `docs/ui-01f6.md`. UI-NET-01 is DONE: v1alpha6 provider intent, guarded Save/reopen, Entry points editor and Core-preview freshness passed Windows/RED OS acceptance; evidence is `docs/ui-net-01.md`. UI-01G overall is DONE (evidence: `docs/ui-01g4.md`); UI-01H1 is DONE (evidence: `docs/ui-01h1.md`) and UI-01H2 is DONE (evidence: `docs/ui-01h2.md`); UI-01H3 is NEXT.

Status correction (2026-09-21): UI-01H overall is DONE; evidence is
`docs/ui-01h4.md`. UI-01I is DONE; evidence is `docs/ui-01i.md`. UI-01J is
DONE; evidence is `docs/ui-01j.md`. UI-01 overall is DONE. This supersedes the
preceding historical H3-next sentence.

## Phase

CORE-07, CORE-06, EXEC-01, SERVICE-01A through SERVICE-01D centralized
acceptance and the focused generic Kafka role lifecycle refactor are complete.
Ansible-native desired-state ownership and deterministic managed Kafka/PKI
projection are proven through the standalone execution path without requiring
`project.yml`.

SERVICE-02A is DONE. Named Kafka listeners, service-wide TLS profile
consumption, PKI-01 read-only verify reconstruction and SSL consumer
prerequisites are accepted through the standalone Ansible path.

NET-01 is DONE. Endpoint groups own one client-facing DNS domain and wildcard
intent; an endpoint-capable deployment assigns its group directly and Core
derives a read-only deterministic FQDN projection. Keepalived provider
deployments own virtual addresses; transport ports and routing remain deferred
to a future HAProxy milestone.

NET-02 is DONE. One host-scoped Keepalived deployment owns one unicast VRRP
instance, VRID, endpoint-group reference and one-or-more virtual addresses.
Three-node RED OS acceptance proved all-or-none VIP ownership, automatic
failover, rejoin without failback and idempotent apply/verify.

NET-03 is DONE. Authoritative BIND primary-secondary DNS derives canonical
host, endpoint and wildcard records from the Ansible-native desired state.
Three-node RED OS acceptance proved complete candidate/activation barriers,
native zone transfer, exact-once fingerprint/serial lifecycle, primary outage
continuity, recovery and idempotent verify/repeat apply.

NET-03.1 is DONE. The separate host-scoped dns-client package derives split
DNS inputs from one logical BIND deployment reference. Three-node RED OS
acceptance proved systemd-resolved route-only DNS, safe resolv.conf ownership,
normal resolver redundancy and post-recovery idempotence.

NET-04 is DONE. Host-scoped HAProxy provides HTTPS `public` routing on `*:443`,
deployment and opt-in host endpoints, normalized Host routing, and package-owned
stats backends. Three-node RED OS acceptance proved TLS endpoint verification,
runtime multi-node pooling, non-VIP-owner HAProxy failure isolation, recovery,
and idempotent verify/repeat apply.

NET-04.1 is DONE. Opt-in Keepalived HAProxy tracking uses a root-owned bounded
admin-socket helper and cluster-wide candidate/active barriers. Three-node RED
OS acceptance proved owner failure causes atomic configured-VIP migration,
natural recovery without failback, non-owner failure isolation, and idempotent
verify/repeat apply.

NET-04.2 is DONE. Successful source lifecycles run one read-only,
deduplicated integration projection, then full-model BIND before HAProxy even
when the source is already `changed=0`. Three-node acceptance proved provider
drift repair, desired-state-only add/remove, serial `4 → 5`, clean repeats,
shared PKI stability and final Keepalived health/idempotence.

UI-BE-01 is DONE. The accepted Installer boundary is a versioned query,
semantic-command and execution facade over the same canonical Ansible project.
ProjectSnapshot and other rich UI models are derived and read-only; normal
writes require EditPlan review, project/document revision checks and an
Ansible-native writer boundary. Arbitrary existing projects remain read-only
by default, while Installer-owned standard Ansible files are the recommended
write target. No production Go/Wails/React code, YAML writer or second
desired-state store was added.

UI-BE-02 is DONE. The controller-only `ProjectSnapshot/v1alpha1` query opens
the same standard Ansible project with Ansible-resolved inventory variables
and composes deterministic catalog, topology, configuration, endpoint, DNS,
HAProxy, PKI, validation and readiness views without target contact or writes.
Raw-byte project/document revisions, honest physical provenance, partial
results and secret exclusion are accepted against a three-host six-service
fixture, including offline RED OS execution.

UI-BE-03 is DONE. The Go Installer backend accepts a bounded semantic
`EditCommand`, produces an opaque reviewable `EditPlan`, proves staged native
Ansible documents through the authoritative controller-only ProjectSnapshot,
and commits only Installer-owned documents with revision/digest checks and a
journaled rollback-capable transaction. Go owns edit/session/transaction
semantics; Python/Ansible retains project loading, precedence and all
infrastructure authority. No Wails/React, apply/runtime execution, events or
second desired-state store was added.

DEVX-01 is DONE. The repository now has scoped Go/Core engineering rules,
repository-local Codex Skills for backend, adapter, writer and QA work,
documented implementer/reviewer prompt templates and a standardized final QA
workflow. Future Wails remains a thin deferred transport concern.

EXEC-01A is DONE. A trusted Linux acquisition environment builds the exact
Python/Ansible runtime closure, Go verifies and atomically publishes the
immutable bundle, and Prepare transfers, stages, proves and activates it
without requiring Python or Platform Core on Windows. Repeated Prepare returns
`READY` with `Changed:false`.

The production service entrypoint now performs one target repository probe per
requirement, calls the single existing resolver, supplies an ephemeral
target-filtered `ResolvedArtifactSource` projection to Ansible and stops before
transport when any result is `BLOCKED`. Real RED OS acceptance proved Kafka
`NOT_FOUND -> OFFLINE_BUNDLE -> artifact_delivery -> SHA-256 -> apply/verify`
with repeat `changed=0`, and three-node Keepalived
`AVAILABLE_COMPATIBLE -> REPOSITORY -> apply/verify` with repeat `changed=0`
and no artifact delivery. A separate shared-gate test proved a blocked source
cannot reach a mutation sentinel.

Operational offline bundles use only the current project-root
`bundle/<digest>/` cache entry; replacement prunes the prior local digest.
Kafka and future service payloads exist only inside a verified bundle
under `runtime/artifacts/<service>/`; `.runtime/` remains the runtime-only DEV
input and QA state.

UI-BE-04A is DONE. The actual execution implementation and published
plan/event/result contracts were audited without adding production execution
code. `docs/ui-be-04.md` freezes Core ownership of deterministic
`DeploymentPlan`, private `ExecutionManifest`, ordering and trusted execution
semantics; EXEC-01A remains the source-resolution and delivery foundation.
Future execution uses only fixed semantic Execution Node operations, a detached
Core controller, durable non-PID-only ownership, bounded journal/event replay,
reconnect, cancellation and one mutating run per project. The synchronous
Kafka/Keepalived `ExecuteService` is retained only for EXEC-01A regression.

UI-BE-04B is DONE. Core now builds the authoritative target-free public
`DeploymentPlan/v1alpha2` from its own ProjectSnapshot/validation graph and
the same full service catalog, with a private Core-only ExecutionManifest bound
to the identical plan fingerprint. `project.yml.metadata.id` is required for
Installer-managed mutation; a fallback path identity returns
`PROJECT_IDENTITY_REQUIRED` and no executable manifest. Artifact requirements,
not repository/bundle source selection, are planned. The immutable runtime
release digest is semantic; `runtime/current`, timestamps, paths, facts and
secrets are not.

UI-BE-04C is DONE. The Execution Node exposes fixed semantic lifecycle
operations, stages private digest-bound manifests, dispatches only Core-owned
trusted operation identities, and runs them through a detached transient
systemd controller. Durable journal/event replay, reconnect, exactly-once
terminal results, whole-cgroup cancellation, interrupted recovery,
foreign-unit safety and bounded retention passed RED OS acceptance. UI-BE-04D
is DONE. Go now owns only public plan approval and session lifecycle over the
typed Execution Node protocol. UI-BE-04E is DONE: the production-shaped UI
lifecycle completed two serial Kafka runs successfully under an explicit
30-minute test timeout, and the direct Kafka regression proved repeat apply
`changed=0, failed=0`. UI-BE-04 overall is DONE; documentation-only UI-01A is
DONE and UI-01B remains separately gated.

## Established direction

- V2 is an independent Git repository next to V1.
- Ansible Core is the first deliverable and must operate without Installer.
- Standard inventory, `group_vars`, `host_vars` and role defaults are the
  canonical user-owned desired-state source.
- Topology remains a first-class part of desired state.
- Service deployments, placements, direct endpoint-group assignments and certificate scopes are explicit.
- Go backend and UI are deferred until the standalone contract is proven by a production service.
- Standard `ansible-playbook` with normal inventory, `group_vars` and `host_vars` is the initial standalone interface.
- Kafka KRaft is split into single-node `SERVICE-01A`, same-host distributed
  `SERVICE-01B` and real multi-host distributed `SERVICE-01C`.
- Execution Node is a selectable logical role and may be the local Installer,
  a project target or an external Linux host; dedicated host and
  local/target-host execution are supported profiles; WSL2 is development-only.
- Initial placement is explicit only.
- Role defaults remain the canonical default source for standalone Ansible;
  schema `default` values are not semantic defaults.
- Service packages declare explicit logical-setting to role-variable mappings;
  generic Core does not infer names.
- `ResolvedTopology` and `ResolvedServiceConfiguration` are derived,
  read-only projections and never persistent sources of truth.
- Unknown Ansible variables outside service mappings remain opaque,
  pass-through values with physical origin metadata.
- Production Kafka SERVICE-01A is implemented as a standalone service package;
  Kafka-specific playbooks remain inside `services/kafka`.
- The production Kafka role is topology-profile agnostic after input
  normalization; SERVICE-01A/01B/01C names are fixture and acceptance concerns,
  not role lifecycle branches.
- `platform_desired_state` in ordinary Ansible variables owns logical
  deployment intent; inventory `platform_deployments` owns physical member
  placement, roles and member configuration.
- `platform_generated_state` is machine-owned and limited to generated
  identities, fingerprints, locks and metadata. `project.yml.desiredState` and
  legacy `platform_project` are bounded compatibility readers, not new-writer
  targets or required Ansible user input.
- Managed service projections are runtime-only. Kafka continues to consume its
  public manual `platform_kafka_instances` input in standalone mode.
- QA state invariant: stable PKI identities and fingerprints persist, while PKI
  materialization plans remain derived; every independent Ansible execution
  reconstructs those plans through read-only resolution.
- TLS-capable service apply playbooks run a service-scoped `pki-apply` stage
  before service mutation. It selects only that service type's effective
  `tlsProfile` consumers; an empty selection is a PKI no-op. The standalone
  Core PKI playbook remains intentionally project-wide.
- Kafka `clientPort` and `controllerPort` remain bounded PLAINTEXT compatibility
  inputs. SERVICE-02A introduces Kafka-package-owned named listeners; their
  default model supplies PLAINTEXT and SSL endpoints, while SASL remains out of
  scope. A Kafka deployment/member selects one `tlsProfile` for all of its SSL
  listeners; no listener owns a separate certificate profile.
- EndpointGroup owns only a client-facing domain/wildcard namespace.
  `ResolvedServiceEndpoints` is derived-only, DNS-only and is not persisted to
  generated state. A provider deployment owns virtual addresses; PKI adds them
  to SAN only through `includeEndpointVip`. Kafka has no generic NET-01
  endpoint.
- DNS logical content fingerprint and serial are machine-owned generated state.
  Each apply materializes them once, then provides the same runtime projection
  to all BIND role tasks.  Primary zones are Ansible-managed; secondary zones
  arrive only through native BIND transfer.
- DNS clients are a separate host-scoped service package. `dnsServerRef` is
  the sole logical client-to-BIND link; server addresses and managed route
  domains are derived at runtime and NET-03.1 has no generated state.
- HAProxy publication is a typed relationship from a target service deployment
  to one HAProxy deployment. Its reusable backend settings are normalized after
  layered merge; deployment and explicit `hostEndpoint: true` routes share the
  existing DNS/VIP namespace. Keepalived HAProxy tracking is explicit and
  opt-in per Keepalived deployment; a referenced HAProxy deployment must share
  its endpoint group and placement.

## Implemented

- Repository initialized.
- Architecture documentation skeleton created.
- Owner decisions OQ-001 through OQ-007 incorporated; `ARCH-01` is complete.
- Published alpha schemas for project parts, catalog, service manifest, findings,
  validation, plan, event, result and resolved service configuration.
- Standard `platform.core` validation playbook and controller-side module.
- Pure deterministic topology resolver producing canonical `ResolvedTopology`
  and a topology fingerprint from only used service-definition digests.
- Explicit placement/reference resolution with stable ordering and structured
  placement diagnostics; `host_vars` are not resolver inputs.
- Versioned `ResolvedServiceConfiguration/v1alpha1` contract.
- Deterministic deployment-level configuration resolver combining literal role
  defaults with `serviceDeployments[*].configuration` overrides.
- Deployment/member scoped configuration with
  `ROLE_DEFAULT -> DEPLOYMENT_OVERRIDE -> MEMBER_OVERRIDE` precedence and
  `VariableContext(deploymentId, memberId, hostId)` projections.
- Non-literal Ansible/Jinja defaults are represented as `DEFERRED`; exact
  static references resolve deterministically, with `UNRESOLVED` and `CYCLIC`
  findings where applicable.
- Explicit service-package configuration mappings and Kafka role defaults.
- Canonical service-manifest metadata for managed and advanced settings, with
  generated tracked configuration schemas and defaults conformance checks.
- Structured findings for unsupported member-scoped settings.
- Opaque/pass-through variables retain physical origin and redact secret-like
  values without becoming managed settings; their deterministic fingerprint is
  separate from managed configuration fingerprints.
- Independent deterministic member projections and configuration fingerprints.
- Portable valid/invalid fixtures, including Kafka and PostgreSQL topology cases.
- Kafka 4.3.1 single-node combined broker/controller role with offline artifact,
  Java 21 prerequisite, KRaft storage initialization, configuration and
  systemd apply/verify playbooks.
- Generic Kafka member lifecycle with a legacy single-member compatibility
  adapter, deterministic full/local/controller/broker member sets, controller-
  only quorum projections, role-aware listener requirements, host-scoped
  listener/path collision validation, host-once preparation and deterministic
  application of zero or more local logical members.
- Explicit mutually exclusive dynamic/static quorum modes, stable dynamic
  controller directory IDs and role-derived `process.roles`; broker-only,
  controller-only and combined internal members are no longer prohibited by
  production role assumptions.
- SERVICE-01C real three-host fixture for `192.168.56.101` through `.103`,
  dynamic KRaft quorum, with centralized Kafka acceptance completed.
- EXEC-01 execution selection contract with separate candidate eligibility and
  post-preparation readiness, generic execution-environment preparation,
  target bootstrap, local self-target transport and runtime credential boundary.
- EXEC-01 execution identity hardening: persistent runtime SSH identity and
  known-hosts state outside per-run QA workspaces, idempotent preparation and
  generic ensure-access composition for self-target and remote targets.
- CORE-06 canonical state selection with bounded legacy `platform_project`
  compatibility, inventory-owned member normalization and blocking duplicate,
  unknown-deployment and conflicting-source diagnostics.
- Deterministic Kafka runtime projection containing effective member identity,
  roles, node IDs, quorum, addresses and target paths, with a separate
  `runtimeProjectionFingerprint` over final service-relevant values.
- Kafka identity discovery and pure generate/recover/validate decisions,
  transaction-safe project/inventory persistence, disk reload and second
  validation before any Kafka mutation. Verify remains read-only.
- CORE-07 Ansible-native canonical state selection, optional project metadata,
  inventory-owned member composition and isolated generated-state schema.
  Managed Kafka identity materialization writes only
  `platform-state.yml`, reloads from disk and validates again before service
  mutation; unrelated inventory/group/host variables remain byte-preserved.
- CORE-07A authoring safety baseline: managed Kafka apply validates desired
  state before identity discovery/materialization; Kafka managed configuration
  is closed while explicit `advancedConfig` remains the controlled native
  property namespace. `hash_behaviour = merge` remains required Ansible policy.
- Managed PKI request resolution now consumes the same Ansible-native topology
  without requiring `project.yml`; standalone manual Kafka and PKI inputs remain
  supported public contracts.
- Explicit deployment-scoped Kafka clean-install and separately acknowledged
  administrative/QA host reset operations; neither is an automatic reconcile
  or identity-mismatch fallback.
- PKI-01 standalone foundation: canonical MANAGED certificate authority,
  certificate and TLS profiles; topology-derived HOST/MEMBER/DEPLOYMENT
  requests; Execution Node PEM and dedicated PKCS12 materialization; atomic
  target deployment; read-only verification; deterministic request and
  materialization fingerprints. Changed initialized identity is blocked with
  `CERTIFICATE_REISSUE_REQUIRED`.
- PKI explicit leaf reissue: `pki-reissue.yml` requires a non-empty runtime
  selection of exact request IDs. Ordinary apply still blocks changed request
  identity; the explicit operation preserves prior request material in
  protected Execution Node state, rekeys and reissues selected leaves, supports
  marker-based recovery and keeps CA identity changes blocked.
- NET-01 endpoint foundation: the rejected `endpointBindings` alpha entity was
  removed; endpoint-capable service deployments select one endpoint group;
  PostgreSQL opts in through its service manifest; pure resolution yields a
  deterministic FQDN projection and feeds PKI-01 SAN derivation without
  generated-state writes, target contact or certificate lifecycle changes.
- NET-02 Keepalived: host-scoped inventory priority, one deployment per VRRP
  election domain, deployment-owned multi-VIP addresses, native candidate
  validation and read-only all-or-none ownership verification. Three RED OS
  nodes proved failover/rejoin/no-failback; NET-04.1 later adds an explicit
  opt-in HAProxy `vrrp_script`/`track_script` dependency.
- NET-03 BIND: deterministic authoritative primary-secondary DNS with complete
  candidate and activation barriers, native secondary transfer, read-only
  verification and a generated fingerprint/serial lifecycle.  The bounded
  native configuration surface is `advancedConfig.options.minimal-responses`.
- NET-03.1 DNS client: systemd-resolved is selected whenever its unit exists;
  otherwise NetworkManager is considered only with a proven split-DNS backend.
  The role owns a resolved drop-in only, never replaces `/etc/resolv.conf`, and
  blocks unsafe ownership or global-DNS fallback.
- NET-04 HAProxy: complete candidate/activation barriers preserve the exact
  validated graph. The package provides fixed HTTPS `public` routing and
  local TLS stats backends, reloads on active-graph or TLS-bundle changes, and
  treats candidate workspace assembly as ephemeral rather than desired-state
  change.
- NET-04.1 Keepalived HAProxy tracking: the package playbook owns explicit
  prepare, activate and reconcile phases. Barrier A requires every native
  candidate validation; Barrier B requires exact candidate-to-active SHA-256
  equality and every native active validation before any reload. The helper is
  root-owned `0750`, checks active HAProxy plus its local admin socket, and has
  no `weight`; tracking failure makes the local VRRP participant ineligible.

## Completed

- POSTGRES-01 is DONE. PostgreSQL standalone and pg_auto_failover runtime
  acceptance passed, including TLS, automatic failover, natural rejoin,
  post-rejoin verify and repeat apply with `changed=0` and `failed=0` on all
  participating hosts.
- NET-03 is DONE. Three-node BIND acceptance proved host, endpoint and
  wildcard authoritative answers, native secondary transfer, exact-once serial
  increment on logical zone change, service continuity during primary outage,
  recovery, and post-recovery `changed=0 failed=0` verify/repeat apply.
- NET-03.1 is DONE. Three-node DNS-client acceptance proved the derived
  primary-plus-secondary route-only server list, normal system resolution of
  host/endpoint/wildcard records, unrelated resolution preservation, fallback
  with one remaining BIND server, recovery and `changed=0 failed=0`.

## Validation evidence

- RED OS controller VM: targeted CORE-04 suite - 15 tests passed.
- RED OS controller VM: `python3 -m unittest discover -s ansible-core/tests` -
  43 tests passed.
- RED OS controller VM: `python3 ansible-core/tools/build_fixture_catalog.py
  --check` - fixture catalog reproducibility passed.
- RED OS controller VM: Ansible validation smoke passed with `changed=0`,
  `failed=0`, and validation status `PASS` on `localhost` only.
- RED OS controller VM: privileged `unshare -n` offline check passed.
- RED OS controller VM: Kafka 4.3.1 apply and verify passed; repeat apply and
  verify passed with `changed=0` and no storage re-format.
- RED OS controller VM: offline apply through `sudo unshare -n` passed with
  `changed=0`.
- RED OS controller VM: CORE-05 contract/resolver suite, full Core regression,
  generated-schema check, catalog check and offline `unshare -n` check passed.
- RED OS controller VM: Kafka SERVICE-01A apply, verify and repeat apply passed
  with `changed=0` after the metadata migration.
- No temporary remote QA workspace or artifact copy remained after QA.
- EXEC-01 centralized RED OS acceptance: node1 as local Execution Node and
  target, node2/node3 as SSH targets; Phase A preparation, Phase B bootstrap,
  key-based ping, elevated unified playbook and repeat bootstrap all passed.
- EXEC-01 regression: 60 Core tests and 4 contract tests passed; preparation,
  bootstrap and centralized connectivity playbooks passed syntax-check; unified
  PLAY RECAP contained node1, node2 and node3 with `changed=0`.
- EXEC-01 hardening focused validation: 14 focused identity/persistence tests,
  full Core (90) and Kafka contract (16) suites passed; repeated preparation
  and centralized ensure-access passed on RED OS with node1/node2/node3 recap
  and `changed=0`. Persistent key permissions were verified as `0600` private,
  `0644` public and `0600` known-hosts.
- Centralized SERVICE-01C acceptance through node1 Execution Node passed:
  apply/repeat/verify all returned `failed=0`; repeat and verify returned
  `changed=0` for node1, node2 and node3. Stopping node3 preserved a passing
  node1/node2 quorum verify; full verify reported node3 failed; recovery and
  final verify returned all three members healthy.
- Centralized SERVICE-01A replay passed after completing its fixture inputs:
  apply, repeat and verify passed; repeat and verify returned `changed=0`.
- SERVICE-01B focused diagnosis: a fresh canonical dynamic same-host run and a
  separate `127.0.0.1` endpoint experiment both formed a three-voter quorum;
  apply/repeat/verify passed after all controller listeners were ready. The
  earlier verify failure was an immediate post-start convergence race, not a
  dynamic-quorum, identity, storage-format or endpoint incompatibility.
- Focused Kafka lifecycle refactor regression on RED OS / Ansible Core 2.18.15:
  9 Kafka contract tests and 60 Core tests passed; fixture catalog check and
  SERVICE-01A/01B/01C apply/verify syntax checks passed.
- Final real lifecycle replay passed through the centralized Execution Node:
  SERVICE-01A repeat/verify, SERVICE-01B repeat/verify and SERVICE-01C
  repeat/verify all returned `changed=0`, `failed=0`. With node3 stopped,
  node1/node2 quorum verify passed while full desired-state verify failed on
  node3; node3 recovery and final three-host verify returned `changed=0`,
  `failed=0`. Runtime QA SSH key material was removed from node2/node3.
- Centralized SERVICE-01D acceptance through node1 Execution Node passed:
  split broker/controller deployment applied and verified with six members;
  repeat apply and final verify returned `changed=0`, `failed=0`. Broker stop
  preserved controller quorum and produced the expected degraded full-state
  verification; broker recovery restored all members. Controller stop likewise
  preserved the two-controller quorum, and controller recovery restored the
  full healthy state. Readiness polling closed the bounded post-start race.
- SERVICE-01D runner lifecycle evidence is persisted under the Execution Node
  QA directory. The runner records PID/stage/status, rejects a live duplicate,
  converts an orphaned `RUNNING` state to `STALE`, and records terminal PASS or
  FAILED states without secrets.
- CORE-06 RED OS regression passed: 90 Core tests, 20 Kafka tests, 14 focused
  Kafka cleanup/contract tests and 7 privileged offline tests. Catalog and
  configuration schemas were reproducible; apply/reset syntax and diff checks
  passed.
- CORE-06 centralized FAST acceptance passed for SERVICE-01A, SERVICE-01B,
  SERVICE-01C and SERVICE-01D: apply and verify passed, and repeat apply plus
  verify returned `changed=0`. Standalone manual Kafka input remained valid.
- PKI-01 RED OS acceptance: topology-derived managed PKI apply created a
  managed CA, PEM and dedicated PKCS12 key/trust stores on node1; target verify
  and repeat apply returned `changed=0`. A changed standalone request was
  blocked with `CERTIFICATE_REISSUE_REQUIRED` before certificate mutation.
- CORE-07 RED OS regression: 104 Core tests and 22 Kafka tests passed; generated
  configuration schemas and catalog are reproducible; Core, Kafka and PKI
  syntax checks passed; privileged network-isolated validation passed with
  `localhost changed=0` and no target contact.
- CORE-07 centralized Kafka FAST acceptance passed for SERVICE-01A through
  SERVICE-01D with managed `project.yml` deliberately absent. Every apply and
  verify passed; every repeat apply returned `changed=0` on all participating
  hosts. Failure/recovery scenarios were not repeated.
- CORE-07 managed PKI no-project acceptance passed. Apply, repeat apply and
  verify returned `failed=0`; repeat apply and verify returned `changed=0`.
- CORE-07A focused RED OS validation: Core suite (107), Kafka contract suite
  (22), managed-configuration tests and catalog reproducibility passed.
- SERVICE-02A focused RED OS validation: 11 focused listener/PKI tests,
  generated configuration schema and fixture catalog reproducibility, and
  Kafka apply syntax check passed. The isolated fixture bound PLAINTEXT, SSL
  and controller listeners and completed an SSL handshake with CA verification.
- SERVICE-02A FAST regression completed on RED OS with deterministic
  profile-lifetime roots: SERVICE-01A, 01B, 01C and 01D initial apply passed;
  separate verify returned `changed=0 failed=0`; repeat apply returned
  `changed=0 failed=0` for every profile. Core suite (113) and Kafka focused
  suite (22) passed, catalog and syntax checks were reproducible, and
  `sudo unshare -n true` passed. The regression also fixed the real SSL
  handshake EOF/timeout defect and split KRaft broker/controller listener
  projection contract without changing identity or PKI lifecycle semantics.
- NET-03.1 RED OS acceptance: systemd-resolved apply configured the derived
  `~scada.local` route on node1/node2/node3; separate verify, repeat apply,
  primary failure, one-secondary-remaining failure, recovery, post-recovery
  verify and post-recovery apply all passed. Core (137), focused service
  contracts (63), generated catalog/schema, target-free validation and
  privileged offline checks passed.
- NET-04 RED OS acceptance: Barrier A/B and candidate-to-active graph equality
  passed on node1/node2/node3. TLS hostname verification passed for deployment
  and all configured host endpoints; normalized Host with and without `:443`
  selected the same backend and unknown Host returned `503`. Runtime socket
  counters proved all three pooled HAProxy participants served requests. A
  non-VIP-owner HAProxy stop returned `503` only for its host endpoint while
  pooled and other host endpoints remained healthy; recovery restored all.
  Separate verify, repeat apply, post-recovery verify and post-recovery repeat
  apply all returned `changed=0 failed=0` on localhost and every target.
  An explicit selected leaf reissue added the endpoint wildcard SAN, deployed
  it to all HAProxy participants and returned to a clean ordinary repeat apply.
- NET-04.1 RED OS acceptance: opt-in tracking candidate and active barriers
  passed on all three nodes with exact per-node candidate/active checksums.
  Stopping HAProxy on the semantic owner produced helper failure and VRRP
  FAULT, then moved all configured VIPs to one healthy backup while the
  deployment endpoint remained available. Recovery returned the former owner
  to BACKUP without failback. A non-owner HAProxy failure became FAULT without
  moving the VIP. Final Keepalived/HAProxy verify and repeat apply returned
  `changed=0 failed=0` on localhost and all targets.

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles.
- Production services beyond the accepted service slices.
- Production UI editor beyond the accepted UI-01B read-only, UI-01C
  metadata-only creation and UI-01D first-write/review slices.
- Generic backend/project persistence beyond the scoped Kafka identity
  transaction primitive.
- UI-01E4 Execution Node panel, later UI editor slices and UI-02 transport.
- Stateful listener-transition workflows; these remain deferred.
- Imported/external CA materialization, JKS, mTLS, global JVM cacerts,
  renewal and rotation.

## Next gate

CORE-01 through CORE-07, CORE-07A, PKI-01, SERVICE-01A through SERVICE-01D,
EXEC-01, the generic Kafka role lifecycle refactor, SERVICE-02A,
UI-DESIGN-01, UI-BE-01, UI-BE-02 and UI-BE-03 are complete. UI-BE-03 adds the
bounded safe writer but no Wails/React, UI persistence, execution or second
desired-state model.

POSTGRES-01, NET-01, NET-02, NET-03, NET-03.1, NET-04, NET-04.1, UI-BE-03,
DEVX-01, EXEC-01A, UI-BE-04B, UI-BE-04C, UI-BE-04D and UI-BE-04E are DONE.
UI-BE-04 overall, EXEC-OBS-01, documentation-only UI-01A, UI-01B, UI-01C and
UI-01D are DONE. UI-01D was owner-accepted without final revision-bound
review. UI-01E is decomposed into E1-E6; UI-01E1 server CRUD integration is
DONE; UI-01E2 through UI-01E6 and UI-01F1 through UI-01F6 are DONE. UI-01F
overall is DONE; UI-NET-01 is DONE, UI-01G overall and UI-01H overall are DONE, UI-01I and UI-01J
are DONE, and UI-01 overall is DONE.
