# A7 FULL DIFF review

2026-10-12. Independent read-only `architecture-reviewer` agent
`/root/a7_diff_review`. Verdict **BLOCK**, validity CURRENT, two open blockers.

Branch `codex/application-libraries`, baseline HEAD
`bb32857280ba0238a1fc5a744b3226d8d3105f75`, uncommitted A7 scope.
Independently reproduced code/test/schema file-set SHA256
`79b63a2df900bee73a7177545db1d729062a726a139ae085347fdc10116974d8`:
22 changed tracked/new untracked files under ansible-core/contracts, sorted paths,
rows `path lowerSHA256` joined LF. Reviewed plan SHA256
`866e95cfca00309f92e16178085853c8af50b29f8ec6470e78c1a0f9c2a30cd3`.

## A7-D01 — BLOCKING, OPEN

`ansible-core/tools/execution_secret_lease.py:310–316` checks library IDs and
host IDs using the same library regex. Existing controller `_service_targets`
and application-operation schema allow hosts `[a-z0-9][a-z0-9-]{0,62}`.
Valid host `1node` is rejected by the new consumer; dotted/underscore IDs are
accepted there although forbidden by the controller.

Minimal correction: use the existing host contract separately from the library
contract. Add positive `1node` and negative incompatible-host tests. No new
validator or expanded host contract needed.

## A7-D02 — BLOCKING, OPEN

Plan section 9 requires actual infrastructure-only native protocol regression
Build→Start→events/cancel. It has not been executed in this iteration.
Target-free native checks and mocked lifecycle/controller tests do not establish
production compatibility of changed shared projection/dispatch/cleanup paths.

Minimal correction: bounded native infra-only run on owner-authorized QA scope
from current runtime; record project revision, runtime identity, plan/manifest
binding, run ID, events and terminal/cancel result. Request specific target
authorization if needed. Mixed application acceptance remains A8/A9.

## Other conclusions

Overengineering: zero blocking findings. No extra desired-state store,
per-instance scheduler, hook process subsystem or speculative retries. Two fixed
operations reuse existing playbooks and private run custody. Independent review
checked edited modules, playbooks, schemas, relevant tests/plan/instructions and
execution boundary; application plans emit no executable manifest before A8 and
infrastructure capability declarations remain unchanged.

Reviewer inspected, but did not independently run, reported RED OS evidence:
253 cases (249 PASS/four skips), five native Ansible cases; additional 42 PASS
closure/capabilities/resolution/trust/secret-output checks. No secret values read.

Per review procedure, corrections and missing QA stop pending owner decision.
After owner approval, one TARGETED_RECHECK may cover A7-D01–02 and the immediately
affected boundary. No automatic additional FULL review. Implementation is not
accepted or complete. Detailed evidence: [journal](../evidence/a7-test-journal.md).
