# Nonvisual React/Wails acceptance

Required for every service and affected application flow. This is not visual
acceptance and is not the Vite `?qa=e4` mock. Use the supported Wails development
server and headless Playwright against real bound Go methods. Production builds
retain no debug endpoint; do not modify dependencies or add a production bypass.

## Local setup

Run Vite on loopback:

```powershell
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 4173
```

In a separate terminal:

```powershell
wails dev -s -skipbindings -nogorebuild -noreload -frontenddevserverurl http://127.0.0.1:4173 -devserver 127.0.0.1:34115 -appargs '<existing supported Execution Node/bundle flags>'
node scripts/qa-wails-bridge.cjs
```

Use absolute Windows paths with forward slashes inside `-appargs`; the Wails
argument parser interprets backslashes as escapes. Pass only identity file
paths and safe routing/lock metadata, never passwords/token/share values.
Use the configured installed Microsoft Edge; do not auto-download browsers.
The preflight proves real bindings are callable, not full service acceptance.

The WebView2 loader intentionally clears remote-debugging environment overrides.
Do not rely on those flags or patch vendor. The standard Wails dev server is
the existing development bridge, not a new product IPC mechanism.

## Required acceptance flow

Invoke real React controls/handlers for session credentials, structural edits
and local Save as applicable, fresh Plan, approval, Start, event subscription
and terminal Result. Inputs remain runtime-only. For services with protected
outputs exercise encrypted publication, receipt and ACK as well. A prepared
Core/managed project may be opened for installation acceptance; separate typed
edit tests prove authoring. The native folder picker alone may be replaced by
a known QA path calling the real `App.OpenProject`; record that substitution.
Do not replace business bindings, returned DTOs or execution with mocks.

Capture saved revision, runtime digest, safe failure codes, run IDs, terminal
result and repeat changed=0. Disable screenshots, trace/HAR and payload logging
while entering secrets. Never log raw selected files or secret-bearing DOM
values. Rendering exceptions are acceptance failures even if Core returned a
valid plan. Stop the owned dev server, Vite and headless browser after QA.

Visual layout/native-picker acceptance is separate. Direct Go tests and mocked
frontend unit tests are supplementary, not replacements for this gate.

## Nonvisual secret-file selection seam

Owner-approved dev-only selection substitution uses the environment variable
`PLATFORM_QA_SECRET_FILE_SELECTIONS`: a JSON array of 1-16 absolute paths,
each at most 4096 UTF-8 bytes, with no control characters. Set it before starting
`wails dev`. Values are paths only, never file contents or encryption passwords.
New production builds (`!dev`) ignore this variable and retain the native picker.
There is no additional exported Wails method or path field in the secret DTO.

The actual React `Выбрать файл` handler calls the existing bound Go import method.
After descriptor authorization, the private picker consumes one queued path;
the same handle-bound bounded reader, age decrypt/parser, binding/descriptor
rechecks and session-only broker run unchanged. Invalid/exhausted selections fail
closed; exhaustion never falls back to a native dialog. Cancellation does not
consume a queued path. Do not substitute import results, bytes or business calls.

Native Windows picker acceptance is separate and is not claimed by this test.
For this path-only seam do not use Computer Use or the owner-hiding workaround
below. Real encrypted admin-token.age and unseal-shares.age were accepted through
actual React/Wails into the session; no installation was launched by that probe.

## Windows native dialogs in headless acceptance

Use `scripts/qa-native-dialog.cjs` around the real React selection handler and
its completion: standard Wails `WindowHide`, native action, then `WindowShow`
in `finally`. Only the otherwise unused desktop owner is temporarily hidden;
the real Go dialog, file validation and session-secret boundary are unchanged.
The runtime window message is asynchronous; independently observe the dialog
through Computer Use before sending input. Select exactly one returned Window
with the Installer app identity and exact dialog title. If absent/ambiguous,
stop; do not activate the disabled main owner or synthesize a modal handle.
The helper's one-second settling delay is not a substitute for this observation.
On Windows with the owner visible, current automation can activate the disabled
owner and trigger Wails/WebView2 MoveFocus failure with process exit. Hiding the
owner makes the standard dialog independently targetable without modifying
dependencies or adding a product/test-only import method.
