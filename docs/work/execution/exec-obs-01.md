# EXEC-OBS-01: Ansible task observability and Installer-side event mirror

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#exec-obs-01-checkpoint-002).



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

The remote journal has a 16,384-event limit. Task detail admission stops when
the global sequence reaches 16,128, reserving at least 256 slots for critical
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
16 subscribers per run, 16,384 aggregate subscriber slots, and 16,384 retained
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

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#exec-obs-01-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
