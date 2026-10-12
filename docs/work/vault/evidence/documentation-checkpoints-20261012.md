# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## si08-output-run-delivery-decoupling.md

Source document: [si08-output-run-delivery-decoupling.md](../si08-output-run-delivery-decoupling.md).

<a id="si08-output-run-delivery-decoupling-checkpoint-001"></a>

Статус: согласованное владельцем поведение; план для точечной архитектурной
проверки. Реализация и приёмка ещё не выполнены.


## service-install-08f-vault-endpoint-ha.md

Source document: [service-install-08f-vault-endpoint-ha.md](../service-install-08f-vault-endpoint-ha.md).

<a id="service-install-08f-vault-endpoint-ha-checkpoint-001"></a>

## Acceptance evidence (2026-09-29)

- Fresh managed project `project-e74f53b99dd648d4`, canonical revision
  `sha256:5e9c6fc52f0c760a15083b797831f4122ca87d17426f14c277dea07f0a65e6cb`,
  remained byte-revision-identical after both runs. Pinned immutable release
  `sha256:9b0beb40e91b1a1beb20d14096ecd6a45c09274053b6f0bdf412a8424e7a6e3c`
  was still active on the Execution Node after acceptance. Catalog digest
  `sha256:3e92c57ff09461262be6a75d40a21713e7499eb8a984167498a885bd9787385d`.
- Real nonvisual React/Wails flow opened the managed project, selected the
  READY Execution Node, imported encrypted Vault admin-token/unseal-share
  inputs through the service Secrets dialog, built plan
  `plan-7ef0fd3def229115d95c955f`, approved it, supplied the runtime output
  encryption password, started and observed the authoritative run. No mock
  binding or test-only Start path substituted for the Wails Go method.
- Fresh run `installer-56f9aa6637457b0bcf119b6b3abfa0f4` SUCCEEDED
  10:11:52–10:47:47 UTC (35m55s), terminal sequence 3095. PKI apply, four
  service apply actions and four verify actions all SUCCESS. Task results:
  1552 SUCCESS, 421 SKIPPED, 18 CHANGED, 0 FAILED.
- Its independent DNS audit found a cross-project serial collision: new
  project-generated BIND serial 1 matched the serial already served by the
  prior QA zone, so secondaries did not transfer the changed zone. The
  explicit `recover_dns_lifecycle` contract requires the audited historical
  fingerprint and observed SOA serials for exactly all current participants;
  it cannot safely infer those from the new project. Supplying that evidence
  through a temporary runtime-only recovery input advanced the new project's
  persistent state to serial 2. All three authoritative DNS nodes then
  returned `vault-endpoint-ha.asutp.scada.local` → `192.168.56.121` with SOA
  serial 2. No zone file was edited by hand.
- Strict repeat via the same real React/Wails flow, same plan/revision:
  `installer-06510ac6068d9b7a695599d14850d32e` SUCCEEDED
  11:04:50–11:45:44 UTC (40m54s), terminal sequence 3095. All nine actions
  SUCCESS; 1564 task SUCCESS, 427 SKIPPED, **0 CHANGED**, 0 FAILED, no
  sequence gaps or degraded-observability diagnostics. Both run journals
  contained zero forbidden secret-bearing event fields.
- Three exact current Vault units remained active; file audit, KV v2,
  userpass and three Raft voters were confirmed through authenticated API.
  All three HAProxy nodes passed `haproxy -c` and had byte-identical backend
  fragments (SHA-256 `9e1dcd689b115e35ce672100f7674fe3011d95c8be88328b76aff8f833eb93c0`)
  with precisely three `:8200` Vault member targets and `ssl verify required`
  plus `verifyhost vault-endpoint-ha.asutp.scada.local`. `named`, `haproxy`
  and `keepalived` were active on all three; the VIP remained reachable.
- Authenticated KV marker write/read succeeded directly and through DNS/VIP
  from all three nodes. Vault's `/sys/health` can return HTTP 429 when the
  load balancer selects a healthy standby; this did not break authenticated
  client KV traffic. Leader `step-down` moved active status from node1 to
  node2 (HTTP 204); the VIP still served the marker. Stopping only the exact
  node2 Vault unit caused node1 to become leader, and VIP marker read again
  returned HTTP 200. The node2 unit was restarted and explicitly unsealed
  with two protected shares; all three ended initialized/unsealed, one active
  and two standby, with three voters and the marker still accessible.
- Final gates: RED OS Core 416 OK (19 skips, 440.563s); focused PKI 10 OK;
  BIND 11 OK, HAProxy 17 OK (9 skips), Vault 28 OK; catalog/schema
  reproducibility PASS; Windows `go test ./...`, `go vet ./...`, fresh
  executionnode/secretfiles/root Go tests PASS; RED OS race executionnode,
  runtimesecret and secretfiles PASS; frontend lint/67 tests/build PASS;
  Wails production build PASS; `git diff --check` PASS. Six exact remote
  temporary QA workspaces were removed. Source and QA changes were recorded
  in focused commits `f23fb9a`, `d1c0612`, `d1df02d`, `c6f066b`,
  `2b67ed8` and `9773413`; this document records the final acceptance.


<a id="service-install-08f-vault-endpoint-ha-checkpoint-002"></a>

Status: technical acceptance DONE (2026-09-29). SI08-E Vault 1/1, 3/1 and
3/3 acceptance is complete; SI09 all-services execution remains separate and
is not started here.


## service-install-08e-follower-unseal-fix.md

Source document: [service-install-08e-follower-unseal-fix.md](../service-install-08e-follower-unseal-fix.md).

<a id="service-install-08e-follower-unseal-fix-checkpoint-001"></a>

## Regression evidence

Fresh RED OS source transfer used `scripts/qa-sync.ps1`; its temporary workspace
was removed afterward. `python3 -m unittest discover -s services/vault/tests -v`:
21 PASS in 2.535s. The new focused test validates the outer loop variable and
uses real Ansible Templar to resolve follower identity and TLS API endpoints
for colocated and distributed members without a recursive override.
Catalog/configuration-schema reproducibility, verifier syntax-check,
`go test ./...`, `go vet ./...` and `git diff --check`: PASS.



<a id="service-install-08e-follower-unseal-fix-checkpoint-002"></a>

## Real HA 3/1 recovery

Immutable release `qa-si08-vault-20260928-15`:
`sha256:c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03`.
Catalog unchanged. Supported QA promotion verified/published/activated the
new release and advanced project locks through guarded CAS.

The preceding failed run's bootstrap package was delivered and acknowledged
through actual React/Wails into encrypted files under `secrets/vault-qa-ha31/`.
The actual React secret-file handlers imported both files into the session.
No token/shares were logged and no initialized seed was reset or reinitialized.

Fresh plan `plan-c0ccd228d15b7c1481d0b0f1`, saved revision
`sha256:ddf3f1e2c8248810ae69c30b08a963f3b00a7061f71a72d89fa434a9004f70e4`.
Actual React/Wails approval/Start/observe/result:
`installer-1fc2dacbcb428c7ebf2375f981086e12` SUCCEEDED in 2160s (36m),
terminal sequence 942. PKI/apply/verify SUCCESS at sequences 149/761/941.
Task stream: 367 SUCCESS, 98 SKIPPED, 1 CHANGED, 0 FAILED; no sequence gaps
or degraded task observability. The single changed task started the previously
unstarted second follower. This is recovery/installation PASS, NOT a
changed=0 repeat claim. Result output list READY/NO_NEW_PACKAGE.

All three HA units active. TLS-validated health on ports 8300/8302/8304:
all initialized/unsealed, one leader and two standbys, same cluster identity
`dfcf9c15-cf74-5efd-8af4-bf81b04af50d`. Accepted standalone remains ACTIVE.
The existing role's separate verify passed; visual UI acceptance is not claimed.




## service-install-08e-bootstrap-correction.md

Source document: [service-install-08e-bootstrap-correction.md](../service-install-08e-bootstrap-correction.md).

<a id="service-install-08e-bootstrap-correction-checkpoint-001"></a>

Status: owner accepted the revision-1 review correction; implementation and QA
reset are not performed by this document. Review scope is only
`SI08-E-PLAN-01`; `SI08-E-PLAN-02` remains a prerequisite for a separate reset.


## service-install-08d.md

Source document: [service-install-08d.md](../service-install-08d.md).

<a id="service-install-08d-checkpoint-001"></a>

## Evidence so far

- `go test ./...` and `go vet ./...`: PASS.
- Frontend typecheck/lint/build: PASS; 67 tests PASS.
- Windows `wails build -nopackage -clean`: PASS.
- RED OS race tests: installer, secretoutputwire, secretfiles, runtimesecret,
  executionnode PASS. Final source checks also PASS for installer/executionnode
  output tests and the root application secret tests (`-race`, 56.546s).
- RED OS output protocol tests: 15 PASS; Vault role contract: 15 PASS.
- Focused filesystem tests cover the exact default path, no overwrite,
  receipt/ciphertext readback, rejection of a substituted secrets directory,
  unchanged project revision and omission from local Core staging.
- Full Core: 342 cases completed, 4 skipped, PASS. Contracts: 31 PASS.
- Catalog/configuration schema reproducibility: PASS.
- `git diff --check` (dependency content excluded): PASS.
- Historical independent FULL DIFF: BLOCK; targeted recheck: DIFF-01–05
  RESOLVED, DIFF-06 OPEN. Zero new overengineering findings. DIFF-06 is now
  resolved by the owner's exact correction and the final evidence above;
  no additional architecture review was run.

This is implementation evidence, not real Vault service acceptance.



## service-install-08c.md

Source document: [service-install-08c.md](../service-install-08c.md).

<a id="service-install-08c-checkpoint-001"></a>

## Verification

RED OS QA, current working tree:

- focused input/lease/Core/Vault tests: 71 passed;
- full Ansible Core suite: 337 passed, 4 skipped;
- contract tests: 31 passed;
- Vault role tests: 15 passed;
- catalog reproducibility: PASS, `sha256:a460d77a38b7134f9a1639871eeb925a3ce8d673df3bfa5dcc1a40a22ada86d3`;
- configuration schema reproducibility: PASS;
- Vault apply playbook syntax-check: PASS (no target execution);
- `git diff --check`: PASS.

Secret-scope regression proves Apply receives manifest-bound shares and Verify
receives none. Schema and decoder tests reject Verify in the shares operation
list. The contract correction was owner-authorized before any immutable
runtime release advertised these versions; previously published capability,
lease and payload versions were not changed.

The initial full DIFF review found one blocking interruption-cleanup gap and
one nonblocking over-broad Verify scope. The single authorized targeted
recheck passed the cleanup finding. The owner then authorized the exact
operation-scope correction; its Core, lease, schema and service tests pass.
No further review cycle was run. No Vault target or QA server was mutated.



## service-install-08b.md

Source document: [service-install-08b.md](../service-install-08b.md).

<a id="service-install-08b-checkpoint-001"></a>

## Current implementation and evidence

Implemented: closed primitive/member validation, deterministic normalization,
PKI materialization, isolated unit/config/data paths, protected standalone
bootstrap output, one-time init recovery, sequential seed/follower unseal,
audit/KV v2/userpass configuration and read-only verification. Target-free
standalone 1/1, three members on one host, and three members on three hosts
validation fixtures pass under `sudo unshare -n`, changed=0. The focused lock
playbook passed on RED OS: only one contending unit reached READY, and the
lock was reacquired after both normal stop and holder-process failure. Seven
no-follow path-boundary cases (config deployment/member/PKI, data
deployment/member, log deployment/member) were rejected before the test's
outside-write sentinel; the outside sentinel remained unchanged. Vault role
contract tests: 14 PASS. Read-only preflight and apply/verify syntax checks
passed. Full Core suite: 322 PASS, 4 skipped; catalog and service-schema
reproducibility passed. No Vault package, Vault unit or Vault data was
installed or changed.

Audit rotation is per exact Vault unit: daily, maxsize 100 MiB, fourteen
rotations, mode 0600, and HUP only to that unit's main process. Preflight
requires at least 1,600,000 KiB free on the `/var/log` filesystem, enough for
the current file plus the configured rotation bound. The initial targeted
review lacked the lock/path execution evidence; after that evidence was
recorded, the owner-authorized targeted recheck passed DIFF-01 and DIFF-03.
DIFF-02 passed under the owner-approved existing-service source policy. All
three findings are resolved with zero blocking and zero overengineering
findings. SI08-B is DONE. No real Vault deployment is part of B; it remains
SI08-E work.

The QA host has active disk/zram swap. Raft preflight requires swap already
disabled and never changes host swap policy automatically.



## service-install-08-vault-architecture.md

Source document: [service-install-08-vault-architecture.md](../service-install-08-vault-architecture.md).

<a id="service-install-08-vault-architecture-checkpoint-001"></a>

Статус: SI08-A ACTIVE по разрешению владельца; Vault deployment не выполнялся.
Запрос владельца: следующий сервис HashiCorp Vault, TLS cluster, TLS API,
audit logs on, KV on, userpass on; обязательные размещения 1/1, 3/1, 3/3.
Документ не подтверждает завершение Redis и не запускает Vault на targets.

## Mixed-section reconciliation: service-install-08a.md

Source: [service-install-08a.md](../service-install-08a.md). Extracted on 2026-10-12;
original dates, scopes and reviewer verdicts are preserved. This is historical
evidence, not current authorization.

<a id="service-install-08a-reconciliation-001"></a>

Owner-authorized DEV acquisition completed on 2026-09-26: exact
`vault-1.21.2-1.red80.x86_64` from configured RED OS `updates`, no install.
The acquired binary reports `Vault v1.21.2` (cgo). This is artifact evidence,
not deployment or full service/OS compatibility acceptance. Source policy is
unchanged; no runtime release was published or activated.

Evidence: RED OS contract suite 21 PASS and Python codec tests 3 PASS;
`go test ./...`, `go vet ./...` and `git diff --check` PASS. Focused Go
secretoutputwire and executionnode packages PASS. Temporary QA workspaces are
cleaned using qa-sync after verification. Full milestone acceptance gates,
including protected storage/recovery and OS-specific race tests, remain pending.

2026-09-26 continuation: RED OS storage tests 10 PASS, codec tests 3 PASS,
contract tests 21 PASS. Core suite ran 320 tests, OK (4 skipped).
`go test ./...`, `go vet ./...`, and `git diff --check` PASS. Storage tests
cover symlinks/hardlinks/FIFO, mode/bounds, held-directory path replacement,
partial-write and atomic-publication failures, exact retry and no overwrite.
This is unit/fault-injection evidence, not an activated runtime or Vault run.

Not implemented yet: trusted controller package integration and terminal evidence, retention
guard, authenticated runtime operations, local age encryption/publication/ACK,
Vault service package/Ansible init-unseal-configure-verify, Core output
descriptors, conditional incoming credentials, Wails/React and real deployments.
This progress entry preceded closure below. SERVICE-INSTALL-08 has no
end-to-end acceptance result.



<a id="service-install-08a-reconciliation-002"></a>

## Exact SI08-A closure boundary (2026-09-26)

The architecture §9 defines A as owner decisions, a pinned verified artifact,
checked contract gaps and closed manifest/settings/secret contracts. It does
not define A as a Vault deployment or completion of every B–E implementation.
The storage/codec foundation above is progress, not proof of those entire gates.

The artifact prerequisite was previously blocked by missing acquisition
authorization; the owner explicitly supplied it on 2026-09-26. It is now
RESOLVED. Exact download used `dnf download`, with only configured `updates`
enabled, on trusted QA node 101. No package install was performed.

- Local import: `.runtime/artifacts/vault/vault-1.21.2-1.red80.x86_64.rpm`.
- Size: 80,737,986 bytes.
- RPM SHA-256: `sha256:11db853f514625835ed4516876311057b7021fbaf39a53040e5e13d111bc41dd`.
- Repository package checksum equals that exact SHA-256; remote file and
  workstation copy also match it.
- `rpmkeys --checksig --verbose`: existing trusted RED OS RSA/SHA256 signing
  key `f8ac18ee` OK; header and payload digests OK. No key was imported.
- Extracted `/usr/bin/vault` SHA-256:
  `sha256:f72a62dc3209cc60cf96da83b6f13c5452af6994150cd255af6b37bc6762b7c2`.
- Extracted binary version command: `Vault v1.21.2, built 2025-09-26T10:06:34Z (cgo)`.
- `.runtime/artifacts/vault/` is Git-ignored. No artifact was added to Git.
- Remote acquisition workspace and extracted binary removed after local digest
  verification; the verified local RPM remains available for the next steps.

RPM metadata declares BUSL-1.1. The pinned
[upstream license](https://github.com/hashicorp/vault/blob/v1.21.2/LICENSE)
sets redistribution/notice and production-use conditions; no general legal
clearance for distributed product packaging is claimed. This RPM file list
does not include LICENSE. Before an offline distribution, preserve the license
and notices and confirm the intended use under those conditions. Acquisition
does not authorize automatic bundle redistribution.

Pinned initialization bounds were checked against upstream v1.21.2
`SealConfig.Validate`: integer shares/threshold 1..255, threshold <= shares,
and threshold >= 2 when shares > 1. Architecture §5 records the exact rule;
default 2-of-3 is valid. No change to an older schema was made.

SI08-A contract definitions are now present: `services/vault/service.yml`,
reproducible configuration schema and compatibility candidate; exact additive
input-secret schemas and byte/scope admission helper. Definitions and integration
obligations are in [typed contract freeze](../service-install-08a-secret-contracts.md).
ExecutionCapabilities v4, descriptor v2, lease v2 and payload v4 are NOT active
or advertised. Start v2, existing capability/lease/plan/manifest/catalog schemas
are unchanged. Vault is not added to the active fixture catalog.

2026-09-26 A gates: contract tests 31 PASS, including typed input and capability
positive/negative cases; Core suite 320 tests, OK (4 skipped); configuration
schema and catalog reproducibility PASS; network-isolated contract tests 31
PASS (`sudo -n unshare -n`); RED OS Go wire race PASS; Windows full Go test/vet
and diff-check PASS. Existing published schemas have no diff. Frontend/Wails
are unaffected and not rebuilt. Mockup review confirms no new installation
page; file inputs/output password controls remain D implementation obligations.

Remaining A gate: one initial high-risk implementation DIFF review of the
frozen A-owned scope. No new FULL PLAN or exhausted PLAN recheck is run.
ProducerCompletion/retention/ACK and runtime/UI integration remain unimplemented
and must be completed at their approved boundary before any secret-output run.



<a id="service-install-08a-reconciliation-003"></a>

## Initial implementation DIFF result — BLOCK (2026-09-26)

Independent architecture-reviewer reviewed base HEAD
`221b05dee8c54492991af0d61c92842d7cf10d75`, A-owned 31-file content fingerprint
`cbfc00b02ba7faa88bfdddd167c06c03ab739be3ad16aa517d27ad76f21b3a6b`.
This is the one initial implementation DIFF review, not another PLAN review.

- SI08-A-DIFF-01 BLOCKING: canonical/input deployment IDs permit dots and
  underscores, but output metadata and Go binding validation reject them.
  Proposed bounded correction: align output admission with canonical grammar
  and test identical ID cases across schema, Python storage and Go decoder.
- SI08-A-DIFF-02 NON_BLOCKING: Go metadata struct decode accepts altered key
  case. Proposed correction: validate exact metadata keys before decoding.
- SI08-A-DIFF-03 RESOLVED: callback errors cannot propagate secret content;
  Consume returns fixed ErrTransfer and clears borrowed buffers. Independent
  focused QA and its new regression test PASS.
- Overengineering: 0 findings.

After the callback correction: Windows full Go test and vet PASS; RED OS
wire race PASS (1.059s); diff-check PASS. The earlier unchanged Python/schema
gates remain 31 contract tests and 320 Core tests, OK (4 skipped).
The latest explicitly created QA workspace was removed through qa-sync.

At that review revision SI08-A was BLOCKED, not DONE. No SI08-B or Vault
deployment. Work stops for owner direction on the two bounded corrections;
no automatic correction/review loop is started. The fingerprint identifies
the reviewed implementation before this evidence-only documentation append.



<a id="service-install-08a-reconciliation-004"></a>

## Owner-approved correction and closure (2026-09-26)

One TARGETED_RECHECK of SI08-A-DIFF-01/02: APPROVE, both RESOLVED;
DIFF-03 remains RESOLVED. Zero blocking and zero overengineering findings.
Canonical deployment grammar is now identical in output schema and Go,
with a 128-character bound. Python schema/publish/Fetch and Go tests cover
hyphen, dot, underscore, max length and rejected identifiers. Exact metadata
keys are checked before Go struct decode; changed-case aliases fail closed.

Reviewer-bound SHA-256:

- metadata.schema.json: `82138B0B92178789087BE9250E2113CEBC49E2EFFC921AC5E2802F1014F21543`
- frame.go: `F468910930E9B5725600F94C450120442F7A073D001931F60A30E05AE0DA55DB`
- frame_test.go: `A9A1F7967B7461C38FDC6262FC0591EEF2B8761DAD38BBF72A52C2F6E24658B0`
- test_execution_secret_output.py: `18247703DD4C3A4AFBE86E4747B2C7DBD42BE46040081986674B99C88DF53227`

Final gates: Windows focused/full Go test and vet PASS; RED OS contracts
31 PASS; Core 321 tests OK (4 skipped); wire race PASS (1.034s); catalog
and service-schema reproducibility PASS; git diff --check PASS. Independent
callback leakage QA PASS is preserved. Both correction QA workspaces were
removed using qa-sync. Frontend/Wails unaffected; no Vault/target deployment.

SI08-A DONE is limited to the approved contract foundation, pinned verified
artifact and tested codec/storage primitives. SI08-B NOT STARTED. Runtime
advertisement, roles, custody delivery/ACK, retention, Core descriptors and
UI integration remain later milestone obligations, not completed features.


Original title: # SI08-A — contract foundation, DONE

## Mixed-section reconciliation: service-install-08e-clear.md

Source: [service-install-08e-clear.md](../service-install-08e-clear.md). Extracted on 2026-10-12;
original dates, scopes and reviewer verdicts are preserved. This is historical
evidence, not current authorization.

<a id="service-install-08e-clear-reconciliation-001"></a>

## PLAN review

Independent architecture-reviewer: FULL PLAN APPROVE_WITH_CHANGES, zero
blocking findings, reviewed SHA-256
`2d3f3348ab73751658aaef43326746172aa53d1fe6db3152d0447cede3b41248`.
Nonblocking SI08-CLEAR-PLAN-01/02 are incorporated above: full subtree/bind-mount
boundary and fresh destructive-invocation validation plus partial-failure QA.
No automatic re-review is required. Owner approval of this concrete new
Vault-only destructive helper was subsequently granted. Implementation is in
progress; no real clear has run. The PLAN review does not establish the
implementation as safe or complete; independent DIFF and QA gates remain.
