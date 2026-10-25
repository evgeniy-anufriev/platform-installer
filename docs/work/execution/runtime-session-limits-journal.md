# Runtime session and event limits — 2026-10-25

Owner requested four-hour runtime secrets/keys and an event limit of 32768.
The owner explicitly excluded React/Wails testing while work was in progress.

## Change

- The shared `runtimesecret.NewBroker` default changes from two to four hours.
  All ordinary Broker secret categories use that TTL: SSH password/PEM access,
  sudo/PKI, pending and attached service/application secrets, and transient
  output-encryption passwords. Project binding, explicit clear, zeroization,
  replacement and active-run identity retention behavior are unchanged.
- Core `execution_lifecycle.MAX_EVENTS` and Go
  `maxObservedExecutionEvents` both change from 16384 to 32768. Go observers,
  execution-service reconciliation and event mirrors consume the same constant.
  The critical journal reserve remains 256; page, message and byte bounds are
  unchanged. This is the number of events per run.
- Existing session and event contracts are updated. No new persistence,
  lifecycle mechanism or protocol shape is introduced.

## Verification

| Check | Result |
| --- | --- |
| Full `go test ./...` | PASS |
| Full `go vet ./...` | PASS |
| Broker fake-clock boundaries | PASS: SSH/PKI/runtime values and output password before/exactly4h; PEM access and pending typed token/password before/exactly4h; existing clear and active-run retention regression checks PASS |
| Go observer/service/mirror tests | PASS, including count-bound cases using the increased limit |
| RED OS `test_execution_lifecycle.py` | 61 PASS |
| RED OS `test_execution_secret_lease.py` | 28 PASS |
| RED OS `test_execution_task_observability.py` | 25 PASS,5 skipped; skipped tests require opt-in isolated root-owned canonical controller acceptance |
| Actual Core journal count boundary | PASS: event32768 accepted, event32769 rejected with `RUN_EVENT_LIMIT`; existing task truncation/critical reserve tests PASS |
| `git diff --check` | PASS |

Core tests ran from current sources transferred/verified by `qa-sync.ps1` to
`/var/tmp/platform-installer-qa-cc4318ebae294199b6fe4f3571eaeba8` on RED OS
node1 as `platform-automation`, with the owner-located persistent identity copy
`.runtime/secrets/qa-existing-execution-identity.pem` and strict host-key checks.
The helper removed that temporary source workspace after QA.

No real-time four-hour wait, target installation, fresh execution plan or
runtime bundle publication was performed. React/Wails checks were not run, as
requested. The prepared isolated Wails/Vite processes were stopped and their
generated tracked-file noise removed. Existing unrelated SZI work is preserved.
The Core event cap reaches an existing Execution Node when an updated bundle
is built and activated through the normal workflow; Go/Broker changes require
the rebuilt Installer process.
