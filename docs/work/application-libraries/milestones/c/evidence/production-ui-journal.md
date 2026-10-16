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
