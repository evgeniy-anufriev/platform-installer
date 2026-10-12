# UI-01I — Portable native project export and reopening architecture

Status: **PLAN — owner-revised after FULL review; targeted recheck pending**

Milestone: **UI-01I**

Prerequisite: UI-01H is DONE. This document is architecture only. It does not
authorize implementation, a new archive/import format, template slots,
migration, Core execution, service execution or mutation of the source project.

## 1. Goal

UI-01I exports the exact **saved** portable desired state of the current
Installer-managed project into a new native Ansible project directory and can
then reopen that directory through the existing read-only project-open flow.

The exported directory is directly usable by standalone Ansible/Core. It is
not a new persistence model, backup database or generated runtime workspace.
Draft commands, runtime credentials, generated state, plans, facts, logs,
results and verification evidence are not exported.

The milestone proves this flow:

```text
saved managed project revision
  -> bounded safe export preview
  -> explicit destination confirmation
  -> guarded new-directory publication
  -> optional explicit OpenProject(exportedRoot)
  -> standalone target-free RED OS validation
```

Export does not require a READY Execution Node or Core. Core validation of the
export is an acceptance gate, not part of the local export transaction.

## 2. Mockup reconciliation

Before implementation, the relevant mockup areas are:

- **Projects** page and **Export project** action;
- preview of included portable documents and compatibility information;
- the distinction between full configuration and template export; and
- reopening the exported project.

The mockup is aspirational in two material respects:

1. It calls the result a bundle and shows a `.piproject` file. UI-01I instead
   publishes a **native project directory**. The application already opens a
   directory, and standalone Ansible needs that directory layout. Defining an
   archive container, extraction trust boundary and arbitrary archive import
   contract is explicitly outside this milestone.
2. It shows **Template** mode with server slots. UI-01I implements only **Full
   saved configuration**. Template slots, remapping and template import remain
   deferred.

The implementation must update labels accordingly and repeat this mockup
comparison at acceptance. Demo compatibility/status values in the mockup are
not authoritative facts.

## 3. Authority and ownership

1. The portable project remains the only desired-state authority. Export is a
   bounded copy of its saved portable files, not serialization from React or a
   second Go model.
2. React never reads YAML, reconstructs configuration or receives raw file
   contents. It receives only bounded paths, sizes, digests, revision and safe
   status metadata.
3. Export preserves source bytes for included files except `project.yml`:
   the owner-approved export name also becomes the copied manifest's
   `metadata.name`. The source and project ID remain unchanged. Only this
   manifest may have normalized YAML formatting; supported unknown fields
   and extensions retain their values. Anchors, aliases, merge keys,
   duplicate/ambiguous mapping keys and multiple YAML documents are rejected
   before renaming. An absent optional manifest is not fabricated. Preview
   sizes/digests describe output bytes; source revision and stability guards
   still refer to the original saved source. See
   [display-name plan](../project-lifecycle/project-export-display-name-plan.md).
4. Core remains authoritative for project semantics and compatibility.
   Export may copy a saved `UNVERIFIED`, `STALE` or `INVALID` project and must
   show that status without claiming validity. Export never creates fresh
   verification evidence and never makes Installation eligible.
5. A fresh `BuildDeploymentPlan` remains mandatory before every execution.
   Export/reopen cannot reuse a source plan or bypass planning.
6. Runtime-only credentials remain in Installer session state and are never
   exported. UI-01I does not resolve, inline or test SecretRefs. The portable
   project contract already prohibits plaintext secret values; export does not
   invent content inspection as a substitute for that contract.

## 4. Eligibility and source lifecycle

Export is available only when all of the following hold:

- a current project root is open;
- classification is `EMPTY_MANAGED_PROJECT` or `MANAGED_PROJECT`;
- no EditSession/draft is active;
- no `COMMITTED_REFRESH_FAILED` state is awaiting read-only reopen; and
- the source can be observed as one coherent saved revision.

An accepted preview is represented in Go by one bounded in-memory active
export capability. It owns the exact opened source-root handle and destination-
parent handle, their opened-object identities and the bounded plan metadata.
It is neither desired state nor a persistent plan database. At most one exists
per application instance.

`EXTERNAL_PROJECT`, incompatible, unsafe and unavailable projects are not
exportable in UI-01I. Exporting arbitrary foreign ownership would either lose
files or silently define an adoption contract. Such a project may still be
opened by the existing read-only path.

Unsaved changes are never silently ignored. While a draft exists the UI
disables Export and explains that the user must first **Save** or **Discard**.
Export does not invoke Save automatically.

The capability closes both retained handles on successful or failed commit,
preview invalidation, an otherwise allowed project close/switch, and
application shutdown. The source remains the current project after successful
export. Reopening the copy is a separate explicit action and uses the existing
`OpenProject` guard.

## 5. Closed portable file set

UI-01I exports only regular files in this closed set:

- `project.yml`;
- `ansible.cfg`;
- `inventory/hosts.yml`;
- `.yml`, `.yaml` and `.json` files below `inventory/group_vars/**`; and
- `.yml`, `.yaml` and `.json` files below `inventory/host_vars/**`.

The following are excluded even if present below the source root:

- `inventory/group_vars/all/platform-state.yml` generated state;
- `.git/**`, `.runtime/**`, runtime workspaces and caches;
- event journals, logs, plans, facts and execution results;
- local verification evidence and application state;
- runtime credential/session material; and
- every file outside the closed portable set.

The exported structure therefore includes project metadata, inventory,
portable desired `group_vars`/`host_vars`, catalog/artifact locks carried by
the canonical project, and writer-preserved extension fields. It does not copy
bundle payloads or local immutable artifact caches.

The exporter must not reuse the existing broad `copyProject` helper. It needs
a narrow export collector because `copyProject` intentionally stages a larger
tree for a different lifecycle.

## 6. Bounds and path safety

The export collector uses the existing managed-project bounds:

- at most **4096 files**;
- at most **4 MiB per file**;
- at most **64 MiB aggregate content**; and
- at most **512 UTF-8 bytes per normalized logical path**.

It rejects:

- absolute, escaping or non-canonical paths;
- duplicate normalized paths and Windows case-collisions;
- alternate data streams and reserved/device names;
- symlinks, junctions, reparse points and path traversal through them;
- hard-linked source files;
- sockets, FIFOs, devices and all non-regular files; and
- source mutation that prevents a coherent observation.

`PlanProjectExport` safely opens the source project root once without following
links/reparse points, records that opened directory object's filesystem
identity and retains that exact handle for the lifetime of the active export
capability. The source display path is metadata only and is never reopened as
the security authority during commit.

Discovery may identify candidate logical paths, but all discovery and reads
are relative to that retained root handle, and bytes and identity must be bound
to the **same opened file object**. Reuse/extend the existing narrow platform-
specific no-follow opened-object mechanism used by F1-owned reads:

- POSIX/Linux: component-relative `openat`, `O_NOFOLLOW`, `fstat`, regular-file
  and link-count checks;
- Windows: component-relative no-reparse handles, opened-handle attribute and
  file-identity/link-count checks.

The bytes read from those handle-relative opened files are the bytes bounded,
hashed, previewed and written. No check-path-then-`os.ReadFile(path)` sequence,
per-file reopening of the root path, or commit-time reopening of the root path
is allowed. This remains a narrow export helper, not a generic secure
filesystem framework.

## 7. Coherent preview and commit binding

### 7.1 Whole-observation rule

One preview attempt, entirely relative to the same retained source-root handle,
is:

```text
O0 = safely enumerate the closed export set
  -> open, verify, bound, read and hash every included file
  -> compute canonical raw-byte project revision from those exact bytes
  -> build stable sorted export manifest
O1 = repeat the complete handle-relative observation and revision calculation
```

The preview is accepted only when the source-root identity is unchanged and
`O0` and `O1` have identical normalized path sets, sizes, file identities,
digests, canonical revision and manifest. The retained root handle—not the
string path—is the authority for both observations. If they differ, discard
the whole observation and retry once through the same retained handle. A
second difference returns `PROJECT_CHANGED`; partial or mixed preview is never
returned.

The revision algorithm remains the canonical raw-byte `ProjectRevision`
algorithm, but UI-01I computes it from the safely opened handle-relative
objects. The current path-based `ProjectRevision` implementation is not used
as the sole coherence proof for export.

The generated `platform-state.yml` is excluded from both the export and source
revision binding. Runtime changes to generated state therefore neither enter
the output nor create a false desired-state revision.

### 7.2 Closed application DTO

`ProjectExportPlan` is an application/Wails DTO, not a new public portable or
versioned project contract. It contains only:

```text
sourceProjectRoot       normalized display path
sourceProjectRevision   exact saved revision
destinationParent       normalized validated parent
directoryName           validated leaf name
destinationRoot         derived by Go
documents[]             stable {logicalPath, size, sha256}
aggregateSize
excludedCategories[]    closed safe labels, not discovered paths/content
projectStatus           saved verification status for display only
compatibilitySummary    already trusted bounded current projection, if any
planDigest              SHA-256 over all security-relevant fields
```

The plan contains no file bytes, raw YAML/JSON, credentials or arbitrary
diagnostics. Ordering is bytewise stable by normalized logical path.

`planDigest` binds the source root identity, source revision, destination,
sorted document path/size/digest list and contract version. The backend keeps
no persistent export-plan database.

### 7.3 Commit revalidation

`CommitProjectExport` does not trust the React-returned document list and does
not reopen the source root from `sourceProjectRoot`. Through the same retained
source-root handle it repeats handle-relative discovery, no-follow opened-file
reads and hashing, recomputes the canonical revision, and requires the same
root identity, revision, manifest and `planDigest`. Any drift returns
`PROJECT_CHANGED` or `EXPORT_PLAN_STALE` before publication.

This keeps preview meaningful without creating a second save/session system.

## 8. Destination and publication transaction

The user selects an existing destination parent through the native directory
dialog and enters a folder leaf name. During `PlanProjectExport`, Go safely
opens that parent without symlink/reparse traversal, records its opened-object
identity and retains the exact directory handle in the active export
capability. The parent and derived destination string paths are display/UX
metadata only and never become publication authority.

Go owns a dedicated narrow `ValidateExportDirectoryName` rule. It accepts one
non-empty leaf of at most **128 UTF-8 bytes** and rejects separators, rooted
paths, `.`/`..`, ADS syntax, control characters, Windows reserved/device
names, and invalid or trailing dot/space forms where applicable. React may
mirror these checks for immediate feedback, but Go is authoritative. This rule
does not reuse or redefine project display-name semantics.

UI-01I is create-only:

- destination must not already exist;
- no overwrite, merge, repair or adoption;
- destination cannot equal, contain or be contained by the source root;
- existing ancestors and the selected parent must be verified directories
  without symlink/reparse traversal; and
- every destination mutation must remain relative to the retained parent
  handle and opened-object identity.

Publication uses this transaction:

```text
retained identity-bound destination-parent handle
  -> create one uniquely named sibling staging directory relative to it
  -> retain the created staging identity
  -> create only manifest-declared descendants/files relative to staging
  -> write exact safely-read bytes with create-exclusive semantics
  -> flush and close every file
  -> verify staged manifest and aggregate digest
  -> fsync/FlushFileBuffers where supported by the existing platform seam
  -> revalidate source binding through the retained source-root handle
  -> check requested leaf absence relative to the retained parent handle
  -> atomic no-replace rename staging -> requested leaf relative to that parent
```

On failure before publication, remove only the exporter-owned staging
object through its retained parent/staging identity. Never delete or mutate the
source. Never recursively delete a path that was not created and identity-
bound by this operation.

Linux uses a narrow `openat`/`mkdirat`/related dirfd seam and
`renameat2(RENAME_NOREPLACE)` relative to the retained parent. Windows uses the
existing no-reparse/opened-directory-handle approach plus a narrow handle-bound
no-replace publication primitive. It must not re-resolve the destination
parent by path immediately before rename. If a platform cannot provide those
guarantees, it fails closed. Existing project-creation publication code may be
factored only where it satisfies this handle-relative contract; UI-01I must not
introduce a general filesystem transaction framework.

Once the atomic rename succeeds, export is committed. A later reopen failure
returns `EXPORTED_REOPEN_FAILED` with the safe destination path; it never
deletes the exported project and never retries publication.

## 9. Backend and Wails surface

The minimum application surface is:

```text
ChooseProjectExportParent() -> path | no selection
PlanProjectExport({destinationParent, directoryName}) -> ProjectExportPlan
CommitProjectExport({planDigest}) -> ProjectExportResult
OpenProject(exportedRoot) -> existing ProjectOpenResult
```

The backend owns the active preview capability containing the retained source-
root and destination-parent handles/identities plus bounded metadata.
`CommitProjectExport` accepts only the opaque digest from React; it never
accepts replacement paths or a document manifest at commit time and never
reopens either authority from a string path.

Only one export preview/commit may be active per application instance. Project
open/close/create, edit-session start and a second export are rejected while
commit is running. Preview is invalidated by project switch, Save, Discard,
session creation, source revision drift or application restart.

After explicit Export confirmation, commit runs synchronously to success or
failure and has no user-facing interruption operation. Open, Close, Create,
EditSession start and another export remain blocked until it returns. Any
pre-publication failure cleans only identity-bound staging. Atomic publication
is the commit point and is never rolled back by a later UI action. UI-01I adds
no background-operation or interruption framework.

`ProjectExportResult` contains only status, destination root, exported source
revision, document count, aggregate size and safe diagnostic code. No raw file
content or secret material crosses Wails.

## 10. User experience

The **Project** page adds **Export project** only for an eligible managed
project. The modal contains:

- fixed mode **Full saved configuration**;
- destination parent picker and required folder name;
- source revision and saved/verification status;
- stable included-document path/size list;
- aggregate count/size;
- explicit exclusions: drafts, credentials, generated/runtime state, logs,
  plans, facts and results; and
- compatibility summary only when already backed by current trusted catalog
  evidence.

The user first requests **Preview**, then explicitly confirms **Export**.
Changing parent or folder name invalidates the preview and requires a new one.

Success offers:

- **Open exported copy** — invokes existing `OpenProject` and switches only if
  that call succeeds; or
- **Stay in current project** — the default.

The UI never calls export a verified backup, never promises compatibility
without evidence and never shows raw portable values.

## 11. Error model

Closed safe application codes include:

- `EXPORT_NOT_AVAILABLE`
- `EXPORT_DRAFT_ACTIVE`
- `EXPORT_SOURCE_UNSAFE`
- `EXPORT_LIMIT_EXCEEDED`
- `EXPORT_DESTINATION_INVALID`
- `EXPORT_DESTINATION_EXISTS`
- `EXPORT_DESTINATION_UNSAFE`
- `EXPORT_PLAN_STALE`
- `PROJECT_CHANGED`
- `EXPORT_WRITE_FAILED`
- `EXPORT_PUBLISH_FAILED`
- `EXPORTED_REOPEN_FAILED`

Diagnostics identify only the safe logical field/path needed for correction.
They never contain file contents, credentials, arbitrary YAML values or
runtime secret references.

## 12. Delivery slices

### UI-01I1 — bounded export planner and publisher

- closed file-set collector and same-opened-object reads;
- coherent preview and plan binding;
- destination validation, staging and no-replace publication;
- focused Windows/Linux path, race, limit and rollback tests.

### UI-01I2 — Project page export flow

- Wails bindings and bounded DTOs;
- parent picker, folder-name validation, preview and confirmation;
- status/exclusion rendering and synchronous commit state;
- explicit reopen using the existing project-open flow.

### UI-01I3 — cross-platform acceptance and finalization

- real Windows Wails export and reopen;
- byte/digest comparison of included files and proof of excluded artifacts;
- standalone target-free Core validation on RED OS;
- comparison of source and exported normalized Core desired projections;
- regression, security, reproducibility and documentation gates.

Template/archive import remains a separately approved future milestone.

## 13. Acceptance and QA

Focused tests must prove:

1. only the closed portable file set is exported;
2. generated state, runtime artifacts, logs, results, plans, facts and session
   credentials are absent;
3. comments, formatting, unknown supported variables and extensions in
   included documents are preserved as exact bytes;
4. preview and commit are bound to the same source revision, source object
   identities, destination and manifest;
5. source drift, replacement between discovery/open, symlink/reparse paths,
   hardlinks, case collisions and every bound fail closed;
6. destination existing/inside-source/source-inside-destination cases do not
   mutate either tree;
7. any failure before publish removes only identity-bound owned staging;
8. publication is no-replace and a post-publication reopen failure preserves
   the completed export;
9. exported copy reopens through the existing coherent `OpenProject` path;
10. export makes no Core, Execution Node or target-host contact;
11. `UNVERIFIED`, `STALE` and `INVALID` are represented honestly and are not
    changed by export;
12. using the same target-free Core, catalog and runtime identity, source and
    exported projects produce the same normalized portable semantic projection
    and fingerprint, excluding only location/runtime-local metadata and the
    intentionally omitted generated state; and
13. fresh deployment planning remains required for execution from the copy.

Implementation gates:

- focused Go/backend and frontend tests;
- `go test ./...`;
- `go vet ./...`;
- affected Windows and RED OS race tests;
- frontend lint/test/build;
- `wails build -nopackage -clean`;
- standalone target-free RED OS Core validation of the exported directory;
- catalog/schema reproducibility;
- secret/security audit excluding `vendor/**` and generated dependencies;
- `git diff --check`;
- mockup reconciliation; and
- one FULL architecture DIFF review because this milestone adds a guarded
  filesystem publication/security boundary.

## 14. Explicit non-goals

UI-01I does not add:

- `.piproject`, ZIP, TAR or another archive contract;
- arbitrary archive import or extraction;
- template mode, server slots or host remapping;
- overwrite, merge, adoption, migration or repair of an existing destination;
- export history, scheduled/background exports or cloud storage;
- encryption, signing or a second artifact trust system;
- a general secure-filesystem framework;
- local Core/Ansible execution on Windows;
- verification evidence, plans, results, facts or runtime credentials in the
  output; or
- any change to standalone Ansible/Core, service, PKI or execution semantics.

## 15. Owner decisions requested

Approval of this plan confirms:

1. UI-01I output is a native project directory, not `.piproject` archive;
2. only full saved configuration is in scope; template/import remains deferred;
3. export is create-only with no overwrite/merge;
4. only Installer-managed projects are eligible;
5. export does not require READY/Core and does not imply verification; and
6. reopening the result is explicit and uses the existing read-only open flow.
