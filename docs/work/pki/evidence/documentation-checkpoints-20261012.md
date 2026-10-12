# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## pki-store-password-recovery-01.md

Source document: [pki-store-password-recovery-01.md](../pki-store-password-recovery-01.md).

<a id="pki-store-password-recovery-01-checkpoint-001"></a>

Status: owner-approved; implementation IN PROGRESS; real React/Wails/Core acceptance pending.


## pki-single-pass.md

Source document: [pki-single-pass.md](../pki-single-pass.md).

<a id="pki-single-pass-checkpoint-001"></a>

## Implementation evidence — 2026-09-29

Targeted review `PKI-SP-PLAN-01`: APPROVE, resolved, zero blocking findings;
see [review record](../reviews/pki-single-pass-review.md). RED OS four isolated
controller/integrity tests PASS in 194.912s. The broader SI08-F working tree
also passes eight separate-process resolution/consumer tests in 73.150s;
that integration test depends on the pending SI08-F consumer-selection/Redis
files and is retained with that change set, not the isolated optimization commit.
Those tests observe production activation expressions, not live daemon reloads.

Full current-working-tree Core: 414 tests, OK, 19 skips, 447.935s.
Affected service suites: Kafka 28, Redis 10, Vault 28, PostgreSQL 23 and
HAProxy 17 PASS. Go full suite/vet, catalog/configuration-schema
reproducibility, all five service apply syntax checks and scoped whitespace
check PASS. Guard results remain no_log; no secret values are added to events
or documents. Broader pre-existing generated Wails whitespace is outside this
scoped commit. No runtime publication or installation PASS is implied here.


<a id="pki-single-pass-checkpoint-002"></a>

Status: IMPLEMENTED; focused QA and targeted review PASS; real SI08-F acceptance
and measured timing remain pending. Owner accepted the integrity correction on
2026-09-29: retain lightweight PKI resolution in service playbooks and avoid
repeated materialization/deployment after successful PKI in the same run.
This is a bounded prerequisite to the next SI08-F acceptance attempt.


## pki-platform-shared-tls-usages-plan.md

Source document: [pki-platform-shared-tls-usages-plan.md](../pki-platform-shared-tls-usages-plan.md).

<a id="pki-platform-shared-tls-usages-plan-checkpoint-001"></a>

Status: owner-approved implementation direction; PKI-PLAN-01 passed the
targeted recheck. The owner accepted the exact lock correction for the
remaining PKI-PLAN-02 after the review budget was exhausted.
