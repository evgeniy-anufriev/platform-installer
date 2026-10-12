# Local browser mode plan

Status: owner-approved local scope and decisions; implementation is in
progress. Scope is limited to one interactive user on the same computer as the
Installer process. The approved targeted plan recheck resolved BROWSER-LOCAL-01
and BROWSER-LOCAL-03; implementation acceptance remains pending.

## Goal

Allow the existing React Installer to run in an ordinary browser without
starting Wails. Wails remains an optional desktop wrapper over the same
application services and React UI. Keep one React application and one Go
application backend. Do not add browser-versus-Wails branches to page or
component logic.

## Owner decisions and scope

- The user requested browser operation on the same computer for one user.
- Browser mode must not start or depend on the Wails runtime. Wails remains an
  optional desktop wrapper; remote access, multiple users and a persistent
  standalone web service are out of scope.
- The owner approved one active browser tab per host process. Reloading the
  owning tab reconnects it; a second tab is rejected before it can interact
  with Go application state.
- The owner approved Windows as the initial browser-host platform, using a
  Windows-native file picker independent of Wails. Other Wails platforms are
  out of the initial browser-host scope.
- The owner approved an explicit browser Exit action. Closing the tab does not
  cancel an active execution or immediately stop its host; an idle host shuts
  down after a bounded inactivity interval. Exit stops immediately when no
  execution is active and otherwise requests shutdown after the active run
  reaches a terminal state.
- The existing portable Ansible project remains canonical desired state.
  Browser transport does not create another project store or move Core
  semantics out of Go/Ansible.

## Existing contracts and UI flows

- `frontend/src/backend.ts` defines `ProjectBackend`; `App` already accepts an
  injected backend. The default implementation calls generated Wails bindings.
- `frontend/src/main.tsx` is the React composition root. `App.tsx` directly
  subscribes to `EventsOn` for installation events, so event delivery must also
  move behind the injected frontend boundary.
- Go `App` methods currently use Wails dialogs to open a project, select
  create/export directories and choose a runtime-secret file. Installation
  progress is emitted through the Wails event bus in
  `internal/desktop/installation_execution.go`. Browser mode cannot call
  either Wails runtime facility; both must be behind transport/platform
  interfaces.
- Relevant mockup flows in `docs/design/ui-design-01-mockups.html` and
  `docs/design/ui-design-01.md`: open/create project, edit/review/save, project export,
  runtime-secret file selection, and live installation progress. Browser mode
  must keep these flows and their existing Go/Core contracts. Browser mode
  needs a local file-dialog implementation that does not call Wails runtime.
- Existing mockups remain the screen-flow baseline. Browser mode adds the
  owner-approved host Exit action to the application header; it is a host
  lifecycle control and is not shown in the desktop mockups. The browser is an
  alternate presentation transport for the same UI and application state. The
  existing local project/file chooser flows must remain available without
  Wails; the browser-mode file-dialog provider is Windows-native and
  independent of Wails.

## Proposed architecture

1. Keep `ProjectBackend` as the frontend application contract. Move the
   Wails-specific event subscription out of `App.tsx` into that contract.
   Provide Wails and browser HTTP implementations at the React composition
   root; select one adapter once during startup. Pages and components remain
   unaware of the transport.
2. Separate the shared Go application services from Wails runtime calls. Keep
   Wails dialogs and event emission behind injected interfaces for desktop
   mode. Add a browser host entrypoint that runs the same Go application
   services and local HTTP server without calling `wails.Run` or requiring a
   Wails context. The browser host opens the system browser itself.
3. Serve the existing built frontend and versioned API from one loopback
   origin. Bind only to `127.0.0.1` on an ephemeral port. Generate a
   cryptographically random, process-only bootstrap capability. The proposed
   flow passes it in the initial URL fragment, exchanges it for a
   process-only, same-origin HttpOnly/SameSite session cookie, and removes the
   fragment from browser history. Require the cookie and exact Origin for API
   and SSE; do not enable CORS and never log request bodies or capability
   values. The server grants one interactive-tab lease per process; API
   requests require that lease, and a second tab receives a non-interactive
   "already open" response. Reload/reconnect by the owning tab reuses the same
   process-only cookie and lease.
4. Expose only explicit typed operations needed by `ProjectBackend`. Do not
   reflect over arbitrary Go methods and do not add a shell/command endpoint.
   HTTP calls delegate to the same `App` methods that Wails invokes.
5. Add a process-local event fan-out for the existing installation event
   sequence. The Wails adapter continues to use Wails events; the browser
   adapter receives authenticated SSE events and reconnects from the last
   observed sequence. Preserve existing run IDs, sequence numbers and
   cancellation semantics.
6. Provide browser-host file dialogs through a platform interface that does
   not depend on Wails. The initial browser-host adapter uses Windows-native
   directory/file dialogs and preserves existing path and secret-file
   semantics. Keep session credentials and secrets in the existing runtime-only
   Go state.
   The browser mode does not change filesystem ownership, project revisions,
   approval gates, Core execution location, or offline bundle policy.

## Implementation sequence

1. Recheck `main` and merge relevant application/API changes before each
   implementation slice; do not overwrite unrelated worktree changes.
2. Extract the frontend event subscription into `ProjectBackend` and add the
   browser adapter at `main.tsx`, retaining current Wails default behavior.
3. Add the independent browser-host entrypoint, loopback server, explicit typed
   API routes, session capability and shutdown lifecycle. It must not call
   `wails.Run` or Wails runtime methods.
4. Bridge installation events to authenticated SSE with sequence-based
   reconnect; keep Wails event behavior intact.
5. Add the browser-host launch option, open the default browser and implement
   the explicit Exit action, bounded idle shutdown and active-run deferral.
   Keep the Wails desktop entrypoint as a separate adapter over the same
   application services.
6. Validate the browser React handlers against the real local Go API and
   validate the existing Wails path separately. Exercise dialogs, credentials,
   project operations, plan/approve/start, event reconnect and shutdown without
   replacing production methods with mocks or bypasses.
7. Recheck the mockups at acceptance and document the supported local-only
   behavior and limitations.

## Explicit non-goals

- Remote/LAN access, multi-user authentication/authorization or a persistent
  daemon.
- A second desired-state or session database.
- Uploading a copied project tree or making browser JavaScript own project
  filesystem transactions.
- Duplicating Go application methods or Ansible/Core rules in TypeScript.
- Changing service plans, execution-node protocols or runtime bundle policy.

## Remaining implementation constraints

- A process restart invalidates the in-memory cookie and tab lease; the
  browser host must issue a fresh bootstrap URL on its next launch.
- The HTTP API must not expose arbitrary filesystem paths or commands beyond
  existing typed project/file-dialog operations.
- Exact API route shape and SSE shutdown/reconnect bounds are implementation
  details within the approved loopback-only, one-tab boundary.
