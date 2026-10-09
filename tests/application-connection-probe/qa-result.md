# RED OS QA result — 2026-10-09

The QA image was built **on the RED OS node1** with its existing rootless Docker
daemon, from the source in this directory. Final image ID:
`sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb`.
No base image was pulled; the build uses installed Go, Vault, psql and OpenSSL.

The running container is `application-connection-probe-qa` under
`platform-docker`. It starts Vault Agent with AppRole and `env_template`, which
executes the probe. Rootless Docker publishes the endpoint only at
`127.0.0.1:18080` on node1. Runtime identity and PKCS12 files are in a protected
QA directory on node1; application passwords remain in Vault KV. The container
has a read-only root filesystem and a tmpfs for extracted PEM material.

`GET http://127.0.0.1:18080/status` returned HTTP 200 with `overall: ok` and
`ok` for PostgreSQL, Redis, Sentinel, ClickHouse, Kafka, Vault Agent, PKCS12
truststore and client keystore. PostgreSQL and ClickHouse executed `SELECT 1`
under `test-user`; Redis and Sentinel authenticated as `test-user` and returned
PONG. Kafka's SSL client listener at `192.168.56.101:9094` completed a trusted
TLS handshake and answered Kafka `ApiVersions` v0. Kafka topic authorization was
not tested because the deployment has no application ACL mechanism yet.

This is a **node1 QA instance**, not an HA credential rollout. PostgreSQL has a
QA-only `pg_hba.conf` rule for `test-user` from the rootless network; ClickHouse
has a QA-only `users.d` fragment with a read-only profile. Redis and Sentinel
ACL users were created at runtime and may disappear after a service restart or
Ansible reconciliation. AppRole, policy and per-service test credentials live in
the QA Vault path. Provider hooks and durable desired-state integration are
future application-library work; this probe is evidence for the image and
connection mechanics only.
