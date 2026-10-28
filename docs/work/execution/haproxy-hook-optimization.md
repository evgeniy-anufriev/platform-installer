# Universal HAProxy partial hook optimization

Owner requested implementation for library and infrastructure service endpoints.
Work remains in codex/application-preflight-optimization, base 64753eed. The
briefly created separate worktree had no code edits and was archived after the
owner corrected the location. Review remains explicitly waived by the owner.

The common partial_prepare / activate / partial_reload contract is used by both
services/integrations/tasks/apply-source.yml (libraries) and
services/haproxy/playbooks/integrate.yml (service endpoint hooks, including Vault
and ClickHouse). No service-name special cases or second desired-state model.

Implementation:
- Dedicated partial candidate tasks avoid installation/PKI-only task expansion.
- One native Ansible template lookup renders existing frontend/backend templates
  into a host-scoped file list. No template logic is duplicated in Python.
- A bounded fragment_batch module compares/writes that list in one invocation;
  atomic per-file replacement, mode/owner, size/count bounds and no-follow
  directory/file checks reuse the existing HAProxy archive safety helpers.
- Proven unchanged graphs retain their candidate. Current active configuration
  and TLS material are still validated; ownership/content is rechecked at the
  activation barrier. No reload is requested for unchanged publication.
- Changed graphs retain full candidate validation, archive/recovery evidence,
  exact active digest verification and active validation before reload. All-host
  prepare/activate/reload barriers remain in the callers. A batch is NOT an
  atomic multi-file or multi-host transaction; existing recovery behavior remains.
- Full service installation/reconcile keeps its existing path and explicitly
  resets the partial batch flags. Sources outside the selected set are preserved.

No bundle publication, installed-service mutation or new installation run is
part of this implementation. Real React/Wails and full-run timing acceptance
remain pending. Isolated native HAProxy fixtures use temporary directories only.

The selected-source application hook also resolves the entire source list in one
Core module invocation. It calls the existing integration/endpoint/DNS functions,
retains per-source policies and expected addresses, and preserves the final DNS
conflict check. No topology rule is moved into Go or Jinja. Singleton service
resolution remains compatible; both service and application publication paths
use the same optimized HAProxy role. External probes remain sequential with
their existing policies; no async lifecycle or unbounded concurrency was added.

## Validation and measured scope

Focused RED OS validation covers 55 distinct passing tests across the final
selections (no skips): batch filesystem safety/archive proofs, existing partial
publication, host/scope isolation, TLS/SNI, DNS conflicts, endpoint-source reuse,
byte-for-byte native template parity, and service/application resolver parity.
The production selected-source task file was also exercised, not only its module.
Apply/Verify plus HAProxy Apply/integrate, Vault Apply and ClickHouse Apply syntax
checks passed (six playbooks). The final dispatcher-only change was then exercised
by native changed/unchanged publication and invalid-TLS tests on fresh sources.

Real HAProxy `-c` fixtures used 1, 5 and 20 selected endpoints plus 40 retained
neighbor fragments. They verified preservation of unrelated bytes, exact active/
candidate graphs, invalid candidate rejection before publication, repeat changed=0,
and unchanged candidate mtime. Native template parity includes Vault-style TLS
and ClickHouse-style HTTP backend models. The final no-op case also rejects a
corrupted TLS PEM while preserving active files and the retained candidate.
These are disposable filesystem/configuration fixtures, not running production
HAProxy reload, a three-physical-host deployment or React/Wails acceptance.

For the same 20-endpoint fixture, legacy cold prepare/activate took 169.126s and
batch cold prepare/activate 67.563s (about 2.50x); batch repeat 29.148s. Resulting files
were byte-identical. This timing was recorded before the final dynamic-include
simplification of unchanged activation; that final path passed separately.
The VM was shared with other QA, so these are indicative observed timings, not a
statistical performance guarantee or an end-to-end stage speedup. The benchmark
does not include upstream Core source resolution, DNS publication or external
HTTP probes. Template/write invocation count stays one per batch at 20 endpoints.

Earlier renderer attempts failed on a missing final frontend LF; fixed and proved
against native template bytes. An initial parity fixture also lacked the required
localhost fact handoff; corrected without weakening assertions. Those failures
remain in ignored evidence and are not reported as passing runs.

Evidence: `.runtime/qa/haproxy-hook/{initial,parity,regression,benchmark,final-one,wiring}.log`
and retained `initial-render-failure.log` / `intermediate-failures.log`.
All six temporary qa-sync workspaces were cleaned. The first root-test transfer
needed its test-created pycache ownership restored before standard cleanup; later
runs disable bytecode writes. `git diff --check` PASS. Owner authorized committing these changes;
no master merge, bundle publication or new installation run was performed.
