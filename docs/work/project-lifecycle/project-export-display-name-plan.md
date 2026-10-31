# Exported project display name

Owner authorizes using the export directory name as the exported project's display name. Source remains unchanged; project ID, infrastructure settings and extensions retained. UI field: «Имя проекта и новой папки».

## Bounded contract change

Existing project.yml only: parse YAML node mapping, reject duplicate keys and malformed metadata/name shapes; set/add metadata.name to validated export name. Add metadata mapping if absent. Absent optional manifest remains absent, with standalone path unchanged. Serialize only this manifest; formatting may normalize while supported unknown fields are preserved. No Core semantics, new project identity or source rewriting.

Source observation/revision remains the original stable file authority. Output observation is derived at preview and again Commit after source has been proven unchanged; it carries transformed bytes, digests, sizes and output revision computed by existing ordered path/digest algorithm. Plan documents/aggregate describe output; SourceProjectRevision stays original; existing plan digest binds name/destination and output bytes. Final source stability still compares original source manifest. Stage/write/verify compare output observation; publication/reparse/no-overwrite/cleanup guards unchanged. Retain per-file/aggregate limits after transformation. Invalid YAML/shape fails EXPORT_SOURCE_UNSAFE without output publication.

## Checks

Go focused + full test/vet. Test renamed manifest with preserved source bytes, ID and unknown extension values; preview output digest/size equal files; stale source rejection, malformed/duplicate metadata, optional absent manifest, name with YAML special characters. Existing negative authority/overwrite/staging tests retained. Frontend field label updated with focused existing export handler test. Packaged EXE rebuilt; real UI repeat pending, no mocked PASS claimed as acceptance. Update UI01I copy policy with explicit exception and journal/current state. FULL PLAN then filesystem FULL DIFF review; no Core/bundle changes or target mutation.

Manifest rename rejects anchors, aliases and merge keys anywhere in project.yml; this bounded fail-closed policy prevents metadata.name changes from propagating into an extension through YAML references. Test anchored name reused by an extension. No generic YAML editor is introduced.

## Windows staging cleanup correction, 2026-10-31

The reported EXPORT_STAGING_RETAINED after confirmation exposed a reproducible
cleanup defect: nested directories were opened without DELETE; file cleanup
also lacked SYNCHRONIZE for the synchronous NT open and FILE_READ_ATTRIBUTES
for its no-reparse verification. Two access-mask corrections preserve retained
parent-handle authority and no-follow checks. No path-based delete fallback,
new API or project mutation was introduced. The customer's failure preceding
cleanup is still unknown; the correction prevents this proven cleanup failure
from masking the original error.

Go tests/vet PASS. Explicit Windows regressions PASS without skips: partial
nested write preserves EXPORT_WRITE_FAILED and removes staging; an injected
junction retains staging and preserves the outside marker without publishing.
Independent FULL DIFF APPROVE, zero blockers, fingerprint
601c931628f394e9f0272b8d025368645c30a7ac4e52404783fbafab881202c8
at base e136d8084fbf651a92c6f07ddab6008f7a3d9777.

Actual React/Wails Export/Preview/Commit/reopen PASS via dev34147/Vite4187:
five documents, source revision331285c0bd0099cb886991ceaf98e5d973c040ab9c1e9826fb3fae4694daabb7,
all output digests match preview and source hashes remain unchanged. Only the
native project folder picker was substituted by original OpenProject; business
methods were observed without replacing results. Safe controller/results are
under .runtime/qa/project-export; owned QA processes were stopped. Production
frontend/Windows Wails build PASS; visual/native-picker acceptance not claimed.
