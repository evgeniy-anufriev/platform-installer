# `platform.core.target_bootstrap`

Создаёт на `bootstrap_targets` технического пользователя и доступ по public key;
self-target пропускается. Запуск: `bootstrap-targets.yml`, обычно через
`ensure-execution-access.yml`.

Настраиваются имя пользователя, `platform_bootstrap_public_key_file` (либо
public key) и явная sudo policy. Пароль не является desired state. После
bootstrap не правьте вручную owned authorized-keys/sudoers: меняйте входные
параметры и запускайте role повторно.
