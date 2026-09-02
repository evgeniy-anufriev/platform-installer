# `platform.postgresql.postgresql`

PostgreSQL 16.14 service role with standalone and `pg_auto_failover` 2.2
profiles. Package installation uses the approved RED OS system repository;
there is no runtime download fallback. User-owned configuration stores only a
username and runtime `SecretRef`; password values never enter inventory,
generated state, argv or evidence.

`platform_postgresql_clean_install=true` is an invocation-only destructive
cleanup. It requires `platform_postgresql_confirm_destructive_reset` to equal
the PostgreSQL service name, stops the selected unit, removes only the
deployment-owned data/config/log and pg_autoctl state paths, and never removes
installed packages or shared system PostgreSQL paths.
