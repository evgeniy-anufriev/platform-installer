# SI08-D — workstation secret files and protected output delivery

Implementation is in the current shared worktree. Initial FULL DIFF review
returned BLOCK with six blockers; owner accepted the bounded corrections below.
The targeted recheck resolved DIFF-01–05 and returned BLOCK on DIFF-06.
The owner subsequently authorized the exact reservation/recovery correction;
its focused and regression gates PASS. DIFF-06 is RESOLVED BY OWNER-AUTHORIZED
EXACT CORRECTION, not by another reviewer verdict. See [review](service-install-08d-review.md).
The automatic review budget is exhausted; no further review was run.
SI08-E has not started. No Vault installation, runtime publication or
activation was performed.

The existing service Secrets dialog imports the trusted administrative token
and unseal-share files as session-only typed inputs. Plaintext and age files
are read through the safe selected-file boundary and admitted by the broker
and existing credential lease/Start path.

Installation → Plan collects and confirms the common output encryption
password when the trusted service contract declares protected outputs. This
password stays in workstation memory. There is no destination picker:
encrypted output files are written to the current project's
`secrets/<deploymentId>/admin-token.age` and `unseal-shares.age`.
The deployment directory also contains a completion receipt bound to project,
deployment, package, generation, source run and runtime digest.

The backend discovers safe metadata on the selected READY Execution Node,
fetches the confidential bounded frame through separate stdout/stderr
transport, validates its binding and typed entries, encrypts locally, verifies
the encrypted bytes and atomically publishes the deployment directory using
the existing held-directory primitives. It ACKs only after the complete local
receipt exists. A delivery retry verifies the existing encrypted files and
reuses that receipt; an unrelated existing deployment directory is preserved.
When safe staging cleanup cannot be proven, the encrypted staging directory is
retained and reported explicitly. The remote package remains pending on a
transfer or local-storage failure.

## Owner-authorized corrections

- DIFF-01: bundle-root-relative module/schema loading; the exact subprocess
  GetCapabilities entrypoint is tested without PYTHONPATH/preimports.
- DIFF-02: attested closed output capability handshake before Start;
  unsupported, failed and malformed responses produce zero Start calls.
- DIFF-03: held-directory durability barriers before receipt/ACK, Linux fsync
  and Windows NtFlushBuffersFileEx flags=0, plus recovery-time reflush.
  Injected publication/barrier failures never return an ACK receipt.
- DIFF-04: final opened directory identity, complete receipt and ciphertext
  readback, and project/secrets parent binding are checked before success.
  Linux staging substitution preserves both original encrypted staging and
  substituted objects and cannot authorize ACK.
- DIFF-05: a local bound receipt and decryptable encrypted files recover ACK
  without Fetch/list availability; known managed deployment paths restore
  package identity after application reopen, without directory scanning.
- DIFF-06: controller creates one retained package directory and passes the
  existing role-prefix bootstrap_output_dir to both Apply and Verify. READY
  publication flushes the same role-written entries; terminal evidence permits
  ACK cleanup of token, shares and recovery init-response. No run-project copy.
- DIFF-07: a new backend plan observation supersedes local password ACK state;
  blocked Start refreshes password availability. Expiry/replacement restores input.
- DIFF-08: Linux selected-file open is nonblocking before regular-file admission;
  a FIFO without a writer is rejected within the bounded test.

Focused controller lifecycle tests: 36 PASS. Production entrypoint/wire: 4 PASS;
retained storage: 16 PASS. Windows full Go tests/vet, frontend 67 tests/lint/build,
Wails production build and held-directory Windows durability probe PASS.
Final RED OS Core suite: 345 cases, 341 PASS and 4 opt-in skips.
Contracts: 31 PASS; Vault role tests: 15 PASS; catalog/schema reproducibility PASS.
RED OS race: installer 124 PASS/1 skip, executionnode 93 PASS/13 skips,
root output delivery/list tests 2 PASS and FIFO test 1 PASS; no race reports.
Final source root race (Start capability gate, delivery/reopen and listing):
PASS 51.889s. Temporary QA workspaces removed using qa-sync cleanup.

### Exact DIFF-06 correction and final evidence

Preparation durably records a closed private reservation before creating the
retained package directory. Admission/listing distinguish that reservation
from corrupt published metadata and filter by its exact project/deployment
binding. This adds no public protocol/schema or second secret custody path.

Controller completion and terminal recovery share the same completion helper:
complete pairs are durably published READY; empty terminal reservations receive
a private NO_OUTPUT completion and permit the next generation; partial pairs
or init-response-only retain the last plaintext copy and return the safe
OUTPUT_RECOVERY_REQUIRED status. Incomplete packages cannot be fetched or ACKed.
Recovery also runs after an already-written terminal result. A reservation
without a directory retains its journal until empty recovery completes.
Other-project reservations do not poison listing/admission. Unknown missing
metadata without a valid reservation still fails closed.

Final current-source offline RED OS checks: lifecycle 38 PASS, storage 24 PASS;
Core 355 total (351 PASS, 4 opt-in skips); contracts 31 PASS; Vault role 15 PASS;
catalog/schema reproducibility PASS. Affected RED OS race: executionnode
94 PASS/13 opt-in skips and root secret-output/capability tests 3 PASS;
no race reports. Windows go test ./... and go vet ./... PASS; frontend
67 tests/lint/typecheck/build PASS. Wails build and filesystem durability gates
above remain prior evidence: this correction changes no Wails DTO/bindings.
Scoped security inspection confirms only a closed protocol/operation/errorCode
response can reach the safe recovery diagnostic; raw stdout/stderr and secret
values are not surfaced. Final diff check PASS. All four QA workspaces created
for this correction were removed with qa-sync cleanup. The shared worktree
retains unrelated changes. C/D are recorded in a focused implementation commit;
mixed catalog/other-service/QA work is left outside it. No clean claim is made.

Installation shows safe delivery metadata/status alongside the execution
result and offers an explicit retry. Secret contents do not enter React,
events, diagnostics or project desired-state documents. Outputs do not change
the canonical project revision; `secrets/` is excluded from the existing
export/archive boundaries and the local Core staging copy.

Owner clarification (2026-09-26): encryption password belongs to Installation;
output location is always `secrets/<deploymentId>/`, with no folder control.
Service input files remain in the service Secrets dialog. The role's plaintext
entry names match the trusted `admin-token` / `unseal-shares` IDs;
`init-response.json` remains recovery-only and is not published.

## Evidence so far

- `go test ./...` and `go vet ./...`: PASS.
- Frontend typecheck/lint/build: PASS; 67 tests PASS.
- Windows `wails build -nopackage -clean`: PASS.
- RED OS race tests: installer, secretoutputwire, secretfiles, runtimesecret,
  executionnode PASS. Final source checks also PASS for installer/executionnode
  output tests and the root application secret tests (`-race`, 56.546s).
- RED OS output protocol tests: 15 PASS; Vault role contract: 15 PASS.
- Focused filesystem tests cover the exact default path, no overwrite,
  receipt/ciphertext readback, rejection of a substituted secrets directory,
  unchanged project revision and omission from local Core staging.
- Full Core: 342 cases completed, 4 skipped, PASS. Contracts: 31 PASS.
- Catalog/configuration schema reproducibility: PASS.
- `git diff --check` (dependency content excluded): PASS.
- Historical independent FULL DIFF: BLOCK; targeted recheck: DIFF-01–05
  RESOLVED, DIFF-06 OPEN. Zero new overengineering findings. DIFF-06 is now
  resolved by the owner's exact correction and the final evidence above;
  no additional architecture review was run.

This is implementation evidence, not real Vault service acceptance.
