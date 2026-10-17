# Redis/Sentinel command policy

Owner instruction2026-10-17: remove Core prohibitions; the operator selects
application-account commands through ordinary defaults/group_vars.

## Scope

Remove the Sentinel command allowlist and Redis administrative-command denylist
from Core provider normalization and the standalone Redis account module. Both
listeners accept the same existing commands/keys/channels structure. Remove
key/channel first-character bans: the existing RESP writer adds the ACL prefix
to each separate argument, so these characters are literal pattern data.

Keep the current bounded typed format: named lowercase commands or subcommands,
nonempty command list, bounded key/channel patterns without whitespace/control
characters. This change does not introduce raw ACL expressions or category
expansion; the existing literal-token verifier does not support categories.
There is no per-command permission policy in either validation boundary.

Keep secret-file custody, TLS, account identity/ownership witnesses, managed vs
existing behavior and current ACL drift/repeat/Verify semantics. In particular,
this work does not implement grant revocation or claim a new exact-reconciliation
algorithm. Redis validates actual command availability when applying ACLs;
untrusted server errors remain redacted.

## Implementation and evidence

Change the two existing validators; add no helper, DTO, store or UI resolver.
Core tests accept previously prohibited named commands on both listeners and
retain malformed-input refusal. Native isolated Redis/Sentinel tests prove that
explicit administrative commands are granted, unrequested commands are denied,
and repeat/Verify preserve ACLs and ownership. Update the project contract,
architecture decision and roadmap with operator-owned command policy.

Run focused current-tree tests on RED OS and one independent FULL DIFF for this
owner-revised policy. The earlier read-only MASTER-only review is superseded.
Build/validate/rebind the resulting bundle, then use actual React/Wails fresh
Build/Approve/Start for SDKU. Runtime group_vars adds the observed required
sentinel|master command; no direct target ACL mutation or validation bypass.
