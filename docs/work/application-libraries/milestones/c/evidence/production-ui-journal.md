# Applications production UI — 2026-10-16

## Authorized scope

Owner approved the interactive mockup, then explicitly limited implementation to
UI on the existing contract. Existing deployment renaming and new writable KV
document/key mappings are deferred. New library IDs default from the selected
package name and remain editable before creation. Existing IDs are read-only.
The approved mockup retains the future grouped KV design; this is not a claim
that Core currently writes those paths.

## Implementation

Reuse ApplicationsPage, ApplicationCredentials, ApplicationSecretInputs and the
existing application draft/writer lifecycle. Seven instance tabs: Основное,
Порты, Подключения, Секреты, Файлы, Запуск, Состояние. Explicit package default
editing and reset; separate host/container ports; library-level placement;
connection projection; inline runtime form; fixed draft/Review footer.
Password-free connections appear in Connections, not credential cards.
No Go/Core changes, parallel desired state, new runtime lease, target mutation,
installation or direct container controls.

Runtime inputs retain exact Core requirement IDs, saved revision and descriptor
fingerprint and use the existing runtime values API. Values are cleared on
successful submission, failure and form cancellation; component unmount removes
local input state. They are not added to draft/Review/Save.

## Checks

- Full frontend regression: 187 PASS, zero failures (before one additional
  package-default ID test); final focused result recorded in local evidence.
- TypeScript, ESLint, production frontend build: PASS.
- Real React handlers / Wails Go editor methods: PASS on isolated copied project.
  Image override/amend/reset, host-port change, adjacent container-port preservation,
  Review/Commit/reopen, two library create/save operations and dirty Stay/Discard.
- Final three real Review plans: 80b177013685e5bf76b7fbe3736b87f3,
  998f4597985cbd68a00333bf446068ca, 29db615fd1c1498c006fae9e90d6b71c;
  all READY and Commit COMMITTED. No execution run started.
- Visual inspection: actual Applications screenshots at 1440x900 and 1024x720;
  corrected breadcrumb layout and footer visibility. No whole-app visual claim.
- Inline submission has focused descriptor/fingerprint/value-clear tests. No new
  real target runtime-secret installation acceptance is claimed for this UI change.
  Previously accepted C target behavior is unchanged; no infrastructure QA rerun.

Local safe evidence: `.runtime/qa/application-design/` contains JSON results,
real bridge report and screenshots. Tests use synthetic values only. No new
credential files were created. Existing owner-retained C QA copies are preserved.
No commit/master synchronization performed.

Final focused run: 13 PASS, zero failures (includes the additional package-default
ID case). Prettier checks PASS. Final production dist regenerated from the current
frontend. Screenshot inspection confirmed footer and breadcrumb corrections.

Cleanup limitation: automatic approval review rejected the combined command to
remove three newly created editor-project copies and stop the exact owned QA
processes. That command did not execute. These copies and QA process state are
retained under `.runtime/qa/application-design/`; no cleanup success is claimed.
The previous owner-retained C QA workspaces were not touched.

## Library ID clarification

Owner accepted ID editing at creation only; saved IDs are immutable. UI now
explains that behavior without Core implementation details and offers an explicit
"Сбросить ID к имени библиотеки" action. Package selection preserves a custom ID.
ApplicationsPage focused tests PASS; TypeScript/production build PASS. Repeated
real React/Wails create/reset/custom-ID/Review/Commit flow PASS (plans
3cc5cd458162d14a2e9449ac85a2e641 and 35d355e1ef4edccf6c567218076b7a4b).
Only isolated local editor fixtures changed; no target operations.

## Username/password variable bindings — 2026-10-16

Owner authorized a UI editor using the existing secret_bindings contract, with
no Core changes. Implemented ApplicationSecretBindings inside Secrets, reusing
SetApplicationLibraryOverride / Amend / Review / Commit. The generic Agent
settings form excludes secret_bindings and preserves it during other edits.
No credential payload is copied into these commands: only account, field and
variable names. Shared-secret bindings and unrelated Agent options are preserved.
Required type/mode fields come from package declarations when needed.

Core recursively combines bindings. Package variables remain; an additional name
is an alias, not deletion/rename of a package key. Reset removes only the authored
binding so defaults apply again. UI describes this limitation explicitly. The
correct existing key is provisioner.secret_bindings; earlier conversation's
variable_bindings name was inaccurate. Existing Core env_template forwards
values to the application under process-supervisor; KV layout is unchanged.

Checks:
- Full frontend: 192 PASS, zero failures before the final additional sibling-dirty
  test; final affected run: 18 PASS, zero failures.
- TypeScript, ESLint, production frontend build PASS; diff whitespace check PASS.
- Tests cover source override/reset, alias add/remove, invalid/duplicate variable
  names, shared/neighbor/Agent-setting preservation, payload exclusion, rejected
  save, accepted-save sibling dirty state and busy controls.
- Real React/Wails: alias Save/reopen, source override Save/reopen with neighboring
  alias preserved, package reset Save/reopen, alias removal Save/reopen and dirty
  Stay/Discard PASS. All four review plans READY and Commit COMMITTED:
  79b0961b33c2e472e85ef506b1372dc4, c55ffe0e8b24365a39bc3da0097e0b0e,
  8194210abab66864077c23e384c3480a, 729e8de9875327932b8f441f44124c81.
- QA initially failed because its expected PG_PASSWORD name differed from the
  retained package's PGPASSWORD; fixed QA assertion only. Explicit accessible
  select labels added after browser selector ambiguity. Those failures are not PASS.
- No Core/Go/contracts diff, target contact or installation. No new claim of
  target Vault materialization: existing accepted mechanism remains unchanged.
- Local evidence: bindings-all.json, bindings-final.json, secret-bindings-wails.json
  and screenshots under .runtime/qa/application-design/. Synthetic values only.

The QA Vite server already existed on 34116 and was reused after a redundant
launch correctly refused the occupied port. Wails QA bridge launched normally.
Temporary public editor copies are retained, consistent with the cleanup
limitation above; no protected credentials were created or removed. No commit.
Final read-only screenshot pass inspected the actual binding form at 1440x900 and
1024x720 after spacing changes. Fixed footer remains visible and binding controls
wrap inside the editor. No new target or project write in this visual pass.
### Library screen alignment (2026-10-16)

Owner approved merging Overview/Placement, Docker runtime selection, and compact
resources grouped by provider deployment with database add/remove/name edits.
Existing deployments.schema.json resources accepts named PostgreSQL databases,
PostgreSQL schemas and ClickHouse databases. application_providers.py consumes
parameters.name and databaseRef; application_library_save.go replaces the resources
map through the existing UpdateApplicationLibraryDeployment intent. No Core/Go or
contract changes are necessary. UI deletion removes desired declarations only;
installed database destruction/rename is not introduced. Dependent references
remain subject to normal Core verification.

Implemented three library tabs, combined identity/runtime/placement overview,
unique Docker runtime autofill at creation, compact provider-grouped resource table,
focused resource editor, two-row resource pagination and collapsed shared-secret
source rows using the existing CredentialSourceEditor. Existing opaque resource
fields and schema databaseRef survive edits. Package and host override settings
remain available under explicit disclosure controls. No new persistence layer.

Real React/Wails add database / Review / Commit / reopen, rename / Commit / reopen
and delete / Commit / reopen PASS on an isolated copied project. Local evidence:
.runtime/qa/application-design/library-layout-wails.json. No target contact or
installation. Initial QA failures were selector timing/accessible-name ambiguity;
corrected bounded selectors then all three flows passed. Read-only screenshots
inspected at 1440x900 and 1024x720. At 1024x720 both default Overview and Resources
bodies have clientHeight=scrollHeight=345; at 1440x900 Overview=524/524. Long lists
use pages; expanded advanced settings may scroll. Public temporary QA project
copies retained alongside earlier owner-retained copies; no credentials created.
Final frontend regression: 200 tests PASS; ESLint PASS; TypeScript and Vite build
PASS. Seven focused resource tests cover grouping, schema-reference preservation,
addition, confirmed deletion, duplicate IDs, pagination and rejected-stage dirty
state. Existing bundle-size advisory unchanged; no test or validation weakened.

### Name-first universal parameters and automatic types (2026-10-16)

Owner retained the universal parameter form but approved name-first addition:
Add parameter asks only for a name, then creates an ordinary editable row.
New empty-valued parameters infer boolean/finite safe numeric values; leading-zero
identifiers, multi-dot versions, IPs, large integers and whitespace-bearing strings
stay strings. Existing/package scalar types are preserved. A collapsed Advanced
control offers explicit string/number/boolean selection; object/list creation
reuses the existing recursive structured editors, not JSON text editing. No
metadata/type store or Core changes. Invalid typed values cannot be staged;
normal rejected-stage and dirty/reset guards remain. Host-scope labels now name
the selected server and all applications affected, rather than membership/slots.

Fourteen focused input cases PASS, covering inference, name-only addition,
package string preservation/manual override, invalid numeric values, reset and
object creation. Real React/Wails evidence and full frontend results follow.
Final real React/Wails name-first addition and Save/reopen PASS for numeric 30,
string 001 and boolean true on node1 membership overrides. Safe evidence:
.runtime/qa/application-design/parameter-types-wails.json (three cases PASS).
Initial bridge refusal did not discard any active draft. Subsequent QA exposed
that selecting a host remounted and closed the disclosure; explicit disclosure
state now survives that edit. No target contact or installation. Full frontend
214 tests PASS, lint PASS, TypeScript/Vite build PASS. Existing generated Wails
bindings were restored after build-only regeneration; no transport change.

### Database name and provider selector simplification (2026-10-16)

Owner removed separate resource-ID input. New database declarations use their
name as resources key; duplicate keys/names are rejected. Existing keys remain
stable when changing the desired database name, preserving account/schema refs
and owned-resource markers; no implicit identifier migration or data rename.
Bindings are filtered by the selected resource kind against existing managed
deployment serviceType metadata. Changing type clears incompatible selection
(or selects the sole compatible binding). Unknown/mismatched references cannot
be submitted. Core provider validation remains unchanged.

Eight resource tests PASS, including PG/CH filtering, exclusion of PKI bindings,
name-derived keys and existing schema reference preservation. Real React/Wails
name-only add / Save / reopen, rename / Save / reopen and delete / Save / reopen
PASS; evidence .runtime/qa/application-design/resource-name-wails.json. Actual
PostgreSQL options contained only qa-postgresql/postgres. No target contact.
Final frontend regression215 PASS; ESLint and TypeScript/Vite build PASS. No Core/Go changes.

### Library connections table (2026-10-16)

Owner requested table alignment for library Connections. ApplicationBindings now
renders named rows with reference kind, deployment/profile selector and existing
Stage/Reset actions. Three-row pages keep the base view compact; paging/addition
is blocked while another row has unstaged edits. Add connection asks only for its
name, then exposes its selectors. Vault reference settings are disclosed separately.
Existing draft update/removal, opaque-field preservation, stale-reference display,
reference-kind switching and dirty/rejected-save guards remain in place. No Core,
Go, credential or desired-state contract change.

Five focused table tests PASS. Existing connection test now locates its table row
instead of the replaced fieldset, preserving the exact neighboring-binding payload
assertion. Real React/Wails add TLS binding / Review / Commit / reopen and reset /
Commit / reopen PASS on an isolated public project copy, no targets contacted.
Evidence .runtime/qa/application-design/connections-table-wails.json. Screenshots
inspected at 1440x900 and 1024x720; at 1024 Connections clientHeight=scrollHeight=345.
Final frontend regression220 PASS; ESLint, TypeScript and Vite production frontend build PASS.

### Unified Vault connection and scrolling (owner revision 2026-10-16)

Owner superseded paged Connections with one scrollable service table. All binding
rows remain mounted; the header is sticky and the draft footer stays outside the
scroll region. Separate Vault reference form removed. The active vault_ref.binding
is marked on its existing binding row. Other bindings targeting managed Vault
deployments expose Select for secrets, saving the same existing vault_ref.binding
through UpdateApplicationLibraryDeployment. Vault credentials, paths and secrets
are not edited or fetched by this action. No new Core field or desired-state store.
Existing service binding updates/reset and reference validation remain unchanged.

Seven focused tests PASS: complete nonpaged list, Vault alias selection, sibling
preservation, reference kind changes, reset and rejected-stage dirty behavior.
Real React/Wails Vault binding selection / Review / Commit / reopen PASS; restoring
the original alias and removing the temporary binding also PASS. Evidence:
.runtime/qa/application-design/connections-vault-scroll-wails.json. The first QA
attempt assumed qa-vault, while this fixture correctly uses qa-vault-consumer;
QA now reads the selected deployment from the actual existing binding. No
production authority or target change. At 1024x720 the list has seven rows and
scrolls internally (201px client / 301px content); page body remains 345/345.
Screenshot inspected. Full frontend222 PASS, ESLint and TypeScript/Vite build PASS.

### Instance General screen (owner-approved 2026-10-16)

General now contains a compact image override/reset row, read-only Core instance
identity, authored/package summary (placements, port pairs, declared connection
count), and a typed readiness form. Generic parameters moved intact to a dedicated
Parameters tab; no parameter value is removed from the project. Readiness exposes
only contract fields mode/container|healthcheck, retries1..60 and delay1..30,
with package sources, explicit edit/stage and section reset. Missing package
values show Core default placeholders without inventing effective defaults.
Existing override/remove intents and sibling-dirty guards are reused.

Owner explicitly chose read-only instance identity after contract inspection:
Core currently derives application-name + library-ID and has no name override.
UI reads the existing Core instance-map key by slotId; absent evidence displays
Not yet calculated. No rename, identity migration or Core extension authorized.

Focused readiness5 and editor11 cases PASS, including contract bounds, absent
package defaults, package/override behavior, rejected saves/reset, separate
parameters and Core-supplied identity. Existing image tests retain exact payload
assertions after the label change. Real React/Wails image+readiness Stage / Review /
Commit / reopen, reset / Commit / reopen and separate Parameters tab PASS.
Evidence .runtime/qa/application-design/instance-general-wails.json. Synthetic
image change only in a copied project, no target contact/pull/install. Actual
screenshots inspected at1440x900 and1024x720; final small-screen content326/326
(client/scroll), footer visible. Public QA copies retained; no credentials created.
Final full frontend229 PASS; ESLint and TypeScript/Vite build PASS. No Core/Go changes or EXE rebuild in this screen task.

### Ports source display and Add port (2026-10-16)

Owner requested the missing-port fix for cspa/apigateway. UI previously enumerated
only application defaults and authored instance ports. It now shows distinct raw
source rows for application package, library slot override, instance override,
host placement override, and existing Core placement ports with revision labels.
These sources are never merged into an invented effective Ansible result. General
shows a bounded source-labelled preview; exact resolved server pairs remain Core
projection data. Partial source rows explicitly show an em dash for the absent
side. No runtime container discovery or target action is implied.

Add port stages a complete named published/container pair through the existing
SetApplicationLibraryOverride property ports operation. Optional inherited/Core
source copy is an explicit operator action, not resolution. Duplicate authored
listeners are rejected; current per-side edit/reset controls remain unchanged.
Range/integer and ID input guards preserve contract bounds. Empty settings show
an explicit Add port / Project Verify explanation rather than an empty editor.

Six focused port cases and twelve editor cases PASS, covering source separation,
library/host/Core data without package or instance defaults, complete-pair payload,
empty state, ranges, duplicate protection and rejected-stage dirty state.
Real React/Wails empty-instance state, Add complete pair / Review / Commit /
reopen, source-labelled General summary and original-pair restoration PASS on an
isolated public cspa/gateway project copy. Evidence:
.runtime/qa/application-design/ports-sources-wails.json. No target contact,
container restart or installation. Screenshots inspected at1440x900 and1024x720;
ports editor body can scroll, keeping the existing fixed draft footer visible.
Final full frontend236 PASS; ESLint, TypeScript/Vite build PASS. No Core/Go or target changes. EXE not rebuilt in this task.

## Working UI aligned to the revised mockup — 2026-10-16

Owner authorized production UI integration of the revised mockup. Instance Ports
and Connections tabs are removed; Parameters remains separate. General now holds
image/read-only Core identity, library/service summary, readiness, Host/Container
editing, Add Port/provenance and endpoint settings. The library link opens its
existing Connections tab. Source rows stay separate: React does not reconstruct
Ansible precedence. A missing application-package port shows an explicit source
hint, never an invented effective value. Core-derived endpoint addresses/ports
are not editable mockup fields; the existing endpoint contract/editor remains
under an expandable section. Readiness retains its actual container/healthcheck
contract instead of the synthetic mockup's HTTP-path example.

Cards/spacing/actions and credential typography are compact. Account management
mode reset now removes only mode, preserving authored credentials/access; an
added regression test checks that distinction. No Core/Go/security boundary or
runtime lease change, no additional architecture review required for this UI
delta. Primary desktop widths1440/1024; below1024 shell remains1024px with its
desktop columns, no smaller composition. Existing layout-only max800 rules were
removed from applications.css.

Real React/Wails Save/Review/Commit/reopen and reset PASS for image and host port
on an isolated QA project copy; library navigation and grouped Secrets checked.
Evidence `.runtime/qa/application-design/ui-parity-wails.json`. Screenshots
general1440x900, general1024x900 and secrets1024x900 inspected. General body:
1440 client505/scroll505px;1024 client506/scroll506px, no horizontal overflow.
At800 viewport shell width1024 with160/864px columns. No target mutation or
infrastructure Apply. Earlier attempts with stopped/starting Wails dev server
failed CONNECTION_REFUSED before project open; subsequent actual bridge PASS.
Final frontend244 PASS/22files, lint/typecheck/build checked; known-value scan
20 values/314files/0matches. This UI acceptance does not close the outstanding
Secrets/Core target-run, repeat and cleanup gates recorded in the access journal.
Production desktop EXE rebuilt successfully with `wails build -skipbindings`
(no Go/binding contract changes). The backend context was restored to the original
QA project after isolated UI checks. Attempted bounded cleanup of newly created
ui-parity-project fixtures and this session's exact owned dev processes was
rejected by automatic approval policy, without a detailed reason. No bypass or
repeat deletion attempted; these temporary resources remain. Existing Vite,
historical owner-retained QA data and target infrastructure are preserved.

### Parameters merged into Startup — owner follow-up

Removed the instance Parameters tab. Startup has separate ENV and Configuration
settings blocks; the latter renders only when package or authored parameters
exist. The existing ApplicationValueFields and parameters/environment writer
operations are unchanged, with no migration or value rewriting. Added tests for
empty hiding, package-only defaults and parameters-only save payload. Focused
editor15 PASS, lint/typecheck/production desktop build PASS. HTML mockup reflects
the two Startup blocks as well.

Actual React/Wails Add configuration parameter, edit, Review/Save/reopen and
reset/Save/reopen PASS on a fresh owned QA project copy. The ENV editor remains
separate. Evidence ui-parity-wails.json now includes startup-configuration cases;
no target operation was invoked. Original QA project context restored. Earlier
cleanup rejection/retention and the independent Core target acceptance remain
unchanged; this local UI follow-up does not relabel those gates.
Owner requested the UI commit and master synchronization. Final frontend
regression247 PASS/22files, lint/typecheck PASS. Unrelated SDKU package definitions,
tests, journal and their CURRENT_STATE row are excluded from the UI publication.
Commit-scope known-value audit:20 protected values,318 source/evidence files,
zero matches; no secret values printed. Publication identity is Git history.
