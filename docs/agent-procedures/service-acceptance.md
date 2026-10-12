# Service installation acceptance conditions

Common conditions extracted verbatim from [the cumulative service-install plan](../work/services/service-install-acceptance.md).
These conditions do not authorize cleanup or Start. Root [AGENTS](../../AGENTS.md),
[QA](qa.md) and applicable stricter cases continue to apply.

## Общие условия каждого milestone

- Зафиксировать конкретный QA project, deployment ID, Execution Node, target
  hosts, активный digest runtime release и источник артефактов. Убедиться, что
  план построен из текущей сохранённой ревизии, одобрен и запущен по
  `CreatePlan -> ApprovePlan -> Start`.
- Перед установкой составить read-only карту существующих установок этого
  сервиса на выбранных target hosts: deployments, systemd units, порты,
  процессы, конфиги, каталоги данных, PKI-материал и зависимости. Снять
  исходное состояние соседних QA deployments.
- Старую установку выбранного сервиса, принадлежащую именно тестовому
  deployment, удалить до новой установки. Применять только подтверждённый
  service/deployment-scoped способ; не удалять данные, unit или пакет по
  одному лишь совпадению имени сервиса. Если ресурс общий, принадлежность
  не доказана или безопасного узкого удаления нет, остановить этот milestone
  и согласовать конкретный способ очистки. Не выполнять host-wide reset при
  наличии других deployments этого сервиса на хосте.
- Использовать изолированные идентификаторы и свободные адреса, порты и
  каталоги. Зависимые сервисы из предыдущих milestones могут использоваться
  как существующие предпосылки; новый milestone проверяет установку одного
  выбранного сервиса. Учитывать, что общий Core plan охватывает весь проект:
  зависимости и уже установленные сервисы могут также проходить idempotent
  apply/verify. Успех нельзя приписывать выбранному сервису лишь по общему
  `SUCCEEDED` — проверить его действия и фактическое состояние отдельно.
- Первая установка: авторитетный terminal `SUCCEEDED`, apply/verify PASS,
  фактическая работоспособность. Второй запуск: новый свежий план,
  `SUCCEEDED`, repeat apply `changed=0`, verify PASS. Зафиксировать оба run ID,
  длительность, per-host recap, relevant task events и итоговое состояние.
- Проверить до/после, что сторонние QA deployments не изменились. Секреты,
  внутренние пути к ним и приватные payloads не выводить в проект, план,
  события, mirror, Result и отчёт. Временные QA workspaces очищать после
  фиксации безопасных свидетельств. Дефект продукта устранять отдельно,
  затем повторять затронутый milestone; не засчитывать прямой Ansible запуск
  вместо полного Installer lifecycle.
- Для каждого сервиса обязательна невизуальная React/Wails integration
  acceptance: реальные React handlers/bindings → реальные Wails Go методы →
  Core/Ansible на Execution Node. Проверить применимые edit/Save, session-only
  Secrets, fresh Plan/Approve/Start, поток событий и terminal Result; для
  сервисов с защищёнными выходами также delivery/receipt/ACK. Использовать
  существующий automation seam без production bypass. Прямой Go harness и
  frontend unit tests с mocked bindings дополняют, но не заменяют этот gate.
  Зафиксировать revision/run IDs/terminal/changed и безопасные свидетельства;
  plaintext секретов не записывать. Если реальный bridge недоступен, gate
  остаётся unavailable/blocking, а не PASS по мокам. Визуальная проверка
  layout/ручные клики — отдельная проверка, не требование этого gate.
