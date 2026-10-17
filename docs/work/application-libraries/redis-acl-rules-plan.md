# Redis ACL command rules

Owner amendment2026-10-17: SDKU DM uses @all; support arbitrary Redis
+@category and -@category input, preserving rule order. This supersedes the
named-command-only restriction for command grants; other account boundaries stay.

The existing commands list accepts named commands/subcommands, signed named
rules and signed categories. Bare names remain additive; bare @all is the
owner-requested shorthand for +@all. Preserve commands order and duplicates;
keys/channels retain their existing normalization. No category allowlist:
the Redis server validates available categories and commands.

The standalone provider converts these into separate ACL SETUSER arguments.
For comparison, expand ordered desired rules and ACL GETUSER command rules
using that server's COMMAND metadata (including subcommands) and ACL CAT category
names. Preserve +@all's
future-command meaning in comparison. This is runtime observation, not desired
state persistence. No temporary account, policy store or UI resolver.

For an owned managed account, reconcile differing command permissions with
nocommands plus the complete ordered desired rules, leaving identity/password
and key/channel behavior intact. Existing accounts and Verify remain readonly;
preflight permits only the existing managed ownership boundary. Repeat with
semantically equal Redis serialization must not write. Other accounts remain
untouched. Redis errors remain redacted.

Test ordered category inclusion/exclusion, subcommands, actual permitted and
denied calls, managed narrow/widen, new/existing/foreign accounts, Verify and
no-write repeat on isolated RED OS Redis and Sentinel. Full independent PLAN
and DIFF review before activation. Then build/validate/publish a fresh immutable
runtime, normal React/Wails plan/approve/start DM on101/102/103, inspect health.
Check persisted infrastructure evidence with a subsequent unstarted plan;
runtime replacement changes its fingerprint and requires one fresh Verify.

FULL PLAN APPROVE_WITH_CHANGES, zero blockers: reviewed identity
59972d8c5d42992ceeb56d81d77a891d50e7a6b35dd8ce8f3d295121ec7902fa.
RACL-P01/P02 clarifications: explicitly test parent/subcommand exceptions,
opposite rule order, future/module command meaning, metadata/unknown-rule
failures without mutation, and password/flags/key/channel/witness/foreign-account
preservation. Uninterpretable metadata fails before mutation.
Owner clarified: DM Redis client uses ['+@all', '-@admin']; Sentinel keeps its
explicit required commands because master discovery is in @admin.
