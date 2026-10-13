# `platform.core.pki_materialize`

Разрешает authorities, certificate/TLS profiles и SAN policy в derived
materialization plans, затем создаёт или явно переиздаёт managed material на
Execution Node. Используйте `pki-apply.yml`, read-only `pki-verify.yml` или
явный `pki-reissue.yml` с request IDs. Выбранный существующий request явно
переиздаётся и при неизменной certificate identity; обычный `pki-apply.yml`
сохраняет fail-closed поведение и не переиздаёт material автоматически.

Пользователь задаёт PKI в `platform_desired_state`; policy defaults находятся в
`defaults/main.yml`. Plans, runtime roots и generated identities редактировать
нельзя. `platform_pki_secret_files` содержит только mapping SecretRef →
runtime-only file, а не значения секретов.

Перед материализацией PKCS12 role проверяет наличие `keytool` на Execution
Node. Если его нет, устанавливается Java-пакет из
`platform_pki_keytool_package` (по умолчанию `java-21-openjdk-headless`), затем
наличие `keytool` проверяется повторно. Переопределите пакет для дистрибутива,
в котором он называется иначе.

Installer удерживает project-scoped advisory lock на Execution Node на всём
интервале `pki-apply.yml` или `pki-reissue.yml`, включая target deployment.
Для параллельного ручного запуска того же проекта оператор должен обернуть
весь `ansible-playbook ... pki-apply.yml ...` или
`ansible-playbook ... pki-reissue.yml ...` в `flock -n` на
`<execution-state-root>/projects/<project-id>/.pki-apply.lock`. Обычный
standalone Ansible запуск остаётся поддержан. Прямой вызов playbook без
`flock` не сериализуется с Installer и не должен выполняться параллельно с
его PKI-операциями. Lock-файл после выполнения не удаляют; блокировка
снимается ОС при завершении процесса.
