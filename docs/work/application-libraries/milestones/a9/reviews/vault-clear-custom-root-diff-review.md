# Vault Clear custom root — FULL DIFF

Owner authorized resetting qa-vault-consumer on node1/node2/node3 for a fresh
bootstrap in the full-service A9 run. Initial native Clear check rejected /data
owned by platform-automation (0755), although the established Apply guard accepts
the configured custom root owner. No mutation occurred in that failed check.

Independent reviewer: /root/vault_swap_removal_review, architecture-reviewer.
Verdict: APPROVE, findings none, blocking findings 0.
Base HEAD: 1db6604488525eb04125630789361e4042665b99.
Reviewed diff SHA256 (UTF-8/LF):
a7295a9382e6a656e9dae0ca9d4dafd6fb67d466acbc71079d15f1a3c1e78e75.
Scope: clear_member.py, clear_entry.yml, clear.yml, test_clear_member_paths.py.

The optional custom-root/owner pair uses existing role variables, resolves UID
through pwd and grants the extra owner only at the exact configured ancestor.
Member ownership, marker/config/unit identity, no-follow held descriptors,
mount/source checks, stopped-unit and no-process requirements remain intact.
Root must strictly contain member data; /var/lib remains root-only. Check mode
uses the same validation. Reviewer inspected source and five new boundary tests;
did not execute RED OS tests or contact targets.

Overengineering: no new layers, DTO, persistence or speculative mechanism. Two
optional arguments to the existing module are smaller than another Clear path
or modifying permissions of the shared /data root.

Post-review bounded compatibility correction in argument projection: omit both
optional arguments for default /var/lib or a member outside the configured custom
root. This preserves standalone callers with their own role-specific data path;
it does not change the independently reviewed module or expand its owner exception.
Main-agent RED OS evidence: 9 path tests PASS, 12 projection cases PASS (3 call sites
times default/custom/matching/nonmatching roots), final native check PASS all3,
actual native Clear PASS all3; details in the A9 journal. No second FULL review
claimed. Reviewer identity above applies to the recorded reviewed fingerprint.
