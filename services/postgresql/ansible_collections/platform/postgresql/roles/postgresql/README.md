# `platform.postgresql.postgresql`

Устанавливает PostgreSQL 16 из approved RED OS repositories в режимах
`standalone` и `pg_auto_failover`. Platform configuration подключается через
include; initdb-owned `postgresql.conf` не заменяется.

Запуск: `services/postgresql/playbooks/apply.yml` и `verify.yml`; оба включают
PKI lifecycle. Настраиваются mode, member topology, port/data/config/log paths,
TLS profile, administrator и pg_auto_failover credential references.
`platform_postgresql_secret_files` содержит только runtime-only secret-file
mapping. В HA members задают monitor/database role, host address и port.

TLS/HBA policy, Platform include, pg_autoctl lifecycle, units и credential files
принадлежат role. Не храните passwords в inventory и не меняйте `.pgpass`, PKI,
generated HBA/include, data directory или units вручную.

`platform_postgresql_clean_install` — только явное destructive recovery с
точным acknowledgement service name; обычный reconcile не очищает PGDATA и не
выполняет manual basebackup.
