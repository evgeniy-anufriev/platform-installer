# A2 — independent FULL DIFF review

2026-10-10. Reviewer: `/root/a2_full_plan_review`, read-only architecture-reviewer.
This is the first FULL DIFF gate, separate from the consumed PLAN gate.

**Verdict: BLOCK. Unresolved blockers: 2 (A2-D01, A2-D02).**
Automatic implementation changes stopped; corrections and the single optional
TARGETED_RECHECK require an owner decision under
[review procedure](../agent-procedures/review.md). No recheck has been invoked.

## Identity and scope

- Worktree: `C:\Users\AnufrievEV\.codex\worktrees\application-libraries\platform-installer-v2`.
- Branch: `codex/application-libraries`.
- HEAD/base: `ac4340be8693c3068dc631be91975a22947aab32`.
- All 43 changed/new files in ansible-core, contracts and examples/valid/application-runtime inspected.
- Fingerprint: `39ce43430fdaf6c8dd2fcd88f0239cd4549c87bbc1d9542eb0d1a2ab2bb883be`, reproduced before and after review.
- Plan SHA256: `56F96F13F0C3EE5F66C5DD003F40EF5F6CB69F674909EDB09465E4C518684A75`.

Fingerprint algorithm: unique sorted relative paths from git diff --name-only and
git ls-files --others --exclude-standard within the three scope roots. Each row
is lowercase SHA256(file bytes), a space and path. UTF8 rows joined with LF plus
final LF, then SHA256. Journal/documentation changes are outside this fingerprint.

Scope: standalone A2 materialization, render/settings contracts, image authority
and delivery, rootless Apply/Verify, compatibility of the shared RPM caller.
Non-goals: A3–A8, Go/UI, provider provisioning, release bundle publication and
unrelated main-project changes. Owner decisions considered: automatic config
digest/Compose recreate; public pinned Nginx for A2 QA instead of the old probe.

## A2-D01 — BLOCKING / OPEN

**Optional offline archive blocks an available registry source before discovery.**

Location: `module_utils/application_runtime.py:108–111`, target discovery in
`roles/application_runtime/tasks/preflight.yml`.

Evidence: whenever image.archive exists, prepare_runtime unconditionally requires
bundle_root and calls bundle_archive before target registry discovery. The image
lock permits registry and archive alternatives; no requiredOffline field exists.

Scenario: a lock has a correct pinned registry image and fallback archive. The
approved registry is available, but the optional bundle is absent or its archive
is damaged. Preparation fails with APPLICATION_BUNDLE_REQUIRED/archive error
without checking the available preferred source.

Impact: violates repository-then-offline policy, making fallback availability a
registry installation prerequisite. This order cannot enter shared execution
integration.

Smallest correction: separate descriptor validation from byte verification.
Controller validates schema and bounded archive references. After target source
discovery, verify bundle/archive only for OFFLINE_BUNDLE placements, completing
this verification across selected placements before filesystem/container writes.
An obligatory offline closure would need a distinct explicit contract requirement.

Required checks: registry succeeds despite absent/damaged optional fallback;
absent registry with that fallback blocks before mutations; auth/transport error
continues to block without hidden fallback.

## A2-D02 — BLOCKING / OPEN

**One mutable localReference can identify different image IDs on one daemon.**

Locations: `module_utils/application_runtime.py:95–116`,
`roles/application_runtime/tasks/image_delivery.yml:12–13,68–70`, image-lock schema
and the library-local guard in apply_library.yml.

Evidence: image records are checked individually; different imageId values may
share localReference. Delivery reassigns a mismatched tag. The guard covers one
library-host directory, whereas a Docker tag is global to the daemon.

Scenario: two libraries use different images A/B with the same allowed local tag.
Apply tags A, then B; each repeat retags A→B. Parallel library runs may reassign
the tag between inspect and compose up, starting the wrong image before Verify.

Impact: breaks changed=0, isolation and image identity before startup. Detecting
the error after startup is insufficient.

Smallest safe correction: derive the managed runtime reference from the full
config/image digest and validate the binding, or start by exact verified image ID
if the installed Compose supports it. A uniqueness check of selected jobs alone
does not protect independent library runs. Avoid a daemon-wide tag registry or
new persistent lock subsystem.

Required checks: conflicting records rejected before mutations or given distinct
immutable references; different-image libraries keep correct IDs and changed=0;
parallel allowed library runs cannot replace each other's startup image.

## A2-D03 — NON_BLOCKING / OPEN

**Private registry credential ownership needs an explicit contract.**

Location: preflight.yml:34, role defaults and fixture authentication documentation.
Default DOCKER_CONFIG uses HOME/.docker; an explicit directory has no privacy or
ownership check. README assigns creation/cleanup to an external credential owner,
while the plan describes a temporary private runtime config and always cleanup.
No confirmed credential leak/write: this runtime does not login or save passwords.

Smallest correction: public registry must not require ambient credentials. Private
registry accepts an explicit runtime-owned private directory with bounded path,
permissions and external owner cleanup, or executor materializes a temporary
config through the existing runtime-secret mechanism. No new credential store.
Check valid/invalid ownership/modes, no persistent login and credential lifetime.
Private registry QA is not proved.

## A2-D04 — NON_BLOCKING / OPEN

**Schema platform.variant is not implemented by target discovery.**

Location: image-lock.schema.json, preflight.yml:61 and artifact_source.py platform
comparison. Target has only os/architecture; whole dictionaries are compared.
Every allowed record with variant fails IMAGE_PLATFORM_INCOMPATIBLE, including a
matching target. This is fail-closed incompatibility, not wrong-image execution.

Smallest correction: remove the unsupported optional field with an explicit
limitation, or implement evidence-backed resolution/checking without a generic
platform discovery framework. Supported variant passes, incompatible blocks,
unknown is never silently ignored.

## Overengineering and evidence

Confirmed blocking overengineering findings: **0**. Shared authority serves real
RPM/image callers. Typed digests retain distinct archive/manifest/config semantics.
Native Compose parsing plus bounded checks introduces no extra dependency.
Digest labels reuse reconciliation without an activation journal. Ownership
markers/atomic guards serve current protection needs, with no second desired-state
store or scheduler. For D02, digest-bound identity is simpler than a daemon-wide
registry/transaction subsystem. Private-account copy/stat has a concrete consumer
permissions difference; no new generic abstraction is mandatory.

Reviewer inspected every frozen source/fixture file, instructions/procedure,
schemas/actions/filters/tasks/playbooks/shared caller and tests. PLAN A2-P01 is
implemented: automatic label, ordinary up independent of changed, Verify compares
labels/files; Nginx fixture tests startup config consumption and isolation.

28 focused PASS and 2 old-probe QA PASS refer to earlier sources. At review time,
public multi-host/registry QA and broad Core regression were RUNNING, not PASS.
Much of the negative real acceptance matrix still lacked evidence. Final-source
10 focused runtime cases and catalog/config-schema checks were reported separately.
Reviewer did not run tests, contact targets, read runtime credentials or change
files. Review does not replace QA.

**Validity: CURRENT for the frozen fingerprint.** Corrections require a new
fingerprint and owner-authorized TARGETED_RECHECK limited to findings and directly
affected boundaries. Already authorized running QA may supply evidence, but
cannot remove these code defects. A2 is not accepted or complete.

Implementer recommendation: fix D01 with selected-source byte verification; fix
D02 with an automatically digest-bound startup reference. Address D03 contract
clarity and D04 unsupported field in the same bounded correction if authorized.

## Owner-approved TARGETED_RECHECK — 2026-10-10

**Verdict: APPROVE_WITH_CHANGES. Unresolved blockers: 0.**

Owner accepted both blockers in response to the correction/recheck request.
This is the single targeted recheck of D01/D02; the DIFF review budget is consumed.
43 corrected source/fixture/test files, independently verified before/after:
`ac801bf4036afe2d7d5ed645b018ec2c785f1c9acfbe3f1f7f4255dba6cce095`.
Worktree, branch and HEAD unchanged. No second FULL gate.

**D01: OPEN → RESOLVED.** Preparation validates descriptor/bounded ref without
root/bytes. selected_archive returns None for REPOSITORY before filesystem lookup;
OFFLINE_BUNDLE requires root and exact manifest/archive digest/size. The thin filter
uses controller DataLoader after target source selection. All selected placements
pass the any_errors_fatal preflight before the next Apply/materialization play.
The selected path is bound into private delivery context. Registry-first restored;
unselected fallback is optional, bad selected fallback blocks before mutations.

**D02: OPEN → RESOLVED.** Startup reference is automatically
platform-application:sha256-<full config/image digest>. Distinct IDs have distinct
names; optional operator localReference must match. Compose/delivery share it.
An existing reserved name with a different ID blocks before writes. Authorized
independent library runs cannot assign different images to one runtime reference.
No daemon-wide registry, new lock or store introduced.

D03/D04 remain NON_BLOCKING/OPEN and were not reopened. No blocking correction
regression found. Overengineering in corrected boundary: **0**. Small helper/filter
and native tagging are simpler than a daemon identity registry/scheduler/store.

Reviewer inspected corrected preparation/filter/preflight/schema, consumers,
sequencing, unit/QA cases and documentation. Supplied evidence: corrected focused
31 PASS (A1 15/RPM 4/A2 12), 2.781s; QA py_compile PASS. Reviewer ran no tests,
contacted no targets, read no runtime credentials, changed no files.

Final-source real fallback/registry/parallel QA still pending at recheck; older
public multi-host QA/broad regression do not prove corrected-revision acceptance.
**Review validity CURRENT** for corrected fingerprint. Journal updates do not
change it. Source selection/reference/preflight-order changes invalidate affected
conclusions. Continue already authorized final QA and report D03/D04/acceptance
limits; no automatic new FULL/recheck and no A2 DONE without the final gates.
