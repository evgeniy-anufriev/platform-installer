# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## ui-net-01.md

Source document: [ui-net-01.md](../ui-net-01.md).

<a id="ui-net-01-checkpoint-001"></a>

## Acceptance evidence

- Windows: `wails build -nopackage -clean` built
  `build/bin/platform-installer-ui.exe`; the launched desktop shell exposed the
  Wails project/open UI and navigation. No project was opened or mutated.
- Frontend: lint, production build and 41 tests passed, including typed
  provider reconcile, catalog-unavailable Clear and neutral stale-preview UI.
- Go: `go test ./...` and `go vet ./...` passed.
- RED OS: in a fresh `scripts/qa-sync.ps1 -IncludeGo` workspace,
  `CGO_ENABLED=1 go test -race ./internal/installer ./internal/coreadapter`
  passed. Core regression passed: 244 tests, 4 skipped. Fixture catalog and
  service configuration schemas were reproducible; catalog digest was
  `sha256:e87acc790d389a67ea90da7b785562018cd3450181fa00f4dfa2b38fe9eaeccf`.
- RED OS target-free `project_snapshot_acceptance.yml` passed on `localhost`
  with `changed=0`, `failed=0`; its deliberate invalid-root case returned the
  expected `PROJECT_SNAPSHOT_INPUT_INVALID` finding. No inventory target was
  contacted.
- The temporary RED OS workspace was removed and its absence confirmed.
- The bounded full DIFF review and its owner-authorized targeted recheck for
  UI-NET-01B had zero remaining blocking findings. No new architecture boundary
  was introduced by the C/D presentation work.
- Changed-file secret audit found no secret assignment/value. `git diff --check`
  passed.

UI-01G Certificates is next. UI-NET-01 itself does not issue, reissue,
materialize or apply certificates.



## ui-net-01-architecture.md

Source document: [ui-net-01-architecture.md](../ui-net-01-architecture.md).

<a id="ui-net-01-architecture-checkpoint-001"></a>

Status: **DONE**. Acceptance evidence: `docs/work/ui-network/ui-net-01.md`.

<a id="ui-net-01-architecture-checkpoint-002"></a>

### UI-NET-01A — contract and managed provider model — DONE

<a id="ui-net-01-architecture-checkpoint-003"></a>

### UI-NET-01B — reducer and guarded local Save — DONE

<a id="ui-net-01-architecture-checkpoint-004"></a>

### UI-NET-01C — Entry points provider editor — DONE

<a id="ui-net-01-architecture-checkpoint-005"></a>

### UI-NET-01D — preview and PKI-impact UX — DONE

<a id="ui-net-01-architecture-checkpoint-006"></a>

### UI-NET-01E — acceptance and regression — DONE
