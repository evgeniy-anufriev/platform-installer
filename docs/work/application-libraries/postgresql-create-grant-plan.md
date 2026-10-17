# PostgreSQL CREATE in existing application access

Owner request 2026-10-17: add CREATE to existing Go/UI grants while continuing the SDKU data-manager deployment on .101/.102/.103.

## Bounded implementation

- Extend the existing PostgreSQL databaseAccess.privileges selection with CREATE (max five rights). Preserve the same account editor, generic Go command/guarded writer and ordinary group_vars authority. Go has no separate privilege enum or infrastructure resolver; verify its existing pass-through by real React/Wails Save/reopen.
- CREATE means CREATE objects inside non-system schemas of the selected library-owned managed database, including future schemas through the existing creator-role default-privilege pipeline. It does not grant CREATE DATABASE, database-level CREATE/schema creation, ownership, membership or superuser rights.
- Core validates the fifth value; the existing SQL reconciler treats CREATE as a schema privilege and keeps table DML separate. USAGE accompanies a nonempty access policy. Existing owner/foreign-object, column ACL, PUBLIC/external grant, grant-option, role membership and creator-role guards remain.
- Apply grants missing CREATE and removes its direct/default grant when deselected. Verify checks the same policy. Removing CREATE preserves existing objects and their owner's authority.
- No new resolver, persistence, API, migration framework, helper or screen. No unrelated SDKU/defaults changes. Static design currently shows four PostgreSQL DML checkboxes; add the fifth in that same row and document its schema scope.

## Validation and risk

Security permission extension: HIGH-RISK FULL DIFF review required. A focused FULL PLAN review precedes implementation; no automatic repeated full review. Owner already explicitly authorized this bounded feature. Any BLOCK stops work for owner direction.

Focused Core/provider projection tests; isolated real PostgreSQL create existing/future/revoke/repeat with SELECT unchanged and no database CREATE; frontend checkbox/reset tests; Go test/vet; actual React/Wails CREATE Save/reopen and reset through the guarded writer. Native QA runs from current sources on .102. New runtime publication, .103 preparation and fresh library-only plan precede continued installation. Installation remains blocked until review and checks close.

FULL PLAN review: APPROVE_WITH_CHANGES, zero blockers. PGC-P01: derive schema USAGE/CREATE separately from table DML in every ACL/default/Verify branch; test CREATE-only, combined, revoke with SELECT, removed creator. PGC-P02: update canonical project contract/UX and verify old schema rejects CREATE before execution. Original reviewed SHA-25634569d50dedbb07b4913471133ecaff21771530016428ef54b1c91a959ce5391; no repeated PLAN review.
