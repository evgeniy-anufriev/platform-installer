# RED OS 7.3 support

## Completion decision — 2026-10-13

The owner closes `REDOS73-SUPPORT-01` for its Ansible Core and service-role
scope. The tested package, standalone and multi-host configurations are recorded
in the [test journal](evidence/test-journal.md). This completion does not claim
that every service version or topology is supported; combinations without
explicit evidence remain unverified. The owner determined that Go/Wails
acceptance is not required because this work made no changes in those layers.
This is direct Core/Ansible acceptance, not Installer UI acceptance.

## Scope

Add a portable Core runtime bundle for RED OS 7.3 and verify the current
service collections with the official Ansible packages available for that OS.
This work is limited to Ansible Core and service-role tests. It does not claim
service installation acceptance through the Installer.

## Completed

- The RED OS VM reports `VERSION_ID=7.3` (`7.3.7`), x86_64, Python 3.8.20.
- Installed the official RED OS Ansible 6.7 package, which provides
  `ansible-core 2.13.13`. The Core `systemd` module is present; the newer
  `systemd_service` FQCN is absent. Updated service YAML and affected test
  expectations to use `ansible.builtin.systemd`.
- Built `redos73-20261012-01` on the trusted existing-runtime build node. Its
  manifest retains RED OS 8.0.3 and adds RED OS 7.3 x86_64. It contains 1,099
  components and five verified service artifact sources.
- The 7.3 offline runtime package closure came from the VM's enabled RED OS
  repositories: 240 RPMs (173 x86_64, 37 noarch, 30 i686). The bundle was
  returned to `.runtime/qa/redos73-bundle-redos73-20261012-01/bundle/` and was
  not published into the active `cache/`.
- All 1,099 bundle component paths, sizes and SHA-256 digests passed local
  verification. Ansible 2.13.13 on the 7.3 VM executed the new bundle's
  `execution-capabilities.yml` against its manifest: `ok=1 changed=0 failed=0`.
- Each of the ten service `apply.yml` and `verify.yml` playbooks passed
  `ansible-playbook --syntax-check` independently (20/20); the Core capability
  playbook also passed syntax-check.

## Service test results

Contract and fixture test outcomes are listed in the [test journal](evidence/test-journal.md).
On RED OS 7.3, direct Core/Ansible Apply, Verify and repeat evidence covers
standalone configurations for ClickHouse, PostgreSQL, Redis, Vault, Docker
Rootless, HAProxy, BIND and Kafka. Three-host evidence covers BIND primary and
secondary, DNS-client with the configured `systemd-resolved` backend, Keepalived
VRRP, PostgreSQL `pg_auto_failover`, Redis Sentinel, Vault Raft, HAProxy, Docker
Rootless, ClickHouse Keeper/replication, and Kafka KRaft with Schema Registry.
Where documented, Verify and repeat Apply completed with `changed=0`.

The journal preserves the individual runs, package versions, important setup
conditions and earlier failures. Some early aggregate unit suites were not
clean, and not every service mode/version combination was exercised. Those
unverified combinations are not accepted as supported by this work item.
RED OS 8 `/usr/bin` PostgreSQL was not retested in the portability correction;
that check is assigned to its separate stage. The active cache was not updated
with the QA bundle.

## Environment cleanup

The temporary QA SSH key was removed from the VM's `authorized_keys`, local
secret storage, and SSH config. Both temporary synchronized source workspaces
were removed. The seven tested service deployments remain on the VM for
inspection. Vault bootstrap token and unseal custody remain in
`/home/admin/.runtime/secrets/redos73-vault-qa` with private file/directory
modes because Vault remains initialized. SELinux is configured `disabled` and
was observed `Disabled` during QA, as requested. The explicitly requested
Ansible packages also remain installed.

## Independent review

The historical FULL DIFF review returned **BLOCK** after a fingerprint
mismatch. The authorized TARGETED_RECHECK was **APPROVE**, with zero unresolved
blockers, for `REDOS73-DIFF-01` and `REDOS73-DIFF-02` at reviewed fingerprint
`sha256:fdee91010b78d766a712dba0523f4eb78ba78092609130555f39b832dd962201`.
Its reproducible manifest is in
[redos73-diff-fingerprint.txt](evidence/redos73-diff-fingerprint.txt).
The PostgreSQL monitor address and HAProxy exact PKI selector were confirmed;
both corrected RED OS 7.3.7 contract suites passed (13 tests each). The earlier
`REDOS73-QA-01` partial-coverage finding is closed by the owner-directed scope
decision recorded above; unverified combinations remain explicitly outside the
support claims. No further review cycle was run.
