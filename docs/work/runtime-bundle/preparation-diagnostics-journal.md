# Bootstrap, activation and Core preview diagnostics

Owner request 2026-10-30: preparation must install missing ansible-core itself;
bootstrap/activation and subsequent Core projection failures need concrete safe
causes in UI, with source publication to GitHub.

## Source defects and corrections

- OpenSSH concatenates remote argv for the remote shell. An unquoted multi-item
  platform list split the seventh runtime argument and displaced the eighth
  bootstrap flag. The generated shell then selected legacy-prerequisite mode
  instead of the verified bootstrap script. Quote all eight data arguments;
  validate exact argc in the remote script. Keep the existing password/sudo
  wrapper and its quoted `"$@"` forwarding.
- BuildServiceConfigurationPreview admitted only capabilities v1alpha5/v1alpha6,
  while current runtime capabilities extend through v1alpha11. Admit the known
  additive versions v5..11, retaining explicit operation/protocol/limit checks.
  Unknown future versions and invalid declarations remain blocked. Transport
  failure is no longer mislabeled as unsupported capabilities.
- Bounded bootstrap/activation output is classified only by whole-line codes
  from a closed vocabulary. An internal typed error carries phase and safe
  finding across PreparationStepError to the existing preparation error message.
  Deadlines retain context identity despite transport redaction.
- Shell phases identify copy, state/Python initialization, capability check and
  runtime switch failures. DNF output stays in process memory and only maps to
  fixed download/package/dependency/signature/space/lock categories. Raw output,
  passwords, URLs and exception strings are not published.
- Missing prerequisites still use installed packages, verified bundle RPMs and
  existing configured DNF repositories under the established bootstrap policy.
  No repository additions, source-policy changes, retry after offline failure,
  weakened checksums/ownership or changed rollback/approval are introduced.
- The existing ServiceConfigurationPreview presentation DTO has optional local
  `diagnostic` metadata, analogous to RuntimeDigest. Desktop converts failures
  to a diagnostic-only result so Wails and browser transport retain the reason.
  Core response decoding explicitly rejects this local-only field. React reads
  diagnostics before revision checks and never accepts them as successful data.
  Runtime Core schemas and desired-state contracts are unchanged.

## Verification

- Full `go test ./...` and `go vet ./...`: PASS.
- Affected executionnode/desktop suites rerun after deadline correction: PASS.
- Bootstrap framing regression: multiple platforms, both existing sudo modes,
  exact two phase calls and no password in argv. Safe-code and capabilities
  acceptance/rejection regressions PASS. Timeout-through-transport test PASS.
- Affected frontend App/Servers tests: 96 PASS; typecheck PASS. Structured Core
  reason remains visible with dependent sections blocked.
- Added RED OS bootstrap tests for automatic missing ansible-core installation
  with multiple platforms and DNF failure category/private-output exclusion.
  NOT EXECUTED: strict SSH probes to RED OS101/102 timed out on port 22.
- Real React/Wails -> Execution Node preparation/Core flow acceptance OPEN.
  No new package transaction, runtime activation, bundle build/publication or
  installation run was performed by this source task. New desktop and runtime
  bundle delivery are needed; do not claim actual target installation PASS.
- Independent FULL DIFF: APPROVE_WITH_CHANGES, zero blockers. RCD-N01 deadline
  preservation corrected. RCD-N02 (actual OpenSSH/remote-shell multi-platform
  test for both sudo modes and missing ansible-core) remains OPEN due QA-node
  unavailability. Source review is not real runtime acceptance.
- `git diff --check`: PASS. Only scoped source/test/evidence files committed;
  pre-existing dirty work preserved.
