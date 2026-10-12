# A6 — independent FULL DIFF review

Date: 2026-10-11. Reviewer: `/root/a6_implementation_review`, independent read-only
`architecture-reviewer`. Verdict formed independently: **BLOCK**. Mode: DIFF / FULL.
This is the first implementation FULL review.

## Identity and scope

Base HEAD: `540aa05c49ae531b3041da16cbad4771f5ccdd6e`, branch
`codex/application-libraries`, uncommitted worktree. Manifest
`.runtime/a6-review-manifest.txt`: 59 sorted path=SHA256/DELETED entries, SHA256
`8476f4c7a0a4a52769661e3b1b52f85be97fe17ce84f3ac071117e199d16f82d`.
Reviewer verified every entry. Plan SHA256:
`bd3784083a322de690c7993f1f00c636b7d5f4a3456f108a55133c755ff86cda`.

Scope: standalone application endpoint projection/settings, existing HAProxy/DNS
Apply/Verify/reconcile, probe relocation to docker. Prior A2 docs, mixed
implementation-plan, CURRENT_STATE, Go/UI, A7 and master excluded.

## Blocking findings

### A6-D01 — BLOCKING / OPEN: child loses parent execution context

Evidence: `ansible-core/playbooks/application-libraries-endpoint-stage.yml:28–44`.
Child receives inventory and selected vars, but loses parent CLI `-e`,
`--private-key`, `--user`, `--become-user`, `--limit`. Providers may use another
desired override, lose SSH prerequisites or contact excluded hosts.

Smallest correction: retain original Ansible context through existing execution
mechanism; if child remains, preserve necessary options/variables under protected
custody. Do not export all hostvars or build another precedence resolver.
Verification: native CLI desired override, SSH identity and host limit remain
effective; excluded hosts are not contacted.

### A6-D02 — BLOCKING / OPEN: HTTP response uses an unverified TLS connection

Evidence: `services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks/check_targets.yml:1–62`.
OpenSSL verifies one connection with SNI/FQDN; URI then connects by IP with
`validate_certs: false`. HTTP Host does not set SNI. HTTP status cannot be bound
to verified CA/hostname identity, contrary to plan §6.

Smallest correction: request HTTP on the same CA/SAN-verified connection with
correct SNI and specific target IP, using a standard existing tool.
Verification: SNI routing PASS; wrong CA/hostname and untrusted responder fail.

### A6-D03 — BLOCKING / OPEN: external DNS is always rejected

Evidence: `services/integrations/playbooks/apply-endpoint.yml:158–164`, plan §5.
Every app has probe policy; final assert always requires BIND. Correct external
DNS is rejected before DNS/HTTPS verification.

Smallest correction: absent BIND skips DNS mutation; ordinary DNS/HTTPS probe
establishes publication. Keep HAProxy provider mandatory.
Verification: external DNS without project BIND PASS; NXDOMAIN/wrong route fail;
foreign zone unchanged.

### A6-D04 — BLOCKING / OPEN: production endpoint acceptance missing

Evidence: `a6-test-journal.md`, plan §10. Projection/task subsets and recovery image
do not prove full endpoint-stage, actual two-host Apply/Verify/repeat or negatives.

Smallest correction: actual standalone entrypoint QA with two placements, external
/status, repeat changed=0, read-only Verify, readiness/reachability failure,
neighbor preservation, full reconcile and required TLS cases. Manual provider
configuration or subset tasks do not substitute for this proof.

## Nonblocking findings

**A6-D05 — NON_BLOCKING / OPEN.** Direct BIND role full reconcile defaults sources
to empty without outer Apply preparation. Evidence:
`services/bind/ansible_collections/platform/bind/roles/bind/tasks/main.yml:64–74`.
Use existing source preparation or assert prerequisite; test native direct role
with application records before deletion can rely on an empty model.

**A6-D06 — NON_BLOCKING / OPEN.** URI result remains available to callbacks;
return_content=false alone does not exclude all error-body content. Evidence:
`services/integrations/tasks/probe-endpoint.yml:23–49`. Protect result with no_log,
retain safe status assertions and test sensitive sentinel in unexpected body.

## Mandatory overengineering assessment

Blocking complexity findings: **0**. Projection/action/role have a present purpose;
Ansible owns precedence, no second desired-state store. Shared settings/provider
pipeline reused without service/application branching. Apply/Verify checks share
tasks. Child solves sequential multi-play invocation; its correctness is D01.
No new daemon, registry, durable retry ledger, speculative Go/UI scope or duplicate
provider API. Probe moved without main.go changes; standard Docker build remains.

## Evidence, validity, next action

Direct inspection: manifest, instructions/contracts, plan, changed resolver/module
adapters, stage/provider tasks/templates, schemas, tests and probe relocation.
P01 exact ownership/P02 domain ordering represented in code/focused tests.
Reviewer ran no tests or target contacts. Parent supplied application78 and syntax3
PASS; BIND21 PASS; integration6/7 with one positional fixture failure. Actual
endpoint acceptance absent. Tests are reported evidence, not independent runtime proof.

Validity: **CURRENT** for manifest. Architecture changes require applicability
assessment; routine QA/documentation updates do not automatically invalidate review.
Unresolved blockers: **4**. Implementation stopped; owner decision pending.
Report D01–D04 and minimum corrections to owner. At most one owner-approved
TARGETED_RECHECK may follow; no automatic additional FULL review.
