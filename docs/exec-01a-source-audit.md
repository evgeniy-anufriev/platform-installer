# EXEC-01A service source audit

This is the implementation audit for the repository-first/offline-bundle
source boundary. It does not change service topology, configuration or
lifecycle semantics.

| Service | Requirement | Current install path | Offline path | Current owner | Classification | Minimal integration |
|---|---|---|---|---|---|---|
| Kafka | Java OS package; Kafka binary archive | repository package and role archive path | shared delivery stages verified package/archive entries; archive path is projected back to the role | role task + Core delivery | ADAPT complete | resolver result must carry the exact bundle-relative entries |
| PostgreSQL / pg_auto_failover | versioned PostgreSQL and failover OS package closure | repository package tasks before lifecycle | shared delivery installs the selected local RPM closure with repositories disabled | role task + Core delivery | ADAPT complete | pg-auto requirement remains mode-conditional |
| HAProxy | OS package | repository package task in prepare | shared delivery installs the selected local RPM closure | role task + Core delivery | ADAPT complete | target source result is consumed before prepare |
| BIND | BIND and utils OS packages | separate repository package tasks in prepare | shared delivery installs selected local RPM entries, including mixed per-requirement sources | role task + Core delivery | ADAPT complete | no service-specific source resolver |
| Keepalived | OS package | repository package task in prepare | shared delivery installs the selected local RPM closure | role task + Core delivery | ADAPT complete | target source result is consumed before prepare |

The generic resolver belongs in the shared artifact boundary. Roles remain
responsible for installation mechanics and service behavior. Repository
availability is evaluated for the actual target host; an Execution Node
repository result is not reused for targets. Existing roles are otherwise
`REUSE`: no topology, TLS, configuration or lifecycle rewrite is part of this
audit.

The integration contract is
`contracts/artifact-source/v1alpha1/schema.json`: a Core-produced
`ResolvedArtifactSource` containing requirement, target node, source,
compatible version, artifact reference, optional immutable artifact entries and
safe provenance. A role must reject `BLOCKED` before any mutating task and must
not independently re-resolve source priority. For `OFFLINE_BUNDLE`, Core
delivery validates bundle-relative references, copies from the active
Execution Node runtime, verifies target SHA-256 and exposes staged paths to the
owning role. Full product repository/fallback service acceptance remains a
separate EXEC-01A gate; no service is marked accepted by these contract tests
alone.
