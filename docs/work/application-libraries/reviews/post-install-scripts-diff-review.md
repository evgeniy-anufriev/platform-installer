# post_install — FULL DIFF review

Дата: 2026-10-25. Независимый architecture-reviewer, read-only.
Вердикт: BLOCK; 3 blocking findings, 1 nonblocking.
HEAD/base: 24e24f9594b38b484682d27e433bc25b572935b5; codex/szi-stage3.
Fingerprint 31 files: sha256:6836281af1723e81c73cdb3949a098b85add79a0e121eb7f5b23ba9777d525ad.
Метод: SHA256 UTF8 JSON sorted [relativePath,SHA256(bytes)].
Рассмотрен только post_install scope; предыдущий Stage3 diff не переоткрывался.

## Blocking / OPEN

- POST-D01: application_plan.py post_reads_vault выбирает Vault потребителя,
  тогда как connection credential vault_ref может принадлежать пропущенному
  провайдеру. used_script_sources/project_vault определяют владельца правильно,
  но POST_INSTALL permission его токена отсутствует. Использовать того же
  разрешённого владельца/sourceJob, без доступа ко всем Vault. Проверить
  потребителя без своего Vault и с другим Vault, точные descriptors, manifest,
  operation projection и отдельный Ansible read.
- POST-D02: build_deployment_plan action без execution_mode/prepared-images/skip
  не вызывает scope_plan. promote меняет версии на plan9/manifest7, но не
  добавляет обязательные executionMode/infrastructureVerification. Сохранить
  обычный standalone Build, обеспечив FULL_PROJECT scope до promotion.
  Проверить реальный action/entrypoint без новых опций и схемы/admission.
- POST-D03: controller dispatch trust guard не включает POST_INSTALL.
  Добавить операцию в существующий execution_target_trust.verify, проверить
  подмену staged known_hosts/marker между Verify и post_install и отсутствие
  вызова callback. StrictHostKeyChecking не заменяет этот guard.

## Nonblocking / OPEN

- POST-N01: callbacks execution_node делят project workingDirectory и
  .scripts/<id>. Разные пакеты с одинаковым id перезаписывают файлы друг друга,
  поэтому copy может давать changed на повторе, хотя скрипты changed=false.
  Добавить соответствующий тест и изоляцию на стороне вызывающей задачи
  либо явно документировать предел гарантии. Раннер оставить универсальным.

Overengineering findings0. Отдельная типизированная операция и новые версии
схем обоснованы; runner/lifecycle/lease/Vault переиспользованы. Поправка
infra verify-prefix/stats/publish для manifest7 просмотрена и учтена.

Ревью не запускало тесты и не обращалось к стенду. Известные автору результаты
не заменяют проверки крайних случаев. BLOCK приостанавливает автоматические
изменения; исправления и один TARGETED_RECHECK требуют разрешения владельца.
Повторный FULL review автоматически не запускать.

## Решение владельца 2026-10-25

Владелец отклонил все блокеры POST-D01/D02/D03 как выходящие за текущий
объём простого вызова после Apply/Verify и требующие доработки общей логики
скриптов. Автоматические исправления и TARGETED_RECHECK не разрешены и не
выполняются. POST-N01 сохранён как неблокирующее наблюдение, исправление
общего раннера не входит в этап. Исторический независимый verdict BLOCK
не переписан в APPROVE; решение о продолжении принято владельцем.
