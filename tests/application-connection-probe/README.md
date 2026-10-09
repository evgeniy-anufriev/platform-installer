# Application connection probe image (QA only)

This is the first narrow test artifact for application-library work. It is not
an application package, role, provider hook, bundle artifact or production image.

`/status` performs credentialed `SELECT 1` with PostgreSQL (psql), Redis and
Sentinel TLS `AUTH/PING`, ClickHouse HTTPS `SELECT 1`, and checks a marker delivered through
Vault Agent `env_template`. Kafka uses its client SSL listener for a TLS-protected
`ApiVersions` request without SASL or ACL; this checks reachability, not topic rights.
Successful checks return HTTP 200; any failure returns
503. Only fixed status codes appear in JSON. No credential or server error is echoed.

The image starts `/usr/bin/vault agent -config=/etc/probe/agent.hcl`. The mounted
agent file must use process supervisor `env_template` for each password and for
`PROBE_VAULT_MARKER`, then `exec { command = ["/usr/bin/connection-probe"] }`.
`agent.hcl.example` shows the expected binding shape with placeholder paths.
AppRole RoleID/SecretID delivery remains the runtime credential mechanism's job;
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
`PROBE_VAULT_MARKER`; optional `PROBE_PORT`.
Names are a QA contract, not final application package defaults.

Transfer `main.go`, Dockerfile and `build-redos.sh` to a unique temporary
directory on the owner-selected RED OS node, run `build-redos.sh`
there, and preserve the returned immutable image ID. The script uses the
installed Go, Vault, psql and OpenSSL binaries, and builds with the existing
`platform-docker` rootless daemon. It never pulls a base image.

The Compose runtime must mount `/etc/probe/agent.hcl` and truststore read-only,
mount `/run/probe` as tmpfs, restrict listener exposure to the QA network,
and supply only runtime secret files to Agent. Do not log `docker inspect` or
environment values. No infrastructure mutation is performed by this image.
