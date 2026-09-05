# EXEC-OBS-01: Ansible task observability and Installer-side event mirror

Status: DONE. Internal gates 01A through 01D passed on 2026-09-05.

## Ownership and event contract

The accepted stream is:

```text
Ansible aggregate callback
  -> execution_lifecycle trusted writer
  -> authoritative Execution Node events.jsonl
  -> GetEvents(afterSequence, limit)
  -> Go RunObserver
       -> local derived events.jsonl for operators
       -> typed subscriptions for future Wails/React
```

There is one `ExecutionEvent/v1alpha1` DTO and one remote sequence authority.
The callback supplies semantic run/phase/action/deployment identities; the
writer derives canonical paths, validates ownership, sanitizes fields, locks,
allocates sequence, appends and flushes. Standalone Ansible does not enable the
callback by default. The existing controller, manifest, approval, artifact
resolution and remote result semantics remain in use.

`TASK_STARTED` represents Ansible's task start, with optional host. Results are
`TASK_COMPLETED` with host-specific SUCCESS, CHANGED, SKIPPED or FAILED. A task
UUID can have several host results. Duration measures time from the observed
task start to that host result; it includes scheduling/waiting and is not an
exclusive per-host CPU time. Unsupported durations are omitted. Hooks cover
ordinary task start, ok/changed, skipped, failed, unreachable and async result
hooks. There is no strategy plugin or invented per-host start.

Only allowlisted metadata enters events. Args, vars, module results, command
lines, stdout/stderr, invocation, diff and connection credentials are excluded.
For `no_log`, task display name is omitted, UUID and safe role/host/status may
remain, and `redaction.applied=true` with `task.name` in redacted fields.
Names are bounded and stripped of control/ANSI characters.

## Durability, capacity and failure policy

The remote journal has a 2,048-event limit. Task detail admission stops when
the global sequence reaches 1,792, reserving at least 256 slots for critical
lifecycle events. Each event is at most 64 KiB. Controller and callback share
the same cross-process event writer; the controller separately owns its run
lock throughout execution.

Detail failure or saturation records a minimal run-local
`task-observability.json` marker. It has no sequence, is internal to Core,
and is never consumed by Go/UI. After the playbook, the controller emits at
most one normalized diagnostic for that action: `error.code` is
`TASK_EVENT_STREAM_TRUNCATED` or `TASK_EVENT_STREAM_DEGRADED`. Successful
Ansible remains successful. Critical journal failures retain the existing
fail-closed lifecycle policy. A diagnostic's error field is not itself a
failed deployment result.

GetEvents accepts limits 1..512; Go normally requests 256. Selected journal
lines are bounded to 1 MiB per page, excluding the response envelope; Go caps
the complete event response at 2 MiB. Pages omit an incomplete final line.
Responses include nextSequence,
hasMore, earliestSequence and historyTruncated. Missing limit remains
compatible; lifecycle-only events do not need task fields. Invalid stream
shapes or unsupported responses fail explicitly. Task availability requires
a runtime containing the managed callback; an older lifecycle-only runtime
does not acquire detailed events merely by upgrading the Installer.

RunObserver drains pages, uses bounded polling/backoff, checks gaps and
conflicting duplicates, and drains terminal events before stopping. It owns
one poller per node/run while consumers exist. Bounds are 32 active runs,
16 subscribers per run, 16,384 aggregate subscriber slots, and 2,048 retained
events per run. Slow consumers are disconnected rather than blocking polling.
Runtime SSH release/state probes and event responses use bounded output.

The Installer mirror has a single cross-process writer, restrictive Unix
permissions or protected Windows DACL, symlink/reparse checks and node/run
binding. Readers may tail it while open. Restart recovers complete lines and
checks the local checkpoint against remote authority. Mirror failure reports
observer degradation and does not change the remote outcome. The local limit
is 128 MiB and 2,048 events. Runtime mirrors are Git-ignored and never exported
as desired state or included in a bundle.

## Operator usage

Run these commands from the Installer repository during development. For an
application installation, supply its runtime directory outside any portable
Ansible project with `-runtime-root`.

The start operation returns the exact run ID. Watch requires that ID; it does
not infer a global current run from timestamps or select another deployment.
Use the same stable node ID across reconnects. At startup stderr prints the
selected runId, nodeId and intended mirrorPath; subsequent mirror errors
explicitly report failure. Stdout contains typed NDJSON events only.

```powershell
$runId = 'installer-1788592474776987100' # replace with the returned run ID
go run ./cmd/platform-installer -command execution-watch `
  -run-id $runId -node-id node1 -address 192.168.56.101 `
  -user platform-automation -identity .runtime/platform-exec-key-20260901 `
  -known-hosts C:/Users/AnufrievEV/.ssh/known_hosts `
  -fingerprint operator-approved -runtime-root .runtime
```

The known_hosts file must already contain approved host keys. The example
uses the established QA trust configuration; watch does not approve new keys.
Only one process may write a given mirror. A second human reader needs no
additional watch process:

```powershell
Get-Content ".runtime/executions/$runId/events.jsonl" -Wait
```

```sh
tail -F ".runtime/executions/$runId/events.jsonl"
```

To inspect the longest observed task completions without parsing Ansible output:

```powershell
Get-Content ".runtime/executions/$runId/events.jsonl" |
  ForEach-Object { $_ | ConvertFrom-Json } |
  Where-Object eventType -eq TASK_COMPLETED |
  Sort-Object elapsedMilliseconds -Descending |
  Select-Object -First 10 actionId,host,status,elapsedMilliseconds,task
```

Redacted task names remain absent. Compare action boundary timestamps for
whole-action durations; do not sum multi-host completion durations.

Watch follows until terminal result. Ctrl+C detaches; it never cancels the
remote installation. Restart the same command to verify/catch up the local
mirror. `-after N` sets the stdout subscriber checkpoint; it does not omit
the earlier history required to reconstruct the local mirror. JSON output is
always enabled; there is no raw stdout parser or arbitrary output-file API.

Executable exit codes: 0 remote SUCCEEDED; 1 remote FAILED/CANCELLED/INTERRUPTED;
2 invalid input; 3 observation/output/result-unavailable failure; 130 detached.
`go run` may wrap a nonzero executable code, so use a built executable when
an external script needs the exact code. Observer failure is not a claim that
the deployment failed. The CLI prints the authoritative outcome separately
when available.

Future UI subscribes to RunObserver through typed Go APIs. It does not open
this file, implement polling or redact Ansible output itself.

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
