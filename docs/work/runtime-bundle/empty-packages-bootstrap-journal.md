# EMPTY-PACKAGES-BOOTSTRAP-01 — evidence journal

## Scope and source identity

Owner accepted implementation 2026-10-13 and identified QA node2
`192.168.56.102`. Package download is allowed only for missing runtime
prerequisites absent from the supplied offline payload. Service artifacts and
their `requiredOffline` contract are unchanged. Branch `portable`, base
`0de2a38222f7ef2222d8808cfc4e0c69587fa1a7`.

## Implemented behavior

- Empty runtime input builds a fixed runtime/packages + runtime/python layout.
  Compatibility comes from populated package directories, repeatable explicit
  `--platform`, or data-only parsing of Linux os-release and uname architecture.
- Manifest-bound POSIX bootstrap checks the selected node's os-release/platform,
  installed RPMs and commands. Supplied missing-package RPMs are selected by
  RPM metadata; wholly local installation disables repositories. Missing names
  not supplied are passed to the existing configured DNF repositories.
  Corrupt RPMs/failed offline installation do not trigger an online retry.
- Transport supports existing SCP directory transfer without tar. Privileged
  bootstrap runs after root-owned content/hash/file-set validation. Separate
  bootstrap and activation SSH phases prevent cancellation from dispatching a
  later activation. Node-local flock serializes each phase. Active digest
  releases are reused, never removed; activation rollback retains prior link
  and metadata. Root-generated Python bytecode caches are derived state, not
  additional source components.
- Preparation preview/confirmation discloses possible package installation.
  READY still requires the normal Core capability handshake.

## Read-only node prerequisite evidence

Strict SSH host-key validation and established `platform-automation` identity,
`sudo -n`, confirmed on node2. Observed `ID=redos`, `VERSION_ID=8.0.3`,
`uname -m=x86_64`; flock available.
Installed: python3 3.11.15, ansible-core 2.18.15, openssl 3.5.5,
ca-certificates 2024.2.68, tar 1.35, gzip 1.12.
No existing package was removed or upgraded for a missing-package test.

## Automated checks

Current tree transferred with `scripts/qa-sync.ps1` to
`/var/tmp/platform-installer-qa-471a9c1662884f19b18a77bdf976a1c5` on node2.
Runtime bundle suite: 7 PASS. Bootstrap suite: 7 PASS; RPM/DNF are isolated
test doubles, not real package transactions. Covered installed-only,
empty-payload repository names, all-offline repository-disabled, mixed sources,
corrupt RPM, offline failure without retry, platform mismatch.

Linux test executable cross-compiled from current Go sources and run in the
same approved temporary QA workspace under sudo. Four affected tests PASS:
cancelled bootstrap does not dispatch activation; no-tar SCP fallback; disclosed
bootstrap step; native isolated activation failure/same-digest retry/concurrent
lock preserves previous runtime/metadata. Native fixture uses fake capabilities
commands and isolated paths; this is supplementary, not a real Wails acceptance.

`go test ./...` and `go vet ./...`: PASS. Local Wails v2.15.0 CLI, frontend
and Windows production application build: PASS.

## Independent review and owner decisions

Initial FULL DIFF: BLOCK at fingerprint
`39c3086ed0097592648e43c89759e32a83bc6f80d0d5aa9d1400b7a83f6da454`.
EPB-D01: DNF dependency solving can update installed prerequisites. Owner
explicitly permits such updates on 2026-10-13; no package-preservation guarantee
is claimed. EPB-D02: actual React/Wails Prepare/READY absent. Owner explicitly
excludes this gate from the current stage on 2026-10-13. No UI acceptance PASS
is claimed. EPB-P01 same-digest preservation/concurrent preparation resolved by
FULL review. One targeted recheck returned APPROVE_WITH_CHANGES with zero blockers;
see [review](empty-packages-bootstrap-diff-review.md).

Physical missing-package installation remains unverified: node2 already has all
prerequisites. Test doubles do not demonstrate real DNF dependency solving.
No runtime bundle publication/rebind/activation or installation Start performed.
Visual inspection not performed. Final source retest and portable repack completed. Both temporary remote QA
workspaces cleaned with the canonical qa-sync cleanup command.

## Final current-source checks

Canonical QA sync to `/var/tmp/platform-installer-qa-a60da950199849718044c9745737e137`
on node2: builder 7 PASS, bootstrap 7 PASS. Fresh cross-compiled Linux test
executable: four native bootstrap/activation cases PASS. `go test ./...` and
`go vet ./...` PASS on final implementation. Physical RPM/DNF solving and actual
React/Wails preparation remain unverified under the owner-approved stage scope.

Portable repack: 6122 files, 15 parts, 6034 readable-text and 88 binary-resource
files; maximum part 4,993,124 bytes. SHA-256 source comparison PASS; unpack and
restored-file comparison PASS. First restoration attempt encountered a Windows
rename access error; a second fresh destination succeeded. CLI build from
restored sources with `-mod=vendor` PASS. Source snapshot retains Wails v2.15.0.
Runtime bundle not published or activated; only portable source branch updated.
