# PostgreSQL CREATE — implementation evidence

Owner authorized CREATE in the existing Go/UI grants on2026-10-17, and the data-manager endpoint through the existing application endpoint flow.

FULL PLAN: independent reviewer APPROVE_WITH_CHANGES,0 blockers; plan identity34569d50dedbb07b4913471133ecaff21771530016428ef54b1c91a959ce5391. PGC-P01 schema/table separation and CREATE-only/revoke/creator tests included. PGC-P02 canonical contract/UX and old-schema refusal included. No repeated PLAN review.

Implementation extends the existing databaseAccess list, Core validation and PostgreSQL SQL reconciler. CREATE applies only inside non-system schemas of the selected library-managed DB, with the existing creator default-privilege pipeline. No database CREATE, ownership transfer, new persistence, API or resolver. Generic Go writer already carries privileges; its real save/reset path is retained and tested.

The real SDKU snapshot exposed an existing Go decoder bug: the published ENV schema accepts string/number/bool, while ApplicationPlacement.Environment accepted strings only. The field now preserves native scalar types; focused Go decoding and actual SDKU snapshot decode PASS. This is a contract conformance fix, not Go-side precedence or value conversion.

Validation so far: frontend249 PASS, typecheck/lint PASS; full Go test/vet PASS; affected Core providers17 PASS; new/old schema compatibility1 PASS; initial isolated native PostgreSQL CREATE test PASS (51.586s, existing/future/create-only/revoke/SELECT retention/no schema creation/owner preservation/repeat). Extended isolated native PostgreSQL suite with removed creator coverage:12 PASS in521.213s; fixture cluster cleanup completed. These tests do not cover PGC-D01, so this PASS does not close its review blocker. Real React/Wails Save/reopen/CREATE deselection/restore is in progress. No visual inspection claimed yet.

New bundle02 built on trusted .102 and validated locally; digestfaf314cb94eb31a2b2d1d06e44e9692176a46b0d49ed42e568faee4b0be6ca88. Not activated for application installation pending review/remaining checks. First bundle01 preparation on .103 reached READY; first actual Verify failed because of the scalar ENV decoding issue. No application Start occurred.

FULL DIFF BLOCK: PGC-D01 PUBLIC default CREATE guard regression; automatic continuation stopped, owner asked to approve minimal correction and one TARGETED_RECHECK. [Review](../reviews/postgresql-create-grant-diff-review.md). Actual Wails exercise reached CREATE checkbox but harness matched three draft buttons and left an uncommitted draft; subsequent reopen correctly failed EDIT_SESSION_ACTIVE. Save/reopen/reset remains NOT PASSED; no app installation triggered. No production bypass or guard change made for harness recovery.

Owner clarification2026-10-17: CREATE is for the selected application account in all user schemas including public; preserve the PUBLIC-role guard. PGC-D01 correction authorized in that bounded scope and one TARGETED_RECHECK. SQL PUBLIC default-schema allowlist restored to USAGE independently of selected-account CREATE. Added native test: actual table creation in public by selected account, denial for neighboring account, preflight/Apply/Verify refusal of default CREATE TO PUBLIC with identical ACLs before/after. Actual React/Wails CREATE Save/reopen, deselect preserving DML and restore PASS; grant table1440/1024 visually inspected. Initial failed harness attempts remain historical.

Final corrected-tree native PostgreSQL focused2 PASS/90.886s including PUBLIC regression; independent TARGETED_RECHECK APPROVE, PGC-D01 RESOLVED, zero blockers. Actual React/Wails endpoint Save/reopen PASS. Corrected bundle03 verified/published: sha256:a0c91f6c5f93a3f0244041594ecfb01f193842f33a4206bea0eaef830cd4acfa. Runtime02 remains historical staging only.

Real target read-only PostgreSQL permission check .102/sdku_dm after actual Wails provider Apply: has_schema_privilege(sdku_dm,public,CREATE)=true; PUBLIC-role CREATE on public=false; has_database_privilege(sdku_dm,sdku_dm,CREATE)=false. No SQL mutation used for this check. Safe evidence .runtime/qa/sdku-postgres-public-check.json.
