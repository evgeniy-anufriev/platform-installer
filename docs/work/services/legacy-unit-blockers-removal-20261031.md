# Removal of installed legacy-unit blockers — 2026-10-31

Owner explicitly requested removal of legacy-deployment blockers because the
new stand has no old deployments. Redis repeat failed when deployment redis
and member redis-3 produced identical current/former systemd names. Confirmed
current unit headers were redis/redis-3/redis and redis/redis-3/sentinel.

Removed dedicated old-unit stat/assert gates in Redis, Vault, ClickHouse and
PostgreSQL, and Kafka's old-unit stat/assert and old-active-unit command/assert.
No automatic adoption, stop, deletion or migration was added. Existing current
unit path/type/ownership, data ownership, collision, listener, TLS and secret
guards remain. Compatibility readers and rejection of contradictory desired
input remain; they are not checks for installed legacy deployments.

Existing contract expectations now require absence of the removed blockers.
An actual Ansible Redis regression normalizes redis/redis-3, checks existing
owned Redis/Sentinel units twice through the production preflight task prefix,
and proves changed=0 and unchanged file contents. Only filesystem paths are
redirected into the isolated fixture. Existing missing/owned/foreign ownership
cases continue to run. A cross-service check covers all five removed gates.

## Evidence

Current sources transferred by qa-sync.ps1 to RED OS101 workspace
583821235e8b43cebfb36765498480f6; runtime-only PEM identity and sudo policy
unchanged. Focused results:

- Redis native ownership/repeat: 4 tests PASS, 12.228s;
- Redis contract: 12 tests PASS;
- Kafka SERVICE-01B contract: 23 tests PASS;
- PostgreSQL contract: 29 tests PASS;
- Vault role contract: 28 PASS, 1 existing ERROR in
  test_artifact_source_gate_matches_existing_service_mode_policy (StopIteration).
  An isolated baseline restores HEAD PostgreSQL main and unchanged peer main
  files and reproduces the same failure; this unrelated test was not weakened
  or repaired in this change. Total96 PASS/1 baseline error, no skips.

Safe outputs under .runtime/qa/approval-target-trust/: legacy-tests.txt,
legacy-baseline.txt and legacy-sync.txt. Standard QA workspace cleanup performed.
No running service, data directory or real installation was modified.

Independent FULL DIFF APPROVE, blocking0, base
eeb7cd73c6eb452e32c28e2eeff37ea57f940ac0; ten-file source diff SHA256
616fffae004d62fe5c0f4eef27f9b1c8c8451b43866e54a87686c40993c26917.
git diff --check PASS. No new abstractions or dangling legacy registers.

No updated runtime bundle or React/Wails installation acceptance is claimed.
Node2 acquisition/build host192.168.56.102 SSH timed out. Bundle-dependent
service acceptance remains pending; source must be rebuilt into a runtime
bundle and activated through ordinary preparation before production consumes it.
Pre-existing unrelated worktree changes are excluded from this commit.
