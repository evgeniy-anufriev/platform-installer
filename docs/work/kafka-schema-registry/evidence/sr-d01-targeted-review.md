# SR-D01 targeted recheck

2026-10-12. Independent read-only reviewer /root/plan_review.
Owner authorized correction after the actual RED OS reproduction.
Verdict: **APPROVE_WITH_CHANGES**. Unresolved blocking findings: **0**.

Base bb32857280ba0238a1fc5a744b3226d8d3105f75. Independently checked frozen diff
.runtime/qa/schema-registry-20261012/sr-d01-corrected-review.diff, SHA256
29c670107132f43aa28184e4f6f1e58ec0bfa0bff8b107eaefda3706923446a0.
This is the one allowed TARGETED_RECHECK of SR-D01 and its immediate filesystem
boundary, not another FULL review.

SR-D01: **RESOLVED**. The shared ownership task independently checks markers for
config/log roots: regular file, no symlink, UID 0, mode 0644 and exact expected
marker SHA256. Ancestors must be nonsymlink directories. Validate, member
preparation and the first operation of Clear invoke the guard. New roots receive
separate markers; existing unmarked roots are not automatically adopted.
The original foreign-log mutation/deletion scenario blocks before mutation.

SR-D02 remains NON_BLOCKING/OPEN, outside this recheck. Its unused x-memberRole
metadata recommendation does not require another review.

No new overengineering found. The shared task uses standard stat/assert and avoids
divergent ownership checks. ownership_paths names two concrete protected roots;
there is no new desired-state store or lifecycle layer.

Reviewer directly inspected frozen identity, guard, projection, call sites and
six regression fixtures. Parent reported RED OS cases PASS with ok=217 changed=36
failed=0 rescued=10, focused suites 16+25+33 PASS and diff check PASS. Tests were
not independently rerun. Full native repeat was running at review time; subsequent
results are recorded in the journal. No target secrets were investigated.

Validity: CURRENT for corrected SR-D01 boundary. Changing ownership rules, guard
call sites or removed paths invalidates this targeted review. Broader acceptance
remains separate; no additional automatic review is required.
