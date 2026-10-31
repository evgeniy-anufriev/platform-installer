# Project Verify snapshot failure diagnostics

Owner requested concrete safe reasons for PROJECT_SNAPSHOT_INPUT_INVALID and
publication to GitHub on 2026-10-30.

The snapshot action now identifies the failing resolution stage and maps known
input failures to fixed messages (missing/invalid documents, inventory selection,
catalog references, application artifact lock conflict and resolution identity).
Unknown exceptions expose a fixed category and stage, never exception text,
input values, parser excerpts, filesystem paths or dictionary keys.
The existing finding code and snapshot/verification contracts are retained.
Go retains bounded matching findings from typed ExecutionError on Verify failure;
the Project page shows those summaries beneath its existing general error.
This is a bounded diagnostic correction within the existing safe-finding path;
it changes no desired-state ownership, writer, execution or trust semantics.

Verification:

- `go test ./internal/desktop ./internal/executionnode -count=1`: PASS.
- `go vet ./internal/desktop`: PASS.
- `npm test -- --run src/App.test.tsx`: 87 PASS.
- `npm run typecheck`: PASS.
- Added Core action tests for missing document, parser-content exclusion and
  closed reason vocabulary. NOT EXECUTED: strict SSH connections to configured
  RED OS 192.168.56.101 and .102 both timed out on port 22. No local Windows
  Python/Ansible execution or installation was substituted.
- Real React/Wails -> updated Execution Node Core acceptance is OPEN, not
  replaced by mocked frontend or direct Go tests. New desktop build and a new
  verified/published/bound runtime bundle are required to deliver both halves.
  No bundle build/publication/activation or installation run was performed.
- No visual inspection PASS is claimed; unrelated dirty work is preserved.

## Follow-up: callback fallback and owner no_log instruction

The owner screenshot showed callback fallback `Project snapshot could not be
built`, not an action finding. The resolution role's snapshot task used
task-level `no_log: true`, which also censors safe findings before callbacks.
The original correction did not cover this path.

Owner explicitly requested removal of no_log from this task and an actual
diagnostic without speculative alternatives. The task flag is removed. Private
cached resolution objects are referenced by two fixed task-variable names inside
the action, rather than templated into arguments. Successful private results
retain `_ansible_no_log: true`; only the public snapshot is written to the
existing output artifact. Failed results publish only the fixed safe finding,
adding actual exception category and code basename/line within the 512-byte
limit. Raw exception text, source excerpts, locals and private configuration
are excluded. Callback preserves that finding. A failure before publication
has a factual fallback without alternate guesses.

Added tests for censored failures, private success result protection,
malformed/oversized/symlink artifacts and native Ansible task failures with
no_log both true and false. After owner startup of RED OS101, current-source
combined bootstrap/snapshot action/output/native resolution/preview suite:
35 PASS (35.115s), no skips, Python3.11.15/Ansible Core2.18.15. Native no_log
failure publication and private-success register/output exclusion passed.
Initial34 PASS/1 FAIL was an obsolete callback wording assertion, corrected
to verify the stable diagnostic code and nonempty safe message. Production
behavior was unchanged. Both qa-sync workspaces were removed and their absence
confirmed. Previous SSH unavailability is historical. Real Wails acceptance OPEN.

Independent FULL DIFF of the initial filtered-publication change and one revised
FULL DIFF after the owner's explicit task-no_log removal instruction both
returned APPROVE_WITH_CHANGES, zero blockers. Revised review recommendation
SDO-N02 (native successful private-register/output check) was incorporated into
the test source; SDO-N01 negative artifact cases were also added. These added
tests now passed on RED OS101 as recorded above. `git diff --check` PASS. No Go/React code changed
in this follow-up, so their earlier results are not a native acceptance claim.

## Explicit root and implicit localhost regression

Owner's manual project-snapshot run exposed a pre-action templating failure:
`platform_project_root | default(inventory_dir | dirname)` evaluates its filter
argument even when an explicit root is present. An implicit localhost does not
have inventory_dir. The action cannot return its structured finding because it
has not started, explaining the callback fallback shown by Project Verify.

Use Ansible's lazy conditional at the nine equivalent root fallback expressions
in resolution/validation and application provider/runtime tasks. Explicit root
remains authoritative, ordinary inventory-root fallback remains available, and
no new defaults, path discovery, persistence or precedence implementation is
introduced. Existing fixtures explicitly declared localhost and therefore
masked this issue.

RED OS101 regression: remove localhost from the representative inventory and
run the production project-snapshot.yml with an explicit relative project root,
once with application libraries and once without. On the isolated baseline with
the two old role expressions restored, both cases failed. Restoring current
sources and verifying them with qa-sync produced37 PASS in36.436s, zero skips,
for native resolution, bootstrap, snapshot action/output and preview tests.
Native Ansible Templar additionally evaluated all nine production expressions
with undefined inventory_dir and explicit root, then with ordinary inventory
fallback. Both branches passed. No target contact or installation was performed.
Real React/Wails acceptance after delivery of a new runtime bundle remains OPEN.

## Prepared-node retention during topology drafts and Verify findings

Owner reported a prepared node reverting during topology edits and an INVALID
Project Verify with an empty diagnostic area. Investigation found two separate
presentation/lifecycle faults: a saved Core preview finishing after a draft opens
could pass through operation-only binding validation and revoke the prepared
binding; GetExecutionNodeContext omitted its runtime digest while editing.
The draft operation guard now rejects operations without revoking trust merely
because a draft exists. Saved-only presentation/publication checks retain the
same endpoint, identity generation, credential availability, host-key pin,
command guard, runtime bundle and saved revision checks. No new Core request is
started for an open draft. Preparation does not authorize execution or retain
an old approved deployment plan after Save.

The Project page previously displayed findings only when Verification.error
was present, hiding ordinary INVALID results. Its counter also depended on a
separately loaded snapshot rather than the current verification evidence.
It now displays current-revision verification findings with code, summary and
subject and severity, including truncation notice; old-revision findings remain
hidden. Warnings are not styled as blocking errors.
The owner's screenshots compare different revisions: manual PASS 767dcc1f...
and UI INVALID 6ae9d4ab.... They are not evidence of contradictory validation of
the same saved bytes.

Validation: desktop regression suite and go test ./... PASS; go vet ./... PASS;
App frontend 93 tests PASS; frontend typecheck, lint and production build PASS;
Windows Wails production build PASS. Tests cover draft operation rejection
without readiness loss, repeated context reads retaining runtime digest,
credential revocation during draft and late preview rejection after saved
endpoint/credential/host-key/command guard/bundle/revision changes. Go race
runner unavailable with this environment's CGO disabled. Real React/Wails
prepared-node/topology/Verify acceptance remains OPEN, not replaced by these
unit tests or compilation. No Core source or runtime bundle change is required
for this desktop/UI correction. Independent FULL DIFF review of six source/test
files at base fcbf4a02 returned APPROVE_WITH_CHANGES, zero blockers. Nonblocking
DBR-N01 (require a nonempty verification revision) and DBR-N02 (distinguish
warning presentation) were corrected with regression tests. The review
fingerprint before these bounded corrections was
d4c19952eb33a42be7fab9e3f807d01731071c72702dcad32d12eaebb72d7228.

## Missing secret reference and header navigation

For RUNTIME_SECRET_REFERENCE_REQUIRED, desktop presentation now names the
service deployment and configuration setting from Core's existing `field`
path. Only the closed `serviceDeployments.<id>.configuration.<setting>` shape
with bounded validated identifiers is rendered. Invalid, oversized or deeper
paths retain the safe Core summary; configuration and secret values are never
read. No Core requirement semantics or public DTOs changed.

INVALID and technical Verify errors share the existing status-chip--danger
palette in the header and are buttons navigating to Project through the
existing requestPage handler. Previously ordinary INVALID was a green readonly
div; technical failure already navigated but used the green readonly class.
This resolves a discrepancy with the shared findings/status visual language.

Validation: go test ./... and go vet ./... PASS; App 95 tests PASS, including
navigation from Servers through both failure badges to the detailed Project
finding. Typecheck initially caught an unsupported test-query option; removed
it, frontend typecheck/build and lint PASS. Go regressions check two different
instance/setting pairs and reject unsafe/oversized/deeper diagnostic paths.
Real React/Wails acceptance and visual inspection remain OPEN; mocked frontend
tests and production compilation are supplementary evidence.

## Project Verify warns about missing service secret references

Owner clarified that missing service secrets are advisory during Project Verify;
the existing plan generation and approval admission must remain unchanged.
The snapshot action copies only RUNTIME_SECRET_REFERENCE_REQUIRED findings to
WARNING. Invalid references and other findings keep their original severity.
Snapshot aggregation retains warnings and counts them without treating them as
partial/blocking or blocking per-service readiness. A complete warning-only
snapshot remains PASS, with validation PASS, and Go retains VERIFIED evidence.
No new status enum or DTO was added. UI projects current-revision VERIFIED
evidence containing WARNING as the existing yellow status palette with
“Проверено с предупреждениями”; the badge still opens Project details. The
instance/setting diagnostic advises configuring the reference before plan
approval. Plan implementation and approval guards were not changed.

Current-source RED OS101 suite: 51 PASS in32.096s (snapshot model/action, native
project resolution and deployment plan). Actual standalone project-snapshot.yml
cases cover absent Kafka adminCredential with and without application libraries
(WARNING, complete PASS) and malformed reference (BLOCKED, PARTIAL). Snapshot
tests cover warning-only and mixed blocking/warning counts/readiness and schema
validation. Plan regression confirms a diagnostic plan is returned with its
existing BLOCKED credential finding; missing references are not downgraded by
the planner. No target installation or contact was performed. Final workspace:
/var/tmp/platform-installer-qa-19a62593b80249b99baf29f36e82d864; initial workspace:
/var/tmp/platform-installer-qa-da5c9477c25548a7a70a02c30315ba3b. Both cleaned and
absence checked after QA.

Go tests/vet PASS; App95 tests PASS; frontend typecheck/lint/build and Windows
Wails production build PASS. Real React/Wails acceptance of the updated runtime
bundle and visual inspection remain OPEN. Delivery needs both the updated
Installer and a rebuilt, validated/published/rebound runtime bundle; this task
does not publish a bundle or change a production node.

## Keep editor screens available after the first Core projection

Owner requested that Services, Applications and Installation be gated only
until the first successful Core projection for the open project. App now
separates in-memory navigation admission (project root/identity) from current
revision/runtime-matched Core evidence. Subsequent Save, refresh waits and
preview errors do not disable navigation or unmount the selected screen.
Opening another project resets first-projection admission. Initial failed,
diagnostic-only or mismatched responses still cannot open these screens.
Pending/error notices remain visible; service effective values are still passed
only from a current matching preview. Existing backend Plan/approval/Start
authority and editor structural safety guards are unchanged. Background
projection requests still refresh saved revisions.

App97 tests PASS; after adding the recovery assertion, focused Save/initial
gate/admission/failure/recovery/project-switch4 tests PASS. Frontend typecheck,
lint and production build PASS. Supplementary ApplicationsPage/InstallationPage
suites:77 PASS,2 FAIL. Both failures are in unchanged InstallationPage.b4.test.tsx
(`B4 excludes infrastructure, leaves libraries Apply/Verify and requests only
that scope`, and `B4 hides approval for a plan from a different selected scope`),
which directly imports unchanged InstallationPage, not App. They expect existing
scope-related notices that are absent for those fixtures; this task does not
change that component or its tests. These failures are not reported as passed.
Real React/Wails acceptance and visual inspection remain OPEN. This UI-only
change requires an updated Installer, not a new runtime bundle.

## One password entry, saved data paths and consistent required-secret metadata

Owner reproduced a service secret dialog that appended an internal reference
to the draft, discarded the entered password and stayed open asking for it
again. Remove that early return: the existing catalog-authorized pending setter
accepts the original password in the Broker and the dialog closes normally.
The normal guarded project Save persists only the generated reference. Reopening
the dialog before Save reuses a matching configuration intent, rather than
adding duplicate references. Operator messages ask for a password through
Secrets; operators do not configure runtime references manually.

Use the existing ClearAttachedRuntimeSecretValues during successful Save and
unchanged prepared-node refresh. It revokes previous Core descriptor evidence
and attached target values while retaining project-bound pending inputs under
their original expiry. Failed refresh, credential/trust replacement, project
close and explicit strict clear retain the full cleanup. Legacy password
promotion now keeps its original pending input for repeat Core attestation,
as typed Kafka inputs already do. No new store, API, timer or Go file was added.
Fresh Core requirements still gate every promotion; stale/removed requirement
sets fail closed and may require clearing/re-entering session inputs.

The service editor keeps the matched saved-revision Core preview visible while
a local draft exists, with a clear saved-version/draft-not-calculated notice.
An explicitly edited setting still uses its pending override instead of the
saved projection. This prevents an unrelated secret-reference intent from
blanking dataDirectory without treating draft values as resolved Core output.

The shared secret requirement checker previously ignored mode-level
x-requiredRuntimeSecretSettings and saw only Kafka's x-runtimeSecretRequired.
It now reads the already-published mode metadata for all services. Core keeps
Project Verify's WARNING mapping, while diagnostic plans retain blocking
credential findings for approval. Tests read real Kafka/ClickHouse/Redis/
PostgreSQL manifests across their modes and exercise native project snapshots
with absent Kafka and ClickHouse credentials.

Validation: RED OS101 current-source snapshot model/action, native resolution,
deployment-plan and service-preview suite62 PASS in30.523s. Workspace
/var/tmp/platform-installer-qa-e0f311f72bfa47a6b7e9b319c4793691 cleaned after QA.
Go tests/vet PASS. App97/typecheck/lint PASS. Regressions cover one-entry password
submission, reopening without duplicate edits, retained dataDirectory, pending
scope/expiry, no attachment before Core proof, repeat legacy/typed promotion,
changed requirements rejected and buffers wiped on strict clear/expiry.
Frontend production build and Windows Wails production build PASS. Independent
FULL DIFF review APPROVE, zero blockers; fingerprint of ten source/test files
at base3bf0d036:
46189c39fec5c87410b5ee5a71397eabdfa32eda13db309f588bdbd0c736e302.
Nonblocking SSR-N01 (duplicate intent on reopening) and SSR-N02 (promotion
documentation wording) were resolved in this reviewed change. Real React/Wails
acceptance with an updated bundle and visual inspection remain OPEN. Delivery
requires updated Installer and runtime bundle for the mode-metadata correction.

## Retain displayed Core values through refresh/errors and localize findings

Owner requested that previously resolved data directories remain visible during
Core refresh, invalid Project Verify and incomplete Core output, without adding
last-calculation labels. App keeps display values alongside the unmodified latest
Core response in the existing observation state. Successful resolved values
replace the display value; absent/deferred fields retain previously resolved
values. Deployment and member settings are both merged. Root/project identity
and deployment type guard reuse; another project cannot inherit the displayed
values. Explicit pending overrides retain precedence in the editor. The latest
response, not the display merge, remains the basis of current-projection checks.
No display cache is sent to Core or used to authorize plan approval/Start.
Technical failures remain visible and retryable even if a matching earlier
response exists. The existing Core notice now states only that values came
from Core; it does not claim all displayed fields match the latest revision.

Owner also requested code plus Russian description for every project finding.
Existing desktop diagnostics now contain Russian descriptions for all literal
finding codes published by the current Core module_utils/action sources and the
generated HAProxy boolean/count codes. A coverage test fails when a published
literal code lacks a translation. The code/severity remain unchanged. Safe
logical field paths identify affected settings; malformed/private paths are
excluded and output remains bounded. Native Russian stage/cause diagnostics
are preserved; unknown future codes receive a Russian fallback with their code,
without raw English/parser output. HAProxy's missing endpoint identity and
certificate SAN mismatch retain distinct explanations.

Validation: App98 PASS, including delayed and failed refresh, empty/deferred
results retaining dataDirectory, new results replacing it, INVALID verification
remaining visible and project isolation. Frontend typecheck/lint/build PASS.
Go tests/vet PASS, including translation coverage, exact screenshot codes,
unknown-code fallback, Russian stage preservation and safe setting details.
Real React/Wails and visual acceptance remain OPEN. These presentation changes
require an updated Installer only. TLS default/profile-selection policy is a
separate owner discussion; it is not changed by this patch.

## Explicit TLS profile selection through ordinary Save

Owner-approved auto-selection uses the existing structural candidate and
configuration command: an absent managed deployment TLS-profile setting gets
the alphabetically first project profile. It is included in the ordinary
review diff and committed by the guarded writer. Existing selections remain
unchanged, including when an earlier profile is later added. Profile creation
after service creation also fills absent bindings on Save. Metadata is read
locally; unrelated Save remains possible without an available catalogue.
No new Go file, DTO, persistence mechanism or runtime selection is introduced.

Seven role defaults now declare an empty TLS-profile string rather than a
hardcoded name. Package-default validation recognizes only a string TLS
reference as unset; authored constraints remain enforced. Core reports
TLS_PROFILE_REQUIRED for service modes declaring that reference without a
resolved selection. Its Russian description instructs creation of a profile
and ordinary Save. Verify/preview do not mutate desired state. Docker and
ClickHouse retain standalone prepared TLS-directory support; actual Ansible
Templar guards are covered by tests.

Validation: current-tree RED OS101 contract/resolution/preview/snapshot/native
resolution/PKI/HAProxy/plan/catalog/bundle-fixture suite136 PASS in41.578s.
Temporary workspace fc7d9230ebb54d28984e68a093b0686e cleaned with qa-sync.
Frontend production build and Windows Wails production build PASS.
Independent FULL DIFF: no open implementation defect or unnecessary abstraction;
BLOCK TLSA-02 because mandatory real React/Wails Save/reopen/late-profile/Verify
acceptance remains OPEN. TLSA-01 standalone undefined-variable regression was
resolved before final review. Fifteen-file source/test fingerprint at base
befc88459e27ab179924410ac47b8ffc39e1e4ee:
9d6d07c181c06893f159aa0fdea0138de6c9ed31aa3106e7c7ee9dcc4cec0926.
No complete acceptance or updated runtime-bundle publication is claimed.

### Owner-authorized real React/Wails acceptance, 2026-10-31

The owner explicitly requested closure of TLSA-02. A separate standard Wails
development bridge34147 with Vite4187 exercised actual React handlers and
bound main.App methods using the installed headless Edge. Only the native
project folder picker was substituted by original OpenProject at the known
QA root. No business response, Save, Verify or Core method was mocked. The
already-running Installer in another worktree was preserved.

Current sources were synced with qa-sync to RED OS101 workspace
/var/tmp/platform-installer-qa-d8d7b7b44e3245508a4fc8e0013c50d9. This existing
Python3.11/Ansible2.18 host built the bounded empty-package QA bundle; no fresh
target bootstrap or SI11 installation was performed. Node102 was unreachable;
the failed transfer did not produce a confirmed QA workspace there. The bundle
was verified/published by the standard publisher into active cache before the
Wails flow, with the previous cache preserved by that publisher in
.runtime/qa/tls-autoselect/prior-cache. Project lock and READY runtime matched
sha256:ec04b2241e197d6dd497ece6eb352a07b4a2b2d2e40c1b97a26b6d8460424ba1.
The real credentials form used only the established private-key path; SSH
approval followed an independent match with trusted known_hosts. Existing
prerequisites were reused. No deployment plan approval, Start or service
installation occurred.

Results in .runtime/qa/tls-autoselect/exercise-results.txt and
late-resume-results.txt (controller acceptance.cjs):

- tls-ui-project3: two profiles created through React, alphabetical a-tls
  selected by ordinary Review/Save at revision
  sha256:7361beabb2132b628d0437020a304a7172da9de42252198b71cee27d631f48b3.
- Manual selection z-tls persisted at revision
  sha256:664a06b1eae315924d677e117bb56c762bf9976221b7fd5e27303c81535d83ba.
  Adding earlier aa-tls preserved z-tls at revision
  sha256:e69c22506da9b6d91ac0c408e375b6dab8d8f2ea813071c90566db3d3093b101;
  actual Close/Open controls preserved it after reopening.
- tls-ui-late: local Save without profiles succeeded. After supplying valid
  host placement, UI Project Verify at revision
  sha256:8197a0b233be8069e2acc819c815cd5ec334f41b9765d8fcb93527f64be11cb9
  displayed BLOCKED TLS_PROFILE_REQUIRED, a Russian description and
  serviceDeployments.haproxy-qa.configuration.tlsProfile. Verify did not
  author a selection. The earlier unplaced fixture correctly reported
  topology errors before configuration evaluation; placement fixed the
  fixture without changing production code.
- Adding the first z-tls profile later and ordinary Review/Save persisted
  the binding at revision
  sha256:c83e37cd5e05febbf596368168a7b1f640fe366ba788f9c62af3b2f28c3a781b.
  Adding a-tls preserved z-tls at revision
  sha256:083935fafe659db860b43572c898fc2028e58020de845b4bc0643763ad5bc7da.

Both successful flows recorded zero React page exceptions. These are nonvisual
React/Wails acceptance results; visual layout and native-picker acceptance
are not claimed. Full installation/offline-artifact completeness is outside
this authoring/Verify test. The established development seam excludes the known
Wails IPC startup exception from React failure accounting.

Independent TARGETED_RECHECK APPROVE: TLSA-02 RESOLVED, zero open blockers;
the original fifteen-file source fingerprint remained unchanged at HEAD
2011b7516f5a1f456d55495d50e8e91393f832be. The reviewer directly inspected the
controller, both successful logs and canonical project selections/lock. This
closes the earlier nonvisual acceptance block; visual/native-picker and full
installation acceptance remain outside scope. Owned Wails/Vite/browser
processes were stopped, the node101 source workspace cleaned with qa-sync,
and the previous local active cache restored through the standard publisher.
The verified QA runtime release remains installed on node101; no service
deployment was changed. QA source bundle and safe local evidence remain under
.runtime/qa/tls-autoselect for reproduction. Final Go tests/vet, frontend
production build and Windows Wails production build PASS.

## Service defaults and shared verification UI, 2026-10-31

Owner requested native Core display of Docker accountName/dataRoot, numeric
Kafka member nodeId defaults, hiding unsupported settings, a single header
verification action with findings on Project, BIND TTL300 and automatic
DNS-client selection. No Go file, DTO, desired-state store or UI infrastructure
resolver was added.

The existing snapshot action renders only Docker's two ordinary role-default
expressions through Ansible Templar with lookups disabled, a bounded context
of the project prefix and already resolved ordinary settings, and the existing
presentation-value admission. Explicit settings retain precedence; authored
expressions remain deferred. The private resolution is not mutated and both
fresh and cached previews use this calculation. The shared configuration
resolver derives absent Kafka nodeId from a member's terminal numeric suffix,
within the nonnegative 32-bit range; explicit values, including zero, win.

BIND declares platform_bind_default_ttl300; DNS resolution applies the same
default only when defaultTtl is absent. A single DNS-reference helper selects
the first BIND ID when dnsServerRef is absent, and is used by validation,
configuration resolution and native DNS-client projection. Explicit invalid
references still fail validation. No implicit value is written by Verify.

Services hides unsupported/advanced editor placeholders, while member-only
settings appear only in the member section. Certificates retains current
identity/SAN evidence, with no separate Verify/error panel. Entry points and
Topology omit duplicate Core findings/check summaries. Header Verify and
Project diagnostics remain authoritative. The UI design records this owner
refinement over the earlier mockup behavior.

QA: current-tree RED OS101 suite155 PASS73.990s, including real Ansible Docker
cold/cached previews and native DNS-client projection with absent reference/TTL.
BIND16 and DNS-client8 contract tests PASS. An initial expanded run155 had one
test-artifact isolation failure: the native test used the standard validation
artifact path within the temporary source tree. The test now supplies its own
temporary output path; the clean final suite passed. No bundle-builder source
change was needed. Frontend App/Certificates/Topology124 PASS, typecheck/lint
PASS; the final scope-filter regression covers unsupported and member-only
fields. Go tests/vet PASS. Production frontend and Windows Wails builds PASS.

Actual nonvisual React/Wails: separate dev bridge34147/Vite4187 with installed
headless Edge, actual handlers and bound Go methods. Only the native folder
picker was substituted by original OpenProject at the known QA root; no
business response/Save/Verify was mocked. A Verify wrapper observed the original
method's completion without changing its result. Existing unrelated Installer
processes were preserved; no Plan approval, Start or service installation.

Docker/Kafka source bundle8db5b2e4160d4448c5837f72057a206ac364fe41df85fec3769a061d80dec6ee
was standard-published before readiness. Project docker-kafka-ui3:

- Default account docker and /home/docker/.local/share/docker displayed.
- Prefix qa produced qa-docker and /home/qa-docker/.local/share/docker at
  revision34231867dc682be75e619001bc6c57510b1db72f99d62e811ae7bc87b7840a15.
- Explicit account operator recomputed the path at
  revisionab9e7086bbaed76d63e4466525e61d4a91bdda12b8b95e299c7cb89b6aa5ec22;
  explicit /data/custom remained at
  revision8df460e9dbf94cc39ed7006fd209b09f41c1bfc2dbc3e650d22f8b91246eed36.
- Kafka kafka-1 displayed nodeId1; manual42 persisted at
  revision331285c0bd0099cb886991ceaf98e5d973c040ab9c1e9826fb3fae4694daabb7.
- The real flow exposed and corrected a member-only setting duplicated as a
  deployment read-only row. The final flow has no unsupported placeholders.
- Header Verify returned VERIFIED with two missing-password warnings. Actual
  Project showed both Russian diagnostics; Certificates/Topology did not.

Final source bundle0f1524ab444fdc35b9ca8768e3c311f7b6e1e25b917310dec09f1e23a3f60c38
was standard-published before the DNS flow; the project lock and READY runtime
matched. Project dns-default-ui created z-dns before a-dns through React:

- TTL300 displayed at revisione23be2264cc95311a6e3b16398a9c54b0c355dd6aa11e151d34aecb6d67939a6;
  explicit900 persisted at revision37ce8eea00ae1db33829e1a45de301e36604f07f49ee71e8fc62a799bd6b5eb6.
- Core displayed a-dns as the default client reference without writing it to
  desired state; manual z-dns persisted at
  revision624405d3e2690120b004a02a7a3ec932037ea1efaad530404df48d175c1cd711.
- Header Verify returned VERIFIED with zero findings. Both successful flows
  recorded ERRORS=[] excluding only the established Wails IPC startup exception.

Safe controllers/logs and test projects remain in .runtime/qa/docker-preview.
QA runtime activation reused installed prerequisites; SSH trust was compared
with independent known_hosts before explicit approval. The final QA release
remains installed on101. Owned Wails/Vite/browser processes were stopped and
temporary source workspaces cleaned through qa-sync. The prior local active
cache was preserved and restored through the standard publisher. Visual/native
picker and full installation/offline-closure acceptance are not claimed.

## Artifact plan diagnostics — 2026-10-31

Installer now preserves Core's finding field and joins it to the full artifact
requirement ID (including service deployment), then displays the service ID,
artifact name and required version beside the original diagnostic code and
Russian description. Identical codes and requirement IDs across different
services remain separate. Source selection, plan blockers and approval rules
are unchanged; Core/bundle changes are unnecessary. Missing legacy context
retains the Russian description; invalid control characters or oversized
identity fields are omitted rather than printed.

Focused Go tests cover exact cross-service joins, missing/unmatched context,
Russian descriptions, duplicate codes, unspecified versions and unsafe display
fields. Full `go test ./...`, `go vet ./...`, frontend production build and
Windows Wails production build passed.

Actual React handlers called real Wails methods and RED OS101 Core using the
standard-published QA bundle0f1524ab444fdc35b9ca8768e3c311f7b6e1e25b917310dec09f1e23a3f60c38.
Project artifact-diagnostics-ui saved revision
3fc15c4f1cc5c48c737d1389d7137f762b8e9e1566f78f46f7d2fceca82043bd.
Fresh plan91ef2a39acfe136403a88e14 returned PLAN_BLOCKED; its actual Installation
findings displayed service kafka, artifact kafka version4.3.1 and artifact
confluent-schema-registry version8.3.2 with Russian descriptions and unchanged
ARTIFACT_SOURCE_OFFLINE_REQUIRED codes. No approval or execution occurred.
React exceptions0 excluding the established Wails IPC startup warning;
visual/native-picker acceptance is not claimed. Only the native Open picker
was substituted with the real OpenProject call to the known QA directory.
Safe controller/results: .runtime/qa/docker-preview/artifact-acceptance.cjs
and artifact-results-final.txt. Owned QA processes stopped; previous local
cache restored with the standard publisher. The QA bundle intentionally lacks
service artifacts; this verifies diagnostics, not offline-install completeness.

## Installation secret names and pending values — 2026-10-31

The generic approval gate returned before obtaining Core descriptors whenever
reference-keyed secrets were missing or the check was not a Start attestation.
Services could correctly report a deployment-bound pending password present,
while approval searched for the Core si- identity and reported it missing. The
same early return prevented loading the service/name label. Re-entering the
password could not repair this order of operations.

The existing getRuntimeSecretDescriptorsLocked(false) path now attests/binds
pending inputs before reporting absence, including inputs saved after a cached
descriptor set. Presence is checked again and errors use Core ServiceDeployment
and DisplayLabel. There is no service-specific branch, identity hashing, new
API/model/storage or secret-value diagnostic. Existing revision/node/runtime,
purpose, expiry and pre-Start guards remain; attached values are not cleared.
Repeated approval with present values does not repeat descriptor discovery.

Focused tests use two generic independent deployments with opaque refs, cold
and warm descriptor caches, partial input, named errors and successful approval
after pending entry. Existing PKCS/password/typed Start tests pass. Full Go
test/vet and frontend/Windows Wails production builds pass.

Independent FULL DIFF APPROVE, blocking0; base
3fef298b35e3dfc7e495b71cbb011e4ae345a427, reviewed source fingerprint
2f54a7cfd83020911ed6ce883295d7eeea3d6503cefb96cc08b874c9c970456d.
Only installation_plan.go and installation_plan_test.go were changed in source.

Actual React/Wails -> RED OS101 Core flow used unchanged verified runtime bundle
b64e552cb9d11a535ff4f6cb6ae7ba53212d70f010206a9434ee128fd0b62a93,
standard-published before launch. QA project projection-ui3 saved revision
a632ed8a1d52c304c15ae0d9894117597af1a8f3618459b08d5fa7a655c4d201,
plan-132728554300d8fed8cdb0ea, EXECUTABLE with no findings. Real UI saved secret
references, then closed/reopened the project to clear values; fresh SSH session
and independently compared host fingerprint were approved, PKCS password set.
Initial approval showed docker: New account password and kafka: Kafka admin
password, no si- identifiers. After entering Docker only Kafka remained;
entering Kafka showed Installed and returned PLAN_APPROVED. No Start or service
installation. ERRORS=[] excluding established Wails IPC startup warning; visual
and native picker acceptance not claimed. Only native Open picker selection was
substituted with real OpenProject; business responses were not substituted.
Generated QA passwords stayed in memory without screenshots/payload logging.
Safe controller/results are .runtime/qa/installation-secret-diagnostics/
acceptance.cjs and results-accepted.txt. Owned processes stopped and previous
local cache restored with standard publisher; runtime bundle itself unchanged.
