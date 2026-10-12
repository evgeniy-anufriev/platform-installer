# Cumulative service-install historical evidence

Recorded checkpoints from [the cumulative acceptance plan](../service-install-acceptance.md).
Current status and owner decisions remain in [CURRENT_STATE](../../../../CURRENT_STATE.md).

## Recorded status snapshot

Статус: SERVICE-INSTALL-01 DONE; SERVICE-INSTALL-02 DONE; SERVICE-INSTALL-03 DONE;
SERVICE-INSTALL-04 DONE; SERVICE-INSTALL-05 DONE; SERVICE-INSTALL-06 DONE.
SERVICE-INSTALL-07 Redis standalone и Sentinel HA; SERVICE-INSTALL-08 — Vault
(1/1, 3/1, 3/3) technical DONE; SERVICE-INSTALL-09 — ClickHouse
(1/1 standalone без Keeper, 3/1 и 3/3 server+Keeper), PLAN;
SERVICE-INSTALL-10 — общий план для девяти сервисов. Исторический UI-02E
тест Kafka (три экземпляра на одном target) остаётся завершённым и не заменяет
SERVICE-INSTALL-05 (три target).

## SERVICE-INSTALL-01 — Keepalived

### Evidence (2026-09-23)

- Cumulative project: `.runtime/qa/service-install-cumulative-project`; its
  immutable runtime lock and active Execution Node runtime were both rebound to
  `sha256:6d85afb53c6994f2f1b152e29b39a329ed35a9af7ed3e9c802be0e888993dca0`.
- The read-only preflight found no active Keepalived unit, test VIP or
  deployment-scoped configuration on node1, node2 or node3.
- Fresh lifecycle runs `installer-5bd04f686b8b5f5f3f936e91a95c6130`
  (3m07s, `changed=6`) and `installer-0f8a485c5b62ff59edd481e3a02bdb0b`
  (2m50s, repeat `changed=0`) both completed `SUCCEEDED`; each recorded
  Keepalived apply and verify success.
- `keepalived.service` is active on all three nodes. The isolated VRID is 61;
  the test VIP `192.168.56.121/32` is currently owned by node2, while node1
  and node3 correctly remain non-owners. The generated configuration declares
  priorities 150, 120 and 100 respectively.
- The authoritative plan contained only the isolated Keepalived deployment;
  no unrelated service deployment was launched.

## SERVICE-INSTALL-02 — BIND

### Evidence (2026-09-23)

- Immutable QA runtime `sha256:5c3188765226fbae6c7de563a1545e613b5970c1a3cd229d48cc21bec763e4e3`
  was activated on the READY Execution Node and bound to the cumulative project
  before the lifecycle runs.
- The Execution Node owns
  `projects/project-64791354ab381f68/generated/platform-state.yml`; it is a
  regular `0600` file keyed by stable project identity, outside archived
  project copies and ephemeral run workspaces.
- Fresh run `installer-05b9e466943edcb5036297d81d418f04` completed
  `SUCCEEDED` in 5m37s with BIND apply/verify success and one real change:
  initial generated-state publication.
- Fresh repeat `installer-3f66123f69d0f83d4e5b6b6c3ae009c6` completed
  `SUCCEEDED` in 5m24s. It loaded and schema-validated the same persistent
  state before reconciliation; BIND apply/verify succeeded and the complete
  plan recorded `changed=0`.
- Keepalived remained part of the cumulative plan and its apply/verify also
  succeeded without changes. No separate project or direct Ansible substitute
  was used.

## SERVICE-INSTALL-03 — dns-client

### Evidence (2026-09-23)

- The dns-client catalog descriptor declares the trusted closed
  `SERVICE_DEPLOYMENT` reference kind for `dnsServerRef`; the cumulative
  project therefore added `service-install-03-dns-client` through typed Go
  EditSession → Review → local Save, referencing only the accepted
  `service-install-02-bind` deployment.
- The initial lifecycle failure was a YAML parse defect in the NetworkManager
  branch of the read-only verify task. It was corrected, syntax-checked on
  RED OS and delivered in immutable runtime
  `sha256:4fd2c1c1f9b876cde9ee7b2b8ae0918b35ecd984aedfa783426e53b578eda0e2`.
  The cumulative project was rebound to that exact runtime and catalog lock
  pair by the QA-only resumable CAS promotion helper.
- Fresh runs `installer-6264b96222b402c24a7d77929bc99d92` (7m12s) and
  `installer-1f0bfd7a8b86592037c15c215bb10a07` (7m02s) both completed
  `SUCCEEDED`. Each recorded DNS-client apply and verify success; both complete
  cumulative plans recorded `changed=0`.
- On node1, node2 and node3, `systemd-resolved.service`, `named.service` and
  `keepalived.service` remained active. The managed resolver drop-in contains
  the three authoritative DNS addresses and route-only `~scada.local`; the
  effective resolver state matches it. No unrelated resolver ownership was
  overwritten.

## SERVICE-INSTALL-04 — HAProxy

### Evidence (2026-09-23)

- Cumulative project added `service-install-04-haproxy` solely through the
  typed Go EditSession → Review → local Save lifecycle. It uses the existing
  three target hosts, isolated priorities 150/120/100, and the managed TLS
  profile `service-install-haproxy-tls`; no inventory or host-vars file was
  hand-authored.
- The immutable runtime
  `sha256:ecb5342cf4a1000d72c0a792bf56f48569fd198447700e98941170485401df7f`
  binds Core-derived PKI materialization plans into the digest-protected
  private ExecutionManifest and controller-only runtime projection, and makes
  the HAProxy role project its one local deployment's configured TLS profile.
  Neither change adds PKI plans, SecretRefs or passwords to the portable
  project, public plan, events or UI.
- Fresh Go-mediated `CreatePlan → ApprovePlan → Start` runs
  `installer-12b577ff3cd57e17a6a69e61560b88a7` (14m04s) and
  `installer-3dfe62bccd8a15dcbb9893b268a41fd2` (15m44s) both reached terminal
  `SUCCEEDED`. Each recorded HAProxy apply and verify success; the repeat
  complete cumulative lifecycle recorded real `changed=0`.
- `haproxy.service` is `active` on node1, node2 and node3. Keepalived, BIND
  and dns-client stayed part of both cumulative plans and completed without
  regression. `TASK_EVENT_STREAM_TRUNCATED` late in verify was
  observability-only and did not alter either terminal result.
- RED OS Core suite passed (284 tests, 4 expected skips), HAProxy syntax check
  passed, and fixture catalog plus service configuration schemas remained
  reproducible.
