# Vault swap preflight removal — FULL DIFF

Owner decision 2026-10-14: remove swap validation from the Vault role; retain
`disable_mlock = true`. No change to host swap or new policy configuration.

Independent reviewer: `/root/vault_swap_removal_review`, architecture-reviewer.
Verdict: APPROVE; findings none; blocking findings 0; validity CURRENT.
Base HEAD: `1db6604488525eb04125630789361e4042665b99`.
Scoped diff SHA256 (UTF-8/LF):
`a6b53537fa9e58ad082b646c62b5a1c8f316a32f03bfa0002f10f6a3d7f3b4af`.

Scope: delete 12 lines from vault_tls/tasks/preflight.yml: reading /proc/swaps
and asserting VAULT_SWAP_ENABLED for raft-ha. All remaining guards retained;
no dangling references in services/vault. vault.hcl.j2 remains unchanged,
including disable_mlock=true; blob 74fe9684ed4ccaa37de3a78f286426c450bdd8d0.
New preflight blob: cf15f1b169b331cbbaa26f3ae4c035f5d80537b3.

Overengineering: no new abstraction, mechanism, contract, DTO or configuration;
minimal removal follows explicit owner policy. Swap exposure is not made safe
by this change; it is no longer an installation blocker enforced by this role.
Reviewer performed read-only source review, not remote QA. Main-agent test and
actual Apply evidence is recorded in the A9 journal.
