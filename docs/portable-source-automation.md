# Automatic portable source snapshots

The `Update portable source snapshot` GitHub Actions workflow runs on pushes to
`master`, including merged pull requests, and supports manual Run workflow.
Local commits trigger it after being pushed. It uses the latest remote master,
packs sources into parts of at most 5,000,000 bytes, verifies SHA-256 against the
source tree, restores into a temporary directory, and verifies restoration.

The bot commits only `portable-source/manifest.json`, `portable_source.py` and
`source-*.txt`. README files are preserved. `sourceRevision` identifies the source
commit before the generated snapshot commit. The generator excludes tests,
documentation, runtime outputs, secrets and package binaries; required dependency
licences and Wails compile-time assets remain included. Text is readable; binary
resources use Base64. Pinned Wails v2.15.0 and CLI vendor dependencies reside in
`third_party/wails`. Building a runtime bundle or activating a node is separate.

Publication uses ordinary fast-forward push with `GITHUB_TOKEN` and
`contents: write`; no personal token or force push is used. Pushes made with
`GITHUB_TOKEN` do not recursively trigger push workflows. Concurrent jobs are
serialized; if master advances, the job rebuilds from its new head, at most three
attempts. Protected-branch or repository permission rejection fails visibly and
requires an allowed repository policy; this workflow does not bypass protection.
Pending runs can coalesce; the snapshot represents the latest master sources.

Run locally from a clean checkout after staging new source files:

```sh
python3 scripts/update_portable_source.py
python3 scripts/portable_source.py verify portable-source .
```

The local helper changes only generated snapshot files; it does not commit or
push. The packer reads Git-tracked paths, so new source files must be added to the
index first. A bot snapshot commit is recognized to avoid a second snapshot of
the same source revision. Restoration/build instructions are in
`portable-source/README.md`.

Validation before publication: workflow YAML trigger/permissions checked and
Bash syntax passed. Imported `third_party` Git tree exactly matches the pinned
portable dependency tree. Full local generation, SHA-256 source comparison,
restoration and restored-file comparison passed. README content is preserved.
The first real GitHub run is checked after pushing the workflow to master.
