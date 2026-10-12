# A1/A2 — независимый FULL DIFF review оптимизации выполнения

Дата: 2026-10-10. Новый scope прямо разрешён владельцем: code review A1/A2 и
оптимизация количества действий/скорости. Это отдельный performance gate,
не повтор прежнего A2 review. A3 implementation, Go/UI, release bundle вне scope.

Reviewer: architecture-reviewer `/root/a1_a2_speed_diff_review`.
Base/HEAD: master `ae3002907842bcdf8700bfb78305fe64d7c7e3c9`.
Exact 16-entry file/deletion manifest:
`.runtime/qa/a1-a2-speed-review-manifest.json`, SHA256
`37762c1225a11ebed909422f75aa60013e30104ad7315297ac17bf6d0c52e8ae`.
Все записи проверены независимо в начале и перед завершением review.

## Вердикт

**APPROVE_WITH_CHANGES, неразрешённых BLOCKING: 0.**

Review validity CURRENT для manifest. Lifetime/key/source/package/secret guard
изменения требуют оценки затронутой границы, не автоматического нового review.

## Проверенные изменения

- Package scan/load cache только внутри prepare или prepare_runtime invocation;
  между resolver/snapshot/runtime границами package digest проверяется заново.
- Native Ansible combine/precedence сохранены; убраны промежуточные facts.
- Docker account/daemon discovery keyed account + DOCKER_CONFIG, только на
  текущем target/operation, с явным reset; rootless/platform/Swarm checks per job.
- Все preflight перед Apply; ownership/symlink/ports/reserved-image checks сохранены.
- Отключены неиспользуемые stat checksum/MIME/attributes; actual archive/file
  SHA256 остаются. Дубликат config directory удалён.
- Compose argv — тот же derived context, один раз/job, включая registry override.
- Нет изменения credentials/no_log/source-selection boundary, новых API/DTO,
  stores/modules/scheduler; overengineering findings: 0.

## SPEED-D01 — NON_BLOCKING / OPEN на момент review

Места: qa_application_runtime.py:182–191, application_runtime/tasks/preflight.yml:4–9.
Native QA проверяет общий account и reset между Apply/Verify, но не два разных
account/DOCKER_CONFIG ключа на одном target. Код использует правильный составной
ключ и host-local словарь; подтверждённой ошибки изоляции нет.

Минимальное дополнение: bounded native Ansible production-task test с двумя
допустимыми ключами A/B/A; два discovery, различающиеся environments, без
третьего вызова. Проверить reset в следующем invocation и отдельный target.
Credentials не нужны. Повторное архитектурное ревью не требуется.

## Evidence / ограничения

Post-review implementer disposition SPEED-D01: RESOLVED IN QA. Добавлен
qa_application_runtime_discovery.py: production routing и discover_runtime tasks,
A/B/A для двух logical local target aliases и два fresh invocations.
RED OS 1 PASS (31.634s), changed=0. Production файлы не изменены после FULL.
Это не новый независимый recheck; reviewer такого повторного review не требовал.

Reviewer прочитал актуальные инструкции, процедуры, scoped Core rules,
ansible-core-review skill, canonical contracts, exact diff и callers.
Получены RED OS 32 focused PASS; runtime/benchmark ещё выполнялись.
Сам reviewer не запускал tests/targets и не читал secrets. Числовое ускорение
ревью не доказывает; результаты — в отдельном performance journal.
