# UI-01E4 — Execution Node panel and one-time selection

Status: **DRAFT — awaiting architecture review and owner approval**.

## 1. Goal and owner decisions

UI-01E4 adds a small, application-owned Execution Node selection context and
its read-only presentation.  It makes the selected context visible globally in
the App Shell and persistently at the bottom of the Servers page.  It neither
proves readiness nor starts preparation.

The following owner decisions are binding:

1. the Execution Node status is global App Shell context, not portable project
   desired state;
2. before a READY Execution Node only **Project** and **Servers** are available;
3. the Servers page has a persistent lower Execution Node panel while the
   server list scrolls independently;
4. automatic selection is exactly `explicit -> local Linux -> first eligible
   project server`, once per project context;
5. bootstrap and readiness do not belong to Installation;
6. E5 is independent of the E3 target-session credential.  E4 and E5 must not
   reveal or consume its internal reference.
7. **OWNER-UI-E4-01:** `AUTO_FIRST_PROJECT_SERVER` uses only typed server
   state already known to the Installer: authoritative `ProjectSnapshot` hosts
   when available, or acknowledged final-state `CreateServer` intents in the
   current Go `EditSession` for a metadata-only project.  It never parses
   canonical Ansible files locally.  A draft-derived automatic selection is
   provisional and is cleared when its source server disappears through
   discard or session invalidation.  This fallback does not make an arbitrary
   existing managed project openable on a fresh workstation without an
   Execution Node; that remains an explicit selection or separately approved
   bootstrap-open contract.
8. **OWNER-UI-E4-02:** `AUTO_LOCAL_LINUX` is available only when a bounded,
   read-only local capability probe confirms that the Installer host is
   supported by the product's local Execution Node adapter.  `runtime.GOOS ==
   "linux"` alone is insufficient.  The probe establishes candidacy only: it
   performs no Core execution, bootstrap, elevation, package installation,
   repository probing or target contact.  Preparation and READY remain E5;
   the local candidate is runtime application context and is never persisted
   in the portable project.
9. **OWNER-UI-E4-03:** the local-only candidacy probe returns `available` and
   `safeLabel` only after confirming all of: Linux host; locally supported
   architecture; locally read `/etc/os-release` matching a product-supported
   Execution Node OS/version; and an actually implemented supported local
   Execution Node adapter in this product build/runtime.  It creates neither
   an external `executionnode.Node` nor an emulated one.  Without that adapter
   it deterministically returns `available=false`, even on an otherwise
   supported Linux host.  A positive result is selectable candidacy only, not
   READY, capability proof or preparation.
10. **OWNER-UI-SAVE-EXECNODE-01/02:** when authoritative Review/Save requires a
   READY Execution Node, its flow may run the current read-only readiness check
   automatically.  If preparation is required, the Installer offers an
   explicit operator confirmation before invoking the existing mutating
   Execution Node prepare workflow.  Save introduces no bootstrap/readiness
   mechanism.  After successful preparation it resumes the original
   Review/Save flow; failure or cancellation preserves the draft and canonical
   project bytes, and offers retry, node change or cancellation.

The mockup at `docs/ui-design-01-mockups.html` already establishes the Shell
badge, the fixed bottom panel, and the `NOT_CONFIGURED` / `NOT_PREPARED`
examples.  Its **Check** and **Prepare** controls, readiness states `READY` /
`UNAVAILABLE`, and the configuration dialog are E5, not E4.  This milestone
implements only the selection/display parts of that design.

## 2. Scope and non-goals

E4 includes:

- an app-memory `ExecutionNodeContext/v1alpha1` view model;
- one-time automatic choice for an opened project context;
- one bounded read-only local-adapter capability probe that establishes only a
  local-Linux candidate;
- a manual switch to an eligible project server;
- a global safe status badge and a Servers-page bottom panel;
- an independently scrolling server-list region;
- lifecycle cleanup on successful project replacement, close and shutdown;
- focused Go and React tests for selection and rendering.

E4 excludes:

- SSH, host-key, sudo, Python/Ansible runtime, bundle, repository or disk
  probes against a node; the sole exception is the bounded local-adapter
  candidacy probe defined by OWNER-UI-E4-02;
- preparation, activation, mutation of an Execution Node, or target contact;
- changing the existing trusted workstation-to-Execution-Node binding used by
  `BuildProjectSnapshot` and candidate Core proof;
- use, export or display of E3 runtime-session credentials or their reference;
- project/inventory/`group_vars`/`host_vars` writes or EditSession commands;
- Core, Ansible, runtime-protocol and portable-project contract changes;
- navigation expansion beyond the existing Project/Servers gate.  E5 owns
  readiness-derived navigation gating and Installation prerequisite behavior;
- a generic node registry, preferences database, local persistence, background
  discovery or a new transport abstraction.

## 3. Existing authority and separation

The current desktop startup path constructs an `executionnode.Node` from the
explicit runtime-only flags and passes it to `projectReader`.  That reader
uses the trusted node for `BuildProjectSnapshot` and candidate proof.  This is
an existing operational binding and remains authoritative for those operations.

E4 deliberately does not derive a new `executionnode.Node` from a project
server, does not replace `projectReader.node`, and does not inspect a selected
server.  A project-server choice is therefore only a safe future-candidate
label in application memory.  It cannot be reported as reachable, trusted,
prepared or READY.

The resulting separation is:

```text
portable project / Core Snapshot        -> canonical desired and derived state
existing startup Execution Node binding -> trusted Core transport, unchanged
E3 RuntimeSecretBroker                  -> target-session secret, unchanged
E4 ExecutionNodeContext                 -> app-memory selection/display only
React/Wails                             -> safe rendering and fixed operations
```

No E4 value enters the project bytes, snapshot fingerprint, edit review, plan,
journal, event mirror or diagnostics.  Conversely, neither a server `type`
nor membership in local `AppConfig` affects eligibility: unknown but valid
types remain a non-blocking application diagnostic by the accepted E1 policy.

## 4. Small fixed contract

There is one app-facing read model, not a second server DTO or a generic node
resource API:

```text
ExecutionNodeContext/v1alpha1
  status:          NOT_CONFIGURED | NOT_PREPARED
  selectionKind:   EXPLICIT_EXTERNAL | LOCAL_LINUX | PROJECT_SERVER | NONE
  selectionSource: EXPLICIT | AUTO_LOCAL_LINUX | AUTO_FIRST_ELIGIBLE | NONE
  selectedHostId:  optional safe project host identifier
  safeLabel:       optional safe display label
  locked:          bool
```

`NOT_CONFIGURED` means that there is no eligible safe selection.  Every E4
selection that exists is `NOT_PREPARED`; E4 never manufactures `READY`,
`UNAVAILABLE` or an inspection finding.  `safeLabel` is constructed only from
safe project host fields or the existing configured node identifier/address;
it never contains a credential reference, identity path, known-hosts path,
fingerprint, secret, command output or a target fact.

Wails exposes only:

```text
GetExecutionNodeContext() -> ExecutionNodeContext
SelectExecutionNode(hostId) -> ExecutionNodeContext
```

`SelectExecutionNode` accepts only an eligible current project host.  It
returns a stable safe error (`PROJECT_NOT_OPEN` or
`EXECUTION_NODE_SELECTION_INVALID`) without attempting a network operation.
There is no setter for arbitrary address/user/credential data and no Wails
operation for readiness in E4.

The Go `ExecutionNodeContextStore` is a private, bounded field of `App`,
guarded by the existing `App.editMu`.  It is keyed to the current canonical
project root and project identity and holds only the context above.  It is not
a map, cache, registry, durable preference or generic state engine.

## 5. Eligibility and exact selection rules

E4 uses only typed server state already known to the Installer and extracts it
once in the Go application boundary rather than creating a second React-only
eligibility model.  For a managed project that is already open, the source is
the authoritative `ProjectSnapshot` hosts.  For a metadata-only project, it
is acknowledged final-state `CreateServer` intents from the current Go
`EditSession`.  It never parses canonical Ansible project files locally.
The projection is display/selection state only and cannot be sent to Core or
persisted.

An eligible project server has a stable `hostId`, a non-empty safe transport
address, and is not a pending `DeleteServer` intent.  An omitted SSH port is
valid and means the existing default transport behavior; E4 does not infer a
new port.  `desiredHostname` and `server.type` are displayed server metadata,
not eligibility requirements.  This preserves compatibility with valid legacy
hosts and the E1 non-blocking unknown-type rule.

At the first successful publication of a project context, selection is:

1. **EXPLICIT** — retain a still-eligible manually selected project server, or
   expose the existing explicit external startup binding as
   `EXPLICIT_EXTERNAL`; it wins without converting or exposing that binding.
2. **AUTO_LOCAL_LINUX** — only when the product's bounded read-only local
   Execution Node adapter probe confirms candidacy at application startup.
   It requires all four `OWNER-UI-E4-03` conditions: Linux, a supported local
   architecture, a supported local `/etc/os-release` OS/version, and an
   actually implemented supported local adapter in this product build/runtime.
   The private result contains only `available` and a safe label; it does not
   construct or emulate an `executionnode.Node`, reveal transport data or run
   a Core operation.  `runtime.GOOS` alone is not evidence that this
   workstation is an Execution Node.  Without an implemented local adapter it
   deterministically returns unavailable; Windows never produces a candidate.
3. **AUTO_FIRST_ELIGIBLE** — select the lexicographically first eligible
   `hostId`, ensuring deterministic results.  A choice derived from a
   metadata-only draft is provisional: discard or session invalidation that
   removes its source clears the context to `NOT_CONFIGURED`.
4. Otherwise publish `NOT_CONFIGURED` / `NONE`.

The selected result becomes locked for that project context.  Adding, editing
or reordering servers does not silently switch it.  A manual selection sets
`PROJECT_SERVER` / `EXPLICIT`.  If the selected project server is deleted or
becomes ineligible, E4 clears it to `NOT_CONFIGURED`; it does not select a
replacement until the operator chooses one.  This respects the one-time rule
and avoids silently changing a future execution authority.

A successful project Create/Open that replaces the context initializes a new
one-time selection.  Successful Close and application shutdown clear it.  A
failed Create/Open leaves both the current project and its selection unchanged.
Unsaved server intents may update the panel's candidate label, but they cannot
become a trusted transport node or alter Core proof.

This policy intentionally does not make an arbitrary existing managed project
openable on a fresh workstation without an already selected Execution Node.
That needs an explicit Execution Node selection or a separately approved
bootstrap-open contract; E4 does not create either path.

## 6. UI behavior

The App Shell renders a compact clickable safe badge:

```text
Execution Node: NOT_CONFIGURED
Execution Node: NOT_PREPARED · node1
```

Clicking it navigates to Servers.  It is expressly application status and is
not represented as a project finding.  The existing UI currently allows only
Project and Servers for an open project; E4 preserves this static gate rather
than pretending that selection equals readiness.  E5 will make readiness-based
gating explicit.

The Servers page uses a two-row layout matching the mockup:

```text
independently scrolling server list
----------------------------------
fixed Execution Node panel
  selected node / source / NOT_CONFIGURED or NOT_PREPARED / Change
```

With zero servers the panel remains visible and says `NOT_CONFIGURED`.  With a
selected candidate it says `NOT_PREPARED` and gives the safe source label,
including “selected once” for automatic choices.  **Change** opens a bounded
server selector of current eligible project hosts.  There are no Check,
Prepare, SSH, credential, fact or fake-success controls in E4.

The E3 shared session-credentials panel remains independent.  Its availability
does not change the Execution Node panel and the panel does not show an E3
reference.

## 7. E5 Review/Save handoff

E4 supplies selection context only.  E5 owns the readiness check, the existing
check/prepare workflow, navigation gating and the `READY` state.  Per
`OWNER-UI-SAVE-EXECNODE-01`, when authoritative Review/Save requires READY, it
first consults E5's current result and may run its read-only readiness check
automatically.  Under `OWNER-UI-SAVE-EXECNODE-02`, any mutating preparation
requires explicit user confirmation.  Successful preparation resumes the
original Review/Save request rather than creating a parallel save path.
Failure or cancellation preserves the active edit draft and leaves canonical
project files unchanged.  The operator can retry, choose another Execution
Node or cancel.  This handoff does not authorize E4 to probe, prepare or claim
readiness.

## 8. Concurrency, failure and security

All context reads, manual selection and successful project lifecycle
replacement are serialized under `App.editMu`.  Selection computes from one
published project/snapshot/intents view, then atomically replaces the small
context.  No goroutine, polling loop, watcher or timer is required.

At application startup the fixed local-adapter probe runs at most once and
publishes its two-field, non-secret candidacy result to `App`.  It uses only
the product's local Execution Node adapter and returns unavailable on any
unsupported, incomplete, missing-adapter or probe-error condition.  Its fixed
checks are Linux, supported local architecture, a bounded local read of
`/etc/os-release`, and the presence of an actually implemented supported local
adapter.  It must not invoke Core, Python, Ansible, `InspectExecutionNode`,
SSH/SCP, elevation, bundle/runtime preparation, package managers,
repositories, target transports, facts discovery, mutation or the E3 broker.
The result is not a readiness finding and is discarded on application
shutdown.

Selection failures are local validation failures.  E4 logs no request objects
and returns no raw project documents.  It does not invoke the existing
Execution Node transport, Core, runtime-secret broker, filesystem writer or
network.  Project replacement and E3 broker cleanup retain their established
ordering; E4 merely clears its non-secret context in the same successful
lifecycle transition.

## 9. Implementation sequence

1. Add the fixed Go context/status type and one private `App` store with the
   explicit binding and selection helpers, plus one fixed local-adapter
   candidacy function; do not create a probe framework or registry.
2. Reuse the authoritative post-commit/current snapshot publication seam and
   the bounded in-memory server intents to calculate eligible rows once; do
   not duplicate React projection rules.
3. Add the two Wails operations and generated bindings.
4. Add Shell status navigation, Servers fixed bottom panel, one selector, and
   independently scrolling list styling.
5. Add focused Go/App and frontend tests, then recheck the relevant mockup
   states before acceptance.

## 10. Acceptance and regression evidence

Focused tests must prove:

- explicit external/manual selection wins; local Linux is considered only from
  the one bounded product-local adapter probe; `runtime.GOOS` alone is
  insufficient; Windows never invents one;
- Linux-positive, unsupported architecture, unsupported `/etc/os-release`,
  absent local adapter and probe-error cases deterministically return the
  expected candidate availability and reveal only a safe label;
- the local probe runs at most once, exposes no transport or credential data,
  and makes zero Core, bootstrap, elevation, package, repository or target
  calls; it produces candidacy, never READY;
- deterministic first eligible selection, zero-server `NOT_CONFIGURED`, and
  candidate `NOT_PREPARED`, using only an available Snapshot or acknowledged
  metadata-only final-state `CreateServer` intent;
- no local parsing of inventory, `group_vars`, `host_vars` or other canonical
  Ansible files; a discarded or invalidated metadata-only source clears a
  provisional selection;
- a selection occurs once per project context; server list edits do not move
  it; invalidation clears rather than silently replaces it;
- manual selection rejects absent/deleting/ineligible rows;
- successful Create/Open starts a fresh context; failed replacement preserves;
  Close/shutdown clear;
- no project file, inventory, host/group vars, Core snapshot fingerprint,
  EditSession, review/commit path or E3 status changes;
- zero calls to target or Execution Node transports, Core, preparation or
  runtime-secret resolution;
- Shell badge routes to Servers; the panel survives empty and long lists; only
  the server list scrolls; no E5 readiness controls appear;
- App/frontend unit tests, `go test ./...`, `go vet ./...`, affected Go race
  tests, frontend test/lint/build, `wails build -nopackage -clean`, secret
  audit and `git diff --check` pass during implementation acceptance.

E4 has no RED OS remote acceptance by itself because it neither contacts nor
prepares a host.  E6 retains combined Windows/RED OS acceptance after E5.

## 11. Overengineering guard

The current requirement needs exactly one small app-memory context because the
selection is neither canonical project desired state nor an established Core
fact.  Reusing `executionnode.Node` would incorrectly turn a project-row
choice into trusted transport authority and expose transport-only fields.
Persisting preferences, adding a node registry, generic CRUD API, discovery
worker, readiness cache or a second server DTO would add unsupported authority
or lifecycle surface.  The existing App mutex and the existing server editor
are sufficient; E4 adds no coordinator or background subsystem.
