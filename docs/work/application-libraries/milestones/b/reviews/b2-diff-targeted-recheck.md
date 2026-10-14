# B2 TARGETED_RECHECK D01-D03

Independent reviewer: /root/b2_diff_review. Verdict: **BLOCK**.
Base 3fa42182892eac0583925d6f6a31b1e124ae2115; final identity
2b78e71f223153f0ff552c06f54bd193241403b38557b93b9d765e2be0eb51c0
(.runtime/qa/b2/owner-corrected-final-identity.txt). All hashes matched.
Only one Core test expectation changed during review; final delta inspected.
Production files remained frozen. Review validity CURRENT.

## B2-D01: remaining typed source boundary - BLOCKING

The owner superseded the earlier name/assignment heuristic requirement. Arbitrary
user environment/parameters/PASSWORD assignments are correctly allowed.
However application_library_save.go safeApplicationInput checks source.kind only
for explicit credentials.password and shared_secrets. A runtime_secret_ref with
extra value field, or without ref, can reach canonical YAML/transaction bytes.
Existing settings.schema.json source declares closed kind/ref shape. This is an
explicit Installer credential descriptor, not free user data.

Synthetic reproduction: accounts.db.credentials.password.source contains
kind=runtime_secret_ref, ref=runtime-id, value=synthetic-marker. Current guard
accepts it; equivalent shared-secret descriptor also bypasses closed shape.

Smallest correction: reuse a small closed typed-source validator for declared
credential/shared-secret descriptors only, with required fields. Do not classify
user parameter names or assignment text. Negative tests should cover extra value,
missing ref and extra fields across Create/Update/Slot/accounts override with no
canonical mutation; valid runtime/Vault references and free PASSWORD data pass.

## B2-D02: SUPERSEDED

Owner allows arbitrary package configuration/templates/assets/.env assignments.
Import/export comply; private-key guard, allowlist/digest/containment retained.
No remaining D02 blocker.

## B2-D03: RESOLVED

Authored write paths and ancestor/descendant comparisons reject applications,
slot and leaf overlap; independent slots remain composable. Tests inspected.

## Complexity and evidence

No blocking overengineering finding: no new persistence/lifecycle/classification
framework/execution API. Fixed paths reasonably extend existing conflict guard.
Reviewer inspected contract/plan/ADR amendment, affected Go/Core code and tests;
reviewer did not execute tests. Parent subsequently confirmed all final focused
native checks PASS; those do not cover the missing typed-source negative case.

One blocker remains. FULL plus sole TARGETED_RECHECK budget exhausted. Automatic
completion stopped; additional independent review requires owner authorization.
Original FULL BLOCK remains historical evidence.
