# PostgreSQL CREATE — FULL DIFF review

2026-10-17. Independent reviewer `/root/library_common_plan_review`; read-only FULL DIFF.

Verdict **BLOCK**, unresolved blockers **1**, validity CURRENT for the identity below. No automatic repeated FULL review.

Base HEAD8feb047af1c24c70ede737fe03941b9bbf04ac3c. Incremental manifest `.runtime/grant-create-review-scope.json`, SHA-2564e5fae6e2cd1d7688261e8dcdd445a20ee437a0cf361a188daa01630e97f8601. All16 before/after hashes checked by reviewer,0 mismatches; baseline retains the preceding dirty SDKU/defaults work.

## PGC-D01 — BLOCKING, OPEN

`services/postgresql/ansible_collections/platform/postgresql/roles/application_provider/templates/database_access.sql.j2:53` changes the PUBLIC default-schema allowlist from `ARRAY['USAGE']` to the selected account's `schema_rights`. Selecting application CREATE therefore accepts preexisting default CREATE ON SCHEMAS TO PUBLIC. Future schemas would grant CREATE to everyone, violating the existing PUBLIC/external-grant guard and the approved plan.

Smallest correction: keep PUBLIC default-schema allowlist independently at `ARRAY['USAGE']`; use schema_rights for the selected account. Reject the external conflict; do not automatically revoke PUBLIC grants.

Required negative QA: install default CREATE ON SCHEMAS TO PUBLIC for an approved creator in an isolated fixture, select application CREATE, verify preflight/Apply/Verify refuse before a future schema exists and ACLs are unchanged; remove conflict in the fixture and retain ordinary CREATE-only/future/revoke tests.

Owner decision required before correction and one TARGETED_RECHECK of PGC-D01 and the directly affected PUBLIC/default-ACL boundary. Automatic deployment continuation stopped. New runtime02 is staging/validated only; no DM Start.

## Other conclusions

PGC-P01 RESOLVED except the separate PGC-D01 regression: table DML and schema rights separated; requested CREATE-only/combined/revoke/creator tests added. PGC-P02 RESOLVED: canonical project contract/UX and old-schema refusal included.

Overengineering findings0: no new persistence/API/resolver/DTO; existing SQL, UI checkbox and generic Go writer retained. Scalar ENV transport correction conforms to existing schema and adds no precedence logic.

Reviewer inspected all16 files and scoped production/test/doc diffs; did not run tests, contact hosts or inspect secrets. Reported Go/frontend/Core/initial isolated PG evidence does not replace the blocker correction. Actual Wails Save/reopen and extended native QA were pending at review time.

## Owner-authorized TARGETED_RECHECK — APPROVE

2026-10-17. Independent reviewer `/root/library_common_plan_review`; PGC-D01 RESOLVED, zero blockers. Identity `.runtime/grant-create-public-recheck-scope.json`, SHA-25620ce857542b6ec5457e5dd3f34abce62f5ecbba26555c0a321b736ac2fd6d084. All16 hashes verified, zero mismatches; fourteen files unchanged, SQL and native regression updated. This verdict supersedes the historical BLOCK above for this identity.

PUBLIC default-schema allowlist remains USAGE; chosen-account CREATE includes schema public. Regression covers selected-account creation, neighboring-account denial, refusal of conflicting PUBLIC default privileges without ACL mutation, and successful Apply/Verify after fixture conflict removal. Overengineering findings0. Reviewer performed read-only inspection, no host access or test execution. Existing owner authorization permits deployment through a fresh approved plan.
