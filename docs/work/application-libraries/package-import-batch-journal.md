# Application package batch import

2026-11-02, owner-requested change. After the Wails launch rejection below,
the owner explicitly requested committing the completed change. This authorizes
publication without claiming real Wails acceptance.

Page-level application import captures all packages below a selected
`application-packages` directory in one existing structural plan/transaction.
Single application import is placed in the instance screen and bound to the
declared application ref. Library import remains a single version directory.
Core, deployment creation, execution and runtime bundles are unchanged.

Validation completed:

- Focused Go import tests pass, including empty/invalid/conflicting batch
  rejection, preview without writes and source changes after preview.
- Real repository packages: SZI, SDKU and CSPA library import/commit followed by
  complete corresponding application directory import/commit pass in isolated
  native Go test projects. This is supplementary evidence, not Wails acceptance.
- React component/page tests: 28 pass. TypeScript/Vite production build passes.
- A separate dev Wails executable was built in
  `.runtime/qa/package-batch-import/installer-import.exe`.

Real Wails acceptance is BLOCKED: automatic approval review rejected both
the configured QA-node launch and the reduced launch without SSH arguments.
The stated reason was only `blocked by policy`. No Wails process was started,
no UI import acceptance, deployment plan or installation was performed.
The temporary Vite server was stopped. Existing project/service data and
unrelated working-tree changes were preserved.

## Import diagnostics follow-up — 2026-11-02

The supported `wails dev` runner subsequently started successfully. The earlier
direct executable launch rejection remains historical, not a current blocker.
Owner's 36-file SZI layout was reproduced by omitting external Keycloak
providers/themes from a private copy of the repository packages. Real React
import handlers called real Wails Go review methods: missing `themes.tar.gz`
returned BLOCKED with the old generic diagnostic. Adding only that archive
returned READY with 37 documents. No installation or structural Save was run.

The diagnostics fix preserves validation/limits, publishes a Russian reason and
logical package/file path through the existing finding, and does not publish
file contents or raw YAML parser messages. Generic import form explanations were
removed at the owner's request.

Final-source Wails checks: missing archive returns APPLICATION_PACKAGE_INVALID,
field `application-packages/keycloak/1.0.0/assets/themes.tar.gz`, with the Russian
reason that a file declared in `files` is absent. Repaired source returns READY,
37 documents; structural plan `d38a4b63fff55d0b688f19d38f8108f4`, base revision
`sha256:ed631f43ba7e4f245a3e1f977c77bd01fb9ab3aaee6d1e8ec32460acc627c439`.
Both reviews were discarded through the UI; project bytes unchanged. UI screenshot
was visually inspected and shows the concrete Russian finding. No execution
plan/run IDs exist for these review-only tests. Safe results/screenshots are in
`.runtime/qa/import-reproduce/review-diagnostic-*.json` and
`.runtime/qa/import-reproduce/diagnostic-missing.png`.

Validation: `go test ./...`, final affected installer/desktop packages, focused
import/export tests and `go vet ./...` PASS. Three import React tests and the
TypeScript/Vite production build PASS. Native regressions cover missing/unlisted
files, forbidden paths, defaults version mismatch, unchanged blocked project
revision and content redaction.

## Automatic slot enrollment — 2026-11-02

Owner-approved policy: include every declared slot whose exact package ref is
available, including optional slots. Library creation sends an explicit authored
applications map through the unchanged v11 Create command. Application import
enrolls missing matching slots in all existing libraries in the same structural
plan/transaction as the captured package files. No Core, binding, placement or
runtime execution rules changed. Existing slot settings are not replaced.

Validation: full Go tests and vet PASS; targeted native transaction regression
covers shared package enrollment in multiple libraries, optional slots, exact
version exclusion, existing override preservation, review without writes and
stale-plan rejection with neither package nor YAML changes published. Twenty-nine
React page/import tests and TypeScript/Vite build PASS.

Real React/Wails checks in separate library-free QA projects:

- Library first (project-2026110200000004): library creation saves applications
  as an empty map while no application packages exist. Bulk import adds all five
  SZI slots in the same successful commit. Final revision
  1f90653dd5db122351eae7e486e5bab785fe3da228e2614f0c9e109666def1f7.
- Applications first (project-2026110200000006): import applications/library,
  then Add Library selects all five slots in its creation commit. Final revision
  305374d4eee10e0cae8d64eb75583eabb447f8788159fa5fd6de845339631f72.
- Both projects have an explicit node1 library placement. Actual Review/Save
  handlers and Wails Go methods were used, without fixture writes after opening.
  Safe results are under `.runtime/qa/import-reproduce/enrollment-library-first/`
  and `enrollment-apps-first-final/`. No installation approval/Start was invoked.

Current-source target-free Core prepare on RED OS102 using the saved library-first
project returns jobs5/findings0: the missing applications/mandatory slot defect
is gone. Full Project Verify is NOT PASS: the intentionally incomplete QA project
has no Nginx endpoint override. The existing SZI provided SSO proxy_url template
dereferences nginx.overrides when Nginx is selected; standalone Ansible templating
confirmed AnsibleUndefinedVariable for overrides. Native snapshot stops while
checking exported library values (changed0); Wails reports CORE_OPERATION_FAILED.
This separate template/configuration issue was recorded, not silently repaired
or counted as successful project validation. Service source/runtime untouched.

The first applications-first automation attempt used Playwright checkbox.check(),
which asserted before the asynchronous authored-placement response arrived. It
was replayed from a fresh project using the same actual click handler and waiting
for the checked state; no test-only production path was added.
Temporary RED OS workspace was removed with qa-sync. QA services/data preserved.

## SSO choices, inherited endpoint and instance deletion — 2026-11-02

Owner-requested follow-up: declared SSO exports are selectable without a successful
Core snapshot. SZI proxy/host templates tolerate incomplete endpoints and fall
back to a library group. One authored library endpoint selection is persisted in
the native x-extension and resolved by Ansible before explicit app overrides.
The selected instance header exposes deletion; reset retains the instance and
General can add an unselected declared slot again. Library deletion atomically
removes its memberships/endpoint selection, preserves packages and installed
resources, and blocks references from other libraries. Additive v12 leaves v11
semantics intact. No new Go file or persistence layer was introduced.

Validation:

- Full `go test ./...` and focused installer/desktop tests PASS; focused vet PASS.
- React page/bindings/import 41 PASS; TypeScript, lint, Vite and Windows Wails build PASS.
- Current sources synced with qa-sync to RED OS102: library tests29, endpoint
  Ansible tests5 and edit contract tests8 PASS. Tests exercise incomplete SZI
  templates, library-group inheritance through early topology and final snapshot,
  explicit app-group priority and invalid references. An obsolete assertion for a
  separate global APPLICATION_LIBRARIES_VERIFY was updated to the documented
  embedded-verify contract; execution behavior was not changed.
- Actual React handlers and Wails Go methods in independent QA project
  project-2026110200000012: library endpoint + SSO saved at
  sha256:9654b3db9eddf3a3179807b476cb26e0823c2db20e9a139781d49777237656fa;
  Keycloak removal saved at
  sha256:836e58000ead98481d36c46f2dd8b8d08ade4f56113c670fa251a34eaaee1e7e;
  adding Keycloak back returned to the same endpoint/SSO saved revision above;
  library deletion saved at
  sha256:4dfc8985229482f939bce7a4e9a2bb76c3a02f179a561e7b264ccf5415f34519.
  Remaining imported packages were confirmed available; memberships and library
  endpoint selection were absent. Safe evidence is under
  `.runtime/qa/import-reproduce/endpoint-delete-complete/`.
- First real bridge attempt exposed a missing Wails command allowlist entry;
  corrected and covered by production session allowlist tests. Automation retries
  corrected immediate assertions before asynchronous handlers completed and an
  exact wrapped-select label mismatch; no production bypass was added.
- Final empty-library screenshot inspected. This is edit/Save acceptance, not a
  full installation or blanket visual acceptance. Wails development IPC emitted
  existing runtime:ready/null-nodes warnings while requested flows completed.

No Approve/Start or service mutation was performed. UI checks used the existing
verified c97e77d7 runtime; new inheritance was checked directly with current-source
Core/Ansible on RED OS. No replacement bundle was published/activated. Distribution
requires a rebuilt runtime bundle and updated SZI package copies; updating the
Installer does not rewrite immutable imports in existing projects. Owned Wails/
Vite processes stopped; temporary RED OS workspace cleaned with qa-sync.

## Reviewed same-version package replacement — 2026-11-02

Owner chose retaining packages on instance deletion and permitting reimport with
replacement. Import now captures the complete incoming closure for each selected
name/version, keeps other versions, replaces changed files, adds new files and
plans obsolete declared files as PRESENT -> ABSENT. Limit accounting uses the
final closure. Existing library/application settings and references are retained.
Identical packages return NO_CHANGE; React discards the empty edit session and
shows the import completion message without a Save dialog.

The existing transaction writer now journals an optional deletion only for
existing application/library package files. It preserves before bytes/security,
revision/document guards and recovery, without recursive directory removal.
No Core, service execution or runtime-bundle source was changed.

Validation: full Go tests/vet PASS; focused tests cover replacement, obsolete-file
review/removal, identical retry, rollback after deletion on publication failure,
crash recovery with ACL preservation and rejection of non-package deletion.
App/import React104 PASS, lint/TypeScript/Vite PASS. Real React/Wails QA in
project-2026110200000013 used the standard Review/Save handlers:

- Identical existing SZI library: NO_CHANGE, form closed, no Save offered.
- Existing application-packages bulk replacement: COMMITTED at
  sha256:b9a5765bcf038d5291f5b4f8344dd82a3a78ec41839edd86cf149104a50b30ee;
  old Nginx asset was reviewed as ABSENT and removed; new asset bytes match.
- Identical bulk retry: NO_CHANGE without an active edit session.
- Existing SZI library same-version replacement: COMMITTED at
  sha256:668af57dbd8aec3def39b6cf8edfdf920691a2af0d3084182fb690d2039351ef;
  replacement defaults bytes confirmed. Desired-state YAML remained byte-identical.

Safe records/screenshots: `.runtime/qa/import-reproduce/reimport-replacement/`.
Replacement review screenshot inspected; this is not blanket visual or install
acceptance. Existing Wails dev runtime:ready/null-nodes warnings were observed;
requested flows completed. No Approve/Start or service mutation, artifact
acquisition or runtime replacement occurred. Owned Wails/Vite processes stopped.

## Fixed connection kinds — 2026-11-02

Owner requested locking the connection-type control for every library binding,
as already done for the library endpoint. The type select now contains only its
current fixed kind and is disabled; the referenced service/profile/export select
remains editable. New bindings use the existing connection-role presentation
filter and PKI hint, so SSO starts as providedConnectionRef even when no matching
export exists yet. Undeclared saved bindings retain their stored kind. A declared
kind mismatch is shown explicitly; the old desired binding is not rewritten
until the operator selects and stages a compatible reference. Save/reset paths
and Core compatibility rules are unchanged.

Validation: React bindings/page/App141 PASS, lint/TypeScript/Vite and Windows
Wails build PASS. Tests cover all disabled type controls, continued target edits,
SSO without candidates, aliased binding names, incompatible saved kinds and no
implicit write. Real React/Wails in project-2026110200000014 verified all six
kinds (endpoint, database, cache, SSO, secrets, PKI) disabled and targets editable;
SSO and TLS references saved through existing handlers at
sha256:bce323b8a5a1ef47ba324b936b79809278473f12e0676126424d853e488e3c5e.
Safe evidence: `.runtime/qa/import-reproduce/locked-connection-kinds/`.
The table screenshot was inspected. No Core/source schema, runtime bundle,
service, Approve/Start changed; existing development IPC warnings observed.
Owned Wails/Vite processes stopped.
