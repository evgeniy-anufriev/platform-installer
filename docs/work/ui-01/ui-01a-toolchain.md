# UI-01A — Wails/React toolchain freeze

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01a-toolchain-checkpoint-001).

UI-01A installs or
scaffolds nothing. Exact application dependencies enter lockfiles only in
UI-01B and must be checked again against security advisories then.

## Selected baseline

| Component | Supported/pinned policy | Reason |
| --- | --- | --- |
| Wails | v2.15.0 CLI and Go module, exact | Current stable v2 docs and installed doctor; generated bindings and embedded frontend |
| Go | module minimum 1.25.0; CI baseline latest 1.25 patch; newer supported after gates | Wails v2.15.0 itself requires Go 1.25.0; workstation Go 1.26.7 is accepted |
| Node.js | 24 LTS; `>=24.19.0 <25` | LTS line, satisfies Vite/Vitest/ESLint; no Current/EOL line |
| npm | 11.17.0 exact through `packageManager`; committed `package-lock.json` | Already available; one package manager and deterministic `npm ci` |
| React / React DOM | 19.2.8 exact | Current stable React 19.2 patch at audit |
| TypeScript | 6.0.3 exact, strict | Current stable version compatible with selected typescript-eslint; TS 7.0.2 is not selected because typescript-eslint 8.69 supports `<6.1` |
| Vite | 8.2.2 exact | Minimal embedded frontend build; Node 24 satisfies engine |
| React plugin | `@vitejs/plugin-react` 6.1.1 exact | Matches Vite 8 peer range |
| Unit/component tests | Vitest 5.0.0, React Testing Library 16.3.3, DOM TL 10.4.1, user-event 14.6.7, jsdom 30.0.1 | User-visible behavior without browser-internal coupling |
| Types | `@types/react` 19.2.18, `@types/react-dom` 19.2.7, `@types/node` 24.13.3 | Strict generated/API boundary; exact Node 24 line |
| Lint | ESLint 10.10.0, `@eslint/js` 10.0.1, typescript-eslint 8.69.0 | Flat config; selected versions have compatible peer ranges |
| Format | Prettier 3.9.6 | Formatting only; ESLint owns correctness |
| Routing | No routing dependency in UI-01B | Desktop page state uses a typed `PageID`; no URL/deep-link requirement yet |
| Styling | Plain CSS/CSS modules; no component framework | Preserve minimal mockup and avoid design-system dependency before real reuse exists |

All JavaScript dependencies are exact in `package.json`; no caret/tilde ranges.
`npm ci` is the only CI/install command. Renovation is an explicit reviewed
dependency change, not ambient `latest` behavior.

## Repository layout planned for UI-01B

```text
app.go / main.go             # Wails bootstrap and thin bindings only
wails.json
frontend/
  package.json
  package-lock.json
  src/
    app/                     # typed page state and application shell
    components/              # reusable presentation components
    features/project/        # feature UI, no YAML/Core semantics
    bindings/                # Wails generated output; policy documented
  tests/
```

Final exact root names are chosen by Wails without moving existing `cmd/` and
`internal/` packages. The existing CLI remains independently buildable. Wails
methods delegate to application services; there is no method-per-button API.

The bridge exports an explicit allow-list of coarse application methods and
generated typed bindings only. It does not expose `os`, filesystem primitives,
generic path reads/writes, shell/argv, SSH, secret getters, YAML maps or a
reflection-based catch-all method. Every call validates size, enum/version,
project-context identity and cancellation server-side; errors are bounded safe
findings. Development tools and debug context menus are disabled in production
builds. The application uses no remote web content, disables navigation outside
embedded assets, and handles external help links through an explicit allow-list.
The embedded frontend ships a restrictive CSP (`default-src 'self'`, no remote
script/style/connect origins; only Wails-required connect/image allowances are
added and tested). Project/Core strings render as React text; `dangerouslySetInnerHTML`
and equivalent raw HTML rendering are prohibited for those values.

## Planned commands

```text
npm.cmd ci
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run format:check
npm.cmd test -- --run
npm.cmd run build
wails doctor
wails build
go test ./...
go vet ./...
```

PowerShell invokes `npm.cmd`, because the workstation execution policy blocks
the `npm.ps1` shim. The repository does not require changing user execution
policy.

## Workstation audit

`wails doctor` on 2026-09-05 reported:

- Windows 11 (reported compatibility version 2009/build 26200), amd64;
- Wails 2.15.0;
- Go 1.26.7;
- Node.js 24.19.0 and npm 11.17.0;
- WebView2 152.0.4191.62;
- system ready for Wails development;
- UPX and NSIS optional and not required for UI-01B.

No packages were installed and no scaffold was generated during this audit.

## Platform and runtime policy

- Windows 10/11 with WebView2 is the first development/acceptance platform.
- UI-01B runs `wails doctor` and fails clearly when a prerequisite is absent.
- Frontend assets are embedded in one Go desktop executable.
- Workstation never needs Python, Ansible or Platform Core.
- Linux/macOS remain architectural targets; platform-specific APIs stay behind
  narrow Go interfaces. Packaging is not claimed until separately tested.
- Frontend dependency acquisition is a DEV/build action. Production installer
  execution never accesses npm or the Internet.
- `package-lock.json`, Go sums/vendor policy, licenses and SBOM input are tracked.
  Offline/reproducible build cache is established before production release.
- UI-01B records every dependency lifecycle script, permits only reviewed
  build-tool scripts required by the locked graph, runs `npm audit
  --audit-level=high`, license/SBOM generation, `npm ci`, tests and production
  build in a clean workspace, and blocks high/critical unresolved findings.
  Lockfile changes and registry source URLs are reviewed; no Git/URL dependency
  or ambient `latest` range is allowed.

## Sources and compatibility evidence

- Wails 2.15 installation and platform requirements:
  https://wails.io/docs/gettingstarted/installation/
- Wails build command and output:
  https://wails.io/docs/gettingstarted/building/
- Node release policy and Node 24 LTS status:
  https://nodejs.org/en/about/previous-releases
- React stable version policy and 19.2 release line:
  https://react.dev/versions and
  https://react.dev/community/versioning-policy
- Vite Node engine requirements:
  https://vite.dev/guide/
- TypeScript 6.0 release notes:
  https://www.typescriptlang.org/docs/handbook/release-notes/typescript-6-0.html
- Vitest 5 engine compatibility:
  https://main.vitest.dev/guide/migration
- ESLint Node requirements:
  https://eslint.org/docs/latest/use/getting-started
- Testing Library setup:
  https://testing-library.com/docs/react-testing-library/intro/

Exact package versions and peer/engine ranges were additionally checked via
the public npm registry using `npm.cmd view`; they are evidence for this freeze,
not a lockfile or installation.

`@vitejs/plugin-react` lists optional alternative transform/compiler peers;
UI-01B does not add them unless its real scaffold demonstrates a requirement.
