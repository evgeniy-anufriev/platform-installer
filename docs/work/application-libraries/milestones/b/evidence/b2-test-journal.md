# B2 — local library writer and package transfer

2026-10-14. Owner authorized B2 per the approved B plan, with reuse/minimalism.
Branch `codex/application-libraries-b2`, base
`3fa42182` (B1 plus generated portable-source refresh).

## Scope

[Writer contract](../../../../../contracts/application-library-writer.md),
project-edit/v1alpha11, existing local structural session/Review/Commit,
package import, package-aware revision/export. No B3 execution lifecycle,
UI editor, service mutation, bundle activation or infrastructure rerun.
UI ownership/Review/Save rules and matching mockup checked: local Save remains
structural; effective values and admission remain Core-owned. No screen changed.

## Reuse

- New fixed library commands use the existing EditCommand envelope and structural
  reducer, managed-header ownership, PlanStore and CommitStructuralSave. Existing
  v10 commands retain their version. No generic YAML patch API or second resolver.
- New fields are authored package references, slot/settings overrides, bindings,
  resources and host membership. Reset removes one authored field; unknown adjacent
  fields and user-owned opaque YAML are preserved. Direct reference/conflict
  guards cover library placements and referenced infrastructure entities.
- Package source reads reuse handle-bound export operations. Exact existing
  manifest closure/identity/digest is checked, destinations derived, existing
  versions refused. No archive extractor or package editor. Existing transaction
  handles publication, partial-write rollback and concurrent revision rejection.
- Local revision/export include package templates and dotenv alongside existing
  project/inventory/locks. Fixed roots exclude runtime credentials, approval/run
  records and infrastructure verification caches. Unsupported closure blocks export.

## Verification

Windows: five B2 tests PASS, including review with zero canonical writes, Save/
reopen/reset/opaque preservation, unsafe/derived input rejection, stale commit,
package digest/version/closure/export, hook/path/symlink refusal, partial-write
rollback and concurrent package commit. Full `go test ./...`, vet and build PASS
before the last bounded combined-package-budget guard; affected B2 tests PASS
after that guard. No test assertions or production behavior weakened for QA.

RED OS current-tree QA via qa-sync:

- New project-edit contract: 4 PASS; established edit versions: 10 PASS.
- Focused native Go writer/export/transaction/recovery/F2/B2 selection PASS.
- Five B2 tests in network namespace with no networking PASS; run as the established
  platform-automation account via sudo-n/unshare/runuser, GOPROXY=off/GOSUMDB=off.
- Final frozen delta: new contract4 PASS, affected native Go selection PASS and
  offline five B2 tests PASS again from workspace029084277dca4d7cb5c60d5d537a7c7b.

Two pre-existing broader-suite failures were identified separately:

1. contracts/tests/test_application_config.py validates config schemaVersion2
   against published application-config/v1alpha1, whose schemaVersion const is1
   and whose allowed keys omit the newer configuration. Full contracts discovery:
   39 cases, 38 PASS/1 FAIL. Config, old schema/test and SchemaValidator exactly
   match base Git blobs. New B2 contract tests pass independently.
2. Full Linux installer Go suite fails
   TestSecretOutputStagingSubstitutionNeverReturnsReceiptOrDeletesForeignObject:
   test searches project/secrets for staging while unchanged publisher now stages
   inside project/secrets/vault-ha. It fails "staging absent" before exercising
   substitution. B2 does not change either secret-output implementation or test.
   Windows full Go suite passes; Linux focused affected writer/export/recovery
   cases pass. No Linux full-suite PASS is claimed.

These failures are not hidden by new skips/exclusions or schema relaxation; their
repair is outside the current library writer change. General regression is not
reported as completely green. No real UI/bridge acceptance claimed (B4).

## Review and cleanup

Independent [FULL DIFF](../reviews/b2-diff-review.md) returned BLOCK: B2-D01 and
B2-D02 open security blockers; B2-D03 nonblocking overlap issue. Frozen18-file
manifest SHA256 c5e7271b9ca79405071a76766cdef0ab1f280f4208090c4d03b06bcc10ba326b.
No reviewed source changed after the report. Existing positive QA does not cover
these secret-entry cases and does not close B2. Implementation corrections and
possible one TARGETED_RECHECK await owner authorization per review procedure.

Six safe logs copied to .runtime/qa/b2/evidence and SHA256 verified against remote
files; manifest sha256.json retained. Three temporary qa-sync workspaces
897d20f743274421bb09e3ed76a2ac2f, a19936b6d12d44649d2888b864a15d96 and
029084277dca4d7cb5c60d5d537a7c7b cleaned with qa-sync. No target services/data,
PKI, runtime credentials or infrastructure changed. No commit/push performed.


## Owner amendment and bounded correction

Owner superseded D01/D02 heuristic requirements: user environment/parameters and
package files allow arbitrary names/assignments including PASSWORD. Go local
writer/read/import/export and Core updated accordingly; explicit Installer
credential/private-key custody remains separate. D03 parent/child conflicts now
rejected, independent slots accepted. Original FULL report retained historically.

Final checks: full Windows go test ./..., go vet ./..., go build ./... PASS.
RED OS current-tree affected application Core100 PASS; v11 contract4 PASS;
Go B2/export/transaction/rollback/recovery/F2 selection PASS; network-isolated B2
PASS. An old dotenv test initially failed because it still expected REDIS_PASSWORD
rejection; corrected to owner policy while keeping SERVER_ID rejection. No checks
skipped. Prior two unrelated broader regression failures remain as recorded above;
no global regression PASS claimed. No UI/bridge acceptance claimed.

Final identity2b78e71f223153f0ff552c06f54bd193241403b38557b93b9d765e2be0eb51c0.
[Independent targeted recheck](../reviews/b2-diff-targeted-recheck.md) BLOCK:
D02 superseded, D03 resolved, D01 residual typed descriptor source accepts extra
value or missing ref. No further production changes after report; completion
stopped for owner. Review budget exhausted, further review needs authorization.

Four safe logs copied to .runtime/qa/b2/evidence/owner-*.log and remote/local
SHA256 matched. Temporary source workspaces58c2a35c1f8c47ec9086fe99fbe1bda8,
e7bc3a20699d40ffb3a344bf51b171b8 and3e2a598744b443caa5aee149b1dfe416
cleaned through qa-sync after evidence copy. No target services/infrastructure
mutated, no commit/push.


## Explicit source correction and additional authorized review

Owner authorized source correction and one additional independent review. Added
small closed source-shape helper using existing source contract; account/shared
source extra value/missing ref/type/wrapper fields rejected. Generated/runtime/
Vault/PKI source shapes retained, literal username allowed. Free user data/files
unchanged. Tests cover Create/Update/Slot/accounts override rejection without
canonical mutation plus shared-secret and valid-source cases; real local
save/reopen positive uses runtime shared-secret and Vault account descriptors.

Windows full go test ./..., go vet ./..., go build ./... PASS. RED OS100 affected
Core application tests/4 v11 contracts PASS; affected B2/export/transaction/
rollback/recovery/F2 selection and network-isolated B2 eight tests PASS. Four
safe typed-source-*.log files copied into .runtime/qa/b2/evidence; remote/local
SHA256 matched. QA workspace31bfe1e06e8b426da03184111efbb70c cleaned through
qa-sync. No target services/PKI/runtime credentials changed, no commit/push.

Frozen identity2004e321f3183761292ff25f8d8ff7378fb9c24a7d492f6ac49ec58ad54c7c9f
unchanged. [Additional review](../reviews/b2-typed-source-recheck.md) BLOCK:
account/shared source issue corrected, but slot.credentials still accepts arbitrary
map instead of only optional vault_binding. Source remains frozen; B2 not complete.
Further correction/review needs owner decision under stop-on-BLOCK procedure.
Existing two unrelated broader regression failures remain; no global PASS claim.


## Final slot credential correction and B2 closure

Owner authorized correction and another bounded independent review. Slot
credentials now allows only optional vault_binding string ID, reusing existing
applicationKeys/validLibraryInputID. Create/Update/SetSlot use the same validator.
Added negative password/value/source/non-string/empty/invalid binding cases for
all three commands with BLOCKED plan and unchanged canonical revision, plus
positive empty credentials and valid binding. Account/shared source validation
and all free user parameter/file behavior unchanged.

Final Windows go test ./..., go vet ./..., go build ./... PASS. RED OS current
source affected B2/ProjectExport/Transaction/Rollback/Recovery/F2 selection PASS;
network-isolated B2 nine test functions PASS. No Python/Core change in this delta;
previous final affected Core100/contracts4 PASS remain applicable. Existing two
unrelated broader regression failures above remain; no global Linux/contracts
regression PASS claimed. No real UI/bridge acceptance claimed (later B4).

[Final independent recheck](../reviews/b2-slot-credential-recheck.md) APPROVE,
zero blockers, identity6455eb0bf37aece857fa0cea79b04e7421613b97bd67a04eab8704240c88ced1
unchanged. D01 RESOLVED, D02 SUPERSEDED owner policy, D03 RESOLVED. Previous BLOCK
runs preserved. B2 backend writer/package-transfer milestone COMPLETE within its
approved scope. B3/B4/UI not started; no commit/push.

Two safe logs .runtime/qa/b2/evidence/slot-go.log and slot-offline.log copied and
remote/local SHA256 matched (f7b294abc2fce97b9829faf60522213bee32dd8f825f74ccf5ff15b039fa621f,
c22b8ad0a8018b1e7a5c658de98b14af6790885b7f3e7b4dbe39a5f90953284d).
Final QA source workspace506a56477ed147dc93b35589be0db0c7 removed through qa-sync.
No infrastructure/service/PKI/credential mutation performed.


## Publication authorization

Owner requested B2 commit and synchronization to master. Reviewed source identity
rechecked with zero mismatches; working tree contains only intended B2 changes.
Fetched origin: local master behind one automatic portable-source refresh; B2
base equals origin/master, no divergence. Publication uses normal fast-forward
updates without force-push. Final commit identity is available in Git history.
