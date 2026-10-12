# SI10 acceptance evidence

Historical checkpoints from [the SI10 plan](../service-docker-rootless-architecture.md).
Recorded statuses describe that snapshot and do not authorize new execution.

## Recorded checkpoint scope

Status: DONE (2026-10-01). This plan does not
change the deferred EXEC-PLAN-SCOPE-01 or partially accepted SI09 milestones.

## Existing-work separation

SI10 is developed in a separate worktree. The primary checkout's unrelated
EXEC-PLAN-SCOPE-01/SI09 changes are not part of this milestone.

## SI10 acceptance evidence (2026-10-01)

- The two owner-approved DIFF corrections are in scope: a narrow root-owned,
  no-follow destination guard for Docker/LXC files, and explicit dual
  `serverAuth`/`clientAuth` EKU proof on the selected PKI certificate. The one
  authorized targeted recheck resolved `S10-DIFF-01` and `S10-DIFF-02` with
  zero blocking or overengineering findings.
- The RED OS repository publishes `docker-ce-rootless-extras` version `29.7.2`
  as `noarch`, unlike the other x86_64 Docker packages. The manifest now uses
  its exact repository architecture; the generic source resolver is unchanged.
  Focused positive/negative source-identity tests pass.
- The immutable QA runtime is
  `sha256:46fbb7be6578c5e5c004188e7ad6b8b4945ab8519365a820374d4d61e8770165`;
  catalog digest is
  `sha256:5d32e0fdc5526625edd329f3cb5a16f3f3cfa471811207435e0daed789dd9c7a`.
  The QA project's saved revision is
  `sha256:bfe22067146e6774cd287ccc23d964197a614f6e01c4f934b710404c445f9501`.
- Real nonvisual React/Wails invoked project open, Execution Node readiness,
  service Secrets, fresh plan, approval, Start and terminal observation through
  bound Go methods. Plan `plan-5b4f134cb5ef60834cdd0290` produced initial
  run `installer-b37382a3d07ccc3ce4472f2d251274db` and strict repeat
  `installer-5c5f5df7fa464a1f7ace36eae87209dc`. Both authoritative runs
  SUCCEEDED with PKI apply, Docker apply and Docker verify SUCCESS. The repeat
  had zero CHANGED and zero FAILED task results; the React/Wails polling
  observed its terminal SUCCEEDED state. A headless dev-bridge warning in
  `/wails/ipc.js` did not prevent any bound operation; it is not a React
  application exception or a substitute for the successful terminal proof.
- Direct autonomous Ansible apply/verify/repeat passed for both an existing
  account and create-user mode; repeat recaps were `changed=0`. After the
  Installer run, stopping `lxc-net` stopped the target, system/user bridge and
  rootless Docker. A manual user-service start failed while the target was
  unavailable. Starting `lxc-net` restored the whole chain. A controlled QA
  reboot restored all four units automatically; rootful Docker service/socket
  remained inactive. `docker compose` reported `5.3.1`; the TLS API returned
  `OK` with the selected PKI certificate and rejected a client without a
  certificate. No active LXC/Docker containers or unrelated execution run
  were present before the controlled stop/reboot tests.
- Final gates: RED OS Core `python3 -m unittest discover -s ansible-core/tests
  -p 'test_*.py' -q` passed 419 tests (19 skipped); focused Docker safety/TLS
  tests 2/2 passed; apply/verify/clear syntax-check passed. `go test ./...`,
  `go vet ./...`, affected RED OS Go race tests, frontend lint, 67 frontend
  tests, frontend production build, and `wails build -nopackage -clean` passed.
  Catalog and service-schema generators reproduced their checked-in outputs;
  focused secret-literal audit and `git diff --check` passed. The temporary
  RED OS source workspace was removed after testing.
