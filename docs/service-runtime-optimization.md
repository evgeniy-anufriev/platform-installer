# Service runtime optimization — 2026-10-09

Owner authorized optimization of service apply/verify and Redis inspection. Existing Ansible roles remain authoritative; no new cache, module, resolver, persistent state, transport setting or secret lifetime is introduced.

## Observed baseline

Execution Node run `installer-7d4d76d9fa1972a4e74b30e68c2fe38e`, bundle `si11-full-service-20261009-10`; 12:45:27–14:50:04 MSK, terminal FAILED. Nine services completed apply and verify. Redis failed on absent-unit ownership processing; Redis verify did not run. These are operation wall times from ACTION events, not predictions of savings. Task timings can overlap across hosts and must not be summed as independent wall time.

| Service | Apply | Verify |
|---|---:|---:|
| BIND | 3:45 | 0:37 |
| DNS client | 1:00 | 1:05 |
| Keepalived | 2:30 | 0:38 |
| HAProxy | 5:22 | 1:49 |
| Vault | 14:42 | 2:40 |
| Kafka | 12:55 | 6:43 |
| ClickHouse | 19:43 | 3:40 |
| Docker | 12:02 | 5:01 |
| PostgreSQL | 16:05 | 5:24 |
| Redis | 4:16 before failure | not reached |

Initial PKI apply: 4:40. This run predates the new HAProxy partial optimization and PKI batched inspection.

## Implemented changes

- BIND/Keepalived source gate runs at preparation, preserving authoritative selection before package mutation and facts across subsequent plays.
- Vault/Kafka/ClickHouse/Docker/PostgreSQL/Redis Verify does not resolve installation sources or probe repositories. Apply still requires the existing source gate; PostgreSQL retains both runtime and pg_auto_failover checks.
- BIND sends the selected repository packages to one standard package invocation. Mixed repository/offline selections remain distinct; all-offline skips it.
- ClickHouse queries four RPM identities together and rejects a wrong generation, installed standalone Keeper or duplicate package entries. Two stock systemd units are inspected together.
- Kafka reads ActiveState and MainPID together. Both active-state and positive-PID conditions remain mandatory.
- Metadata stat tasks in eight service roles disable unused MIME/attribute probing. Unused checksums are disabled; checksums required for artifact proof, candidate/active equivalence and fingerprints remain.
- Redis/Sentinel foreign-unit guards skip only explicitly skipped slurp results for absent unit files. Existing files still require exact managed headers and non-symlink regular paths.
- Redis TLS authentication, replication observations, Sentinel quorum/master agreement and readiness retries remain active. The incomplete run provides no Redis verify performance measurement.

Earlier HAProxy/PKI source optimizations retain per-service backend publication/reload and fresh integrity checks; no combined reload across services.

## Evidence and remaining gates

RED OS current-source: 20 public Apply/Verify syntax checks PASS. Service regressions: Redis13, ClickHouse1, Docker3, Kafka32, BIND15, Keepalived13, Vault29, PostgreSQL25 — 131 tests PASS. Production-task optimization fixtures: four tests PASS; real read-only RPM/systemctl fixture additionally PASS. Missing-source Apply rejection and Verify skip exercised for all eight source gates; BIND/Keepalived later-phase skip, mixed BIND source choices, Kafka inactive/no-PID, ClickHouse generation/Keeper/duplicate rejection covered.

Docker guard fixture must run as nonroot platform-automation: running it as root makes its foreign-owner fixture root-owned; correct identity passed. Vault source-mode contract assertion updated for phase-specific gates. PKI repeat/repair separately: 16-test suite and expanded corrupt/missing/mode/fingerprint repair scenario PASS.

Independent FULL DIFF APPROVE for 45-file security scope, SHA256 3B03B95F438663AF387A11EA4EB957F89861EFC5EBA7335E9E9B1B95CE955CBC, zero blockers. Additional Docker shell_environment stat metadata flags are a low-risk adjustment outside that snapshot; its runtime profile preservation/idempotence test passed. Bundle -11 released and placed in full-services/bundle, digest sha256:656a25e8db574a2095414c0483e8f12bd9ca9d6ff9eefd8c38113b87dde29f0d. Real React/Wails installation retry and measured before/after performance remain separate acceptance gates; no speedup percentage claimed.
