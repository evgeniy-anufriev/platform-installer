# A1 — независимое FULL PLAN review

Позднейшее решение о `connection_defaults` библиотеки по serviceType и
`connectionRef` добавлено после этого A1 review; прежний hash его не покрывает.

Позднейшие уточнения владельца об исходном общем `.env` пакета библиотеки
и автоматическом ID приложения `<application_name>-<library_instance_id>`
и пользовательских Redis parameters `user`/`password_ref` с account defaults
добавлено в технический план после указанного ниже review; эта часть его hash
и заключением не покрыта.

Дата: 2026-10-10. Вердикт независимого read-only architecture-reviewer:
**APPROVE_WITH_CHANGES**, неразрешённых BLOCKING: **0**.
Scope: только [технический план A1](../a1-technical-plan.md), его schemas,
read-only resolution, fixtures и Core projection. Реализация/Apply не разрешаются.

HEAD при review: `64e1b69a5cfacb07297e50f8c6c1dca5bb226c10`.
Проверенный SHA256 A1: `70DE5C50A4A6243AA8C4B0097937BA4E89654B06A59F00D8718C4D074A470632`.
После bounded correction SHA256:
`5CD9E97474BB9D995B77CC1DFEFEBDDFA89F85DF784DADA04E03213C08CCCA10`.
Повторное независимое ревью не выполнялось; процедура допускает очевидную
неблокирующую коррекцию без автоматического полного rerun.

## A1-P01 — NON_BLOCKING

Evidence: строки 140–151, 254–257 проверенной версии. Общий Ansible resolve
предусмотрен, но способ передачи результата existing structured action не был
определён. Готового общего entrypoint сейчас нет; риск реализации второго пути
или рекурсивного Ansible запуска из action.

Минимальная рекомендация reviewer: первой работой A1-03 выбрать конкретный
playbook/role entrypoint, способ передачи projection action-плагину и проверить
небольшой прототип двух экземпляров; не создавать Python merger.

Коррекция основного агента: в раздел 5 и A1-03 добавлен controller-only прототип
playbook → role → structured action с фактическими hostvars/defaults, machine-owned
projection и source revision. Указаны существующие project-snapshot/validate
playbooks; recursive execution и alternative desired state запрещены.
Доказательство работоспособности остаётся обязательной задачей реализации A1-03.

## Overengineering и evidence

Reviewer не выявил доказанных ненужных абстракций, дублирования DTO, преждевременного
scope, спекулятивных функций или пропуска более простого подхода. Native inventory,
role defaults, combine, existing locks и provider contracts сохранены; scheduler,
plugin DSL, signing service и новый package manager исключены.

Прочитаны CURRENT_STATE, scoped Core instructions, review procedure, task index,
общий и технический планы, релевантные project/Core contracts. Проверены schema
dispatch и resolver entrypoints project_snapshot.py/validate_project.py. Тесты и
target operations не выполнялись; ранее запущенный QA образ не доказывает A1.

Изменение canonical ownership, secret/trust boundary, resolver authority или
расширение A1 на mutations выходит за область данного заключения.
