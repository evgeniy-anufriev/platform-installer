# APPLICATION-IMAGE-METADATA-01 — FULL DIFF review

2026-10-20. Independent read-only reviewer `/root/image_defaults_plan_review`.
Verdict: **BLOCK**. Four implementation defects and one missing acceptance gate;
five unresolved blocking findings. No source corrections or automatic re-review
are authorized by this report. Owner decision is required by review.md.

## Frozen identity

- Worktree: `C:\Users\AnufrievEV\.codex\worktrees\application-image-metadata\platform-installer-v2`.
- Branch: `codex/application-image-metadata`.
- HEAD: `930d5f71a83e3be99901ea40e2af6464394526f5`.
- Approved plan SHA-256: `FA4C351EA79E2917E23D8D2037477371CD94761C6B54F840FD6A722219F40580`.
- Owned manifest SHA-256: `F8A6D132F478BE68EEAA17A7104EF4E68350E26CAF39E2C1F251CDF695C83D62`.
- Owned diff SHA-256: `7EEEAEE83A484435735E20C371CC4BCAD179EAAFD578D394B87D4D3BC8197486`.

The reviewer verified all79 frozen after-files before and after review; inherited
before-files were compared with the preserved dirty baseline or HEAD, accounting
for LF/CRLF. Unrelated transferred SDKU changes were excluded. The plan's final
editorial revision and the direct owner approval were confirmed to the reviewer.

## AIM-D01 — BLOCKING / OPEN: offline platform and mixed-placement identity

Evidence: `ansible-core/collections/ansible_collections/platform/core/plugins/action/prepare_application_images.py:40`,
`ansible-core/playbooks/application-images-prepare.yml:45`,
`ansible-core/collections/ansible_collections/platform/core/plugins/module_utils/application_images.py:133`.

A single offline candidate becomes ready using its own platform without target
discovery. An arm64 archive may therefore prepare authority for an amd64 target.
The final ready/target merge also occurs after the cross-host identity check;
offline image A and registry image B for the same reference/platform may escape
the required conflict rejection.

Smallest correction: use trustworthy matching target evidence or the existing
bounded discovery; check identities after combining all placements, including
ready. Verify incompatible single-platform archive, mixed offline/registry
conflicting IDs, and a compatible positive case.

## AIM-D02 — BLOCKING / OPEN: secret-bearing add_host output

Evidence: `ansible-core/playbooks/application-images-prepare.yml:7–14`.

The task copies the full runtime secret map into add_host arguments without
no_log. Detailed standalone callbacks may print these values; suppression by the
machine wrapper does not protect standalone usage.

Smallest correction: remove the redundant secret map assignment if private
extra-vars already provide it, otherwise apply no_log. Verify a synthetic
sentinel is absent from verbose success and failure output. No real credentials
are needed.

## AIM-D03 — BLOCKING / OPEN: scoped secret requirements collapse to sourceRef

Evidence: `ansible-core/tools/execution_image_preparation.py:45`,
`ansible-core/collections/ansible_collections/platform/core/plugins/module_utils/application_plan.py:42`,
adjacent admission at `internal/desktop/app.go:1199`.

Distinct library/registry requirementRefs are flattened into runtimeReference
keys. Repeated sourceRefs overwrite values across scopes. The schema allows
such references, while desktop's global sources check rejects them. Direct
Core preparation can consequently use another auth scope's value.

Smallest correction: retain scoped requirementRef through the concrete Ansible
consumer and align desktop admission, reusing the existing broker/store. Verify
two scopes with repeated sourceRefs, distinct values, no cross-scope delivery and
successful descriptor admission.

## AIM-D04 — BLOCKING / OPEN: malformed registry assignment downgrades auth

Evidence: `contracts/application-libraries/v1alpha1/deployments.schema.json:13`,
`frontend/src/ApplicationRegistryCredentials.tsx:60`,
`ansible-core/collections/ansible_collections/platform/core/plugins/action/prepare_application_images.py:49`.

The credential map accepts arbitrary keys. An assignment to
`https://registry.example` is saved but lookup uses `registry.example`, silently
choosing node credentials or anonymous access instead.

Smallest correction: validate the declared host[:port] authority form in the
canonical Core/schema boundary and return a finding for malformed assignments.
React must not become a resolver. Verify scheme/path/userinfo/wildcard and
unsupported authority inputs cannot trigger fallback; valid host:port works.

## AIM-D05 — BLOCKING / OPEN: real acceptance and regression evidence

The actual React handlers → Wails methods → current Core flow has not exercised
registry assignment, Review/Save/reopen, session inputs and Create Plan. Mocked
frontend and direct protocol tests are supplementary. Full regression also
remains incomplete with an unclassified error on an earlier source snapshot.

Smallest correction: obtain current-revision evidence, classify regression
failures and state visual status separately. Updated QA runtime publication/
preparation requires the separate owner authorization specified by the plan;
this review does not provide it.

## Overengineering and evidence limits

Confirmed unnecessary mechanisms: **0** in abstractions, duplicate DTO/contracts,
premature scope, speculative features and missed simpler mechanisms. The index
reuses components; fixed preparation preserves a target-free planner; the
request-lifetime lease avoids fictitious plan bindings. Built-in Ansible tasks,
the existing journal/session and transient DOCKER_CONFIG fit the requirement.
AIM-D02 permits removing redundant secret copying rather than adding machinery.

The reviewer directly inspected the frozen diff and dependencies, but ran no
tests and accessed no targets or secret values. Parent-reported evidence: Go/vet
PASS, frontend265/build/lint PASS, focused14 PASS, offline10 PASS and offline
Validate64/changed0/failed0. Actual Wails and visual acceptance are absent.

Validity: CURRENT for the frozen implementation. Evidence updates cannot repair
AIM-D01–04. Following BLOCK, implementation stops; return AIM-D01–05, minimal
corrections and recommendation to the owner. Only one owner-approved
TARGETED_RECHECK of corrected blocker IDs remains; no automatic new FULL review.

## Owner decision, 2026-10-20

The owner explicitly rejected AIM-D01 (only amd64 is used; obtaining the same
image from different sources is acceptable) and AIM-D03 (the proposed repeated
reference scenario was not accepted). These findings are **REJECTED_BY_OWNER**,
not source corrections. Their reviewed code is retained. Existing image identity,
delivery verification and source policy are not removed or relaxed.

The owner instructed correction of AIM-D02, accepted AIM-D04 and instructed
execution of AIM-D05. Work resumed within that scope. AIM-D02 removes redundant
secret propagation through add_host; AIM-D04 uses the existing schema/writer
boundary to require host[:port]. QA and the single permitted TARGETED_RECHECK
are recorded separately; the original FULL verdict above remains historical.
