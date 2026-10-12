# PKI single-pass execution: retained per-process resolution

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#pki-single-pass-checkpoint-002).



## Evidence and problem

The observed SI08-F run `installer-56e9a38b153a6c380da413656d10bdb3`
spent 6m49s on global `pki:apply`, including approximately 4m32s on target
deployment. Vault action then spent approximately another 6m36s in PKI
(6m45s including its preceding validation). HAProxy also imports that playbook.
These timings describe one QA run, not a performance guarantee.

Prior review `PKI-SP-01` blocked skipping the entire import: each service
Ansible process needs `platform_pki_requests` produced by resolution.
The private runtime projection supplies plans, not those request facts.
That implementation was reverted and was never published or activated.

Relevant existing boundaries:
- `pki_materialize/tasks/main.yml` already includes `resolve.yml` first;
- `resolve.yml` resolves ordinary Ansible desired variables on localhost;
- `select_consumer_plan.yml` selects requests by deployment/host/TLS consumer
  and selects the matching materialization plan;
- the controller derives global and service projections from one manifest,
  using the same run-owned project inventory and PKI materialization plans;
- global `PKI_APPLY` is unfiltered and covers all project PKI consumers.

## Proposed execution

Keep the existing `pki-apply.yml` imports in all five service apply playbooks.
Within the existing role/playbook, mark only the mutating portion with one
reserved internal Ansible tag, `platform_installer_pki_materialization`:

1. `pki_materialize/tasks/resolve.yml` always executes, including publication
   of request facts in the current localhost Ansible process.
2. Runtime shape assertions remain enabled.
3. Preparing protected execution roots and including `request.yml` belong to
   the tagged mutation block. Its dynamically included tasks inherit the tag;
   the include itself is tagged as well.
4. The target `pki_deploy` role retains plan selection. Its ordinary deploy
   include carries the tag. In optimized mode it runs the integrity guard below;
   repair calls the existing deploy task file through an untagged include.
5. Service consumer selection, service-owned TLS copies, validation,
   reload/restart decisions and verify are outside that tag.

Use existing task files and standard Ansible tag/block/include semantics.
Do not add another resolver, public protocol, DTO, fact cache, persistence,
generated certificate database or Go PKI branch.

The fixed Execution Node controller tracks successful `PKI_APPLY` only in
the current dispatch invocation. After its process returns zero and the
successful action journal event is appended, subsequent `SERVICE_APPLY`
commands receive `--skip-tags platform_installer_pki_materialization`.
The controller never accepts this state from project variables or from a
previous run. A failed/cancelled PKI action cannot authorize the skip.
Service actions preceding PKI, service-only runs and new runs use the full
existing path. SERVICE_VERIFY commands are unchanged.

This relies on the existing immutable run project and manifest checks:
project identity, plan fingerprint, manifest digest and runtime identity are
verified before dispatch; all operation projections carry the same PKI plans
and inventory. There is no broad boolean supplied by UI or portable project.
If future execution introduces per-operation inventories, partial PKI actions,
mutable project input or resume after a different manifest, this optimization
must stay disabled until coverage can be proven for that execution model.

Resolution must produce requests compatible with the manifest-bound plans.
Before optimized service mutation, compare the freshly resolved plans to the
existing frozen plans using their complete current Core plan fields and stable
ID order. A mismatch fails closed; do not override the frozen projection with
newly computed state. Read the resolver module result directly for this check,
because Ansible extra-vars can shadow `set_fact` output. This check belongs to
the Ansible/Core boundary, not Go, and does not redefine PKI identity/SAN.

## Service activation and standalone behavior

Do not fabricate or forward `platform_pki_material_changed=true` for every
service: that would cause repeat restarts. Preserve existing per-consumer
activation rules and prove them across separate Ansible processes:

| Service | Existing signal to preserve |
| --- | --- |
| Kafka | `platform_kafka_member_pki_changed` from copying all PEM/PKCS12/fingerprint files into the Kafka consumer directory; existing aggregate flag remains available for standalone apply |
| Redis/Sentinel | `_platform_redis_tls_copy.changed` controls affected unit restart |
| Vault | copied TLS result records exact changed member IDs |
| PostgreSQL | service-owned PEM copy notifies TLS reload handler |
| HAProxy | rendered PEM bundle change controls TLS activation/restart |

The optimization must not suppress a reload/restart when service-consumed
material changes, or introduce a restart when that material is unchanged.
Missing/corrupt/unreadable target material must fail before activation or be
repaired through the existing full PKI path; it must not be accepted as healthy
merely because the earlier action succeeded. External mutation between actions
is not made atomic by this design; existing service TLS checks remain active.

Owner-approved correction for PKI-SP-PLAN-01: use existing Ansible stat with
follow=false and SHA-256 to inspect the five source files on the controller
and the five target files plus fingerprint marker. Source files must be readable
regular files. Target files must be regular, non-symlinked, have exact source
checksums and expected owner/group/modes; the marker must match the exact plan
fingerprint content. All checksum/results tasks use no_log. A target mismatch
or missing file runs existing plan.yml for that plan, preserving its change
signal. Missing/unreadable source material blocks before service activation.
The validated target directory must be a non-symlinked directory with expected
ownership/mode. No persistent integrity cache is introduced. The controller
clears inherited Ansible run/skip-tag environment overrides.

Plain `ansible-playbook services/<service>/playbooks/apply.yml` retains full
resolve/materialize/deploy behavior. The standalone role and manual-inventory
path require no Installer state. PKI issuance, rotation authorization and
`CERTIFICATE_REISSUE_REQUIRED` rules are unchanged.

## Acceptance and gates

Controller tests must prove success ordering, no skip without PKI, failure,
cancellation, service-before-PKI behavior and no reuse across runs. Verify
the tagged boundary with real Ansible execution, not just command mocks or
`--list-tasks` output.

Required isolated RED OS Ansible proof:
1. Global PKI followed by a NEW service Ansible process: requests exist,
   frozen-plan equality holds and exact consumer selection succeeds.
2. Optimized service process performs no authority/request issuance or target
   PKI deployment tasks, while resolution and service-owned TLS copies run.
3. Same inputs without controller skip run the complete standalone PKI path.
4. Frozen-plan mismatch, missing request and missing/corrupt TLS file fail safe.
5. For all five TLS consumers, changed consumed files trigger their existing
   reload/restart path; unchanged repeat does not. Include Kafka PEM/PKCS12,
   distinct members and the case where the aggregate PKI fact is absent.
6. No TLS consumers yields empty resolution without PKI filesystem mutation.

Run focused Core/PKI/controller and affected service suites, full Core suite,
catalog/schema reproducibility, service syntax checks and scoped diff/secret
checks. Existing Go test/vet gates apply to final SI08-F acceptance; no Go or
frontend changes are proposed here.

Only after implementation gates and applicable review pass, publish a new
immutable runtime through the existing supported QA promotion path, advance
the QA project's artifact lock by guarded CAS and run the fresh real
React/Wails full plan. Record action/task timing, terminal results and repeat
idempotence. Existing releases and prior run journals are not modified.

## Review process

One FULL PLAN review of this owner-selected alternative. The previous
whole-import-skip DIFF review is recorded as blocked, not relabelled PASS.
Any blocking findings are returned to the owner with the smallest correction;
no automatic review loop. Implementation requires the concrete plan disposition.

## Implementation evidence — 2026-09-29

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#pki-single-pass-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
