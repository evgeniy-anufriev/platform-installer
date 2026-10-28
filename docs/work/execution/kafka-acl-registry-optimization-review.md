# Kafka ACL / Schema Registry optimization — review and evidence

Status: corrections complete; TARGETED_RECHECK APPROVE, blocking0.
Real installation and measured speed acceptance remain pending.
Date: 2026-10-28.

## Worktree and source boundary

Branch: `codex/kafka-acl-registry-optimization`.
Base `0e739c61ce0ed079cbb3367449a12516cade9690` is a snapshot of the source
worktree at `ee8e35e69a33b4ebda16db61c047ad6165bad020` plus its 34 inherited
dirty files. The snapshot was committed only in this new worktree. Inherited
controller/Go changes are outside this optimization's review scope.
Owner authorized the optimization commit and branch merge into master after the successful targeted recheck. No bundle publication, rebind, target
Apply or active-run control was performed.

## Independent reviews

Reviewer: architecture-reviewer subagent `/root/plan_review`, read-only.
FULL PLAN: APPROVE_WITH_CHANGES, blocking0. Original plan SHA256
`937fd967462895e68b8230885c1d3dcf269cd3517a39509d72a7caacb2a8272c`.
KRO-P01 requires systemd LoadState/ActiveState as well as unit-file absence for
cold classification. KRO-P02 requires linear strategy and batch-local candidates
under serial. Both refinements were incorporated without a second FULL PLAN.

FULL DIFF: BLOCK, one blocking finding. Review identity was computed as SHA256
of the UTF-8 manifest of sorted changed/untracked file paths and SHA256 hashes,
one `path hash` per LF-separated line, no final LF:
`cd6d63585ee65a74de94a776b52216e2a4b204f6f4ac98ab7b480ec268b3fd95`.
Plan SHA256 then was
`5555141e44f05449ed8921f0952f9ce6ca530fb091d5e44ce997c2f57193ca6e`.
Production code was frozen at BLOCK until the owner's subsequent explicit
"разрешаю исправляй" authorized both corrections, repeated QA and one
TARGETED_RECHECK. That recheck has now been consumed: APPROVE, no open blockers.
Reviewed fingerprint:
`5902a9d422efbc9118e5f925ba8a02c28e6239fb52b01d345d9eb8334698ac88`;
plan SHA256 `3727a8cf8f4918546a5509097bd112d904f96dc60a98f30c7bd7b5efb6e540bd`.
Only evidence/status documentation was updated afterward; production/tests stayed
unchanged. No further automatic review is authorized by this completed budget.

### KRO-D01 — RESOLVED by TARGETED_RECHECK

`schema_registry_instances.yml:19` selects registry_instance from the coordinator's
full projection, then delegates to another host. Only the CLI install directory
is rebound; host-local Registry config root/name/paths can therefore refer to the
coordinator's settings. Preparation on the destination used its own local projection.
With reversed inventory and distinct host_vars, the topic command can select an
absent or wrong client file. Existing fixtures share a projection and do not check
client-file existence, so do not cover this case.

Minimum correction: select the exact prepared local instance on candidate.host by
(deployment_id, id), assert uniqueness and an activation record, and use its full
context. Native regression must have distinct host-local config roots/names,
multiple deployments, reversed inventory, exact command-config ownership, and
partial/serial coverage. No new resolver or cache is necessary.

Correction: schema_registry_topic_for_host.yml validates the exact prepared local
instance by deployment/id/host and exactly one activation record, then uses that
host's full local instance, projection and captured effective CLI directory.
The fixture now gives each host different Registry roots/names and CLI paths;
the CLI recorder requires an existing client file with matching host/instance/
deployment identity. Fixtures materialize host facts just as production validation
does, instead of relying on play-only variables invisible through hostvars.

### KRO-T01 — RESOLVED by TARGETED_RECHECK

The explicit stale-map assertion in the expanded native fixture fails:
`'stale' not in _platform_kafka_registry_activation` evaluates false on all three
hosts under the repository's hash_behaviour=merge. `set_fact` of an empty mapping
does not override stale keys supplied from the lower variable layer in this test.
The activation map reset must be made robust and revalidated for multiple
invocations. Preserve the failing assertion; do not weaken it to get PASS.
This was confirmed independently of service collection-path configuration.
Correction: activation records are a list, replaced on every invocation and
updated by exact deployment/id identity. Regression covers a lower-precedence
stale list, the legacy stale dictionary, co-location and repeated role invocations.

## QA evidence and limits

All Python/Ansible execution occurred on RED OS101 as platform-automation using
the established PEM identity and strict host-key checking. Sources transferred
with scripts/qa-sync.ps1 into isolated /var/tmp/platform-installer-qa-* workspaces.
No installed Kafka/Registry instance or real credential was used by the fixtures.

- First focused suite: 24 tests PASS, 124.880s (ACL writes, Registry orchestration,
  partial topic cases). These precede the stronger stale-map/co-location assertions.
- Apply and Verify playbook syntax checks PASS.
- Expanded regression completed: 80 tests, 516.789s; raw result 15 failures,
  10 errors and 1 skip (counts include subtest failures). This is not PASS.
  Role-based tests were initially launched without
  ANSIBLE_COLLECTIONS_PATH; their environment failures must not be counted as code
  passes or diagnosed as implementation defects without a corrected rerun.
- The existing test_registry_phase_runtime principal-sharing fixture still refers
  to _platform_kafka_admin_principals while the inherited source uses
  _platform_kafka_internal_principals. This unchanged fixture also failed; it was
  not repaired during the blocked optimization.
- The focused cold-order test was repeated with the proper collection path and
  failed KRO-T01, 12.468s. Ordering itself reached all three starts/readiness calls.
- Real React/Wails installation, real Kafka CLI batching acceptance and wall-time
  improvement remain untested. Synthetic CLI/orchestration proof is supplementary.

Local logs: `.runtime/qa/acl-registry/initial-24.log` and `expanded-80.log`.
Both remote QA workspaces were cleaned with qa-sync after their runners exited.
The source worktree's 33 inherited code/test/doc paths (excluding CURRENT_STATE)
still match the initial hashes. Its CURRENT_STATE changed concurrently; this task
issued no writes to that source worktree.

## Corrected QA and acceptance boundary

- Corrected source transferred with qa-sync; explicit ANSIBLE_COLLECTIONS_PATH
  includes the Kafka service and Core collections. Accounts/ACL/phase modules:
  26 test cases finished `ok`, including the refreshed inherited principal fixture.
  Their enclosing 39-test run failed because the Registry fixture still used a
  play-only variable in place of the production host fact. That combined run is
  not claimed as PASS; its log remains `corrected-accounts-acl.log`.
- After aligning that fixture with production set_fact, the separate full Registry
  optimization suite passed all 13 tests in 104.781s, no skips. Evidence:
  `.runtime/qa/acl-registry/registry-corrected-13.log`.
- These final selections cover 39 unique tests across the two runs. No successful
  all-in-one 39-test run is claimed. The earlier raw 80-test regression result is
  retained above, not rewritten as a successful run.
- Apply and Verify syntax checks repeated on corrected production sources: PASS.
  git diff --check: PASS. All four QA transfer workspaces used across this task
  were cleaned using qa-sync after their processes exited.
- Reviewer directly read both local logs and confirmed KRO-D01/KRO-T01 resolution.
  It did not independently rerun tests or contact targets.
- No active run, published bundle or installed service was changed. Actual
  Kafka/Registry performance and React/Wails installation acceptance remain open.

No unnecessary abstraction, duplicated DTO, new persistence or generic scheduler
was found by the reviewer. ACL tuple preservation, separate cluster grants and
retained ownership/PKI/HTTP+HTTPS checks had no additional blocking findings.

## Owner-authorized master integration (2026-10-28)

Optimization commit: `ab49eb09`. Integrated `origin/master` at `16b37d99`,
including the shared Kafka/Registry distribution and configurable CLI suffix.
Conflict resolution retains phased Registry orchestration and ACL batching;
new CLI tasks also consume `platform_kafka_script_extension`. Shared-distribution
fixtures now select the tasks inside the fatal preparation block.

Fresh qa-sync source on RED OS101: combined 94 tests PASS in 332.576s, no skips
(Registry optimization/phase, accounts, ACL writes, application batch, shared
archive native/assertion checks, member normalization, SERVICE-01B/01D contracts).
Apply and Verify syntax checks PASS. Local evidence:
`.runtime/qa/acl-registry/merge-focused-94.log`. Temporary source workspace cleaned.
Source diff whitespace check PASS; two whitespace lines inherited unchanged from
the origin/master generated portable-source snapshot were not edited.
This integration does not claim installed-service or React/Wails performance acceptance.
