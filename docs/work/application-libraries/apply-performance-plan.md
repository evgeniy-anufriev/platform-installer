# Ускорение Apply библиотек — технический план

Дата: 2026-10-15. Ревизия P2 (сужение scope владельцем). **Только план; реализация и target QA не разрешены этим документом.**
Основание: запрос владельца после завершения B4. Текущий статус — только в
[CURRENT_STATE](../../../CURRENT_STATE.md). Это отдельная оптимизация существующего
Apply, не начало UI-этапа C и не изменение admission библиотек.

## 1. Цель, измеренная проблема и ограничения

Уменьшить постоянную стоимость SSH и повторение endpoint-публикации при росте
числа приложений. Сохранить полный набор проверок, standalone Ansible и существующий
Build → Approve → Start → events → Cancel. Не добавлять новый execution engine,
желаемое состояние, UI-настройки, сервис, очередь или постоянный кэш здоровья.

Контрольная база: B4 commit `3fcf54c83ec13dcb2fda035862a5305c843a1095`, bundle08
`sha256:bac6ba030953635ae7e82e7ab7af68a2181baf1ef775f7de3c8c3bf989f33dfe`,
run `installer-9ba62439061817f6b571fcc8716ec91f`. Две библиотеки, три размещения,
три HAProxy-хоста, два логических endpoint sources. Сохранённый infra Verify,
ровно APPLICATION_LIBRARIES_APPLY/VERIFY, без инфраструктурных операций.

| Участок | Wall time | Наблюдение |
| --- | ---: | --- |
| Apply | 28:47 | 12:31:58Z–13:00:45Z |
| Verify | 7:57 | 13:00:45Z–13:08:42Z |
| Preflight до provider stage | 7:19 | 184 TASK_STARTED; application_runtime около6:27 |
| Проверка предков каталогов | 2:53 | Три stat-loop; checksum/MIME/attributes выключены |
| Проверка output files / чтение owner markers | 0:42 / 0:30 | Много отдельных удалённых вызовов |
| Endpoint stage | 9:18 | Два последовательных прохода примерно по4:39 |
| HAProxy внутри endpoint | 7:57 | 174 запуска задач, повторная сборка candidate |
| Общие конфиги / прежние backend-фрагменты | 0:53 / 0:42 | Повторное копирование в candidate |
| Финальные публичные HTTPS-пробы | 0:04 | Не основной источник текущей задержки |

Длительности отдельных стадий рассчитаны по границам событий, округлены до секунд.
Они не являются суммой CPU time. Для параллельных хостов нельзя складывать elapsed
всех hosts. Safe evidence: B4 journal/final summary, локальные
`.runtime/qa/b4/evidence/run9ba624-safe-events.jsonl` и `apply-task-timing.json`.
Исторические FAILED runs не переклассифицируются.

Контроллер заменяет ANSIBLE_SSH_ARGS собственным строгим набором без ControlMaster/
ControlPersist; `-F none` исключает SSH config. Активный ansible.cfg не включает
pipelining; read-only проверка показала False и forks=5. Раздельного измерения SSH
handshake нет: его вклад — обоснованная гипотеза, которую AP1 проверяет A/B.

## 2. Неизменяемые контракты

- Portable inventory/group_vars/host_vars/defaults остаются desired state.
- Проекции source IDs, provider placement, backend/FQDN/CA и probe policy вычисляет
  Core; Go/React их не воспроизводят. Никаких новых публичных DTO/wire versions.
- Проверяются все выбранные размещения, backend targets и публичные FQDN; сохраняются
  точки сетевого наблюдения, TTL, ожидаемые IP/status, TLS CA/SNI/hostname и redirect policy.
- Сохраняются owner/symlink/path guards, foreign-fragment rejection, hashes,
  полный HAProxy candidate validation, active graph equivalence и active validation.
- Неизменённые и сторонние backends/записи сохраняются. Пакетный partial scope
  никогда не превращается в full reconcile или Clear.
- Секреты только через существующий runtime lease; raw stdout/body и ключи не
  попадают в safe events. Не включать глобальный verbose/debug ради измерений.
- Исчезнувший/недописанный результат, timeout или Cancel не считаются PASS.
- Оптимизация не пропускает текущие проверки по старому здоровью/infra Verify.
- Не менять API `/status` или существующую глубину application Verify. Текущий
  endpoint HTTP check не выдавать за проверку всех восьми зависимостей.

## 3. Точки переиспользования

| Код | Изменение |
| --- | --- |
| `ansible-core/tools/execution_controller.py::_environment`, `_dispatch`, `_wait_for_operation` | Штатный transport, область mux и уборка; без второго runner |
| `ansible-core/ansible.cfg` | Стандартный Ansible pipelining; inventory precedence остаётся Ansible |
| `application-libraries-endpoint-stage.yml` | Один вызов выбранного набора вместо loop полного lifecycle по sources |
| `services/integrations/tasks/resolve-source.yml`, `apply-source.yml`, `probe-endpoint.yml` | Расширить текущие tasks для нормализованного множества источников |
| `resolve_endpoint_sources`, `resolve_service_endpoints`, `resolve_haproxy_backends`, `resolve_dns_zones` | Переиспользовать существующие список-ID входы, фильтрацию и validation |
| HAProxy `resolve/prepare/activate/activate_publish/start/endpoint_verify.yml` | Один candidate/activation на provider host; прежние барьеры |
| HAProxy `archive_managed_backends` | Прежние capture/name/hash/archive guards, не новая система rollback |
| BIND `publish_source.yml`, `update_a_record.yml` | Текущие AA/CNAME/TTL/address checks и
supdate -l`, пакет по primary/zone |
| HAProxy `check_targets.yml`, integration `probe-endpoint.yml` | Сохранить последовательные проверки, прежние semantics и позиции исполнения |
| Существующие service/Core tests и real React/Wails seam | Дополнить сценарии, не строить новый QA framework |

## 4. AP0 — фиксация baseline и критериев

1. Сохранить safe aggregate timings по stages/roles/tasks, количество targets,
   candidate builds, validations, nsupdate и reload. Счётчики — derived evidence.
2. До/после контролируемого repeat снять IDs/StartedAt/images контейнеров, KV versions,
   provider DB/account identities и grants, live HAProxy/BIND metadata и reload counters.
3. Различать logical application instance, placement/container и endpoint source:
   рост контейнеров не всегда означает столько же источников или зон.
4. Не добавлять performance database/telemetry API. Достаточно текущих events и
   небольшого QA-only отчёта; для loops фиксировать безопасный source/host identity,
   если его сейчас недостаточно, без argv/env/body/credentials.

## 5. AP1 — pipelining и SSH multiplexing

### 5.1. Pipelining

- Включить стандартный pipelining в Core ansible.cfg, используемом standalone и
  execution controller. Не хардкодить connection semantics в Go.
- Проверить `become` root и переключение на rootless Docker account, установленный
  sudo/TTY policy и read-only модули. Не менять sudoers ради ускорения.
- SCP/copy/template и модули, которым нужны файлы, продолжают использовать штатные
  механизмы Ansible. Не заменять materialization самописным shell pipeline.
- Если поддерживаемая среда несовместима, применим обычный документированный
  Ansible inventory/config override; не скрытый retry после произвольной ошибки.

### 5.2. Multiplexing с изоляцией credentials

- Добавить штатные `ControlMaster=auto`, короткий `ControlPersist` (начально60s)
  к текущим строгим SSH args. Не ослаблять `-F none`, known_hosts, StrictHostKeyChecking,
  IdentitiesOnly и существующий выбор runtime identity.
- ControlPath находится в приватном runtime-каталоге **конкретной операции**;
  owner/controller UID, mode0700, no symlink. Не использовать общий `~/.ansible/cp`.
- Нельзя разделять master между runs, operations, SSH accounts/ports, ключами или
  trust revisions. Даже при том же IP новый lease/trust context получает новый
  namespace. Короткое хешированное имя учитывает UNIX socket path limit; значения
  credentials в имени/diagnostics отсутствуют.
- Не добавлять реестр socket sessions: namespace детерминирован из текущего journal
  и operation context. Standalone использует стандартное Ansible управление
  соединением, документированное отдельно; controller не требует Go для работы.
- В `finally` существующей операции после подтверждённого завершения Ansible закрыть
  только собственные masters штатным `ssh -O exit`, затем удалить свой каталог.
  Уборка конечна по времени; не сканирует/не завершает чужие SSH процессы.
- Для Cancel/failure сохранить existing systemd/process-group semantics. Проверить,
  что фоновые masters находятся в контролируемой области и завершены; не выдавать
  подтверждённую остановку при неизвестном результате. При crash использовать
  существующую recovery/confirmed-stop ветку для того же operation namespace.
- Отзыв/смена lease и host key запрещают reuse: истёкший master не должен обходить
  новую аутентификацию. Перед следующей операцией штатная credential admission
  повторяется; mux не продлевает срок действия lease.

AP1 не меняет порядок service/provider mutations. Увеличение forks не входит в
решение: три provider-хоста уже помещаются в текущий forks=5.

## 6. AP2 — пакетная endpoint-публикация

### 6.1. Нормализация scope и совместимость

- На входе только множество source IDs, уже выбранных текущей Core-проекцией.
  Нормализовать unique/sort, проверить существование, placement и полноту hosts.
- Существующий singular `platform_haproxy_partial_deployment_id` и single-source
  entrypoints сохраняются: внутри нормализуются к singleton. Новый plural runtime
  input — минимальное расширение документированных role vars, не новое desired state.
  Одновременные противоречивые singular/plural inputs — явная ошибка до mutation.
- Пустой partial set — ошибка/отсутствие endpoint work по внешнему решению Core,
  **никогда не признак full reconcile**. Исходный full-service HAProxy путь сохранён.
- Сгруппировать по фактическому provider deployment/host и BIND primary/zone.
  Не объединять разные CA, deployment configs, listener policies и zone authority.
- Переиспользовать существующие list-ID resolvers. Union результата строится один
  раз для выбранного scope; отклонить conflicting FQDN, backend filenames, RRsets,
  TTL и несовместимые policies до любых записей. Совпадающие RRsets дедуплицируются.
- Сохранить per-source probe settings: нельзя назначить всем sources timeout,
  expected status, CA или expected IP из последней loop iteration.

### 6.2. HAProxy — один candidate на provider host

1. Capture существующего managed inventory один раз, с прежними ownership/hash guards.
2. Скопировать unchanged graph один раз; заменить только выбранные backend-фрагменты.
   Из prior inventory исключить union выбранных файлов, остальные сохранить.
3. Проверить каждый backend target с каждого участвующего HAProxy-хоста.
4. Render всех выбранных backend fragments; один полный `haproxy -c` на candidate.
5. **Барьер:** все candidates на всех provider hosts валидны до первой activation.
   `linear`/`any_errors_fatal` сохранить; не запускать mutations с `strategy: free`.
6. Прежняя activate последовательность: archive только доказанно-owned stale files,
   install выбранного графа, active digest == candidate digest, active `haproxy -c`.
7. После подтверждения activation на всех участвующих hosts — максимум один
   reload на изменившийся provider host. При неизменённом графе reload отсутствует.
8. Публиковать DNS только после успешного HAProxy activation/start barrier.

Не объявлять существующую многофайловую/многохостовую activation распределённой
атомарной транзакцией. Сейчас failure может требовать восстановления по archive
с `HAPROXY_ACTIVATION_RECOVERY_REQUIRED`; пакетный путь сохраняет это поведение и
точные recovery evidence, не добавляет автоматический global rollback.
При сбое одного source **до activation** весь его provider batch не публикуется.
Сбой после начала activation — FAILED с фактическими изменёнными hosts; DNS не
продолжать. Batch увеличивает единицу candidate, это явный trade-off.

### 6.3. BIND — один dynamic update на изменившуюся зону

Текущий механизм — **dynamic update через
supdate -l`**, не перезапись файлов зоны
и не service reload. План не заменяет его другим DNS storage/transaction engine.

1. Проверить каждый owner/zone/IPv4/TTL и primary placement прежними правилами.
2. Прочитать authoritative текущие RRsets для всех owners; сохранить AA/NOERROR либо
   NXDOMAIN проверки и запрет CNAME/foreign-owner conflict. Не менять AAAA/CNAME и
   соседние owners. Желательно один `dig` invocation на bounded набор вопросов с
   сохранением ответа/статуса каждого вопроса; не парсить перемешанный stdout без ID.
3. Вычислить только изменившиеся RRsets и передать их одним
supdate -l`/`send`
   на `(primary deployment, zone)`. Не применять общий nsupdate к разным зонам.
4. Перед mutation привязать update DNS prerequisites к наблюдённым существованию,
   type и RDATA. При конфликте этих полей — fail, не overwrite. Для NXDOMAIN
   использовать owner-not-exists prerequisite; для существующего owner без A —
   A-not-exists и CNAME-not-exists; для существующего A — точный RDATA prerequisite
   и запрет CNAME. Проверить эти условия на текущем nsupdate/BIND до реализации.
   DNS UPDATE prerequisite не сравнивает TTL: TTL проверяется до/после, но атомарный
   TTL-CAS не обещается. Конкурентный TTL-only update может быть заменён desired TTL;
   исход явно отражается в тесте, без добавления lock/transaction layer.
5. Проверить authoritative ответы и точные TTL/IP каждого изменённого owner после
   успешного send. Проверить отсутствие изменений у несвязанных контрольных owners.
6. Если изменений нет, nsupdate не выполнять; existing force-probe policy сохранить.

Размер batch обязан укладываться в ограничения используемого nsupdate/DNS message.
До реализации определить и проверить bound по фактическим encoded bytes; oversized
request отклоняется **до первого update**, без скрытого обрезания. На30–60 owners
проверить целевой сценарий. Автоматическую систему chunk/retry не добавлять в AP2;
если она необходима для согласованного scope — вернуть владельцу конкретный лимит.
DNS atomicity только внутри одного update message/zone; несколько zones не одна
транзакция. При частичном успехе сохранить точные zone outcomes, не обещать rollback
HAProxy или уже обновлённых зон. Existing repeat/reconcile восстанавливает desired state.

### 6.4. Verify и no-op

Application Verify использует ту же нормализованную группировку в read-only режиме:
без candidate install, DNS updates, archive/reload. Проверяет каждый selected source.
No-op Apply сохраняет текущие проверки; оптимизация graph equality убирает только
лишние writes/reloads, не preflight/TLS/active validation.

## 7. Проверки остаются последовательными; параллелизм отложен

Решение владельца от2026-10-15: **не добавлять параллелизм в текущую оптимизацию**.
Сначала использовать transport, пакетную публикацию и устранение повторной общей
работы. Затем измерить фактическое время Apply и остаточные bottlenecks.

- Сохранить существующие Ansible loops, uri/curl/openssl/getent и их порядок внутри
  observer host. Не добавлять probe-batch module, module_utils runner, workers,
  async jobs, scheduler, concurrency limits или новые настройки.
- Штатное уже существующее выполнение Ansible по хостам не расширяется: forks=5,
  strategy linear и existing barriers сохраняются. SSH multiplexing переиспользует
  соединения, но не разрешает параллельные mutations или сетевые пробы.
- Backend probes остаются на provider hosts, публичные DNS/HTTPS — на Execution Node.
  Все selected targets и FQDN проверяются; batching публикации не объединяет разные
  observer/TLS identities в одну проверку.
- Сохраняются прежние GET/Host, proxy/no-proxy, redirects, timeout, expected status,
  CA/SNI/hostname и DNS exact-set policies. Не менять uri на иной transport ради скорости.
- Не сокращать timeout/retry/покрытие и не пропускать проверки по старому PASS.
  Неполный результат, ошибка или Cancel не дают PASS.

Параллелизм можно рассмотреть **только отдельным запросом владельца**, если после
AP1/AP2 и других простых оптимизаций фактическое время всё ещё неприемлемо и новые
замеры показывают существенную долю независимых сетевых проверок. До такого решения
не проектировать и не писать заготовки concurrency. Сохранённый review P1 описывает
историческое более широкое предложение, а не разрешение этого отложенного scope.

## 8. Последовательность исполнения и приёмки

| Этап | Выход | Условие перехода |
| --- | --- | --- |
| AP0 | Baseline и QA fixtures | Воспроизводимые counts/timings; ничего не установлено |
| AP1 | Pipelining/mux | Положительные и отрицательные transport/lease/Cancel gates |
| AP2 | HAProxy/DNS batch | Singleton совместимость, partial preservation, failure/retry |
| AP3 | Отложен владельцем; не реализуется | Возможен только отдельный запрос после измерений всех простых оптимизаций |
| AP4 | Real-flow приёмка AP1/AP2 | Сравнение с baseline, последовательные проверки, repeat/no-op и hygiene |

Не выполнять следующую оптимизацию ради маскировки ошибки предыдущей. Один
implementation diff допускает последовательные checkpoints; immutable bundles
публикуются стандартным путём, только после окончания текущего target run.

## 9. QA-матрица

| ID | Сценарий | Обязательное доказательство |
| --- | --- | --- |
| P01 | Прежние последовательные probes после batching | Полное прежнее покрытие и GET/Host/proxy/no-proxy/redirect/timeout policies; нового concurrency нет |
| P02 | mux on/off, pipelining on/off | Те же guards/results; measured wall time/SSH reuse, без key/debug dump |
| P03 | root и rootless become, manual inventory | Нет sudo policy изменений; standalone без Go |
| P04 | Смена ключа/user/port/trust, lease expiry | Новый context не использует старый master; mismatch блокирует |
| P05 | Success/failure/Cancel/crash/reconnect | Нет чужих kills; confirmed stop/cleanup; нет оставшихся собственных SSH masters/sockets |
| P06 | Singleton/plural/full/empty/conflicting input | Совместимость single-source, отсутствие случайного full reconcile |
| P07 |2sources3placements3providers | По одному candidate/activation на provider,<=1reload при change |
| P08 |30sources с общей и разными provider/zone группами | Число common stages зависит от групп, не от sources; every target проверен |
| P09 | Один плохой backend/TLS/SNI/CA/status/redirect/proxy | Ошибка с source/host; candidate не публикуется до полного prepare barrier; нет обхода proxy/TLS |
| P10 | Foreign backend/symlink/hash/conflict | Прежний fail-closed; чужие файлы/записи неизменны |
| P11 | Сбой activation одного provider | FAILED, DNS не начат, recovery evidence соответствует факту |
| P12 | DNS CNAME/не-AA/TTL/IP/concurrent change/oversize | Нет нежелательного overwrite; точный набор RRsets и zone outcomes |
| P13 | Неизменённый Apply повторно | Container IDs/StartedAt/KV/provider identities/live graph стабильны, reload/update0 |
| P14 | Неизменённый Verify | Никаких writes/candidate install/archive/reload/nsupdate |
| P15 | Несколько tenant/source configs и CA | Нет last-loop-variable leakage и dedup разных identity |
| P16 | Последовательные timeout probes | Прежние конечные timeout/output bounds; полное покрытие, ошибка/Cancel не PASS |
| P17 | Real React/Wails libraries-only | Fresh Build/Approve/Start, saved infra proof, exact2ops, terminal/health PASS |
| P18 | Missing/stale infra proof | Прежний fixed Verify prefix, отсутствие SERVICE_APPLY |
| P19 | Hygiene/cleanup | Нет secrets в safe artifacts; only-owned temp resources удалены/исключения явно записаны |

P08 масштабный fixture требует отдельного явного разрешения на его target resources;
составление этого плана не разрешает создавать30контейнеров или менять общую infra.
До такого разрешения — native isolated tests на RED OS и synthetic target-free
projection/structural counts; не выдавать их за real30target acceptance.

Core full regression и affected HAProxy/BIND/integrations/controller/lease/service
suites — на RED OS из текущего tree через qa-sync, offline tests для pure resolve.
ALT только при ALT-specific изменениях. Go/frontend regressions требуются только
при изменениях этих слоёв; real React/Wails acceptance всё равно обязательна.
Windows не используется как Python/Ansible runtime. Проверки не ослаблять ради PASS.

## 10. Критерии скорости и сохранения поведения

- Для N selected sources, H provider hosts, Z zones: common candidate/activation
  stages O(H), не O(N*H); DNS sends O(changed Z), не O(N). Индивидуальные проверки
  остаются O(полного числа probe identities), выполняются последовательно как сейчас.
- При неизменном Apply: reload0, DNS update0, неизменные containers/KV/grants.
- AP1 отдельно измерить на той же topology; AP2 сравнить2 и30sources по числу
  common stages; время последовательных probes оценивать по числу и per-probe timeout,
  не обещать константное время при неограниченном числе endpoints.
- Целевой ориентир для исходной2source QA-topology: preflight<=3мин и endpoint<=3мин;
  это **цель измерения, не доказанный SLA**. Если не достигнута, дать breakdown,
  не вырезать проверки. Абсолютное время30sources не утверждать без target evidence.
- Не обещать ускорение user CPU/сети/занятых VM по одному результату. Сравнить
  парные runs в одной среде; повторить только при нестабильности/новых изменениях.

## 11. Review, документация и решения владельца

План P2 сужает P1: параллельные пробы и новый runner удалены по решению владельца;
независимый review P1 сохранён с исходным SHA, повторный review не выполнялся.
План архитектурно чувствителен: credential-bound connection lifecycle и provider
partial publication. Требуется один независимый FULL PLAN review текущего SHA;
вердикт не разрешает реализацию без владельца. HIGH-RISK implementation diff —
один FULL DIFF review; максимум один owner-approved targeted recheck по blockers.
BLOCK останавливает работу, не запускает цикл перепроектирования/review.

До implementation синхронизировать документированные role vars/standalone usage,
соответствующий execution contract/ADR и roadmap в части изменяемых границ;
не добавлять новый публичный mode или desired-state store. В CURRENT_STATE — только
ссылка на план/owner decision; подробные результаты в отдельном QA journal.

Минимализм: сначала стандартный transport, затем расширение текущих partial/list
hooks. Probe runner и весь новый параллелизм исключены решением владельца. Не создавать generic DAG,
framework batch jobs, persistent cache, распределённую транзакцию, новый daemon,
вторую DNS/HAProxy модель или UI performance switches. Дополнительная preflight
path batching не входит в эту ревизию: оценить только после AP1, отдельным bounded
решением, если stat loops всё ещё доминируют.
