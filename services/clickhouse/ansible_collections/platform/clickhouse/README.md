# platform.clickhouse

The `clickhouse_tls` role supports one standalone server or three paired
ClickHouse server and Keeper members using ordinary Ansible variables. Runtime
secrets are supplied through protected controller-side files, never inventory.
