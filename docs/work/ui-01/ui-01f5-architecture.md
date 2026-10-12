# UI-01F5 — Endpoint groups and Entry points architecture

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01f5-architecture-checkpoint-001).

Milestone: **UI-01F5**

Parent architecture: `docs/work/ui-01/ui-01f-architecture.md`

Plan baseline: `08d2b6c42af5d56302a4737335ce0b26fe16014e`

Prerequisites:

- UI-01F1 local catalog and managed desired-state projection — DONE;
- UI-01F2 v1alpha5 endpoint-group and consumer-assignment intents — DONE;
- UI-01F3 deployment UI and common structural draft — DONE;
- UI-01F4 placement UI and both Topology projections — DONE.

This document authorizes no implementation by itself. UI-01F5 remains a
separate owner gate until this plan is reviewed and accepted.

## 1. Goal

UI-01F5 completes the third **Topology** tab, **Entry points**, using the
already published v1alpha5 local edit lifecycle.

It permits only:

- create, update and delete an endpoint group;
- set or clear a generic consumer deployment's `endpointGroup`;
- inspect the saved/draft consumer assignments;
- inspect Core-derived FQDN and provider/VIP evidence when it is fresh and
  bound to the current saved revision.

The milestone adds no desired-state schema, writer, reducer, transaction,
Core operation or service-specific endpoint rule.

## 2. Scope

### 2.1 Included

- replace the disabled **Entry points** tab with a real view;
- endpoint-group list and a shared Add/Edit modal for the two owned fields:
  `address.domain` and `address.wildcard`;
- stable endpoint-group ID on create, with no rename operation;
- consumer deployment rows and set/clear assignment controls;
- final-draft overlays for endpoint groups and assignments over
  `ManagedProjectView`;
- catalog-gated admission for a new non-empty assignment using only
  `ProjectCatalogService.endpointConsumer`;
- catalog-independent endpoint-group CRUD and assignment clear where the
  existing backend permits them;
- read-only resolved FQDN, provider identity, provider `endpointGroupRef`,
  `virtualRouterId` and `virtualAddresses` from fresh ProjectSnapshot
  evidence;
- explicit NOT_VERIFIED, UNAVAILABLE, STALE, INVALID and CURRENT preview
  states;
- one minimal typed/bounded Go endpoint preview after Verify; raw
  `ProjectSnapshot` maps never cross into React;
- common command count, Review, local Save, discard and refresh-failure
  behavior;
- deterministic frontend acceptance through the injected public
  `ProjectBackend` seam and a Windows Wails build.

### 2.2 Excluded

- editing `endpointGroupRef`, `virtualRouterId`, `virtualAddresses` or any
  provider/consumer integration relation;
- a provider mutation command or a new project-edit contract version;
- endpoint bindings, aliases, listener names, listener ports, routing,
  HAProxy backends, BIND zones or Kafka advertised listeners;
- automatic provider selection, VIP allocation, DNS-domain generation,
  wildcard recommendation or endpoint-group creation;
- local FQDN/VIP/provider computation or validation of infrastructure
  semantics;
- Core Verify redesign, Execution Node preparation, DeploymentPlan,
  execution, target contact or service apply;
- a service-settings route or placeholder page; the real service editor owns
  that navigation when its milestone starts;
- UI-01F6 acceptance work or any later milestone implementation.

## 3. Mockup reconciliation

The required pre-start comparison used:

- `docs/design/ui-design-01-mockups.html`, Topology → **Точки входа**;
- `docs/design/ui-design-01.md`, Topology → **Entry points**;
- `docs/work/ui-01/ui-01f-architecture.md`, F5 ownership;
- the current F4 Topology implementation.

| Mockup/design intent | F5 decision |
| --- | --- |
| Third Topology tab | Implemented in the existing `TopologyPage`; no new global page |
| Endpoint-capable deployments | Show every final deployment whose catalog capability is `endpointConsumer`, plus any saved/draft deployment that already carries an assignment so invalid or legacy state is not hidden |
| Group, FQDN and VIP | Desired group/assignment are editable; FQDN and provider/VIP are separately labelled Core-derived read-only evidence |
| Edit endpoint group | One modal edits only domain and wildcard; ID is immutable after create |
| Provider relation/VIP | Read-only only when snapshot evidence is fresh; no F5 mutation |
| Listener/port/routing | Not displayed as editable fields |
| Save topology | Reuse the common F3/F4 Review → local Save controls, not a tab-specific Save path |
| Demo statuses | Never interpreted as product rules |

The HTML currently presents Entry points as a placeholder. F5 replaces the
placeholder with a compact three-pane layout while preserving the mockup's
minimal style:

1. endpoint groups;
2. consumer assignments;
3. derived preview and providers.

## 4. Existing contracts reused unchanged

### 4.1 Desired state

The canonical model remains:

```text
endpointGroups.<groupId>.address.domain
endpointGroups.<groupId>.address.wildcard

serviceDeployments.<consumerId>.endpointGroup

serviceDeployments.<providerId>.endpointGroupRef
serviceDeployments.<providerId>.virtualRouterId
serviceDeployments.<providerId>.virtualAddresses
```

The endpoint group owns only its DNS namespace and wildcard intent. VIPs and
provider networking remain properties of provider deployments.

### 4.2 Existing v1alpha5 intents

F5 sends only the already published closed commands:

```text
CreateEndpointGroup(endpointGroupId, endpointGroup)
UpdateEndpointGroup(endpointGroupId, endpointGroup)
DeleteEndpointGroup(endpointGroupId)
SetServiceEndpointGroup(deploymentId, endpointGroupId)
ClearServiceEndpointGroup(deploymentId)
```

`endpointGroup` has exactly the contract body:

```json
{
  "address": {
    "domain": "apps.example.internal",
    "wildcard": true
  }
}
```

React does not send `apiVersion`, base revision, paths or documents. The
existing Go session supplies the version/revision and the existing reducer and
writer own canonical mutation.

### 4.3 Existing read models

F5 reuses:

- `ManagedProjectView.endpointGroups` for locally saved group fields;
- `ManagedProjectView.deployments[*].endpointGroup` for locally saved consumer
  assignments;
- `ProjectCatalogView.services[*].endpointConsumer` for admission and labels;
- `ProjectVerification` for project, Execution Node and runtime-bound
  freshness;
- `ExecutionNodeContext` for the current application-only selection identity.

`coreadapter.Snapshot` is not itself a UI safety boundary for endpoint data:
`serviceDeployments`, `endpoints` and `integrations` are decoded as
`map[string]any`, while the current ProjectSnapshot schema constrains those
fields only as objects and supplies no collection bounds. F5 therefore does
not pass these raw maps to React.

**OWNER-UI-F5-03:** one minimal read-only Go projection extracts only the
fixed fields required by Entry points from the accepted in-memory snapshot:

```text
GetEndpointPreview() -> EndpointPreview

EndpointPreview
  status: CURRENT | INVALID | STALE | NOT_VERIFIED | UNAVAILABLE
  endpoints[]: { deploymentId, fqdn }
  providers[]: {
    endpointGroupId,
    providerDeploymentId,
    endpointGroupRef,
    virtualRouterId,
    virtualAddresses[]: { address, interface }
  }
  findings[]: existing safe VerificationFinding shape
  truncated: bool
  error: existing safe ProjectOpenError shape
```

This is a Wails read projection, not a desired-state DTO, persistence format,
Core contract or Save input. It is built under the existing App lock from the
already accepted snapshot and verification evidence. React receives only this
closed typed result and remains presentation-only.

## 5. Ownership matrix

| Data | Owner | F5 behavior |
| --- | --- | --- |
| Group ID/domain/wildcard | Canonical managed desired state | Editable through v1alpha5 |
| Consumer `endpointGroup` | Canonical service deployment | Editable through Set/Clear |
| Consumer capability | Exact local catalog | Read-only admission proof |
| Resolved FQDN | Core ProjectSnapshot | Read-only when fresh |
| Provider relation | Core integration projection | Read-only when fresh |
| Provider group/VRID/VIPs | Provider deployment in Core snapshot | Read-only when fresh |
| Findings/validity | Core Verify | Read-only; never recreated in React |
| UI-safe endpoint preview | Bounded Go projection of accepted Core evidence | Read-only; never persisted or sent to Save |
| Review/Save/session | Existing Go application lifecycle | Reused unchanged |

## 6. Final-draft projection

The Entry points view uses the same acknowledged-intent array held by `App` as
Servers and the other Topology tabs. It introduces no second form buffer after
an intent has been accepted.

Pure selectors apply intents in command order over `ManagedProjectView`:

1. `CreateEndpointGroup` adds one draft group;
2. `UpdateEndpointGroup` replaces the visible owned domain/wildcard fields;
3. `DeleteEndpointGroup` marks the group pending deletion;
4. `SetServiceEndpointGroup` replaces the visible assignment for exactly one
   deployment;
5. `ClearServiceEndpointGroup` removes that visible assignment.

Unknown canonical extension fields are not exposed in the view and are never
reconstructed by React. The existing writer preserves them.

The backend permits only one endpoint-group lifecycle command per group and
one endpoint-relation command per deployment in a session. After an intent is
acknowledged, that entity is locked until Save or Discard. The UI does not
rewrite command history or emulate undo.

The common Review limit remains **16 commands**. F5 does not increase it.

## 7. Endpoint-group UX

### 7.1 Add

The modal contains:

- technical group ID;
- DNS domain;
- wildcard checkbox.

The ID uses the existing v1alpha5 identifier presentation check and duplicate
check. The domain is required and bounded as an input, but React does not
reimplement Core's DNS/FQDN semantics. Core Verify remains authoritative for
semantic validity.

### 7.2 Edit

Edit sends one complete `UpdateEndpointGroup` body for the two owned fields.
The ID is displayed read-only. The writer updates `address` while preserving
canonical extension fields.

### 7.3 Delete

Delete never cascades. Direct consumer references visible in the final draft
must first be cleared or moved. The generic backend reference graph remains
authoritative and may still return `REFERENCE_IN_USE`, including for a
provider `endpointGroupRef` that F5 cannot edit.

When deletion is blocked by a provider edge, F5 shows the safe backend finding
and explains that provider editing belongs to the later provider-networking
milestone. It does not offer a hidden cleanup or service-specific workaround.

## 8. Consumer-assignment UX

Rows are stable-sorted by deployment ID and include:

- deployment and catalog display label;
- current final-draft group or **Не назначена**;
- resolved FQDN only from fresh Core evidence;
- Set/Change or Clear action;
- draft and verification badges.

A non-empty Set is enabled only when:

- the exact catalog is READY;
- the deployment's service declares `endpointConsumer`;
- the target group exists in the final draft and is not pending deletion;
- the deployment is not pending deletion;
- no endpoint-relation command for that deployment is already acknowledged;
- the common command limit is not reached.

Clear remains available without READY catalog for an existing saved/draft
assignment, subject to the normal session and refresh guards. A saved
assignment whose service is missing or no longer endpoint-capable is shown as
unsupported state and may be cleared, but cannot be replaced until catalog
admission succeeds.

Draft-created deployments and groups participate after their create intents
are acknowledged. F5 does not infer endpoint capability from service names.

## 9. Read-only Core preview

### 9.1 Freshness states

**OWNER-UI-F5-01:** Core-derived preview evidence is bound to one exact
in-memory key:

```text
projectIdentity
+ projectRevision
+ effective Execution Node selection identity
+ verification.executionNodeId
+ exact verification.runtime evidence
```

The effective selection identity is the closed existing
`ExecutionNodeContext` tuple (`selectionKind`, `selectionSource`,
`selectedHostId`) plus a frontend-local selection/request generation. The
generation is incremented on open/close, accepted structural draft changes and
whenever the effective selected node changes; it is neither persisted nor added
to a transport contract. Go clears in-memory evidence under its App lock, and
the frontend generation prevents an older asynchronous response from being
published afterward. Runtime evidence is
the existing closed `bundleDigest`, `coreVersion`, `catalogDigest` and
`protocol` tuple. Empty or partial node/runtime evidence can never be
`CURRENT` or `INVALID`.

The derived panel has a closed presentation state:

| State | Condition | Display |
| --- | --- | --- |
| `CURRENT` | verification VERIFIED; the complete evidence key still equals the current project/selection/runtime key; snapshot, verification and managed revisions are equal; no active structural draft | FQDN and provider fields may be shown |
| `INVALID` | verification INVALID with the same complete evidence key and exact revision; no active draft | Show safe findings only; `endpoints` and `providers` are empty and no FQDN/provider/VIP value is authoritative or rendered |
| `STALE` | any active structural draft, effective Execution Node selection change, or snapshot/evidence identity, revision, node or runtime mismatch | No FQDN/VIP is presented as current; show stale explanation |
| `NOT_VERIFIED` | saved project has no bound snapshot evidence | Show Verify prerequisite |
| `UNAVAILABLE` | verification has a safe availability/readiness error or snapshot shape cannot be projected safely | Show safe status/error only |

Any structural draft, not only an endpoint command, makes the Core preview
STALE. This is deliberately conservative and avoids reproducing Core's impact
graph in React.

When `SelectExecutionNode` actually changes the effective selection, Go clears
the in-memory `Snapshot` and resets `Verification` to the existing
`UNVERIFIED` value while holding the existing App lock. Selecting the same
effective node is a no-op for evidence. Canonical project bytes, saved
verification contracts and Execution Node readiness semantics do not change.
This narrow invalidation prevents other App consumers, not only the Entry
points component, from observing old-node evidence as current.

**OWNER-UI-F5-02:** an `INVALID` verification never authorizes authoritative
FQDN/provider/VIP preview. Findings remain visible through the existing safe
finding projection, but Core-derived endpoint/provider rows are absent. F5
does not present partial invalid-snapshot data as informative preview.

### 9.2 Refresh after Verify

`VerifyProject` already stores the exact verified snapshot in the Go-owned
current `ProjectOpenResult`, but currently returns only `ProjectVerification`.
F5 adds the narrow `GetEndpointPreview()` Wails read method described in
section 4.3. Raw `CurrentProject().Snapshot`, arbitrary Core maps and snapshot
JSON are not added to the frontend backend interface.

After Verify returns, React requests `GetEndpointPreview()` once. Go builds and
returns rows only if:

- the same project remains open and the verification project identity/revision
  equal the current canonical project and managed revision;
- verification status is exactly `VERIFIED`;
- the accepted snapshot revision equals that revision;
- verification `executionNodeId` and exact runtime tuple are complete and
  match the currently selected/bound Execution Node evidence;
- no structural draft is active.

Otherwise Go returns the matching non-current status with zero endpoint and
provider rows. A monotonically increasing frontend request/selection token
prevents an older Verify/`GetEndpointPreview` completion from replacing a
newer project, selection or Verify result. The token captured before Verify
must still match immediately before publication. No new Core execution,
polling loop or persisted cache is introduced.

### 9.3 Typed and bounded Go projection

`GetEndpointPreview()` validates and copies the required fields while holding
the existing App lock. It is the only F5 code allowed to inspect the dynamic
endpoint/provider portions of `coreadapter.Snapshot`. The projection:

- accepts at most 4096 entries in each relevant source map, at most 4096
  provider records in one source collection and at most 4096 source virtual
  addresses; exceeding an input bound returns `UNAVAILABLE` with zero rows;
- accepts identifiers only in the existing canonical grammar and at most 128
  characters, FQDNs at most 253 characters, IPv4 addresses parsed by Go's
  standard library, interfaces in the existing grammar with an additional
  128-character presentation bound, and `virtualRouterId` only in `1..255`;
- requires fixed object/array/primitive shapes and rejects malformed known
  fields; it never stringifies or forwards unknown/raw values;
- cross-checks provider integration records against the referenced provider
  deployment's `endpointGroupRef`, `virtualRouterId` and
  `virtualAddresses`; disagreement makes the whole projection `UNAVAILABLE`
  rather than selecting one source or returning partial rows;
- stable-sorts and copies values into the closed Go structs from section 4.3;
- exposes at most `MAX_ENDPOINT_PREVIEW_ENDPOINTS = 64` endpoint rows;
- exposes at most `MAX_ENDPOINT_PREVIEW_PROVIDERS = 64` provider rows and at
  most `MAX_ENDPOINT_PREVIEW_ADDRESSES_PER_PROVIDER = 64` virtual addresses
  for each row;
- emits one safe `truncated=true` presentation flag when any output limit is
  exceeded and never renders the omitted values;
- performs no FQDN, provider, VIP or status calculation.

`INVALID`, `STALE`, `NOT_VERIFIED` and `UNAVAILABLE` responses always contain
zero endpoint/provider rows. `INVALID` may contain only the already bounded
safe verification findings. React renders the typed result and does not parse,
validate, join or reconcile ProjectSnapshot data.

## 10. Save, Verify and recovery

F5 preserves the existing lifecycle:

```text
UI intent
  -> common EditSession
  -> AppendEditCommand
  -> local structural Review
  -> guarded local Commit
  -> ManagedProjectView reopen
```

Save requires no Execution Node or Core. Any successful semantic Save clears
the draft and makes previous verification evidence non-current. Verify remains
a separate target-free operation and does not mutate project files.

`COMMITTED_REFRESH_FAILED` keeps the existing F3 behavior: canonical bytes are
already committed, so Commit is never retried; overlays/session state are
cleared, topology CRUD is disabled and only the existing read-only reopen of
the current root is offered.

`EDIT_COMMAND_CONFLICT` retains the bounded draft; recovery remains Save where
valid or Discard all changes and re-enter. F5 adds no undo stack.

## 11. Error and unavailable behavior

- catalog unavailable: saved groups and assignments remain visible; group
  CRUD and assignment Clear remain subject to backend guards; new Set is
  disabled;
- endpoint group referenced: show `REFERENCE_IN_USE`; do not cascade;
- missing group/deployment: show `REFERENCE_NOT_FOUND` or the exact safe
  backend finding;
- malformed known local projection: project open remains fail-closed under F1;
- malformed/unexpected Core preview shape: desired editing remains available,
  derived preview becomes UNAVAILABLE;
- Verify INVALID: saved data remains editable and saved; Installation remains
  blocked by existing gates;
- session expiry/project change/refresh failure: reuse existing App handling.

## 12. Security and privacy

- no secret, credential, private key, command output or raw finding payload is
  introduced;
- no project path, YAML document or arbitrary snapshot object is rendered;
- endpoint inputs are ordinary desired values and pass through the existing
  bounded command/session decoder;
- React never contacts Core, an Execution Node or a target;
- no URL is opened automatically from domain/FQDN text;
- visible errors use existing safe backend/verification messages.

## 13. Implementation map

Expected bounded changes:

| Area | Change |
| --- | --- |
| `frontend/src/TopologyPage.tsx` or a focused `EntryPointsView.tsx` | Third tab, groups, assignments and preview |
| `frontend/src/App.tsx` | Extend `StructuralIntent`; pass endpoint intents; request typed preview after Verify and guard late responses |
| `frontend/src/backend.ts` | Add the typed `getEndpointPreview` adapter; do not expose raw snapshot maps |
| focused frontend selectors | Final-draft desired-state rows only; no Core snapshot parsing |
| frontend tests | Group CRUD, assignment, freshness and shared lifecycle |
| `app.go` plus one focused Go projection file if useful | `GetEndpointPreview`, strict typed/bounded extraction, and selection-change evidence invalidation under the existing lock |
| Go tests | Projection bounds/shapes/cross-checks, INVALID no-preview, selection invalidation and binding regression |

No schema, reducer, writer, transaction, Core Python or service package change
is expected. Discovery of such a need stops F5 and returns the gap to the
owner.

## 14. Test and acceptance plan

### 14.1 Focused Go safety tests

- VERIFIED exact evidence produces only the closed typed rows;
- INVALID returns safe findings but zero endpoint/provider rows;
- STALE/NOT_VERIFIED/UNAVAILABLE return zero rows;
- malformed/scalar/wrong-shape known fields fail closed with no partial rows;
- source map/list sizes exactly 4096 pass structural bounds and 4097 fail
  closed before projection;
- output sizes exactly 64 and 65 endpoints/providers/addresses prove stable
  truncation and the single `truncated` flag;
- identifier, FQDN, IPv4, interface and VRID grammar/length/range boundaries;
- provider integration/deployment disagreement produces UNAVAILABLE with no
  partial projection;
- no raw map, unknown field, project path or unsafe payload crosses the Wails
  result;
- effective Execution Node change clears evidence, while same-node selection
  is a no-op.

### 14.2 Focused frontend tests

- create/update/delete group intents with immutable ID;
- Set/Clear assignment and consumer-capability gating;
- saved unsupported assignment remains visible and clearable;
- catalog unavailable permits structural cleanup but blocks new Set;
- draft-created group/deployment participation;
- pending-delete group/deployment exclusion;
- direct consumer reference blocks presentation delete until cleared;
- backend `REFERENCE_IN_USE` from a provider edge remains visible;
- one acknowledged command locks the same group/relation;
- 16-command common limit;
- stable ordering and empty states;
- CURRENT/INVALID/STALE/NOT_VERIFIED/UNAVAILABLE preview states;
- INVALID renders findings but no FQDN/provider/VIP preview;
- any active draft hides current derived preview;
- React consumes only typed `EndpointPreview` rows and never receives/parses
  `ProjectSnapshot` maps;
- changing the effective Execution Node after Verify clears Go evidence and
  makes the preview non-current; reselecting the same node does not create a
  false invalidation;
- changing project or node between Verify and `GetEndpointPreview`, and completing
  an older Verify after a newer request, cannot publish old FQDN/VIP evidence;
- provider relation/VRID/VIP are read-only and never become intents;
- discard, Review/Save, Commit, refresh failure and close/reopen.

### 14.3 Deterministic App acceptance

Through the injected public `ProjectBackend`:

1. open a managed project without Core/Execution Node methods;
2. create a group and assign an eligible deployment in one common session;
3. Review/Save, close/reopen and prove direct desired fields persist;
4. Verify through a fake that returns exact revision-bound snapshot evidence,
   read the typed `getEndpointPreview`, and display FQDN/provider/VIP
   read-only;
5. switch the effective Execution Node and prove old evidence is cleared and
   never rendered as current; simulate a late Verify/`GetEndpointPreview` result
   after a project/node switch and prove it is rejected;
6. return INVALID with findings and prove no FQDN/provider/VIP row exists;
7. start any structural draft and prove the derived preview becomes STALE;
8. Save, clear assignment, delete the group, Save/reopen and prove removal;
9. assert emitted commands are only the five published endpoint intents.

### 14.4 Regression gates

- focused endpoint reducer/writer/reopen Go tests already owned by F2;
- full frontend test/typecheck/lint/build;
- `go test ./...` and `go vet ./...`;
- `wails build -nopackage -clean`;
- affected race/RED OS tests only if Go production behavior changes;
- catalog/schema reproducibility only if generated inputs change unexpectedly;
- changed-scope secret/security audit;
- mockup recheck;
- `git diff --check` and clean worktree after the focused implementation
  commit.

F5 does not repeat service apply/verify, Kafka/PKI, target SSH or Execution
Node preparation acceptance because it changes no runtime behavior.

## 15. Overengineering assessment

| Candidate | Decision |
| --- | --- |
| New endpoint contract/version | Rejected; v1alpha5 already contains the exact commands |
| Minimal Go endpoint read projection | Required because current snapshot fields are dynamic unbounded maps; keep one closed Wails output and no persistence/mutation semantics |
| Raw ProjectSnapshot in React | Rejected; Go owns strict extraction, bounds and cross-source consistency checks |
| New Verify response envelope | Rejected; Verify remains unchanged and the separate read-only preview method consumes accepted in-memory evidence |
| New persisted freshness record | Rejected; reuse verification identities and one App-local selection/request generation |
| Endpoint database/cache | Rejected; canonical project and in-memory snapshot remain authoritative |
| Dedicated endpoint Save | Rejected; reuse one App session/Review/Commit lifecycle |
| Provider editor in F5 | Rejected; ownership is outside F5 |
| Generic form/state framework | Rejected; two small forms, desired-state selectors and one narrow Go projector are sufficient |
| Graph visualization | Rejected; three compact panes express the required relations |

The smallest viable F5 is one Entry points view, a closed five-intent frontend
union, final-draft desired-state selectors and one bounded read-only Go
projection. The projection is justified by the current dynamic/unbounded
snapshot representation; a generic snapshot framework or second endpoint
contract is not. Anything that mutates provider networking, reconstructs Core
semantics in React or adds storage would be unnecessary architecture.

## 16. Future milestone ownership

The owner resolved the former naming conflict. **UI-NET-01** owns provider
relation, VRID and VIP editing and precedes **UI-01G**, because Core may include
provider VIPs in certificate SAN. **UI-01G** remains the Certificates editor.
F5 does not absorb either milestone.

## 17. Exit criteria

UI-01F5 may be marked DONE only when:

- one bounded FULL PLAN architecture review has zero blocking findings or all
  blockers have been returned to and resolved by the owner within the allowed
  review budget;
- the Entry points tab edits only endpoint groups and consumer assignments via
  the existing five v1alpha5 intents;
- provider relation/VRID/VIP remain fresh-Core-only and read-only;
- INVALID exposes safe findings but no authoritative endpoint/provider rows;
- React receives only the strict typed/bounded Go endpoint preview and never
  parses dynamic ProjectSnapshot maps;
- Save/reopen/clear/delete use the common local lifecycle without Core or
  target contact;
- deterministic acceptance and regression gates pass;
- docs, `CURRENT_STATE.md` and roadmap record F5 DONE and F6 NEXT;
- one focused implementation commit exists and the worktree is clean.

UI-01F5 is **DONE**. The focused implementation commit records the typed Go
projection, Entry points UI, generated Wails binding, Go/frontend acceptance,
Windows Wails build and RED OS race evidence. UI-01F6 subsequently completed;
its final evidence is `docs/work/ui-01/ui-01f6.md`. Later milestones remain separately
authorized.
