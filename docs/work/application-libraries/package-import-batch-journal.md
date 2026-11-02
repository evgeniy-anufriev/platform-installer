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

## Database defaults and pre-snapshot diagnostics — 2026-11-02

Owner requested immediate display/use of the databases declared in library
resource_defaults and concrete Core failure reasons. Existing Resources table
now renders PostgreSQL/ClickHouse declarations before Core succeeds; it does not
stage a draft on display. Editing stores only the selected override, and reset
removes that override. Existing controls/Project diagnostic area are reused.
Core selects those database declarations through the library/selected-app
connection metadata when the provider binding is unambiguous. Names continue to
resolve with native Ansible defaults/overrides; desired files are not rewritten.
Explicit resource IDs override defaults; Kafka/Redis selection is unchanged.

Pre-snapshot application tasks retain their original expressions and no_log.
An ordinary block/rescue publishes a safe adapterError through the existing
snapshot-output channel. Existing snapshot_input_message was extracted from the
snapshot action for reuse, rather than retaining a second classifier. It adds
bounded missing-field/variable identifiers and library/slot/host context; raw
exception values are never returned. Snapshot and earlier library calculations
now share that formatter. No new UI error rendering or Go error model was added.
Original task bodies were checked byte-equivalent after de-indentation.

Validation: focused RED OS suites application_libraries30, snapshot_output7,
snapshot_action10, native project-resolution1, resource-context1, connections11,
providers25 and endpoint-stage5 PASS (90 total). Native failures under no_log
cover missing sso/url/postgres with context and no private sentinel in stdout,
stderr or public artifact. Native database resolution succeeds without saved
resource entries and leaves desired YAML unchanged. React page/resources/App146
PASS; TypeScript/lint/Vite and Windows Wails production build PASS. Existing Vite
chunk-size warning and development IPC warnings were observed.

Updated current-source QA bundle 8f2f6f1c8c2e2a0690fe8cfd4c65ca6eaeb7053f21cf1617b4f7ffea740bed51
was built on trusted RED OS102, verified/published through the standard publisher
and prepared on101 through real React/Wails. No service installation or
Approve/Start was invoked. QA project project-2026110200000015:

- Revision8e25cf424b990d7ed376cd095b273067c36e126cbc91fb1a8eb66b51ad58dc42:
  keycloak/keycloak-db and szi_audit/audit-db are visible immediately. Header
  Verify returns PROJECT_SNAPSHOT_INPUT_INVALID with missing sso, library szi,
  application grant-access and node1. The existing Project area visibly shows
  the same reason; its screenshot was inspected. This expected invalid fixture
  does not constitute successful full-SZI verification/installation.
- Actual resource edit -> review -> Save COMMITTED at
  e6bcd06265d2a28651d5437994830521b1d6a776b0ad5202183896000fc54ef1.
  Only keycloak-db name custom_keycloak was persisted; audit-db remains inherited
  and visible. No freezing/copying of sibling defaults.

Safe outputs/screenshots: .runtime/qa/import-reproduce/db-diagnostics-result.json,
db-diagnostics.png, db-override-result.json and db-override.png. Distribution needs
an updated Installer plus rebuilt runtime bundle; existing imported package
settings remain desired inputs. No independent review was launched, per owner.

After QA, the prior verified c97e77d7 bundle was republished through the standard publisher and restored to READY on101 through React/Wails preparation. Both temporary RED OS source workspaces were cleaned with qa-sync; owned Wails/Vite processes stopped. Local QA bundle/evidence retained under ignored .runtime only.

## Project findings instead of unavailable Core; application ENV — 2026-11-02

Owner identified that the previous diagnostic fix still misclassified an
incomplete application as an unavailable Core operation. Library setting failures
now return APPLICATION_INPUT_INVALID findings with exact library/slot/placement
fields. Ordinary block/rescue records those findings with builtin set_fact and
continues other placements. Shared-default/connection failures use the same
path. Snapshot identity checks permit only missing placements explained by those
scoped findings; duplicates, unexplained omissions and changed packages retain
their technical failure. Project Verify returns INVALID with a PARTIAL snapshot;
existing project-error badges/links and infrastructure values are reused. No Go
status translation, UI status branch, execution permission or new DTO was added.

Owner also requested ordinary environment settings outside parameters. Keycloak
now has no parameter aliases: actual ENV defaults derive advertised IP/node ID
from the current placement and discovery peers from this library/slot only,
using effective published/container ports. Container bind defaults to 0.0.0.0;
Compose memory consumes KEYCLOAK_MEMORY_LIMIT from ENV. SZI cluster/realm ENV uses
existing identity/SSO context. SDKU URL defaults use endpoint configuration;
empty scalar aliases no longer shadow common Redis ENV. Structured IDENTITY_CLIENT,
IDENTITY_GROUPS and mount_sources stay in parameters per explicit owner answer.
Explicit ENV overrides retain normal Ansible precedence. Existing imported
projects are not rewritten; distribute/reimport the updated package copies.
SDKU import-catalog digests were regenerated with the canonical Core package loader.

Validation: RED OS snapshot_output7, snapshot_action10, project_resolution_native4,
application_connections11, application_providers25 and SZI projection3 PASS (60).
Native tests cover incomplete templates -> ordinary findings/retained service
projection, no_log secret-sentinel exclusion, unexplained missing rows still
failing, own-placement Keycloak IP/hosts/ports, and structured-only parameters.
SDKU28 schemas/digests and26 Compose renders PASS. Existing SZI presentation
fixtures were updated to current resolved SSO/host/provider context. React147
PASS including application-input INVALID status with retained dataDirectory;
TypeScript/lint PASS. No independent review, per owner instruction.

Current-source final QA runtime b57fc4b7e20a5631e5231002764dc67b85378f38827495a9a3305f7a1158cb0b
built on trusted102, validated/published with the standard publisher, and prepared
on101 through actual React/Wails. Real flows:

- project-2026110200000016 revision39bca75cbe97efce86b89e97651dee7d0255371d527a22721fa0aa24b261cf65:
  Header Verify INVALID, concrete missing-sso application findings, project-error
  badge instead of unavailable check; infrastructure dataDirectory retained.
- project-2026110200000017 revisionbdfb182dd4fb0b486ce300ca95ad4e345ebed468116db7d3e46599401be51f2b:
  Verify VERIFIED with only the existing unset-service-secret warnings.
  Keycloak on101/102 received corresponding IPs and the same ordered discovery
  list192.168.56.101[7800],192.168.56.102[17800]. Node2 container port7801 and
  explicit ENV memory4G/logDEBUG confirmed. Actual Applications -> Keycloak ->
  Startup ENV controls showed calculated values and host switching.
  Edit KC_LOG_LEVEL -> draft/review/Save COMMITTED at
  8c68141de1c7ed6b85161867465e0f60f5162b4ddf5f948ca63ff75727190881;
  authored value TRACE is under overrides.environment with no parameter alias.

Safe local evidence: .runtime/qa/import-reproduce/project-findings-{errors,env}.json,
matching screenshots and keycloak-env-save.json. Screenshots inspected for the
requested Project status and ENV location only; no blanket visual acceptance.
No Approve/Start or service installation was performed. Development IPC warnings
remain observed; these flows completed through real React/Wails methods.

Final Windows production Wails build PASS. After QA the previous c97e77d7 bundle was republished with the standard publisher and restored to READY on101 through real React/Wails preparation. Temporary RED OS source workspace cleaned with qa-sync; owned Wails/Vite processes stopped. Generated frontend outputs restored; unrelated guide/npm/portable-source work preserved.

## Runtime placement choices and reduced library UI — 2026-11-02

Owner requested library placement choices only on servers with a containerization
entity, removal of package/advanced-placement/shared-secret-source editors, and
reported sequential visible command windows during Project Verify.
Applications now filters authored host/member service placements by the selected
library runtimeRef, instead of listing every server or every Docker deployment.
Runtime changes immediately change the choices; absent/empty runtime placements
show an empty state. Hiding a saved incompatible placement does not delete it.
Existing structural placement commands, review/save and Core validation remain.
Package-reference, advanced host overrides and shared-secret-source sections are
removed from rendering; their stored metadata/defaults are preserved.

The missed Windows process was fsutil hardlink list in readStableCandidateFile,
called for each candidate project/package file. It now uses the existing
commandwindow.Configure (HideWindow + CREATE_NO_WINDOW), as SSH/SCP already do.
Without a console, fsutil localizes its error label; the existing unsupported-FS
exception now matches the stable numeric Win32 code50 instead of English Error50.
Other failures, multiple links and existing file identity/size guards still block.
No new Go file/process abstraction, Core rule or SSH/trust request was introduced.

Validation: Applications33 + App102 =135 React tests PASS, TypeScript/lint PASS;
full Go tests and vet PASS. Uncached executionnode suite PASS. Focused candidate
archive/package-revision tests also ran with temporary files on the workspace
NTFS volume: positive archive/limits and hardlink rejection PASS; existing
Windows case-collision skip unchanged. This covers both localized unsupported
Temp FS and actual NTFS hardlinks with hidden fsutil execution.

Actual React/Wails project-2026110200000018 used existing verified b57fc4b7 Core
runtime (unchanged Core sources). Initial revision
9b0c9d1b29c7e433681a3b0cf883646c17f89886580e4130349eeff2e7e4e85a:
Docker selected -> node1/node2 only; docker-alt selected -> node3 only.
Runtime edit was discarded through normal Review/Cancel. Removed panels absent
in General/Resources. Unchecking node2 -> Review/Save COMMITTED revision
89ab4565efe808d4e0c53f0b92a78baa54a69aa8ad5747391fd6f40dfdc4a1e0;
node1 library placement retained and Docker's node2 placement unchanged.
Header Project Verify through real Go/SSH/candidate-file checks finished VERIFIED
with only three existing unset-service-secret warnings. No service installation
or Approve/Start occurred. Core sources/bundle semantics were unchanged.
Safe evidence: .runtime/qa/import-reproduce/placement-ui-result.json and
placement-{general,resources}.png. Screenshots inspected for requested removed
sections; transient native-window visibility was not claimed as a full visual
observation. Windows process flags and the actual Verify path were exercised.
Development IPC warnings remained observed. No independent review per owner.

Windows production Wails build PASS. Prior c97e77d7 cache/runtime restored through the standard publisher and real Wails preparation (READY); owned Wails/Vite processes stopped. Generated frontend outputs restored; unrelated guide/npm/portable-source work preserved. No new runtime bundle is needed for these UI/Windows-launch fixes.


## Registry Save session retention (2026-11-02)

Owner reported that registry Save dropped node/target checks and session secrets.
Successful structural Save previously cleared every target pin; React also
cleared all server facts on every project revision. Preserve confirmed target
keys only across the exact committed old/new revision when project/root and
SSH host/address/port still match. Removed/changed targets and failed refresh
remain revoked. Existing saved-project revision and SSH pin validation remain.
Server facts now follow project identity and transport endpoints, not arbitrary
configuration revisions. New plans and approval are still required after Save.

The unchanged startup EXPLICIT_EXTERNAL connection now follows the same Save
retention as PROJECT_SERVER: preserve readiness and project-bound pending
secrets; detach old descriptor evidence and re-attest before execution. No
secret lifetime extension or new persistent storage, SSH probe, Core rule or
service-specific secret handling. Existing tests cover application, service
and PKCS pending inputs; address changes revoke target trust. No review per owner.

Full Go tests/vet PASS; React App102, TypeScript and lint PASS. Actual React/Wails
flow used a separate copy of the c97 locked QA project, existing READY runtime,
real Kafka secret dialog and registry add/Review/Save handlers. PKCS was seeded
through the existing Wails method as a supplementary check. Saved revision
911217d47790021cfbb927a675f35067f2503f521d6595ad57dd73f24f22f5a1:
node READY, Kafka secretsInstalled=true, PKCS PRESENT, server facts retained.
No Approve/Start/service installation or runtime bundle replacement. Initial
automation retries used incorrect Registry textbox / status-chip locators; the
corrected real UI flow passed. Visual inspection not claimed. Existing dev
runtime:ready/nodes warnings observed. Production Windows Wails build PASS.

Separate owner question: registry credential form calls GetRuntimeSecretDescriptors
before showing inputs. Its current transport stages the project and invokes
Core describe-runtime-secrets; each click can repeat that work. Latency/caching
is not changed by the session-retention fix. SSH/SCP/fsutil use the existing
hidden-window helper in current source; no new visible-console fix claimed.


## Registry credentials without a Core round trip (2026-11-02)

Owner requested local registry input like pending service credentials. The
existing registry form now opens from saved authored username/password sources;
no descriptor query, project staging, SSH or Core call on open/Save. Source
identifiers are not shown. Values stay in the existing Broker's project-bound
pending bucket, with bounded expiry and clearing. No new Go files/endpoints or
persistent credential storage. Existing SetDeploymentRuntimeSecretValues accepts
an additive authored-source submission, guarded by exact saved revision, library
and source membership; draft/foreign/mixed submissions are rejected locally.

Core still owns requirement IDs and execution admission. Existing validated
application descriptors map sourceRef to requirementRef during promotion; image
preparation also consumes this mapping. Unselected sources cannot be delivered.
Replacing a registry value with current Core evidence updates its attached
value; otherwise it waits for normal Core attestation. Other service/application
and PKCS inputs remain in the same pending session.

Full Go tests/vet PASS, including no-Core/offline input, stale revision/foreign
library/source/draft rejection, source expiry/zeroing, sibling-service retention,
and replacement values in image-preparation payloads. React138, TypeScript/lint
and Windows production Wails build PASS. No review per owner. The source test
initially exposed empty unmapped-source promotion rejecting an empty target map;
corrected to leave unattested sources pending, final suite passed.

Actual React/Wails on the existing c97 READY runtime: saved project revision
911217d47790021cfbb927a675f35067f2503f521d6595ad57dd73f24f22f5a1;
registry button -> four fields for two configured registries -> session Save
PASS. Measured opening18ms in this single QA run; intercepted real
GetRuntimeSecretDescriptors count0 for open and Save. Project revision unchanged.
Core/Ansible sources and runtime bundle unchanged; no plan approval, installation
Start or registry login/pull executed. Source-to-requirement consumption tested
through existing Go contract tests; no new installation acceptance claimed.
Owned Wails/Vite processes stopped, generated outputs restored, unrelated work
preserved. Updated Installer only is required.
