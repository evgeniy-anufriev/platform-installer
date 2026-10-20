# Kafka SCRAM source implementation and QA

2026-10-20. HEAD baseline `930d5f71a83e3be99901ea40e2af6464394526f5`,
existing dirty working tree preserved. This work does not authorize installation,
service Apply, Kafka mutations or application startup on the stand.

## Owner decisions and review

The owner approved existing library/provider hooks and Vault Agent supervisor,
simple Ansible tasks, the two producer/consumer SASL JAAS ENV names, required
runtime-only admin input, User:admin as the final sole superuser, anonymous data
access with security administration reserved to admin, and temporary exact member
certificate bootstrap. The owner accepted KS-P04/KS-P05 corrections explicitly.
Four packages are excluded: data-manager, user-preferences, evo-scheduler,
ef-backend. SHA-256 comparison against the pre-edit snapshot confirmed all four
defaults unchanged; unrelated preexisting data-manager changes were preserved.

[Initial admin FULL PLAN](../reviews/kafka-scram-admin-plan-review.md) BLOCK is
historical. Owner-approved [TARGETED_RECHECK](../reviews/kafka-scram-admin-plan-targeted-recheck.md)
APPROVE closes both findings at PLAN level; it is not FULL DIFF approval.

## Source scope

Added SASL_SSL client resolution and package capability; native Kafka account/ACL
tasks in existing provider stages; explicit anonymous/internal data ACLs; required
admin creation through approved SERVICE_APPLY; temporary bootstrap finalization
with stable process/file proof. No production executable Python script was added.
Existing Core projections/validation, shared identity and Java-properties codec
were extended. Existing Broker pending custody binds deployment-scoped admin
inputs to Core-issued requirements before the existing password map/lease.
Library runtime aliases prevent collisions between equal logical SecretRefs.

Eleven application defaults receive SCRAM accounts, grants, existing Kafka
settings, two formatted Agent bindings and INFO for KafkaManagerConfig. Streams
internal topic prefixes are declared for kafka-ch-replicator. Shared SDKU library
default selects SASL_SSL. Existing UI forms retain binding formatter metadata.

## Executed checks

- RED OS .102, platform-automation persistent identity, isolated qa-sync source
  workspaces: focused suites test_deployment_plan34, application_providers20,
  application_mixed_execution9, execution_secret_lease28, application_plan13,
  application_libraries22, application_runtime_contract20 (one existing skip),
  application_vault15. Total 161 cases: 160 PASS / one skip.
- Listener resolution6 PASS; additional service-file materialization2 PASS,
  including two separate admin files with mode0600; Registry regression16 PASS.
  These are separate focused runs, not a full Core regression.
- After native snapshot exposed the closed-schema metadata omission, service
  configuration contract5, resolution25 and fixture catalog7 PASS on the corrected
  schema. Combined focused unit evidence: 222 cases, 221 PASS / one existing skip.
- Native Ansible runtime-proof QA2 PASS: interrupted final file before restart
  and partially restarted three-member fixtures fail closed; fully restarted
  fixtures pass. Exact process arguments and stale timestamps are covered.
  Only synthetic processes and a temporary fake systemctl are used; installed
  units and Kafka are untouched.
- Native Vault Agent1.21.2 → real Java21/Kafka client parser PASS for both exact
  ENV names and CLI properties, using synthetic credentials with quotes,
  backslashes, HTML characters, control whitespace, Cyrillic and a supplementary
  Unicode character. The HTTP token-lookup endpoint is a loopback test stub;
  no real Vault/Kafka server or secret is accessed. This proves template/ENV/
  parser compatibility, not application connection acceptance.
- Native tests exposed and corrected argv NUL escaping and Kafka Java-properties
  Unicode encoding. Failed intermediate fixtures/runs are not counted as PASS;
  final native process-proof ran 110.335s and Agent/parser ran 16.292s.
- SDKU: 27 package schemas/digests, 26 synthetic Compose renders and one shared
  base variant PASS. No target application execution.
- Kafka Apply/Verify and provider Apply/Verify syntax-check PASS. Catalog and
  Kafka configuration schema regeneration/reproducibility PASS; catalog digest
  `sha256:0312ef6d691d72d2a9aca03b208632391045191dffaed8f83b76e0e6f95524ad`.
- Windows Go test ./... and go vet ./... PASS. Frontend typecheck, binding tests8
  and lint PASS. Git diff whitespace check passed before final evidence edits.

Native process proof used qa workspace d25f9a412b5245a4ace23884dd7dd1fb;
Agent/parser and extra service-file/Registry checks used
994864399cfc48bcafbcc118978ce123. Workspaces are temporary and are cleaned through
the standard helper after their checks; final cleanup status is recorded below.

Cleanup: all twelve source workspaces created for Kafka SCRAM in this session
were removed with scripts/qa-sync.ps1 -Cleanup. No installed Kafka/Vault state,
existing application containers or other tasks' workspaces were changed.

## Remaining gates

Native target-free standalone SCRAM ProjectSnapshot PASS (10.223s) in workspace
52a5d50be02d418db067f68fe7df2bcd. Both libraries resolve SASL_SSL/9096, account
credentials and formatted JAAS bindings. It caught missing explicit boolean
metadata properties in the closed ServiceManifest schema; both are now declared.
The standard transfer helper verified the current source tree. FULL DIFF review
returned historical [BLOCK](../reviews/kafka-scram-diff-review.md): KS-D01/KS-D02;
KS-D03 nonblocking. Owner subsequently accepted D01 correction and explicitly
rejected D02 restrictions; see plan §11 and the follow-up below. Frozen scope93 SHA-256
`B2180611562B78362006A6A65A9D358827A3009484DAA8907F053DDCC20EAEF3`.

Real React/Wails Save/reopen/plan, matching verified runtime
bundle, three-broker transition/recovery, real SCRAM negative/positive ACL tests,
all eleven application factory paths, Registry/internal health and global TRACE
logging acceptance remain unperformed. A later owner-authorized installation is
required for stand acceptance. No milestone completion or deployment PASS claim.

## Owner disposition and D01 correction, 2026-10-20

KS-D01 accepted: administrative SASL candidates and deployment-scoped admin
requirement are independent of the first library data selector. Existing provider
action binds exact member PKI plans to these candidates; account hook uses them.
Actual application credential checks retain their own account candidates.
KS-D02 explicitly OWNER_REJECTED: principal mapping/builder configuration stays
operator-controlled. No additional reservation/validation restriction introduced.
This owner disposition does not rewrite the historical reviewer BLOCK verdict.

D03 nonblocking: ordinary config restart and bootstrap-finalization restart cross
the write-second boundary with a built-in Ansible wait_for timeout1 task. Verify
and unchanged repeat do not wait/restart; strict runtime proof remains intact.
The native fixture now emits whole-second systemd timestamps.

Current-tree RED OS workspace a65f66d2e97144dcbcf51e30a1c3ea77:
provider23 PASS; real action fixture4 PASS (three imported provider tests plus one
action test with eight subcases for order/mode/exact versus wrong PKI request).
All four Kafka/provider Apply/Verify syntax checks PASS. Initial target-free
snapshot repeat timed out60s with VM load average32; no service operation ran.
The bounded snapshot repeat also timed out60s; no further repeat was launched.
The isolated D03 proof is recorded below. Excluded four
application defaults match their pre-edit hashes. Git diff whitespace PASS.

TARGETED_RECHECK D01 scope SHA256:
`05839E1A6DD0C18C1E42D7962A6DE5C03B6AC21F051DA5F3219781F2F5DE11FE`.
D02 is outside the correction/recheck scope by explicit owner decision.

Independent TARGETED_RECHECK KS-D01: APPROVE within D01 scope, zero blockers,
11/11 fingerprints matched. See the separate targeted report. D02 remains
OWNER_REJECTED outside reviewer resolution; no global DIFF approval is claimed.
All nine reviewed code/test fingerprints still match after status-only doc edits.
Final D03 native process-proof2 PASS, 389.968s on the loaded VM, using workspace
358d4bbe3e4d4133bebc6a2cf8b772ce. Whole-second timestamps retain fail-closed
behavior for final-file/old-process and partial-restart states, then pass when all
three synthetic members loaded final configuration. Processes are isolated test
children with fake systemctl, not installed Kafka units. Test finally cleanup ran.
At that checkpoint snapshot repeat remained TIMEOUT (twice60s); its earlier
pre-correction PASS remains historical evidence. No installation was attempted.

Follow-up cleanup PASS: faa025f08f7f488383d14f34e8bd8548,
a65f66d2e97144dcbcf51e30a1c3ea77 and 358d4bbe3e4d4133bebc6a2cf8b772ce
removed through scripts/qa-sync.ps1 -Cleanup. These are the three additional
source workspaces after the twelve already recorded above. No unrelated process
was stopped and no other task workspace was removed.

## Target-free SCRAM repeat after load check — 2026-10-20

Owner requested a fresh repeat after VM load decreased. The previous .102 VM
remained saturated (one CPU, load average26–32, generally zero CPU idle); its
fresh transfer 3dba75335a524df98e21365c8f819558 was cleaned without running a test.
No process/service was stopped to reduce load.

Used the primary RED OS QA node from the project procedure, 192.168.56.101:
RED OS8.0.3, Python3.11.15, ansible-core2.18.15. Its one-minute load decreased
from10.93 to9.65 before the run; the CPU was still busy. This was a less loaded
node, not an idle-VM claim or proof that load caused the previous timeouts.
Transferred the current working tree with scripts/qa-sync.ps1 into
/var/tmp/platform-installer-qa-8aca178e23c64e36816cfd66cad835c9, with source
verification by the standard helper. Git baseline remains
930d5f71a83e3be99901ea40e2af6464394526f5, working-tree sources include current changes.
qa_application_libraries.py SHA256:
95DC269309E7DE81090DE20A718D060FE7C47A1276E91E6C0669DCD546E55B22.

Executed:
`python3 ansible-core/tests/qa_application_libraries.py StandaloneLibrariesQA.test_scram_listener_accounts_and_jaas_bindings_resolve_target_free`

Result: **PASS, 1 test, 18.289s**, exit0; observed completed by
2026-10-20T12:33:12Z. The existing subprocess timeout remains60s; no test or
production code changed. Actual standalone ProjectSnapshot resolves both
libraries to SASL_SSL/9096, Kafka account requirements and producer/consumer
kafka_scram_jaas secret bindings; the harness rejects changed=1 output.
This fresh PASS supersedes the timeout as the current result; both earlier
60s timeouts remain recorded above as historical attempts.

Cleanup PASS: both new temporary source workspaces (.102 and .101) removed with
scripts/qa-sync.ps1 -Cleanup. No installed service/application changes, Kafka
installation, SERVICE_APPLY, migration, bundle publication or live acceptance.
Real React/Wails and stand acceptance gates remain open.
## Kafka-only commit isolation and validation — 2026-10-20

Owner authorized committing Kafka SCRAM with its documentation, excluding unrelated
changes. master/origin/master were fetched and initially equal at 930d5f71.
Selected Kafka hunks in mixed files; Redis resource bindings, their tests/docs,
CSPA state, excluded applications and generated frontend assets remain outside
the index. Alarm Redis ENV settings are retained in the committed package view.
The SDKU library changes only its Kafka listener selection. No working-tree
content was replaced by the isolated view; five Kafka-owned new files received
only trailing-blank-line normalization. Unrelated working file hashes preserved.

Exported the staged source directories to a temporary local QA copy, then used
scripts/qa-sync.ps1 from that root to transfer the selected source view into
/var/tmp/platform-installer-qa-467692470e434c5a92f805515a32d95b on RED OS .101.
Import-catalog digests were regenerated for those exact selected package bytes
through existing Core load_package and returned into the index. The excluded
data-manager digest stays at HEAD; its unrelated working change is not committed.
Source/test selection identity before this publication evidence:
tree e940f09422678bfeba819d1067f3037975dd82e2. Trailing-blank normalization is
semantically unchanged from the transferred source view.

Isolated-view validation PASS:
- Core unit suites: deployment_plan34, application_libraries21, application_vault15,
  application_mixed_execution9, application_plan13, execution_secret_lease28,
  kafka_listener_resolution6, fixture_catalog7 and exact runtime-projection
  two-deployment lifecycle case1: 134 cases PASS.
- Kafka provider22, real provider action4 and standalone target-free SCRAM snapshot1
  PASS (snapshot8.280s, unchanged60s timeout). Together with the above: 161 cases
  PASS. Provider count excludes the unrelated Redis-key test from the shared tree.
- Package schemas/digests27, synthetic Compose renders26, shared base1 PASS;
  realTargetExecution=false.
- Current Go sources match selected Go changes: go test ./... and go vet ./... PASS.
  Frontend secret-binding tests8 and typecheck PASS; generated dist excluded.
- Staged file allowlist103, excluded application paths, unrelated working hashes
  and git diff --cached --check PASS.

Remote source workspace cleaned with scripts/qa-sync.ps1 -Cleanup. No installation,
SERVICE_APPLY, migration, application startup or bundle publication occurred.
Real bridge/stand acceptance remains pending as stated in the plan/current state.
