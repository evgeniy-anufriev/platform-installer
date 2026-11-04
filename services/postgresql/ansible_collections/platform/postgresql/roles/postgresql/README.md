# `platform.postgresql.postgresql`

Устанавливает PostgreSQL 16 из approved RED OS repositories в режимах
`standalone` и `pg_auto_failover`. Platform configuration подключается через
include; initdb-owned `postgresql.conf` не заменяется.

Запуск: `services/postgresql/playbooks/apply.yml` и `verify.yml`. Apply
подготавливает PKI. Verify выполняет `SELECT 1` на каждом экземпляре с
настроенной аутентификацией и TLS. В HA Verify также проверяет на мониторе через
`pg_autoctl show state --json`, что оба ожидаемых узла данных доступны, их
текущие и назначенные роли совпадают, а secondary входит в кворум репликации.
Настраиваются mode, member topology, port/data/config/log paths,
TLS profile, administrator и pg_auto_failover credential references.
`platform_postgresql_secret_files` содержит только runtime-only secret-file
mapping. В HA members задают monitor/database role, host address и port.

Apply сначала полностью подготавливает monitor, включая запуск и готовность,
затем последовательно data-узлы, независимо от порядка inventory. Ошибка monitor
останавливает playbook до регистрации data-узлов. Standalone выполняется как раньше.
Для собственного playbook с прямым вызовом роли также обеспечьте этот порядок.

Обе команды `pg_autoctl create` ограничены
`platform_postgresql_pg_autoctl_create_timeout` (по умолчанию 300 секунд).
После истечения срока команда получает TERM, через 5 секунд — KILL, если требуется.
Обычные временные ошибки `create postgres` сохраняют существующие 20 повторов
с паузой 3 секунды; истечение таймаута немедленно завершает задачу ошибкой,
без повторения зависшей команды. Данные сохраняются. Для длительного
первичного копирования увеличьте положительное значение таймаута в переменных Ansible.

TLS/HBA policy, Platform include, pg_autoctl lifecycle, units и credential files
принадлежат role. Не храните passwords в inventory и не меняйте `.pgpass`, PKI,
generated HBA/include, data directory или units вручную.

`platform_postgresql_clean_install` — только явное destructive recovery с
точным acknowledgement service name; обычный reconcile не очищает PGDATA и не
выполняет manual basebackup.
