# SERVICE-RUNTIME-OPTIMIZATION — independent review

## FULL DIFF — 2026-10-26

Reviewer: independent `architecture-reviewer`, `/root/service_runtime_diff_review`.
Base: `4236abaf1472761646f29b66f461e4ff3baeeaa9`.
Reviewed source/docs/tests fingerprint:
`026467446735fe0c7fb18b6edae1a6c3c64ec32565fa1634b475d784dbd025ac`.
Plan SHA256: `beee01e2e32053042ec02b6922326d70486ed47852dbd4e2388b3cacd05ade97`.
Verdict: **BLOCK**, one blocking finding. BIND/HAProxy unchanged was confirmed.

- **SRO-D01 / P2 / BLOCKING**: the new first-member condition around
  `schema_registry_topic.yml` can skip every topic check in a partial standalone
  play, or allow peers to start after the selected member fails. Minimum
  correction: remove that condition and retain the previous check per member.
- **SRO-N01 / NON_BLOCKING**: `pki-resolve.yml` duplicates the initial resolver
  play in `pki-verify.yml`; later reuse by import is possible. No new DTO,
  persistence, daemon, cross-run cache or unjustified abstraction was found.

Owner explicitly approved correcting D01, testing the standalone scenario and
one TARGETED_RECHECK. The condition was removed. Native positive/incompatible/
missing-topic scenarios on a non-seed member passed: one method, three cases,
6.972 seconds on RED OS, actual production include and topic tasks.

The reviewer did not run tests. No cold-install benchmark, new runtime bundle
or React/Wails acceptance is claimed by this review. The initial BLOCK remains
historical evidence; it is not overwritten by later results.

## TARGETED_RECHECK SRO-D01 — 2026-10-26

Verdict: **APPROVE_WITH_CHANGES**, blocking findings **0**.
Target fingerprint:
`3d65b9cee28b028e11a106515383b73bd53f36904953c61874b7d06f4fa15404`.
Scope: schema_registry_member.yml, schema_registry_topic.yml and the new partial
native test. D01 is RESOLVED; N01 remains NON_BLOCKING/OPEN. Production topic
checks match the base. No further review cycle is authorized by this result.

The subsequent bounded endpoint-source reuse change is outside this targeted
review: it reuses existing Ansible facts within one process and retains the
standalone fallback, with separate native QA. It introduces no public contract,
cross-run cache or new source of authority; no review coverage is claimed for it.

## Этап2 — FULL PLAN и FULL DIFF, 2026-10-26

Новая расширенная область явно принята владельцем; прежний D01 не пересматривался.
FULL PLAN: APPROVE_WITH_CHANGES, blocking0; исходный plan hash
`6f3431e6dd46bcb8d7f488c6f9a13187968dc2ffdd447a683f7ba57207b33297`.
N01: обе endpoint-точки/непустая service-only scope; N02: раздельные findings и
артефакты/legacy inputs; N03: полные успешные package families/смешанные источники.

FULL DIFF: **APPROVE**, blocking0, новых замечаний0. Все N01–N03 RESOLVED.
Fingerprint28 файлов этапа2:
`3450075d1aa1a9911ea2a35620b18f8124b0d62289aa8b9f7be9132631336a4c`.
Уточнённый plan hash:
`ac68284ca47c6f3314fca84181421f5954008ada39bf4726978d1240f884529b`.
Подтверждены неизменность exact source filter и Verify BIND/HAProxy, отсутствие
нового precedence resolver/cache/DTO/scheduler, сохранение PKI integrity и
публикации endpoint перед потребителями. Загрузка manifest исправлена через
фактический результат include_vars, без затенения старым set_fact.

Reviewer выполнил read-only исследование, не target QA. Результаты native QA
предоставлены родителем; safe package fixture не доказывает реальную установку
RPM. Новый bundle/React/Wails и cold benchmark остаются открытыми.

## Этап 3 — подготовка библиотек, отдельный review gate

FULL PLAN 2026-10-26: APPROVE_WITH_CHANGES, blocking0.
Исходный phase3 plan SHA256:
`4746ccf6f64592dbc7b71a4c4f219d05a4ad06b88d16c1f35458cbe2f0451b4a`.
SRO3-N01: canonical missing operations / unique resources; N02: scoped batching
и batch→account→direct последовательность; N03: partial write / fresh retry.
Ограниченные уточнения внесены, новая архитектура не вводится.
FULL DIFF и финальные результаты native QA пока pending.

Этап3 FULL DIFF: **APPROVE**, blocking0/new findings0.
12-file fingerprint:
`a7b2f61d8fb3d5aa00b35bf6f5985170386cdb03b150e2334ac0f662bf3f499e`.
Уточнённый plan SHA256:
`84d9acd8a0d1752c8a2d5e7178770cfc0522db3cf93603396b86073502d5e4bf`.
SRO3-N01–N03 RESOLVED. Reviewer проверил исходники/стабильность fingerprint;
самостоятельно native/target tests не запускал. Реальные updated-source
ACL writes, bundle/UI и benchmark не подтверждены этим ревью.

## Этап 4 — FULL PLAN / FULL DIFF и решение владельца

FULL PLAN APPROVE_WITH_CHANGES, blocking0; исходный plan SHA
74c04bfa4fadcada88ce9c6f53b850f497f6b7c5d23f18a036ffcaf64763ddca.
N01 требовал latest-destination readiness, N02 aggregate timeout/private batchfile.
FULL DIFF **BLOCK**, SRO4-D01/P1: shared directory ownership позволяет другому
аккаунту заменить соседний source file при сохранённом cache hit. Fingerprint29
44f968a631f3d85500a66cfb23f7e0cd72a8338439c57664a54d4b432c48b80b;
plan SHA0395d676f1b0ee96775670465154635a9ab3c3c8528c29a90449ef082bca8a7d.
Владелец явно выбрал «Убрать кеш файлов скриптов, оставить штатный copy» и
разрешил исправление, Ansible proof и один TARGETED_RECHECK. Source reuse удалён;
корректировка и речек ещё проверяются. Исторический BLOCK не заменён self-review.

SRO4-D01 TARGETED_RECHECK: **APPROVE**, OPEN→RESOLVED, blocking0.
Owner-approved единственный речек; исходный FULL DIFF BLOCK сохранён выше.
Fingerprint10:
a89340756dd17310bd37f768c96051a0eeeed601651e4d33f7b25a8c1d5be975.
Уточнённый plan SHA80e420b382708b2d9621699257d6ca041b19ae7c96b98b68def9faae6ffa90ab.
N01 SUPERSEDED (source cache удалён), N02 RESOLVED. Reviewer проверил actual
file/copy на каждый вызов и native A(root)/B(nobody)/A fixture; тесты сам не
запускал. Остальные принятые batch/Vault границы не менялись. Новый bundle,
реальная updated-source установка и benchmark остаются отдельной приёмкой.

### Этап5 FULL PLAN — resolver/snapshot reuse

Independent architecture-reviewer preparation_reuse_plan_review:
APPROVE_WITH_CHANGES, blocking0. Reviewed section stage5 in main plan,
original whole-file SHA256 cbb02f81bb13e5c3028dce1021439b94785b1bbd9d9ca163873b383631d3d883.
PRR-N01: before cross-request implementation define supported deterministic
contexts/eligibility; one-resolve target only for eligible inputs, unknown
external input fresh fallback. Clarification incorporated, no generic lookup parser.
PRR-N02: preserve current lightweight configuration_only preview on cache miss;
reuse complete result if already available, do not force full library resolver
for early dataRoot display. Clarification incorporated. No repeated FULL review.
Implementation remains owner-approval pending. Current installation unaffected.

### Kafka Apply serial optimization — FULL DIFF, 2026-10-27

Owner explicitly requested implementation of analysis items1/3/4 and independent
review; parallelism is excluded. Later explicit decisions remove the second
_schemas policy describe entirely and the broker-api-versions precheck before
Schema Registry. Current run and active bundle remain unchanged.

Independent architecture-reviewer `kafka_apply_serial_diff_review`:
**APPROVE_WITH_CHANGES**, unresolved blockers **0**. One FULL DIFF used; no
TARGETED_RECHECK requested or performed. Base f3225d184266ca3d1cc593265384f5355f13b07f.
Scoped diff fingerprint sha256:33bb2c8827a5330495de95e57c157f4358f938479b9d277121183a12d01f91bb.
Ten-file content fingerprint sha256:8b489366b4719b6e2c7717093f080074066057e7b184fa3421db1809c1573acc.
Hashes verified twice by reviewer; previous unrelated dirty changes were excluded.

KAS-N01 — NON_BLOCKING, low priority: add native coverage of
platform_kafka_member_pki_changed on a same-path certificate/key rotation, then
false on the unchanged repeat. Calculation was moved unchanged; no production
defect identified. The owner-authorized follow-up is test-only and does not
require another review. RESOLVED_BY_QA: expanded native test PASS (42,185с),
same-path rotation asserts true and the next unchanged repeat false/changed=0.
Only this test file was expanded after review; production scope remains identical.

Overengineering: unnecessary abstractions0, duplicated contracts/DTO0,
speculative features0, new persistence/cache/scheduler/concurrency0. Two task
files separate material preparation from listener settings; the existing direct
wrapper remains compatible without duplication.

Evidence read by reviewer: Kafka/repair61 PASS, real JVM PEM/PKCS12 four PASS,
Apply syntax PASS. Reviewer did not run tests or connect to target hosts.
Verdict is limited to the stated source scope; new bundle, real full Apply and
performance benchmark remain pending. Production scope is unchanged after review.

## Подготовка ресурсов и провайдеров — FULL DIFF 2026-10-27

Owner-approved serial scope: resolver raw defaults loading, read-only parent
observations, existing aggregate Kafka jobs/response validation, ClickHouse SQL
rendering through the existing template. PostgreSQL/Redis/Vault implementation,
parallelism, active bundle and active installation are excluded.

Independent architecture-reviewer `preparation_diff_review`: APPROVE_WITH_CHANGES,
blocking0. Base f3225d184266ca3d1cc593265384f5355f13b07f; 16file runtime scope manifest
`preparation-review-scope.json` SHA256
`5a407db21ccb6357c718ebae47b1e23b0bb298e00316517b59be6091d45daebe`, 16/16 verified.
No unnecessary mechanisms found. Architecture verdict is not overall QA acceptance.
PREP-N01 nonblocking: HA template coverage. Closed after review by test-only
standalone/raft-ha byte equality cases incl indexes/codec/settings; PASS6.141s.
Updated test SHA256 `48bf6a53f55612d5b8250ce0d7ee1576cde0d1d0285d5b341e5d8574cfa11d51`.
Production files unchanged after reviewed freeze; no second FULL review requested.

Focused RED OS83 cases OK/1 explicit SSH-target skip; Kafka native selected-library
create/repeat passes with skipInfraVerify false and true; standalone Apply syntax
PASS. Resolver baseline/current two-library application projection/status/findings
are identical. Extended legacy fixture QA has failures reproduced with prior
resolver (missing required Kafka admin reference and empty PostgreSQL parameters
rejected by current schema); broader QA completion/classification is tracked in
journal, not silently marked PASS. Updated-source real bundle/run and timing
benchmark remain pending; existing installer-c14d36d0 is not stopped.

QA closeout: native48 completed34PASS/14legacy fixture failures; Kafka12,
ClickHouse7 (real standalone/3server HA) and private-resolution1 PASS.
Corrected synthetic fixture9 PASS (runtime admin-reference input only).
Baseline topic task witness also fails before new parser, matching obsolete CLI
selector expectation. Existing14 failures remain visible, full regression is
not labelled PASS. Runtime acceptance/benchmark of new sources pending.
