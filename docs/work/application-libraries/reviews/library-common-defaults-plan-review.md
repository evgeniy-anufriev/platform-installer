# Library common defaults — independent FULL PLAN review

2026-10-16. Reviewer: independent architecture-reviewer subagent.
Verdict: **APPROVE_WITH_CHANGES**, zero blocking findings.

Historical scope: the owner subsequently requested no SDKU slot overrides and
clarified separation of common library defaults, application-owned defaults and
instance group_vars overrides. The plan/package draft was updated, including
library-before-application default order. This report applies to the SHA below;
it does not independently review the amended plan or prove the new package format.

Reviewed plan: `../library-common-defaults-plan.md`.
Reviewed SHA-256: `868cc04011fa7432f073aace634e73d37456098acd0dc1ed9d1265485e8441fd`.
Verified base: `8feb047af1c24c70ede737fe03941b9bbf04ac3c`.
The implementer subsequently added the two bounded nonblocking clarifications
below. No new FULL review was requested or performed.

Scope: library package defaults, library deployment overrides, slot opt-out,
native Ansible composition, common runtime base and existing Go/UI lifecycle.
Excluded: installation, target runs and runtime-bundle publication.

## Findings

**LCD-P01 — NON_BLOCKING, clarified in plan.** UI must distinguish the shared
library/host baseline from an application's inherited baseline including slot
overrides but excluding its own instance override. The current UI feeds application
package defaults directly to ENV/parameter controls. Reset must not return stale
instance values or omit a higher-priority slot difference. The plan now specifies
a read-only Core baseline or a fresh resolve, stale-result presentation, and a
multi-layer Reset case. No React/Go precedence implementation is introduced.

**LCD-P02 — NON_BLOCKING, clarified in plan.** Resolve and runtime preflight keep
application facts. Common resolution must use an isolated context without those
facts; text matching cannot detect indirect inventory-variable dependencies.
The plan now requires isolated native templating and negative indirect-reference,
reverse-order and frontend-first cases. No new expression parser is introduced.

The reviewer classified both as bounded implementation clarifications and did not
require another PLAN review for them.

## Overengineering and evidence

Zero unjustified mechanisms identified. Existing schemas and transport are extended;
defaults plus one opt-out boolean meet the concrete SDKU/backend/frontend case.
An include/base-only solution cannot provide inherited Core/UI values and Reset.
Built-in Ansible combine, existing writer and draft/Review/Save are retained.
No profiles, duplicate state store, generic hook engine, new daemon or CRUD API.

Reviewer read root/scoped instructions, CURRENT_STATE, review procedure and role,
the full plan, schemas, native resolver, affected runtime preflight, writer
addressing, ENV/parameter UI, relevant UI design/mockup and C plan. Plan/base hashes
were verified read-only. Targets and secret material were not accessed; tests were
not run during review. Prior SDKU structural checks do not prove the new contract.

Review approval is advisory. Owner approval of the contract/UI extension is the
next gate; the request to prepare packages does not authorize installation.
