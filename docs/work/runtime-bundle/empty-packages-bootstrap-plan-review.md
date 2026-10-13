# EMPTY-PACKAGES-BOOTSTRAP-01 — independent FULL PLAN review

2026-10-13. Reviewer: independent `architecture-reviewer` subagent
`/root/bootstrap_plan_review`. No implementation, target mutation or new QA.

## Verdict and identity

APPROVE_WITH_CHANGES; zero unresolved BLOCKING findings.
Base commit: `0de2a38222f7ef2222d8808cfc4e0c69587fa1a7` (`portable`).
Reviewed original plan SHA-256:
`d2fff0270d62cb12666577ba5bf25e79bca7980b8ded0f8c5b63254472f1321f`.
ADR-021 blob: `146e02dca09eb5dcfe1ddd082d3bff39f275edf5`.
Manifest contract blob: `5db93d24006fc345a836c0f09795d15ff5d348bb`.

Scope: empty runtime payload, explicit/observed platform identity and os-release,
pre-Python bootstrap, local RPM/DNF fallback, transfer without tar, privileged
execution of root-owned verified content, activation/failure guarantees,
existing UI Prepare and required QA.

## EPB-P01 — NON_BLOCKING / OPEN

Existing `internal/executionnode/openssh.go:422` removes the digest-named release
before copying. A test limited to a different new digest could miss destruction
of the currently used release during retry or overlapping Prepare attempts.

Reviewer correction: clarify the already stated invariant that an active release
is never removed/replaced before successful verification; explicitly test the
same digest and intersecting Prepare operations. Use existing coordination,
without a new transaction manager.

The parent added the clarification to preparation §9 and the verification matrix.
This is a nonmaterial clarification; no additional FULL PLAN review was run or
claimed. Implementation/verification of the finding remains pending.

## Mandatory overengineering assessment

Unnecessary mechanisms found: 0. A fixed verified shell resource is justified
before Python exists; standard sh/RPM/DNF is preferable to a daemon or Python
bootstrap. Existing manifest/platform/plan/result contracts are reused. No
service-source resolver, speculative extension points or new persistence layer
is proposed. Explicit platform arguments serve acquisition-host builds for
other targets; existing SCP directory transfer handles a missing tar command.

## Evidence and validity

Reviewer directly inspected current root/scoped instructions, CURRENT_STATE,
task index, review/runtime-bundle/QA procedures, the plan, ADR-021, architecture
contracts, UI Servers/Installation design and mockup, builder, manifest
validator, preparation service and SSH transfer/activation.

Tests were not run; no target access or secret material inspection occurred.
Plan review is CURRENT for the reviewed architecture. Source authority,
privilege/trust ordering, activation guarantees, ownership or material scope
changes invalidate the corresponding part. A HIGH-RISK implementation needs
the planned independent FULL DIFF review. Fresh-node and real React/Wails QA
remain separate acceptance gates.

Next action from reviewer: owner acceptance of the concrete plan and ADR-021
exception, followed by implementation. Review does not authorize that transition
or prove QA acceptance.
