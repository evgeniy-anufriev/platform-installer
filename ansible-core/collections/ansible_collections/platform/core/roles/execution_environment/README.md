# `platform.core.execution_environment`

Подготавливает Execution Node: Ansible prerequisite, workspace, persistent SSH
identity/known-hosts и при необходимости технического пользователя. Targets не
настраивает. Запуск: `prepare-execution-node.yml` или
`ensure-execution-access.yml`.

Публичные настройки: `platform_execution_workspace`,
`platform_execution_state_root`, требования Ansible/offline payload и его
несекретный путь. Технического пользователя настраивайте только при включённом
`platform_execution_manage_technical_user`.

Private workspace, identity и known-hosts — lifecycle-managed derived state.
Не редактируйте их и не передавайте private key/пароли через inventory.
