# Kafka Verify optimization

Owner-authorized implementation in the current
`codex/application-preflight-optimization` worktree, base `d8309225`.
Review explicitly waived. Current installation runs must remain untouched.

## Baseline and changes

Observed run `installer-50f0c027f03980ce89344c8f981e8c99`, Kafka Verify:
2026-10-28 19:52:05–19:54:54 UTC, SUCCESS, 169 seconds, 180 task starts,
310 results (268 SUCCESS, 42 SKIPPED). Nine relevant runtime source files
matched the checkout after CRLF normalization. Summed task durations are not
wall time: 218.08 seconds total, including 16.55 seconds skipped.

- Preparation/projection: approximately 50 seconds; the eight normalization
  steps produced 72 results for three members on three hosts. The replacement
  renders the same Jinja expressions in one template lookup per host, preserving
  local defaults and sorted numeric node order. The single-member role entry
  remains as an adapter to this same template. No second normalizer or cache.
- Local health: 43 seconds, with node1/node2/node3 effectively serialized by
  includes carrying different loop objects. Member and listener includes now
  carry ordinal slots and host-independent labels, resolving each host's actual
  object through task vars. Ansible also compares `_ansible_item_label` when
  grouping includes; retaining per-member labels would serialize them again.
  The systemd, TCP, TLS identity/CA and retry checks remain unchanged.
- Cluster diagnostics: 65 seconds, including two CLI commands totaling 37.84
  seconds. SCRAM diagnostics share their exact administrative connection and
  one temporary config, removed in `always` even on failure. The independent
  quorum and unfenced-member checks remain. Non-SCRAM controller/client paths
  remain separate. No JVM startup saving or asynchronous execution is claimed.
- Registry health remains one HTTPS check per local instance.

## Validation

Focused isolated RED OS QA: **34 distinct tests PASS**, no skips, across final
selections. Tests use temporary files, synthetic
PKI and HTTPS endpoints, and bounded systemctl/Kafka CLI fixtures. They do not
start, stop, reload or inspect the current installation run. No bundle update,
deployment or merge is included. The owner authorized committing this change together with the service HAProxy hook correction. Full React/Wails acceptance and actual
stage performance measurement remain pending.

- Initial 32-test selection: 30 PASS / 2 FAIL (470.015s). Native parity exposed
  integer versus legacy-string auxiliary listener ports; the template preserves
  the existing scalar types. The other failure was an old task-name assertion,
  updated to check the shared normalization entry and numeric sorting.
- Final normalization and contract selection: 24 PASS (21.480s). Complete
  normalized objects match the legacy fixture for broker/controller/combined,
  explicit compatibility overrides, sequential calls and batch execution.
- Initial parallel/CLI selection: CLI reuse/failure cleanup PASS; grouping FAIL
  because distinct labels still prevented grouping. Corrected final native
  selection: 2 PASS (122.541s), covering uneven placements (four members across
  three logical hosts), real TLS checks and SCRAM success with exactly one
  config creation/cleanup. Local systemd tasks form two groups instead of four;
  TLS tasks form six groups instead of twelve. This proves grouping, not a
  whole-stage wall-time speedup.
- Existing native health cases PASS: repeat changed=0, inactive process, missing
  broker, wrong quorum, unready Registry, untrusted CA and wrong TLS identity.
  Both CLI commands retain their independent validation/retry predicates.
- CLI failure test verifies both commands receive the same mode-0600 config,
  deletion after the second command fails, and no synthetic password in output.
- Apply/Verify syntax and `git diff --check`: PASS. Final logs are under
  `.runtime/qa/kafka-verify-optimization/`. Four qa-sync source workspaces cleaned.
- No live Kafka CLI, systemctl operation on installed services, bundle rebuild,
  or interaction with the active run was performed. CLI/systemctl fixture results
  are not real Kafka cluster acceptance or a new performance measurement.
