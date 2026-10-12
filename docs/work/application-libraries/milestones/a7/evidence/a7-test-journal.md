# A7 implementation evidence

2026-10-12. Branch `codex/application-libraries`, worktree
`C:\Users\AnufrievEV\.codex\worktrees\application-libraries\platform-installer-v2`.
Baseline HEAD `bb32857280ba0238a1fc5a744b3226d8d3105f75`; changes uncommitted.
Owner accepted the corrected A7 plan and authorized implementation.

Code/test/schema file-set SHA256:
`79b63a2df900bee73a7177545db1d729062a726a139ae085347fdc10116974d8`.
Identity: sorted unique tracked changed + untracked paths under ansible-core and
contracts, each `path + space + lowercase file SHA256`, joined with LF, UTF-8;
22 files. Documentation is excluded from this implementation identity.

## Environment and scope

Current worktree synchronized with `scripts/qa-sync.ps1` to RED OS node1
192.168.56.101, `platform-automation`, existing persistent identity,
IdentitiesOnly and strict host-key checking. Python 3.11.15 / Ansible 2.18.15.
No Python/Core execution on Windows; no target service mutation, Docker deploy,
artifact acquisition, bundle publication or benchmarks.

## Verification

| Evidence | Result |
| --- | --- |
| First focused run, workspace d0905a7d0cbc4150a0c0e3e325562ece | 164 cases: 160 PASS, one stale PKI wait mock FAIL, three ERROR (lease fixture binding and two stale wait mocks) |
| Corrected focused run, workspace 489473902a8b4c8094fe0f553e9c8ac2 | 164 PASS, 3.946s |
| First native fixtures | Four ERROR: test catalog wrapper assumption; fixture corrected |
| Native run c3c5e65fd0284c1aac880cbfd769f409 | Three PASS, one FAIL: application plan unnecessarily consulted unavailable PKI reissue state; blocked application path corrected |
| Focused/native 4467541893d6448a94e0c1f05ce5053a | 171 PASS, 15.574s |
| First expanded regression | 81 cases, three ERROR in existing stale two-result wait mocks; tests updated to established triple result |
| Final expanded f22dc8ebbf194df9953c6c74be3fb9e4 | 253 cases: 249 PASS / four existing skips, 14.958s |
| Closure and boundary suite 5992c5b324ce4470acc4aa6d74f8073d | 42 PASS, 0.640s; qa-sync Verify PASS |

Final expanded suites: application plan, deployment plan/action, application
libraries/runtime contract, secret lease, Docker dispatch, lifecycle, native
application plan, hardening, failure diagnostics, task observability, runtime
bundle/artifact sources, Vault/providers/endpoints.

Additional suites: runtime bundle, capabilities, execution resolution, target
trust and secret-output protection. Closure test uses standard builder
SOURCE_ROOTS/copy_tree/components and catalog-layout validation; A7 module,
existing application playbooks and new schemas are copied with matching source
hashes and without runtime/test entries. This is source closure evidence, not
publication or acceptance of a newly installed bundle.

Five native Ansible cases: application snapshot, blocked application plan with
no executable manifest, no-secret descriptors, empty-library legacy snapshot,
empty-library legacy plan. All target-free and without changed tasks.

## Acceptance limits and review

At initial FULL DIFF, real infrastructure protocol Build→Start→events/cancel
had not yet been exercised. Existing lifecycle/protocol unit tests were
supplementary. Mixed application production execution is intentionally gated
until A8; Go/UI acceptance belongs to later stages and is not claimed here.

Independent FULL DIFF review reports BLOCK: A7-D01 host-ID contract mismatch in
application secret admission, A7-D02 missing real infrastructure protocol
regression. No corrective production edits were made after the review finding.
See [review](../reviews/a7-diff-review.md). Owner decision is required before
correction/QA and the single TARGETED_RECHECK. This was the initial BLOCK status;
owner-approved correction and final independent closure are recorded below.

All six unique remote QA source workspaces were removed through the standard
qa-sync cleanup operation. No containers or infrastructure credentials were
changed by these tests. No commit or master synchronization performed.

## Owner-approved correction and native protocol QA

The owner approved D01 correction, bounded real infrastructure QA and one
TARGETED_RECHECK for D01–02. D01 now checks hosts with the existing inventory
regex separately from library IDs. Positive `1node` and negatives for dotted,
underscore, overlength and leading-hyphen hosts added. RED OS focused regression:
124 cases, 120 PASS/four existing skips, 6.544s.

Corrected code/test/schema file-set SHA256:
`93ff87df5b9a05a6909a2846e9c6116d5acbd94421a4246d7e84acfdc94b2897`
(23 files, same identity algorithm). Native QA helper source SHA256:
`063502f56f4c103f73e7372a6804a32b351b13b520b1604c4bbf14bc6f719ffd`.

Current-source runtime `a7-native-20261012` built with the standard builder on
node2 from its existing approved runtime inputs. Go standard `validate-bundle`
PASS after extraction; initial validation attempt pointed to a not-yet-extracted
directory and returned EXECUTION_BUNDLE_ROOT_INVALID. Verified bundle digest:
`sha256:8743412cca4868d51e3786383859418a6700c4c6acecf71e26f838acb3b1e215`;
catalog `sha256:928f45a27c8f81999b02c0922d2d20837c4d9b7b0b5452ce3cef8643fbbd2a3d`;
schema `sha256:37cdc98cc3e8b4982d80a68c6536b25e0c5c3f525ad00a22ee180e7d2f0e149b`.
No acquisition/download, publication, activation or project rebind performed.

QA scope: standalone native production protocol on node1, one `qa-docker`
deployment, existing-user `platform-docker`, current TLS directory
`/home/platform-docker/.config/docker/pki`, matching empty name prefix and `/data`.
No application deployment, PKI issuance or password/account replacement.
Separate project ID `a7-infra-protocol`; actual Build/lease/Start/events/Get/Cancel
use existing production protocol with a protected temporary copy of the
established transport identity. Existing root state is used because the task
callback writes to the established execution state root.

Earlier native attempts remain failures:

- `installer-3d079bca0e0fa052d180331efc6ae07d`: FAILED with generic
  EXECUTION_OPERATION_FAILED. Private QA state root prevented task events.
- `installer-ece7c2ce8b217d3a5658998d0452ccbf`: FAILED on the existing role's
  refusal to replace foreign LXC dnsmasq configuration. QA supplied name prefix
  `qa`, inconsistent with the existing installation; fixture corrected to empty
  prefix. The guard preserved the active configuration. No production code fix.

Both used real detached controllers; lease credentials were cleaned after
terminal observation. Earlier failed runs remain failures.

### Corrected native production regression — PASS

Current-source workspace `2ea87bd73bdc49f5a801d222b021ce7d`, qa-sync Verify PASS.
Additional focused/native suites: 17 PASS, 36.819s (concurrent VM load).
Transferred bundle archive SHA256 matched on workstation/node1:
`e0f556db41b6eb47ca2615658c128cf3d787508cb49409c061c414288381238e`.

Real protocol calls: BuildDeploymentPlan → host trust staging → typed credential
lease → StartExecution/v1alpha2 → GetEvents/GetExecution. No mock subprocess,
injected operation or rewritten manifest. Core built and registered the manifest.
Both scenarios bind:

- Project revision `sha256:6b45a6ba114d17417cbefd17964343752d3fada07b228ca590f87c40d8ca40d4`.
- Plan fingerprint `sha256:77c126a7e871cc4b73f552e0fc39b99dddfc4da04a1ec60ebff6bd863671b9e1`.
- Manifest digest `sha256:69b4b4ec641c0315a95a3b10630a5995efa7d9d8a80a64ea533f7ea1771e0ebe`.
- Runtime bundle `sha256:8743412cca4868d51e3786383859418a6700c4c6acecf71e26f838acb3b1e215`.

| Run | Real terminal evidence |
| --- | --- |
| `installer-d6e2f3105a39eb1520fe88fdd840f06e` | SUCCEEDED; fixed SERVICE_APPLY `apply:qa-docker` and SERVICE_VERIFY `verify:qa-docker` both ACTION_COMPLETED SUCCESS; 483 events observed; changed task count 0; recursive temporary-key and typed-input cleanup PASS |
| `installer-45af8367dfb20a5078d86f7429e1dc1f` | Separate fresh Build/lease/Start, active Cancel after TASK_STARTED in SERVICE_APPLY; CANCELLED; seven events observed before final cancellation; changed task count 0; recursive temporary-key and typed-input cleanup PASS |

This closes the missing native infrastructure evidence for D02, subject to
independent TARGETED_RECHECK. It does not establish mixed application execution,
UI/Wails acceptance or A8 readiness. Active runtime was never replaced. Run
journals remain the existing authoritative execution evidence.

### Final review and cleanup

Independent owner-approved [TARGETED_RECHECK](../reviews/a7-diff-targeted-recheck.md)
APPROVE, A7-D01–02 RESOLVED, zero open blockers. A7 scope is implemented and its
required QA/review gates passed. Initial BLOCK and failed QA attempts remain
historical evidence. No A8 execution, Go/UI acceptance or commit implied.

All four known QA controller units were independently checked inactive/dead
before removing their source runtime. Eight correction-round remote QA source
workspaces (seven node1, one node2), temporary bundle/archive and protected
staged transport identity removed through qa-sync Cleanup. Initial cleanup
failed on root-owned Python cache files; ownership was normalized only inside
the exact verified temporary workspaces, then standard cleanup passed.
Persistent execution journals and existing installation were retained.

Automatic command approval rejected recursive local deletion twice with
`blocked by policy`. The nonsecret verified temporary bundle/archive remains
under worktree `.runtime/qa/a7` (ignored runtime artifacts); no alternative shell
or deletion bypass used. This is artifact retention, not credential retention.
No active bundle replacement, commit or master synchronization performed.
