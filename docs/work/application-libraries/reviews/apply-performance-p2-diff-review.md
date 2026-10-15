# Apply performance P2 — independent FULL DIFF review

2026-10-15. Reviewer: architecture-reviewer `apply_performance_p2_diff_review`.
**Verdict: BLOCK. Unresolved blocking findings:1.**

## Verified identity

Base `3fcf54c83ec13dcb2fda035862a5305c843a1095`, branch
`codex/application-libraries-apply-performance`. Frozen43-file manifest
`.runtime/qa/apply-performance/diff-review-identity.json`, SHA-256
`F652198192E9CC577009E9C037357F16E698046A7818EFB43E5BAF2BFDCF9D76`.
All43 hashes verified before/after:0 mismatches. Review read-only; no tests,
target commands or credentials accessed. Findings formed independently.

## AP-P2-D01 — BLOCKING / OPEN

`services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks/main.yml:15`
still validates the singular variable after normalizing plural scope. For plural-only
input its left-hand absent-scope check is false and `match` receives undefined
`platform_haproxy_partial_deployment_id`. Production batch apply-source passes only
plural IDs, so the new path fails before HAProxy lifecycle.

Smallest correction: check singular only when defined, or remove the duplicate
singular assertion while preserving validation of every normalized ID in
partial_scope.yml. Do not substitute the first plural ID as singular.

Required native regression: production main assertion after actual normalization
for two plural-only sources, singleton and full/no-partial; empty/conflicting scope
must still fail before mutation. Current extracted-task tests missed main assertion.

## Overengineering

No blocking complexity findings. execution_ssh.py is limited operation-private
socket custody/standard cleanup, no registry or daemon. Batch task files reuse
resolvers/candidate/activation/DNS/probes. No new DTO/store/API/scheduler/workers or
parallel probe runner. Singleton adapters preserve compatibility.

Reviewer inspected lifecycle/trust/lease/recovery, host scope, barriers, DNS
prerequisites/bounds and per-source probe policies. Reported tests are supporting
evidence, not independently rerun. Full regression/real target/timing gates remain
uncompleted; review is not QA acceptance.

Implementation stopped at BLOCK. No correction or TARGETED_RECHECK performed.
Owner approval is required for the minimal correction and one finding-scoped recheck;
no second automatic FULL review. Built perf-bundle01 is not published or activated.
