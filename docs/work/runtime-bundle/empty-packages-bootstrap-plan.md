# EMPTY-PACKAGES-BOOTSTRAP-01: runtime bundle without RPM payload

Status: owner accepted implementation on 2026-10-13: downloading is allowed
only for packages not installed and absent from the offline bundle. Independent
FULL PLAN review: APPROVE_WITH_CHANGES, zero blockers.
[Review](empty-packages-bootstrap-plan-review.md). No target mutation or milestone
acceptance has occurred. Implementation/QA status is recorded in CURRENT_STATE
and the [journal](empty-packages-bootstrap-journal.md). Base:
`0de2a38222f7ef2222d8808cfc4e0c69587fa1a7`, branch `portable`.

## Owner decisions

- Allow the bundle builder to work when `runtime/packages` is empty.
- Execution Node preparation must install required runtime packages through
  `dnf install` when they are absent from the bundle.
- Add reading of `/etc/os-release`.
- Concrete plan accepted by subsequent direct instruction; download only when
  the runtime prerequisite is absent from both installed state and bundle.
- Owner clarification 2026-10-13: dependency updates during DNF installation
  are allowed; actual React/Wails Prepare/READY is not required at this stage.
- Scope is runtime prerequisites, not service payloads. ClickHouse/Kafka
  `requiredOffline` declarations and deployment-source selection are unchanged.

## Existing contract and change

ADR-021 currently says preparation never downloads packages. This proposal
changes that rule for the fixed pre-Core runtime prerequisite set only, using
the selected node's existing configured approved DNF repositories. No repository
is added/enabled, no Internet URL is introduced, and no distributed bundle is
modified. Source/desired-state ownership remains unchanged. Go owns pre-Core
orchestration; a verified fixed shell resource under `ansible-core/tools` owns
bootstrap package actions on the selected Linux node before Python exists.

A bundle with no RPMs is repository-dependent for a fresh node; it does not
claim a complete offline runtime. An already provisioned node needs no package
transaction. Fresh targets still do not build their own bootstrap bundle.

## Builder

1. Keep required Core/services/contracts/catalog content and manifest integrity.
   Allow an existing empty runtime-input directory and absent/empty `packages/`
   or `python/`; construct the fixed empty layout in the new output directory.
   Never modify runtime-input or an existing output.
2. Keep discovery of platform identities from populated package directories.
   Add repeatable `--platform OS:VERSION:ARCH` for explicit compatibility
   identities, usable to target a different host/platform.
3. If no package platform and no explicit identity exist, infer build-host
   identity on Linux by parsing `ID`/`VERSION_ID` from `/etc/os-release` as data
   and architecture from `uname -m`. Never execute file contents in Python.
   Validate all three tokens; fail with an actionable error if inference is
   impossible. Retain exact OS/version/architecture matching; no wildcard or
   guessed version aliases. Current execution support remains RED OS/x86_64.
4. Manifest `platforms` is always nonempty and deterministic. Manifest format
   and component SHA-256 binding remain unchanged. Explicit platform metadata
   declares intended compatibility, not acceptance evidence for that platform.
5. Document manual CLI creation and UI project-import path. Creating a bundle
   from a new empty runtime input remains a trusted acquisition-host operation.

## Execution Node preparation

1. Use the existing approved preparation plan and selected node/SSH identity,
   strict host-key checks, `sudo -n`, context/cancellation and safe error paths.
   Add a bounded `ensure-runtime-packages` step to the existing preparation
   preview; no new arbitrary-command bridge, transport DTO or UI source policy.
   Existing READY runtime preparation does not reinstall packages.
2. The remote bootstrap reads `/etc/os-release` (`ID`, `VERSION_ID`) and
   `uname -m`, checks them against the selected manifest platform, and derives
   only that platform's verified `runtime/packages/OS/VERSION/ARCH` directory.
   Unsupported OS, identity mismatch or missing required tools fails clearly.
3. The fixed prerequisite names are `python3`, `ansible-core`, `openssl`,
   `ca-certificates`, `tar`, `gzip`, plus dependency closure resolved by DNF.
   Use RPM installed-state checks and command checks before any transaction.
   Installed prerequisites are omitted from explicit install arguments. Owner
   decision 2026-10-13 permits DNF dependency solving to update installed
   packages when required by installation of missing prerequisites. There is
   no standalone upgrade/reinstall transaction when all prerequisites exist.
4. When local RPMs exist, use RPM metadata rather than filenames to associate
   missing prerequisites. Install local candidates/dependency closure through
   DNF. If every missing prerequisite has a supplied complete local closure,
   run the local install with all repositories disabled. If requested runtime
   packages are absent locally, install their package names from existing
   configured approved repositories; local RPMs may satisfy the other missing
   prerequisites in that transaction. Do not silently switch to repository
   after a corrupt/incompatible supplied RPM or failed offline transaction.
   Incomplete advertised offline closure fails with a precise prerequisite
   error instead of pretending to support offline bootstrap.
5. Stage transfer currently depends on remote `tar`. If tar is unavailable,
   reuse existing `transferBundle` SCP directory transfer, rather than requiring
   tar before it can be installed from the supplied bundle. Do not introduce
   another archive format or a second transfer abstraction. Ensure fixed empty
   runtime directories exist after archive extraction for an empty payload.
6. Preserve bundle verification on the workstation and after remote transfer.
   Before running the new bootstrap as root, copy verified staged content into
   the exact managed release, make bundle content root-owned, and recheck the
   exact component digests under root. Do not execute a new privileged shell
   resource directly from mutable SSH-user-owned staging. Paths must remain
   within the existing managed stage/release roots; reject symlinks/unsafe
   entries. Reuse existing release handling rather than another persistence
   model. Review must consider this ordering/ownership change explicitly.
7. Run the fixed bootstrap resource from the verified root-owned release before
   Python-dependent storage setup/capability handshake. Afterwards perform the
   ordinary existing Core activation and authoritative capabilities check.
   Do not mark READY from `dnf` exit code, command presence or unit-test results.
8. Package-manager output must not expose repository credentials or URLs with
   secrets. Return bounded safe errors and nonsecret package/source observations.
   Failures retain the prior active runtime/state and stop activation. Installed
   OS packages cannot be promised to roll back after later capability failure;
   report partial preparation honestly and allow an ordinary retry.
9. EPB-P01 clarification: an active release must not be deleted or overwritten
   during retry of the same digest or overlapping Prepare attempts. Preserve
   existing release contents, `current` and active metadata until the new
   candidate passes verification/handshake. Use existing coordination and
   managed activation mechanisms, without a new transaction-manager layer.

## UI consistency and documentation

Servers owns selected-node Check/Prepare; Installation never bootstraps a node.
Use the existing preparation confirmation and status transitions from
`docs/design/ui-design-01.md` Servers/Execution Node section. No layout change
is proposed. The preparation preview must disclose runtime package installation
and possible configured-repository access. Update ADR-021, runtime-bundle
procedure, architecture prerequisite wording, roadmap/state entry and portable
README when the proposal is approved. Do not claim a fresh-node/offline PASS
from existing installed tools.

## Verification and acceptance

- Builder tests: empty runtime input with explicit platform; Linux os-release
  inference; quoted values; malformed/missing identity; unsupported architecture;
  populated legacy input; mixed declared/discovered platforms; deterministic
  manifest; duplicate/path-traversal tokens; read-only input and output refusal.
- Go/transport tests: visible bootstrap plan step; os-release mismatch before
  mutation; installed runtime no DNF call; empty payload repository fallback;
  local-only repository-disabled path; missing offline closure; corrupt RPM;
  no tar SCP transfer; root-owned recheck before privileged bootstrap; cancellation,
  package failure and capabilities failure without READY/active-pointer changes.
  Explicitly cover same-digest preparation failure and overlapping Prepare
  attempts, preserving previous release bytes, `current` and active metadata.
- RED OS tests run current working-tree builder/bootstrap sources with the
  canonical QA transfer and identity. Read-only host checks first. Existing
  shared-node packages are not removed to fake a fresh host. A missing-package
  mutation case requires a suitable explicitly owned fresh/disposable target.
- Owner decision 2026-10-13: actual React/Wails Check/Prepare/READY is outside
  acceptance of this stage. Automated builder/bootstrap/transport checks are
  the current gate; real UI flow and physical missing-package transaction are
  unverified and must not be reported as PASS.
- HIGH-RISK DIFF requires one independent FULL review after implementation.
  Keep one FULL plus at most one owner-approved TARGETED_RECHECK budget; BLOCK
  stops automatic work. No review or unit test replaces owner acceptance.
- Repack portable sources only after implementation checks; preserve raw text
  payloads and the 5 MB part limit. Update published `portable` only for the
  approved, validated scope. Do not silently publish/rebind a runtime bundle.
