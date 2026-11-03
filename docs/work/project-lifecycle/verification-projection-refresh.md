# Coherent verification and snapshot publication

Owner request, 2026-11-03: after automatic Verify following Execution Node
preparation the header showed «Проверено», while SSO/Keycloak still showed
«Адрес ещё не рассчитан». Repeating manual Verify made the address appear.
Owner approved sharing the UI publication path and returning verification with
its current snapshot in one result. Independent review remains declined.

## Cause and implementation

Go already stored a verified snapshot for both paths. Manual React Verify fetched
CurrentProject separately; the preparation handler updated only verification
metadata. The same successful Core operation therefore produced different UI
projections depending on its caller.

ProjectVerification now has an optional response-only `current` field containing
the established ProjectOpenResult. It is copied under the existing edit lock
after exact Core/runtime/revision validation. Cached verification metadata does
not contain `current`, so CurrentProject has no recursively nested response.
Both VERIFIED and INVALID terminal Core results carry their snapshot/findings.
Readiness/transport errors still return unverified metadata without inventing a
snapshot. Core/projection semantics and desired-state storage are unchanged.

React uses one publication handler for manual and preparation results. It applies
the project/snapshot and metadata in one state update, without a second
CurrentProject call. Missing/mismatched successful projections are unavailable;
INVALID findings remain usable even if no projection was returned. Request token,
root/project identity, revision, node and runtime guards reject superseded
responses. Prepared runtime transition is accepted only for the automatic path.
Endpoint/PKI views refresh through their existing read methods with the same
context checks.

UI ownership/design check: shared status/projection rules, Applications library
Connections and Servers preparation flow in the UI design/mockup and Save/Verify
architecture were inspected. The original two-handler mismatch is corrected;
no infrastructure endpoint calculation moved into React or Go.

## Evidence

- Go tests verify that explicit Verify and Prepare's automatic Verify return the
  exact current snapshot with matching metadata and no recursive cached response.
- App tests exercise automatic preparation -> VERIFIED -> Applications -> library
  Connections, where the SSO URL appears without manual Verify or CurrentProject.
  Refusal cases cover missing current state, mismatched snapshot/managed revision,
  root, node and runtime. A delayed automatic result cannot replace another
  project's state. Existing manual/INVALID/PKI paths remain covered.
- Real full-App React -> Wails -> RED OS Core acceptance PASS on node101
  `192.168.56.101`, using the established platform-automation identity,
  IdentitiesOnly, strict trusted known_hosts and sudo -n. PEM encoding checked.
  Existing active/published bundle matched:
  `sha256:c97e77d7f9d2336a83fd588f790fa737759c2a4a56157d4cce4216a41b051a4f`.
- Isolated QA project created and saved through actual UI with one documentation
  target (`192.0.2.200`); no connection to that target was made. Both
  PrepareExecutionNode's automatic Verify and manual Verify returned VERIFIED,
  current state and snapshot revision
  `sha256:14d794bbdccf911eaf493b8d431bc3307f94238a4609fe3d90c514f507d7e020`.
  Header updated successfully; manual Verify made no second CurrentProject call.
- Preparation was restricted to the existing READY runtime (RECONCILE/VERIFY
  steps). Workspace ownership/modes were checked beforehand: root0711 and
  platform-automation0700. No bundle activation, deployment plan, approval,
  Start or service installation was performed. No execution run IDs exist.
- Real QA evidence/script/screenshot retained under
  `.runtime/qa/verification-projection-20261103/`. Test project:
  `Verification atomic QA`. Full-App screenshot inspected: matching green
  verification/readiness indicators. Live QA did not deploy Keycloak; its
  provided-connection URL regression is the focused React test above.
- Full Go tests/vet PASS. Final App tests110 PASS; typecheck/lint/frontend build
  and Windows Wails build PASS. Frontend full run: 379 PASS, 2 unchanged B4
  text-assertion failures, 28 files; the two unrelated failures are not waived
  or marked passed. Existing frontend large-chunk warning remains.
- Initial real QA used an empty metadata-only project; Core correctly did not
  verify absent inventory (UNVERIFIED/PROJECT_VERIFY_FAILED). After normal UI
  server creation and local Review/Save, the complete project passed both real
  paths above. Agent-started Wails/Vite processes were stopped after acceptance.
- No independent reviewer invoked, per owner instruction.

## Owner-requested B4 test follow-up (2026-11-03)

The two old assertions in `InstallationPage.b4.test.tsx` expected the prior
infrastructure-toggle behavior. Disabling infrastructure now selects explicit
Infra Verify skip; that change invalidates approval of the displayed plan until
a fresh libraries-only plan is requested. Tests now verify the actual warning,
checked skip flag, disabled approval/hidden Start, absence of approval/start
callbacks and the new plan request with `skipInfrastructureVerify: true`.
The approved-plan fixture also uses the current plan ID so it proves scope
invalidation rather than accidentally failing the unrelated plan-ID gate.

Targeted B4 suite19 PASS. The initial full rerun had380 PASS/1 FAIL: an additional
B4 case in `App.test.tsx` clicked Installation before asynchronous navigation
admission completed. Its three cases now wait for the enabled navigation button
and the Plan tab. Targeted shared B4 cases3 PASS. Final full frontend regression:
**381 PASS, 28 files, zero failures**; typecheck and lint PASS.

Only tests and this evidence/status record changed. No production behavior,
Core/Go code, runtime bundle or target was changed. The earlier failing runs
above remain historical evidence; no new Wails/installation acceptance is claimed
for this test-only follow-up.
