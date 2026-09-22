# UI-02D — credentialed Start and bounded execution observation

Status: **DONE**.

UI-02D wires the existing runtime-only credential broker into the one
`ExecutionService` credentialed Start path. The Wails facade starts only an
already approved plan and returns the Execution Node's authoritative run ID;
it neither handles a lease ID nor contacts targets directly. The frontend can
explicitly request cancellation, but leaving Execution/Result, replacing a
project, changing the Execution Node or closing the application only detaches
the local observer subscription. None of those actions cancels remote work.

Progress reaches React through bounded, closed `InstallationEventView` and
`InstallationResultView` DTOs. Paths, mirror locations, diagnostic
references, raw Ansible output, protocol metadata and secret material are not
part of that boundary. Unknown observer failures map to the fixed
`OBSERVABILITY_DEGRADED` diagnostic; a terminal-looking event, reconnect or
opening Result refreshes the authoritative run through `GetInstallationRun`.

The App-private registry is limited to 32 local subscriptions and is bound to
the active project/Execution Node generation. Final Start validation plus run
publication, and final Subscribe validation plus subscription publication, are
atomic under the application edit lock. A project replacement, close or actual
Execution Node change advances the generation and clears only local observer
state, so an old asynchronous result cannot be rebound to the new context.

Evidence: focused concurrency tests (50 repeated runs), `go test ./...`,
`go vet ./...`, frontend test/lint/build, Wails build, RED OS
`CGO_ENABLED=1 go test -race .`, catalog reproducibility and `git diff --check`
passed. The permitted targeted architecture recheck resolved
`AR-UI02D-002`; the earlier closed observer, detach and Wails DTO findings
were already resolved. No target host was contacted.

UI-02E is next.
