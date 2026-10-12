# A7 DIFF TARGETED_RECHECK — A7-D01–02

2026-10-12. Owner expressly authorized correction, bounded native QA and one
targeted recheck after the independent FULL DIFF BLOCK.
Independent read-only reviewer `/root/a7_diff_review`, architecture-reviewer.

**APPROVE. CURRENT. Zero open blockers in the recheck scope.** FULL scope was
not reopened. Original FULL BLOCK remains historical evidence.

Reviewed branch `codex/application-libraries`, baseline
`bb32857280ba0238a1fc5a744b3226d8d3105f75`, corrected file-set SHA256 independently
reproduced: `93ff87df5b9a05a6909a2846e9c6116d5acbd94421a4246d7e84acfdc94b2897`
(23 Core/test/schema files, same algorithm as FULL report).

- A7-D01: BLOCKING OPEN → RESOLVED. Consumer checks host IDs separately using
  the existing inventory regex. Positive `1node` and dot/underscore/length/
  leading-hyphen negative assertions preserve the established contract.
- A7-D02: BLOCKING OPEN → RESOLVED. Inspected native QA helper and journal:
  genuine BuildDeploymentPlan/trust staging/typed lease/Start v1alpha2/events/Get
  and active Cancel; Core creates the manifest; real SERVICE_APPLY/SERVICE_VERIFY
  execute the changed shared projection, dispatch and cleanup paths.

Reported current-source native evidence:

| Run | Result |
| --- | --- |
| `installer-d6e2f3105a39eb1520fe88fdd840f06e` | SUCCEEDED, Apply/Verify SUCCESS, 483 events, changed=0, credential cleanup PASS |
| `installer-45af8367dfb20a5078d86f7429e1dc1f` | Active Cancel after TASK_STARTED, CANCELLED, changed=0, credential cleanup PASS |

Both bind the journal's project revision, plan fingerprint and manifest digest
to verified current-source bundle
`sha256:8743412cca4868d51e3786383859418a6700c4c6acecf71e26f838acb3b1e215`.

Overengineering: zero new findings; no new validator, DTO, persistence layer or
scheduler. Reviewer directly inspected correction/assertions/helper/journal and
revision identity; tests and target connections were not independently rerun.
Reported RED OS regression: 120 PASS/four skips and additional 17 PASS. No secret
material read. Mixed application execution and Go/UI acceptance not established.

Cleanup evidence alone does not invalidate this review. A changed secret or
execution boundary invalidates its corresponding reviewed part. Commit, master
merge and A8 require separate owner requests.

[QA journal](../evidence/a7-test-journal.md), [historical FULL review](a7-diff-review.md).
