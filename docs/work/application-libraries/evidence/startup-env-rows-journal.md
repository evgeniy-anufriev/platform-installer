# Startup ENV compact rows — 2026-10-21

Owner request: one line per ENV key/value with draft/reset actions, automatic
types without Advanced, Add parameter in the instance header beside Reset.
The preceding design used stacked generic parameter controls and a local add
button. The owner request resolves that layout discrepancy; UI design updated.
Bounded existing-contract UI/input refinement; no architecture boundary or
Core/Go/schema change, no independent FULL gate required.

`ApplicationValueFields` has an opt-in compact layout and optional externally
controlled add form. Startup ENV alone uses it; it retains the existing
environment draft/Review/Save/reset writer. Existing generic recursive editors
remain available for other settings. Compact input uses the existing
inferParameterValue conversion automatically, without manual type selection.
Leading zeros, unsafe numbers and Ansible expressions remain strings. No YAML
or template evaluation was added. Key and origin/type tooltips retain full
information; all four parts remain on one line at primary desktop widths.

Focused37 PASS: parameter18 and ApplicationsPage19. Covers auto number/bool,
string identifiers and templates, reset, header add location, existing baseline
invalidation and neighboring generic parameter controls. Typecheck/Vite build,
lint and git diff --check PASS. Initial tests were adapted for compact row DOM
and correctly literal template input; the final focused run passed.

Actual React/Wails/Go node-free acceptance PASS on an isolated copy of
full-services / cspa / alarm-view-service: Open → Startup → header Add parameter
→ QA_STARTUP_ROWS_VALUE → input3 → draft → Review → Save → reopen; public managed
value was numeric3. Actual Reset → Review → Save → reopen removed the custom
ENV override. No test-only writer or backend bypass was used; file chooser
selection used the existing bounded seam calling real CloseProject/OpenProject.
No credential submission, Execution Node/Core Verify, Approve/Start/Apply or
target contact. Core/Ansible execution and fresh Core baseline acceptance are
not claimed for this layout/input-only change.

Initial revision `sha256:be3c233e9156e3040fbe69ca917b223dd54bcb9c1a45a9cfc6eb4875b18d395f`.
Saved numeric ENV revision `sha256:4a66f9f19c980f4da56e5d71df0f4b2693743dc4c0a6c7ae2c31c7f00f39c031`.
After reset revision `sha256:3327b9ceff860ec6b10e602c8eaa513ccb340c2608ae89166c2d90ae55cf20d6`.
No execution run ID. No byte-identical full-project restoration claim.

Evidence `.runtime/qa/inline-secret-input/startup-rows-acceptance.json`
PASS/complete, driver `startup-acceptance.cjs`; five real ENV rows each36.1875px
at1440 and1024, all four controls vertically aligned and right action inside
the container. Screenshots `startup-rows-1440.png` and `startup-rows-1024.png`
in the same directory inspected: visual PASS. First launch attempts reached
the bridge before Wails finished compiling (connection refused); final run
started after readiness. Exact isolated child/Wails/Vite processes stopped;
original user process preserved. Sources/project/evidence retained; no commit
or push performed, earlier dirty changes preserved.

## Defaults/Core display and compact-panel follow-ups

Owner requested visible defaults/effective Core ENV, three command/user/restart
columns, matching library Common ENV and General Endpoint rows, hidden resource
add actions, and vertical resource scrolling. Per-key source labels/Core changes
were discussed and explicitly declined. No Core, Go, schema, provenance, bundle
or execution changes made; no architecture review gate introduced.

Application ENV always retains raw application package declarations plus authored
overrides. A fresh saved-revision Core placement supplies both inherited defaults
and effective environment values for the selected host. Dirty/busy/draft/stale
contexts discard effective display. Focus opens source, blur without edits shows
Core again; display does not create overrides. Tooltips expose default values.
Ansible expressions are not evaluated by React. Common library ENV/Endpoint use
the existing generic editor's opt-in compact mode (including nested Endpoint
objects/arrays). Other generic configuration controls retain their existing mode.

Command/user/restart are three grid columns. The resource table previously
rendered only two resources per page. It now renders every selected resource
inside a420px scroll region with sticky column headings. The production page
disables resource add actions, including add-from-defaults. Resource definitions
in resource_defaults remain parameter templates; Core's selected resources loop
uses deployment.resources. No implicit activation or frontend precedence added.

Final focused58 PASS: ApplicationValueFields21, ApplicationsPage22 and resource
table15. Coverage includes Core display/source editing, false/zero, stale
projection removal, package ENV with missing shared baseline, host selection,
library boolean override/reset, nested Endpoint payloads, complete resource list
and hidden add actions. Final typecheck/Vite build, lint and diff check PASS.

Actual React/Wails/Go/Execution Node Core:

- Before Verify,49 package ENV declarations and existing authored overrides
  visible on a copy of full-services / cspa / alarm-view-service.
- Current runtime53, node1 trusted through independently checked known_hosts,
  Verify VERIFIED. Base project shows126 effective ENV,77 beyond the application
  package's own keys. Final recheck shows127 including one explicit QA key;
  every displayed value equals the corresponding existing Core projection.
- Actual React draft/Review/Save preserves the authored QA expression. Final
  saved/verified revision
  `sha256:c5eb8335806802495e91fb692a2d1d636e19a4614866cf16bbe61a0d3983200b`.
  Focus/blur preserves the source and revision. A template preserved by Core
  remains a template in the display; no claim that all expressions are expanded.
- Evidence `startup-core-env-acceptance.json` PASS/complete and driver
  `startup-core-recheck.cjs` under `.runtime/qa/inline-secret-input/`.
  Source/value-distinct focus behavior and second-host changes are also covered
  by unit tests; this real flow used node1 only. Credential cleared through React.

Separate node-free real React/Wails/Go panel flow: three-column layout, library
ENV false boolean add/draft/Review/Save/reset, Endpoint enabled boolean
draft/Review/Save/reset, complete10/10 selected resource rows and functioning
vertical scroll, no add/pagination actions. `compact-panels-acceptance.json`
PASS/complete; driver `compact-panels-acceptance.cjs` in the same directory.
Library ENV saved revision
`sha256:c64184d3572af8f5f2d0c9479f7b87b8fe7c011868643fbfb6976b3b609081c9`;
Endpoint false revision
`sha256:952c16efa16adb516b2c751f0999c99ea344a344bec5a6d1feb51d189751bb8e`;
after each reset
`sha256:b1eb190562ca0cb5dc5cb4a36725bacdc28a1783e0d90825f4bc024e37140f2e`.
No byte-identical original-project restoration claim. Screenshots
`startup-core-env-*`, `startup-policy-*`, `library-env-*`, `endpoint-compact-*`
and `resources-scroll-*` at1440/1024 inspected: visual PASS.

Earlier QA attempts retained: an incorrect package-only comparison ignored
authored overrides; an exploratory application_instance_id input did not reach
VERIFIED (cause not established); a later assertion incorrectly demanded that
Core expand inventory_hostname, although Core returned the preserved template.
Final checks compare exact Core output instead. Evidence retained in
`startup-core-env-first-failure.json` and `startup-core-env-template-assertion.json`.
The initial panel driver nested its locator's outer container inside a row,
timed out before staging the changed value, and left an isolated edit session.
The locator was corrected; the owned isolated backend was restarted to clear
that QA session, and the final stable-source panel flow above passed. This was
automation selection, not a product save failure.

No Approve/Start/Apply, target service mutation or application password entry;
no execution run ID. Exact owned child/Wails/Vite processes stopped; original
user processes preserved. QA copies/evidence retained. No commit/push; earlier
dirty work preserved.

## Owner-authorized commit preparation

Full frontend regression294/26 files PASS, lint and typecheck PASS on the final
combined UI source. Build and bounded real acceptance are recorded above.
Master fetched before integration: HEAD/origin-master ahead0/behind0. Commit
scope contains the related pending secret-row/Core-name refinements, Kafka ACL,
ENV/Endpoint/layout/resources changes, tracked dist and their evidence only.
Core/Go and runtime/credential/cache paths have no staged changes.
