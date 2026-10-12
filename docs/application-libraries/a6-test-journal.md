# A6 implementation and QA journal

Date: 2026-10-11. Branch: `codex/application-libraries`.
Base HEAD: `540aa05c49ae531b3041da16cbad4771f5ccdd6e`.

## Current status

COMPLETE: standalone A6 accepted by owner on 2026-10-12. The authorized
implementation TARGETED_RECHECK returned BLOCK for D04/D07. D07 was corrected
and tested; original review results are preserved and no additional review was
requested. Real two-host application Apply, Verify, verified HTTPS /status,
ordinary repeat, full HAProxy reconcile/Verify/repeat and full BIND reconcile
with subsequent application Verify now pass. Earlier synthetic negative cases
remain separate evidence. Owner approved ClickHouse backend verify=none to
remove the QA trust prerequisite. All prior DNS records survived full reconcile.
No Go/UI acceptance or master synchronization is implied. Fixtures/containers and staged private key were cleaned; images and
protected logs were retained.

## Latest A6 recheck preparation

- D01–03 focused RED OS regression: 56 tests PASS in
  `/var/tmp/platform-installer-qa-8e0acc237b4e4e2982242b7fdbc60359`.
  Coverage includes original CLI context/limit, wrong external-DNS target,
  verified SNI/CA and negative TLS identity.
- Current-source syntax checks on RED OS: application Apply, Verify, endpoint
  stage, integration endpoint Apply, HAProxy Apply and BIND Apply — all six
  PASS. `git diff --check` is clean apart from Git line-ending warnings.
- Previous real two-host A6 run stopped at a redundant Vault-hook PKCS12
  preflight. Its nonzero result on node2 was not a Vault or application failure:
  PKCS12 validation already belongs to A5/PKI. Removed the `openssl pkcs12`
  command from the Vault provider hook and removed A6-only manual/delegated
  checks that duplicated it. A6 still checks the live `pkcs12` and
  `pkcs12Client` states on each container through `/status`.
- After this correction, Vault-focused RED OS suites: 41 PASS; application
  Apply syntax-check PASS; A6 and A4 QA harness Python compilation PASS.
  The prior 56 D01–03 focused tests and six affected playbook syntax checks
  also remain PASS.
- RED OS endpoint-stage QA workspace `/var/tmp/platform-installer-qa-39d87cef62314ea28a4532b45b8d7dae` used the actual shared Core projection, existing HAProxy source Apply/Verify tasks and BIND source update. Two synthetic `/status` listeners on node1/node2 were published through the three real HAProxy providers and BIND VIP; `apigateway-sdku.evoscada.internal` returned HTTP 200 through verified HTTPS/443. Apply repeat and read-only Verify both completed with `changed=0`.
- The first run exposed source-projection facts scoped only to the first provider host. The hook now publishes the single resolved projection once to controller facts and all provider hosts read that shared result; no resolver is rerun. A RED OS Ansible regression test covers that handoff.
- With node2's exact fixture process stopped, read-only Verify rejected the unavailable target; after restoring it, Verify passed. Wrong CA and wrong hostname each failed TLS verification. Existing ClickHouse and Vault HAProxy fragments retained their pre-test SHA-256 values on all three proxies; their DNS records still resolve to the VIP.
- This is provider-stage evidence only: no application container was running and the temporary HTTP fixture does not validate PostgreSQL/Redis/Sentinel/ClickHouse/Kafka/Vault Agent connections or the image's `/status`. Full application D04 acceptance remains pending. The authorized TARGETED_RECHECK completed with BLOCK. No Vault admin token was used or needed for this endpoint-stage test.
- Follow-up to A6-D07: the hook now normalizes one `platform_endpoint_probe_expected_addresses` value before probing. Application/Core expected addresses and existing service DNS-record addresses feed that shared probe contract; the probe itself has no application/service-specific lookup. RED OS endpoint-probe and source-projection tests: 11 PASS, including the legacy service-source case without an application source map and application wrong-address rejection. Temporary source workspace was cleaned. The targeted review remains BLOCK until the owner requests any further review; D04 application-container acceptance remains open.

## Focused evidence

- Owner-required PKI/DNS wildcard separation: endpoint projection supplies
  certificate wildcard candidates independently of DNS wildcard publication;
  existing PKI default remains enabled and explicit profile `false` disables it.
  RED OS current-source tests: PKI 13, service endpoints 9, DNS 12 PASS.
  Workspace `/var/tmp/platform-installer-qa-2589385467914602a83d7125364c3c0c`.
  Existing QA PKI CA reused to reissue only the HAProxy TLS profile through
  the Core PKI materializer; existing SAN set retained. Certificate inspection
  on nodes 192.168.56.101/.102/.103 confirms `*.evoscada.internal` on all three.
  HAProxy completed prepare, activate and start on all providers.

- RED OS QA workspace `/var/tmp/platform-installer-qa-5dd0166e724e4a5da0db6054a34a8729`,
  transferred with `scripts/qa-sync.ps1` from this working tree.
- Application suite: 78 tests PASS. Includes native Ansible defaults/snapshot
  projection for two hosts, exact source-owned fragment isolation and
  longest-domain-first frontend rendering.
- Previous source revision: DNS resolution 12 PASS and three standalone
  Apply/Verify/integration syntax checks PASS. These do not prove latest-source
  endpoint acceptance.
- New native snapshot test initially missed service collections in its test
  environment; corrected collection paths and reran all 78 application tests.
- Latest standalone Apply/Verify/integration syntax3 PASS; BIND21 PASS.
- Integration7:6 PASS/1 FAIL. Existing fixture extracts first production task by
  index, now selecting include_role rather than Initialize facts. With collection
  path supplied it fails on missing catalog_path in the isolated fixture. No
  correction made during frozen review.

## Probe recovery

Rootless Docker on node1 had no images. Owner referenced task
`01a11bc4-1df6-7303-977a-c887a6636666`. Its cleanup report says the probe
configuration directory was retained, while Docker was removed. The retained
`/var/lib/platform-app-probe-qa` contains Agent/PKCS configuration, not an image.
No Docker archive or registry transfer was found in that task.

The build context `/var/tmp/platform-app-probe-build-NqBJWrbC` still contains
Dockerfile, binary and rootfs. Recovery build uses `FROM scratch` and
`docker build --pull=false` under `platform-docker`, without acquiring artifacts.
Recovery build and image metadata verification PASS: tag
`platform-application-connection-probe:a6-recovered`, image ID
`sha256:0fc7c3d2ef93e4c7c739f308f1bab1ffe8ca1f13e822db0d16380eb633abe513`.
Entrypoint remains `/usr/bin/vault agent -config=/etc/probe/agent.hcl`.
This verifies recovery only; A6 usage remains pending.

Owner requested durable build sources under `docker/`. The canonical source,
Dockerfile, build script, placeholder Agent example, tests and documentation were
moved to `docker/application-connection-probe`; QA transfer and chapter links
were updated. Go probe tests PASS after relocation. Generated rootfs/binary/image
archives are ignored; no runtime credentials were copied.

### Owner-requested Vault backend TLS override — 2026-10-12

Owner requested `ssl verify none` for the existing QA Vault backend. Updated
`qa-vault-consumer.haproxy.backend.sslVerify: none` in the runtime full-services
inventory and the active Vault backend fragment on node1/node2/node3. Each
HAProxy configuration passed native validation; graceful reload completed and
all services are active. HTTPS frontend certificate verification remains enabled.
The Vault endpoint returned HTTP 200 with the HAProxy CA; individual proxies
returned native Vault health responses (200 active, 429 standby), and node2
returned 200 with `standbyok=true`. The preceding 503 is resolved. This operation
does not complete the open A6-D04 real application-container acceptance.

### Real two-host application acceptance — 2026-10-12

Current-source workspace: `/var/tmp/platform-installer-qa-6e7ef1a723ee46558c0633a83a24ee9e`.
Standalone test `qa_application_a6.py`: one test PASS in 487.077s, return code 0.
QA project: `a4entry-363db15e82`; Docker placements: node1 and node2.
Offline-delivered image ID:
`sha256:caa73a170e7bc73ffc6a44a37360163ceb3939f6a986abba3c867094256c0f0d`.
Both containers returned overall=ok and all checks=ok: PostgreSQL, Redis,
Sentinel, ClickHouse, Kafka SSL without authentication, Vault Agent, PKCS12 and
PKCS12 client. Verified frontend HTTPS `/status` returned 200; DNS resolved the
application name to VIP `192.168.56.111`.

Verify: localhost/node1/node2/node3 changed=0, failed=0, unreachable=0.
Repeat Apply: localhost/node1/node2/node3 changed=0, failed=0, unreachable=0.
Fixtures and both application containers were cleaned by teardown. The previous
synthetic application backend was restored in active and retained candidate
configurations on all three proxies, validated and gracefully reloaded. Images
were retained. Owner-approved Vault backend verify=none remained in place and
its frontend endpoint returned 200 with verified TLS.

The first run correctly rejected a fixture-created database without Core's
ownership witness. QA now creates managed resources through the normal provider
entrypoint before adding fixture tables. The second run rejected stale retained
Vault candidate state after the owner-approved backend override; the matching
candidate was updated after proving other files unchanged. Neither guard was
weakened. Protected logs remain under `/tmp/a4-full-services`; no credentials
are included here.

Full reconcile prerequisite: native `openssl s_client` with the active HAProxy
CA, SNI and hostname verification against all three ClickHouse targets on 8443
returned rc=1 / verify code 19 (self-signed certificate in certificate chain).
The existing ClickHouse backend requires verification. Full reconcile must
preserve this route and cannot pass its strict target preflight until the QA
trust/certificate mismatch is repaired. Only Vault verify=none was authorized;
no equivalent override was applied to ClickHouse. This is a remaining QA gate,
not a new independent review or evidence of A6 completion.
### Full provider reconciliation — 2026-10-12

Owner authorized ClickHouse backend `sslVerify: none`. This is persisted under
`qa-clickhouse.haproxy.backend` in the runtime full-services inventory, and was
applied to active and retained candidate fragments on all three proxies. Native
HAProxy validation and reload PASS; frontend certificate verification remains
active. Verified frontend requests to both Vault health and ClickHouse `/ping`
returned 200.

Current-source workspace: `/var/tmp/platform-installer-qa-c542fa50dfb3405382c535ba81eef1be`.
HAProxy role resolve SHA256:
`430ac191aae88fc753baedbe66cbe364b6a675ca258b2ad6691075b0ce8b3592`.
BIND Apply SHA256:
`6862352b566a29dd486053fd85d047fcf94d7afef6c5e3413f8c6e7498a99977`.
QA test SHA256:
`6c06e76aa4a81eeff8d208032e9cb2283a64f6e93b39504678e9ff813945ae4b`.

The existing full flag must resolve the complete backend model even when the
caller retains a source ID for its endpoint stage. Both resolver selections now
omit the partial filter in full mode. No new production tasks were added.
The QA desired model includes existing Vault and ClickHouse endpoint deployments
and their real placements, alongside the two application placements. Shared
ClickHouse's unused admin credential is omitted only from this isolated QA copy:
the current service-password requirement contract rejects duplicate ClickHouse
administrative requirement IDs. The real full-services credential is unchanged.

`a6-full-reconcile-3.log`: ordinary two-host Apply/Verify/repeat PASS, all eight
connection states=ok; full HAProxy Apply/Verify/repeat PASS and repeat changed=0
on all four Ansible hosts. The overall test initially ended FAIL after 847.824s
at direct BIND package loading. This failed combined run is preserved; it is not
reported as an overall PASS. Earlier attempts failed on duplicate administrative
requirements before application mutation.

Direct BIND QA now supplies the ordinary `platform_contracts_root` variable.
A subsequent test reached generated-state validation and exposed an integration
error: BIND passed application declarations into the legacy infrastructure
schema, which rejected the root field and misclassified `bindings.secrets` as
plaintext. Both persisted-state and next-state checks now use the same filtered
infrastructure desired state plus application snapshot findings as the existing
common Validate entrypoint. Application validation is retained, with no new
validator or production task.

Targeted `test_a6_full_dns_reconcile`: one test PASS in 445.760s, rc=0.
It creates both real application containers through standalone Apply, verifies
all eight connection states on each, runs the normal complete BIND Apply with
full reconcile enabled, then invokes application Verify. Final Verify:
localhost/node1/node2/node3 changed=0, failed=0, unreachable=0. Marker:
`A6_FULL_DNS_RECONCILE_APPLICATION_ENDPOINT_PRESERVED_PASS`.

Canonical zone comparison after `rndc sync`, excluding SOA serial and TTL:
9 records before / 10 after, zero missing; the added record is the desired
`qa-haproxy.evoscada.internal` A record. Application, Vault and ClickHouse A
records remain on VIP `192.168.56.111`. Native full reconcile therefore preserves
the application and existing infrastructure records.

HAProxy host-scope tests: 3 PASS. BIND regression: initial 19 PASS / 2 FAIL due
to tests expecting inline tasks that A6 moved into shared includes. Assertions
now follow the same production includes and retain exact primary-only DNS
ownership checks. All 21 BIND tests then PASS in 50.420s.

Cleanup: both application containers and isolated providers removed by fixture
teardown. Original synthetic application/backend graphs restored in active and
retained candidate directories on all three proxies, native-validated and
reloaded; owner Vault/ClickHouse verify=none overrides preserved. No prior DNS
record was removed. Staged SSH private key deleted; images and protected QA logs
under `/tmp/a4-full-services` retained. Source workspace verified against the
current tree and cleaned with `scripts/qa-sync.ps1`. Original independent review
BLOCK remains history; no new review occurred. Owner acceptance followed this QA snapshot.
## Owner acceptance — 2026-10-12

Owner explicitly accepted A6 and authorized a commit on `codex/application-libraries`.
Standalone A6 is complete on the recorded functional QA evidence. Historical independent
BLOCK verdicts remain unchanged; milestone closure is by owner acceptance.
PKI wildcard changes are kept separate from this A6 commit.
