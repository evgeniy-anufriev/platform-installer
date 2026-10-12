# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## exec-obs-01.md

Source document: [exec-obs-01.md](../exec-obs-01.md).

<a id="exec-obs-01-checkpoint-001"></a>

## Acceptance evidence

On 2026-09-05, bundle
`sha256:3260257b01cb98b8b651e695fd641cc3d3e02e5d2ac732d87c3fd9af43adb6d4`
was verified, published and prepared READY. The established three-node
`kafka-real-multihost` project was reused, preserving deployment TLS, identities,
ports, paths and active `kafka@kafka-kafka-{1,2,3}` units. Other QA deployments
were not reset or reconfigured.

First run `installer-1788591717613836600` completed SUCCEEDED in 11m56s:

| Action | Duration | Task events |
| --- | ---: | ---: |
| PKI apply | 1m19s | 164 |
| Kafka apply | 7m24s | 913 |
| Kafka verify | 3m13s | 636 |

It produced 1,723 events (1,713 task events), a 945,064-byte Installer mirror,
zero CHANGED tasks, and no stream degradation. The remote decoded stream,
typed subscriber and local mirror were identical. A shared UUID had results
from all three hosts. Windows `Get-Content -Wait` observed fresh sequences
1179/1180 during Kafka verify, including node3 completion duration 2302ms.

The observer was restarted while the run was active. During detachment the
remote sequence advanced 759 -> 770 and state stayed RUNNING; replay resumed
after subscriber sequence 753 without conflict. A separate CLI process was
also terminated/restarted against its own derived mirror. Terminal CLI replay
after sequence 1723 returned `remoteOutcome=SUCCEEDED`, exit code 0.

The original local test process was replaced to strengthen acceptance
assertions; only its observation process stopped. The infrastructure run was
not restarted. The final test attaches only to a still-active run with the
expected project identity and measures live growth again. Observation time
and full run duration are reported separately.

Repeat run `installer-1788592474776987100` completed SUCCEEDED in 9m07s:
PKI apply 1m21s, Kafka apply 5m19s, Kafka verify 2m27s. It again produced
1,723 events / 1,713 task events; mirror size was 944,878 bytes. The test
asserted `changed=0`, complete task coverage without degradation and identical
remote/mirror/subscriber streams.

The final real test command was:

```powershell
$env:PLATFORM_EXEC_OBS01_E2E = '1'
$env:PLATFORM_EXEC_OBS01_RESUME_RUN = 'installer-1788591717613836600'
$env:PLATFORM_EXEC01A_ADDRESS = '192.168.56.101'
$env:PLATFORM_EXEC01A_USER = 'platform-automation'
$env:PLATFORM_EXEC01A_IDENTITY = (Resolve-Path .runtime/platform-exec-key-20260901).Path
$env:PLATFORM_EXEC01A_KNOWN_HOSTS = 'C:\Users\AnufrievEV\.ssh\known_hosts'
$env:PLATFORM_EXEC01A_KAFKA_PROJECT = (Resolve-Path .runtime/qa/exec-obs-01d-project).Path
go test ./internal/executionnode -run '^TestEXECOBS01ProductionKafkaObserverE2E$' -count=1 -v -timeout 30m
```

It returned ordinary PASS: test duration 1067.87s, package duration 1068.149s.
The resume variable above records this acceptance invocation, not a recipe
for replaying a completed run: the test rejects a terminal resume target.
For a new full acceptance, omit it and supply the established QA fixture.
The temporary fixture was a copy of the successful UI-BE-04E run project.

Final systemd inspection confirmed active/running:
node1 `kafka@kafka-kafka-1`, node2 `kafka@kafka-kafka-2`,
node3 `kafka@kafka-kafka-3`. No running Installer controllers remained.
No loaded `kafka-broker-*`/`kafka-controller-*` units were reported by the
legacy-pattern audit; no legacy reset/disable/delete was performed.

The earlier lifecycle-only reference run took 8m02s (PKI 1m15s, apply 4m48s,
verify 1m59s). First observed wall time is +3m54s and repeat is +1m05s;
these were separate runs
under different QA load, so that difference is not a measured callback-only
overhead. An isolated, temporary RED OS writer measurement for 1,713 events
took 14.732s, including 12.954s in 3,426 fsync calls (about 2.1% of the first
run's wall time for the whole writer). This measurement does not include all
callback or polling costs. Durability was preserved; no unproven batching
policy was introduced.

Focused RED OS acceptance passed 4 methods / 7 real local Ansible executions:
multi-host SUCCESS/CHANGED/SKIPPED task results; no_log success/failure; safe task failure; callback
exception; detail-writer failure; and tiny detail capacity. Failed Ansible
produced a safe failed result exactly once. All three observability faults
kept successful Ansible SUCCEEDED, with one appropriate diagnostic and a
preserved critical terminal. QA controller fixtures hold their run lock so
concurrent production recovery does not misclassify them as orphaned.

Final regression:

- Core full suite: 221 tests, 217 passed / 4 opt-in skipped. The four opt-in
  methods were then executed separately with all 7 real Ansible runs passing.
- Kafka contracts: 28 passed; affected PKI: 16 passed.
- RED OS `go test -race ./...`: all 6 packages passed;
  `go test -race -count=10 ./internal/executionnode ./cmd/platform-installer`
  passed. Final remote source snapshot matched all 527 transferred files by
  SHA-256. Local `go test ./...` and `go vet ./...` passed.
- Core full suite includes existing planning, lifecycle and protocol
  regressions; Go includes ExecutionService and relevant EXEC-01A regressions.
- Catalog and service configuration-schema reproducibility passed.
- Network-isolated empty validation passed with `changed=0 failed=0`.
- Real event secret audits passed against the runtime-only PKI secret without
  printing it; no_log sentinel tests and source/diff audit passed.
- Core-contract-reviewer and safety-reviewer: 0 blocking findings after fixes.

QA workspaces were removed with the repository helper. Local duplicate bundle,
CLI mirror, temporary fixture and test binaries were moved to Windows Recycle
Bin and can be recovered there. The two normal Installer runtime mirrors remain available
for operator inspection under `.runtime/executions/`; they are ignored by Git.
Three pre-existing remote QA directories from 2026-09-04 were left untouched.
The current verified runtime bundle remains in the normal immutable cache.

Next production UI milestone remains separately authorized; no Wails/React
implementation is part of EXEC-OBS-01.


<a id="exec-obs-01-checkpoint-002"></a>

Status: DONE. Internal gates 01A through 01D passed on 2026-09-05.


## exec-01a.md

Source document: [exec-01a.md](../exec-01a.md).

<a id="exec-01a-checkpoint-001"></a>

## Final acceptance evidence

- The published runtime uses `ansible-core/`, so service playbook relative
  imports resolve inside the immutable bundle. Activation capability checks
  passed; repeated Prepare returned `READY`, `Changed:false`.
- Kafka production E2E: the real target probe returned `NOT_FOUND` for Kafka,
  the resolver selected the verified Kafka 4.3.1 artifact from the published
  bundle, automatic runtime projection and shared gate ran,
  target SHA-256 verification passed, apply and verify passed, and repeat apply
  returned `changed=0 failed=0`. No Internet download or manual SCP was used.
- Keepalived production E2E: all three actual targets returned
  `AVAILABLE_COMPATIBLE` for 2.4.3, the resolver selected `REPOSITORY`, apply
  and verify passed, repeat apply returned `changed=0 failed=0`, and
  `artifact_delivery` was not invoked.
- BLOCKED acceptance: unsuitable repository plus absent compatible bundle
  stopped the production entrypoint before runtime (`artifact_delivery=0`,
  service mutations=0). The shared Ansible gate independently rejected a
  `BLOCKED` projection before a mutation sentinel.
- Fresh RED OS regression: 177 Core tests and 84 service tests passed; catalog
  and configuration schemas were reproducible; real `validate.yml` passed
  normally and under `sudo unshare -n`; `go test -race ./...` passed with the
  QA-only `golang` toolchain. Windows required only Go and OpenSSH for product
  orchestration and never executed Python/Core.
