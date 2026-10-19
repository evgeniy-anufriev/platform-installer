# Direct resource keys — FULL DIFF

2026-10-19. Independent read-only reviewer: `/root/topic_roles_plan_review`.
Verdict: **APPROVE**, zero unresolved BLOCKING findings. No additional review.

Base: `a5ce142cfb9f29dbab524d45b0ec6f3cb6ef73fb` with before-images of earlier
uncommitted ENV/ports/topic work; that earlier work was not attributed to this delta.
Original40-file set: `7c03df83041bc4476b7dc3faa6f675c4c0ec5ce6ca6ab438204bd43496294f88`.
Final31-file set excluding docs/CURRENT_STATE, including README:
`881ce20a2eed2d9be0b0e7ba00fbe49daad6aa1cc219d1275b521a5a0d9c18cf`.
Final30-file set excluding README:
`d88bdcee57bc469be261579b0f8ab5675431227662cd915d9603353717fd511a`.
Method: SHA256 of UTF-8 compact JSON `[path,sha256]` pairs, path.localeCompare order.
All individual hashes and final identities independently checked.

DIRECT-P01 RESOLVED: legacy maps override colliding direct keys, native collision/
reset regression covers restoration, and migration removes obsolete SDKU bindings.
No new findings. Context reset/early expansion, selected-provider separation,
shared normalized provider inputs and explicit selection were checked. PostgreSQL
JDBC/account references agree; ef-store isolation and ClickHouse parameter remain.
Database-only hyphen support preserves SQL quoting and existing ownership guards.
UI persists authored overrides and uses fresh Core names without a second resolver.

Overengineering: zero unnecessary mechanisms. Existing resources/defaults and
standard Ansible tasks are reused; no new DTO, API/store, lock, Python script or
lifecycle layer. Legacy handling has a concrete compatibility purpose.

Reviewer inspected logs, not by rerunning tests: Core81 (80 PASS/one skip),
native440 tasks/failed0/one synthetic change,27 package schemas/digests/26 renders,
Go/vet, frontend260/build/lint. Runtime42 digest2dbefe8b has907 components; four
affected runtime files match frozen source. Real React/Wails inheritance/override/
Reset/Save/reopen/Verify and plan-only evidence checked independently.

Final revision `sha256:73736eea45b9197015911666af14e8414de81b7caf26b3dae751d31990ebcc99`.
Plan `plan-92ab0cae0c53795159d68260`: EXECUTABLE, only Library Apply/Verify,
skipInfrastructureVerify=true, approved=false; no Approve/Start. Initial staging
failures/space cleanup remain documented. Previous execution-context loss is not
claimed fixed; no rebind was needed in the successful CRUD flow. Visual inspection
and actual SQL/Kafka creation were not performed. Review authorizes no installation.

Review validity: CURRENT for the fingerprints above. Evidence-only journal updates
do not invalidate the review. See [journal](../evidence/direct-resource-keys-journal.md).
