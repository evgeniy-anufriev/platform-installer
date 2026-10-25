# post_install — FULL PLAN review

Дата: 2026-10-25. Независимый architecture-reviewer, read-only.
Вердикт: APPROVE_WITH_CHANGES; blocking0; overengineering findings0.
Рассмотренный план SHA256: 597b29449456b49a95f4bdde9f308d3e273c3a6e912dc36af2b72d9d2bd5db96.
HEAD/base: 24e24f9594b38b484682d27e433bc25b572935b5, codex/szi-stage3;
незафиксированные Stage3 изменения присутствуют.

Отдельная последняя операция обоснована: Apply и Verify — разные процессы;
конец Apply слишком ранний, side effects в Verify нарушают контракт.

Неблокирующие замечания:

- POST-P01: до реализации зафиксировать версии package/plan/manifest и capability;
  проверить новые и прежние payload Build → schema → manifest → Start.
- POST-P02: полный стабильный ключ для смешанных scope/order/id и строго
  последовательное выполнение между хостами без scheduler.
- POST-P03: проверить восстановление secret_binding и generated account secrets
  отдельным Ansible-процессом после cleanup Apply; исходного lease недостаточно.
  Использовать существующее точное чтение/защищённую materialization.

Уточнения внесены автором в план без повторного FULL review; реализация и тесты
ещё не выполнены. Независимое DIFF review потребуется после реализации.
Следующий gate по review procedure — утверждение плана владельцем.
