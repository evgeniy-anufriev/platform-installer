# SDKU package validation

## Current source revision — 2026-10-22

SDKU/CSPA library defaults and the shared alarm-view-service defaults match the
packages used by successful run installer-4a5d154de7944a7578261d0ce0c0b312.
Kafka uses SASL_SSL/SCRAM-SHA-512 and account-bound JAAS for producer/consumer;
the other25 application packages were not replaced. Three import-catalog digests
were recalculated from canonical Git bytes. Generic PostgreSQL example resources
now include their existing default names, as required by the current schema.

The separate alarm-view-secrets example prepares SDKU5 generated/CSPA5 manual
runtime-secret references, managed history databases, distinct PostgreSQL names,
tested memory/pool/readiness overrides and CSPA port10022. It contains no runtime
credentials, QA addresses or artifact/image locks.

Current-tree RED OS validation PASS:28 package schemas/digests, generic preparation2,
secret-example preparation2, synthetic Compose renders26, shared base variants1.
The examples validator does not execute targets. The preceding actual React/Wails
run performed Apply and existing library Verify with skipInfraVerify=true:
all6 Java/Agent delivery comparisons100/100, direct manual-password hashes15/15,
and all6 health endpoints200/UP PASS. Full review/published-value reuse/visual
acceptance limits remain documented in the
[generated-password journal](../../docs/work/application-libraries/evidence/generated-password-journal.md).

## Historical library-defaults amendment — 2026-10-17

Owner amendment: common values now live in library defaults; application defaults
retain their own values; instance overrides live only in group_vars. Removed
overrides from all 26 SDKU slots, moved the exact 48-entry common ENV map and
opted out the eight frontend slots. Templates use the planned library_runtime.defaults
projection instead of reading alarm-service. Package digests were recalculated.

**The current Core schemas/resolver/UI implement this format.** Updated native
package/digest27, preparation2 and synthetic render26 checks PASS. Native
inheritance/Reset/opt-out and indirect-context refusal PASS. Real React/Wails
library ENV/typed parameter and instance ENV Save/reopen/Reset PASS; full Go
test/vet/build and frontend249/typecheck/lint/build PASS. Three existing native
assertion failures reproduce with the baseline module; no broad native PASS is
claimed. No runtime bundle publication or target installation occurred. See the
[implementation journal](../../docs/work/application-libraries/evidence/library-common-defaults-journal.md)
and the
[updated plan](../../docs/work/application-libraries/library-common-defaults-plan.md).

## Historical checks before the owner amendment

Scope: package content and structure only, as explicitly limited by the owner.
Excluded: service installation, image acquisition, production changes and real
React/Wails or target application acceptance.

| Check | Result |
| --- | --- |
| Live SSH read of `/data/manifests/scada` on `.107` | Completed; no source service changes |
| Native Core package loader on RED OS `.101` | 27/27 package schemas, allowlists, identities and final digests passed |
| Native Core preparation of example group_vars + host_vars | Two selected instance jobs; no findings |
| Native Ansible Templar + YAML parsing | 26/26 Compose templates and common base rendered with synthetic nonsecret values |
| Actual Go import manifest validator, Windows | 27/27 package byte sets accepted, expected digests matched |
| Forbidden markers in delivered SDKU files | No SSH-password marker, private-key header or redaction-placeholder matches |
| Temporary RED OS source workspace | Removed with standard qa-sync cleanup |
| Real UI import / Save / reopen | Not exercised |
| Image execution / Vault authentication / application health | Not exercised; outside owner-approved scope |

The first checks found stale catalog digests after template edits, a generator
path error placing Compose deploy settings in defaults, and missing newlines
after inline Jinja loops. These were corrected before the final passing run.
The test fixture supplies dummy external URLs, mount paths, database names and
missing commands; these values are not product defaults or startup evidence.

Reproduce locally supported structural checks:

```powershell
go test ./internal/installer -run '^TestSDKUImportPackageBytes$' -count=1
```

On the configured RED OS Execution Node, after transferring the **current** tree
with `scripts/qa-sync.ps1`:

```sh
python3 /path/to/current-tree/examples/sdku/validate_packages.py /path/to/current-tree
```

Historical native result (superseded package bytes):

```json
{"packageSchemasAndDigests":27,"prepareJobs":2,"syntheticComposeRenders":26,"realTargetExecution":false}
```

The catalog binds the updated package bytes. Historical checks above do not
replace the current implementation journal. Remaining image/TLS/config
prerequisites are in [README.md](README.md).
