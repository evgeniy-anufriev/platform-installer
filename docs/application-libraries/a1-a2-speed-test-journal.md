# A1/A2 — журнал оптимизации скорости

Дата: 2026-10-10. Owner explicitly authorized code review и оптимизацию A1/A2.
Base master: `ae3002907842bcdf8700bfb78305fe64d7c7e3c9`.
Документация A3 сохранена отдельно; A3 implementation не выполняется.

## Scope и изменения

- prepare/prepare_runtime: lazy package scan один раз/invocation, validated
  package reuse по kind/ref; snapshot/runtime boundaries повторно проверяют bytes.
- Native resolution: удалены промежуточный effective fact и отдельный initial
  rows task; combine order/identity → parameters → final row сохранён.
- Rootless account/info/Compose discovery: один раз/account+DOCKER_CONFIG/host/run;
  dict reset в standalone preflight, platform/rootless/Swarm assertions per job.
- Preflight stat не считает ненужный checksum/MIME/attributes; Verify/archive
  сохраняют SHA256. Config directory loop нормализован/дедуплицирован.
- Derived Compose argv один раз/preflight job вместо трёх context includes,
  включая image registry override. context.yml удалён.
- Не менялись registry-first authority, fallback hashing, reserved image identity,
  ownership/symlink/ports guards, closed Compose profile, healthcheck, file SHA,
  native Compose hash, secrets lifecycle или planner guard.

Количество устранённой повторной работы: A1 native resolve на 30 placements —
31 task execution меньше; runtime preparation 30 одинаковых packages placements
загружает 2 уникальных пакета, а не 60. Account/getent/info/version discovery
на одном host с N apps/shared account выполняется один раз, а не N.
Это structural counts и focused-test evidence, не native 30-container benchmark.

## Независимое review

[FULL DIFF](a1-a2-speed-review.md): APPROVE_WITH_CHANGES, zero blockers.
Manifest SHA256 `37762c1225a11ebed909422f75aa60013e30104ad7315297ac17bf6d0c52e8ae`.
Nonblocking SPEED-D01 закрыт дополнительным read-only native QA ниже;
implementer disposition, не отдельный architecture recheck.
Production после FULL не менялась; добавлен только bounded QA файл discovery.

## Sequential before/after benchmark

RED OS node1 `192.168.56.101`, platform-automation + persistent SSH identity,
sudo -n; Docker account platform-docker, rootless runtime discovered dynamically.
Exact public image/fixture A2 сохранены. Каждый run создаёт свой уникальный QA
project: две libraries/два containers на одном host. Реальных credentials нет.
Общий сценарий: first Apply → Verify → clean repeat Apply → status/IDs/cleanup.

| Версия | QA project | Время полного testcase | Результат |
| --- | --- | --- | --- |
| master baseline | a2qa-8wimsn8k | 305.317s | PASS |
| optimized | a2qa-6_f9m1o3 | 263.973s | PASS |

Уменьшение 41.344s, примерно 13.5%, в одном сопоставимом измерении.
Baseline source c71900994f334b298e37912e6a6ae9b9; optimized source
777d75ad56d24299a4429c8efb2d730e. Native benchmark runs выполнялись последовательно,
без параллельного broad QA. Небольшие focused checks/source transfer происходили
во время ожидания: результат не является лабораторным SLA или статистической оценкой.
Полное testcase время включает fixture preparation и cleanup, не только deploy.

Optimized monotonic play durations: first Apply 100.791s, Verify 56.886s,
repeat Apply 98.756s. Baseline individual phases не измерялись; нельзя сравнивать
100.791s с прежним 307s замером одиночного Apply под parallel load.
Clean repeat changed=0, IDs preserved, /status содержит runtime-loaded config.
QA также доказывает один discovery/shared account на каждом новом invocation.

## Focused / read-only QA

- RED OS focused: A1 17 PASS (0.766s), A2 15 PASS (0.545s); current production
  source snapshot 777d75ad56d24299a4429c8efb2d730e; Apply/Verify syntax PASS.
- Новые meaningful tests: one scan/unique package loads, 30 placements,
  changed bytes detected следующим invocation, без cache между boundaries.
- Native discovery QA: 1 PASS, 31.634s. Два logical target aliases в local
  RED OS inventory, actual production routing/discover tasks, A/B/A config keys,
  два fresh ansible-playbook invocations, two discoveries/target/run, changed=0.
  Config paths отсутствуют и не создаются; credentials не требуются.
  Это проверка host-local isolation, не два физических SSH hosts.
- A1 standalone: 14 PASS, 129.827s; artifact authority: 4 PASS, 0.066s.
- Affected target-free Core regression: snapshot4 + snapshot action7 + validation24
  + deployment plan32 + plan action2 = 69 PASS. No full broad/PKI rerun claimed.
- Offline (sudo -n unshare -n): A1 17 + A2 15 + artifact4 = 36 PASS,
  0.312s/0.248s/0.018s. Network namespace только процесса, без изменения host сети.
- A2 native runtime regression: **6 PASS**, 830.585s, QA project a2qa-tbrh_0pk.
  Apply/Verify/repeat, interrupted activation/isolation, public registry с
  missing/corrupt unused fallback, selected corrupt fallback block до mutations,
  parallel libraries с different image IDs и healthy/unhealthy readiness.
  Это regression duration, не дополнительный isolated benchmark: часть начала
  выполнялась одновременно с target-free A1 QA. Production после review неизменна.

Final QA source: 60f4be2a8f254b27ae9c0973e27ffb94, scripts/qa-sync.ps1 verified.
Runtime-only benchmark outputs на node1: /tmp/a1-a2-speed-before.log,
/tmp/a1-a2-speed-after.log, /tmp/a1-a2-speed-runtime-regression.log; mode0600.
Не переносить полные успешные logs в docs.

## Final gate и cleanup

**PASS: bounded A1/A2 optimization.** 105 affected unit tests (32 A1/A2 +
artifact4 + Core69), 36 из них также offline; 14 standalone A1, один native
discovery/isolation и шесть реальных runtime scenarios. Apply/Verify syntax и
scoped git diff --check PASS. Независимое review zero blockers, SPEED-D01
дополнительная QA проверка PASS; повтор review не запускался.

Read-only exact-project audit на node1 подтвердил отсутствие контейнеров,
Compose networks и runtime project directories для a2qa-8wimsn8k,
a2qa-6_f9m1o3 и a2qa-tbrh_0pk. Проверялись exact project/network labels,
discovered Docker UID/HOME/socket и exact runtime subtree, не общий a2qa prefix.
Четыре source copies c719..., 0c49..., 777d... и 60f4... удалены через стандартный
qa-sync cleanup после завершения их процессов. QA-generated project temp roots
и discovery play temp roots очищены unittest lifecycle. Public image cache
сохранён; unrelated projects/containers и старые чужие QA roots не удалялись.
Safe benchmark/regression summaries остаются runtime-only mode0600.

Результаты относятся к зафиксированной QA копии/перечисленным Ansible changes;
появившиеся параллельно чужие Go/frontend edits не входят в scope и сохранены.
Новых source commits, bundle publication либо A3 implementation не выполнялось.

## Limits

Нет native timing 10/30 running containers, private registry credentials,
platform.variant, ALT, нового bundle/Go/UI acceptance. D03/D04 A2 остаются прежними.
Обязательные свежие guards и повторные inspections составляют оставшуюся работу;
новый generic filesystem executor, scheduler или persistent cache не добавлялись.
