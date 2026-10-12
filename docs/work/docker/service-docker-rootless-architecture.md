# SERVICE-INSTALL-10 — Docker rootless + Compose architecture and acceptance

Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
Architecture is maintained in [the Docker contract](../../contracts/docker-rootless.md);
dated acceptance and worktree context are retained in [evidence](evidence/si10-acceptance.md).

## Goal and boundaries

See [the dedicated document](../../contracts/docker-rootless.md#goal-and-boundaries).

## Runtime and network

See [the dedicated document](../../contracts/docker-rootless.md#runtime-and-network).

## Docker TCP API and TLS

See [the dedicated document](../../contracts/docker-rootless.md#docker-tcp-api-and-tls).

## Service package and owned files

See [the dedicated document](../../contracts/docker-rootless.md#service-package-and-owned-files).

## Gates

1. One independent FULL PLAN architecture review with mandatory
   overengineering check before implementation; BLOCK stops the milestone.
2. RED OS package/preflight and autonomous Ansible apply/verify/reapply,
   including `changed=0`, unsupported OS, missing LXC helper, existing-user
   safety, create-user password, TLS positive/negative clients, and
   no-Swarm proof.
3. Target/bridge proof: lxc-net stopped means dockerd never starts; a late
   lxc-net start activates the target and Docker without polling; stopping
   lxc-net deactivates target/bridge and Docker; after reboot the same order
   holds. Also prove a manual user-service start cannot bypass the gate.
4. Target-free Core plan and actual Go execution; real nonvisual React/Wails
   Secrets -> plan -> Start -> terminal result. Mocked frontend tests are
   supplementary only.
5. Focused unit/schema/catalog tests, full Core suite, Go tests/vet, frontend
   lint/test/build, affected race checks, security/secret audit, and
   `git diff --check`. High-risk container runtime DIFF gets one independent
   FULL DIFF review. No DONE claim without all applicable gates.

## Existing-work separation

See [the dedicated document](evidence/si10-acceptance.md#existing-work-separation).

## SI10 acceptance evidence (2026-10-01)

See [the dedicated document](evidence/si10-acceptance.md#si10-acceptance-evidence-2026-10-01).
