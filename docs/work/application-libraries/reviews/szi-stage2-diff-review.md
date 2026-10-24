# SZI-STAGE2 — independent FULL DIFF review

Verdict: **BLOCK**. Reviewer: `/root/szi_stage2_plan_review`, independent read-only review using ansible-core-review. This file records its delivered final report; no second review was performed.

## Identity and scope

Worktree: `C:/Users/AnufrievEV/.codex/worktrees/szi-stage2-implementation/platform-installer-v2`, branch `codex/szi-stage2`.
Base/HEAD: `327c0b76af5ff315c2a104abb1248de042debe5c`.
Source fingerprint: `975c1eb7138728b4b62906f202b8d031291ad6455bacf081389ec568a73acbf3`.
Amended plan SHA256: `738ab4459385fcd740c17f02390b96a9e08a5063feb9b2f86ee8f522ba3a1c25`.
Reviewer independently reproduced the fingerprint twice over95 intended source paths. Source identity excludes frontend/dist, vendor, portable-source, .runtime and _vendor. This report and subsequent status documentation are outside that original frozen identity.

Scope: contracts, Core resolve/plan/runtime, provider batching, script callbacks/runner, Vault delivery/retention, SZI/SDKU packages, Go writer/projections, affected UI. Historical PLAN approval is not proof of implementation correctness.

## SZI2-D01 — BLOCKING — OPEN: PKI packaging/delivery

Evidence: grant-access and grant-access-audit compose.yml.j2:24; nginx compose.yml.j2:31. prepare_application_runtime.py:35 attaches library PKI plans to Agent apps. application_runtime.py:155–163 requires `<instance>/pki -> /opt/application/pki:ro` with such plans. GA/audit supply separate CA binds but omit that directory bind, causing APPLICATION_COMPOSE_MOUNT_INVALID before start.

nginx expects pki/leaf.crt, leaf.key and CA but has no Agent template. apply_instance.yml:67–76 invokes application_identity_files only for Agent apps. That module materializes keystore.p12, truststore.p12 and ca-chain.pem, not leaf.crt/key. A clean installation cannot obtain its expected PEM files through these mounts.

Impact: full-library preparation/start cannot pass. Some nginx mounts predate this diff, but working full-library packaging is in Stage2 scope.

Smallest correction: align GA/audit with existing directory bind contract; establish real PEM/CA delivery for non-Agent nginx with correct UID. Do not bypass validation or add a fictitious Agent/secret binding solely to trigger PKI. If a general PKI delivery correction is necessary, present that minimum to the owner.

Acceptance: native render/Compose validation of all five apps with resolved PKI; clean nginx materialization/start without pre-existing leaf files; ownership, TLS and repeat Apply.

## SZI2-D02 — BLOCKING — OPEN: consumer/provider argument context

Evidence: application_scripts.py:182 passes `_argument(value, job, provider, hosts, desired)` for connection callbacks. Its connection branch at62–64 indexes `library['instances'][job['instanceId']]['connections']`. Here job is the consumer but library is the provider. An external consumer ID causes KeyError. Current cross-library test covers provided_connection but misses connection arguments.

Smallest correction: explicitly separate consumer library context for connection from provider export context for provided_connection, matching existing secret-source separation. Keep script source/execution target provider-owned; no new resolver/DTO.

Acceptance: callback with consumer infrastructure connection, consumer application connection and provider provided_connection; different library/instance IDs.

## SZI2-D03 — BLOCKING — OPEN: retargeted each_target

Evidence: application_scripts.py:123–143 derives frequency/eligible hosts from consumer placements, then target.connection picks only sorted(provider targets)[0]. application_integrations.py:47–50 dedup omits execution host. A one-host consumer/two-host provider with each_target silently invokes only the first provider. targetHostId is resolved before retargeting and may name the wrong host. The schema permits this combination.

Smallest correction: derive eligible execution set from provider targets, apply once/each_target there, retain actual execution host in invocation identity and resolve targetHostId accordingly. No product-specific executor. Restricting the contract instead would require explicit owner decision and target-free rejection.

Acceptance: one consumer/two provider hosts and two consumer/one provider host; once/each_target; library/instance scope. Assert exact hosts, no duplicates and correct targetHostId.

## Boundaries and overengineering

No additional blockers established in infrastructure batch ordering, package-owned product API, invocation-local completion, allowlisted provider callback source, private credential files/no secret outputs, deferred shared Vault fields/CAS, no-revoke policy retention, unchanged Verify, structural Go writer, or UI/Core ownership.

The candidate sensitive-literal override issue was WITHDRAWN: project_snapshot.py:604–617 validates effective provided connections and clears public libraries on findings.

Blocking overengineering findings:0. Existing connections, callbacks, batch projections, private batch JSON, bounded policy retention and CAS deltas have current requirements. D02/D03 need corrections within existing projections, not new lifecycle layers.

## QA limitations and next action

Reviewer inspected sources/contracts/tests but ran no tests or target operations. Parent reported focused Core51/native Ansible1, Go/vet and frontend299 PASS; isolated API groups/client/group-role create/repeat/retention/readback passed. At review time account/user-role/rotation/guard checks and full Core regression were incomplete. Native coordinator/Vault delivery/retention and real React/Wails full-library installation acceptance remain open; processes merely running do not prove acceptance.

CURRENT for the recorded source fingerprint. Open blockers: **SZI2-D01, SZI2-D02, SZI2-D03**.

Per review procedure, BLOCK stops automatic fixes and deployment pending owner decision. After owner-approved corrections, one TARGETED_RECHECK may inspect these IDs and directly affected boundaries. No automatic additional FULL review is assigned.
