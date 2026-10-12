# Application connection probe image (QA only)

This is the first narrow test artifact for application-library work. It is not
an application package, role, provider hook, bundle artifact or production image.

`/status` performs credentialed `SELECT 1` with PostgreSQL (psql), Redis and
Sentinel TLS `AUTH/PING` plus master discovery and authenticated Redis master access,
ClickHouse HTTPS `SELECT 1`, and checks a marker delivered through
Vault Agent `env_template`. Kafka uses its client SSL listener for a TLS-protected
`ApiVersions` request without SASL or ACL; this checks reachability, not topic rights.
Successful checks return HTTP 200; any failure returns
503. Only fixed status codes appear in JSON. No credential or server error is echoed.

The image starts `/usr/bin/vault agent -config=/etc/probe/agent.hcl`. The mounted
agent file must use process supervisor `env_template` for each password and for
`PROBE_VAULT_MARKER`, then `exec { command = ["/usr/bin/connection-probe"] }`.
`agent.hcl.example` shows the expected binding shape with placeholder paths.
AppRole RoleID delivery remains the runtime credential mechanism's job;
do not put them in the image or build context.

The PKCS#12 truststore and client keystore are mounted read-only and unlocked by
passwords delivered through Vault Agent. OpenSSL extracts public CA certificates
and the client identity. psql needs PEM files; these are written only under
`/run/probe` on a **required tmpfs mount**, mode 0600. The stores/passwords never
enter the image. PostgreSQL, Redis, Sentinel and ClickHouse verify server certificates and
present the client certificate. Kafka verifies the server certificate.

Required process env: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`,
`REDIS_HOST`, `REDIS_PORT`, `REDIS_USER`, `REDIS_PASSWORD`, `SENTINEL_HOST`,
`SENTINEL_PORT`, `SENTINEL_USER`, `SENTINEL_PASSWORD`, `KAFKA_HOST`, `KAFKA_PORT`, `CLICKHOUSE_URL`,
`CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `PROBE_TRUSTSTORE_PKCS12`,
`PROBE_KEYSTORE_PKCS12`, `PROBE_KEYSTORE_PASSWORD`,
`PROBE_VAULT_MARKER`, `SENTINEL_MASTER_NAME` and `REDIS_TARGETS` (comma-separated
resolved data-member host:port addresses). `SENTINEL_MASTER_NAME` comes from the
resolved Sentinel connection's `masterName`, not a separately chosen user ID.
`KAFKA_TARGETS` can supply all advertised SSL broker host:port addresses instead
of the single `KAFKA_HOST`/`KAFKA_PORT`. Every target must return a complete,
successful ApiVersions response. Optional `PROBE_PORT`.

Explicit QA-only permission checks: `PROBE_REDIS_KEY_PREFIX` enables SET/GET/DEL
of a unique expiring fixture key and denied GET outside the namespace.
`PROBE_CLICKHOUSE_DATABASE` plus `PROBE_CLICKHOUSE_TABLE` enables a fixture-table
SELECT; `PROBE_CLICKHOUSE_DENIED_DATABASE`/`PROBE_CLICKHOUSE_DENIED_TABLE` name an
existing foreign fixture table whose SELECT must be denied. Never enable fixture writes
for production Verify; these options are solely for this test application.
Names are a QA contract, not final application package defaults.

The canonical build sources are in `docker/application-connection-probe`.
Transfer this directory with `scripts/qa-sync.ps1 -IncludeApplicationProbe`
to the owner-selected RED OS node, then run `bash build-redos.sh`
there, and preserve the returned immutable image ID. The script uses the
installed Go, Vault, psql and OpenSSL binaries, and builds with the existing
`platform-docker` rootless daemon. It never pulls a base image.

Build on RED OS from the transferred directory:

```bash
PROBE_IMAGE_TAG=platform-application-connection-probe:qa bash build-redos.sh
```

To retain the image independently of Docker's storage, save it to an operator-owned
archive directory outside the source tree:

```bash
sudo -n -u platform-docker env XDG_RUNTIME_DIR=/run/user/$(id -u platform-docker) \
  DOCKER_HOST=unix:///run/user/$(id -u platform-docker)/docker.sock \
  docker save platform-application-connection-probe:qa > /path/to/archive/probe.tar
sha256sum /path/to/archive/probe.tar > /path/to/archive/probe.tar.sha256
```

Restore with the same rootless environment and `docker load -i /path/to/archive/probe.tar`.
Generated binary, rootfs and archives are ignored by Git. Real Agent configuration,
RoleID, passwords and PKCS stores are runtime inputs and must never enter this folder.

The Compose runtime must mount `/etc/probe/agent.hcl` and truststore read-only,
mount `/run/probe` as tmpfs, restrict listener exposure to the QA network,
and supply only runtime secret files to Agent. Do not log `docker inspect` or
environment values. Only an explicitly enabled Redis fixture namespace receives
temporary QA data; the image never creates users, databases, grants or policies.
