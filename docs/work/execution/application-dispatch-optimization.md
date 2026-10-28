# Application preparation and dispatch optimization

Owner-authorized continuation in `codex/application-preflight-optimization`,
base `a66853a1`. Review is waived by the owner. The owner authorized committing
this change. No bundle publication, deployment or merge is part of this continuation.

## Behavior

- Library preparation records the instance IDs actually prepared on each host,
  only after the entire preparation succeeds. The pending dependency snapshot
  used to select those jobs also determines the recorded IDs. Ordered startup
  prepares only remaining placements. An already satisfied dependency no longer
  causes duplicate directory, configuration, Compose or identity-file delivery.
  Facts reset for each library; another operation prepares files again. Deferred
  jobs still receive their complete preparation after provider/Vault delivery.
- Dependency guards and ready-provider batch selection execute once under the
  existing linear strategy. Host-local preparation/start/scripts share one
  include guarded by the presence of placements. Endpoint publication remains
  outside this include and runs on all relevant HAProxy/DNS hosts.
- Script dispatch selects jobs with matching phase and scope before expanding
  roles. Ordering and readiness checks are unchanged.
- Shared Vault delivery records successful field identities (provider, library,
  mount, document, field), never values. The provider stage resets this list and
  records its successful initial delivery. Later callbacks select only newly
  ready fields, snapshot that selection, perform fresh owner/CAS preflight and
  write through the existing CAS/retry implementation before recording success.
  Instance credentials retain their existing once-per-operation delivery guard.
  No cross-run cache or cached-CAS shortcut is introduced.

## Acceptance limits

The motivating run `installer-9803e6f83c34abb9bc9823e19d5024be` attributed 33
results and 52.4 seconds to duplicate SDKU preparation. This is summed task
duration, not a measured saving for the changed installer. Preparation follows
the same generic path for every library; deferred SZI instances were previously
prepared only once and keep that behavior.

Focused RED OS validation: **42 distinct tests PASS** across final selections,
no skips. Real React/Wails installation and whole-stage timing remain pending.
Active runs and installed services were not modified by isolated QA.

- Initial selection: 40 tests, 36 PASS / 4 FAIL (387.394s). The preparation
  fixture supplied play variables rather than the host facts consumed by the
  production tasks. Three Vault cases lacked the newly initialized delivered
  shared-fields list. These fixture failures are not recorded as a passing run.
- Three-host scheduling check PASS: only node2 enters placement actions while
  all three logical hosts execute endpoint publication and receive the common
  ready-provider batches. This uses isolated local connections and endpoint
  probes, not deployed HAProxy/DNS services.
- Corrected native preparation and shared-field coordinator checks: 2 PASS
  (80.654s). Already ready dependency, late dependency, new operation, empty
  delivery repeat and newly ready shared-field delta are covered.
- Corrected Vault native delivery suite: 5 PASS (68.178s), including real
  Ansible roles against an isolated HTTPS fixture, generated credential custody,
  repeat, CAS conflict with preserved neighbor fields, foreign ownership
  rejection and route isolation.
- Existing script execution/order, job scoping, integration batches and Vault
  ownership/policy tests passed in the initial selection. Production safety
  conditions were not relaxed to fix the fixtures.
- Apply/Verify syntax checks and `git diff --check`: PASS.
- Local final logs: `.runtime/qa/application-dispatch/`. Four qa-sync source
  workspaces were used and cleaned after their checks.
