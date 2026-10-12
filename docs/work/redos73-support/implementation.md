# RED OS 7.3 support

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

These are Python/Ansible role contract and fixture tests run on the RED OS 7.3
VM from the synchronized current working tree. They do not install the named
service packages on the VM.

See [test journal](evidence/test-journal.md) for per-service results and
remaining failures. Several failures reproduce issues in already-dirty
Kafka, PostgreSQL, Redis and service-role work; the run is not a clean
comparison against the previous RED OS 8 baseline.

## Remaining service compatibility gates

- RED OS 7.3 repositories provide `postgresql16` through 16.15 and
  `pg_auto_failover-16` 2.2-1. The PostgreSQL role now probes both legacy and
  major-scoped package families using exact-version masks, then installs the
  selected exact NEVRA. Read-only package resolution passed on 7.3. The
  service-level Apply/Verify/repeat remains untested, and the artifact metadata
  still describes the previously accepted Red OS 8 package combination.
- ClickHouse 26.8.14.3 RPMs (client, common-static and server) are present in
  the offline bundle and use the same artifact set as the Red OS 8 bundle.
  They can be used for a 7.3 Core Apply test; package compatibility still
  requires the isolated Apply/Verify/repeat evidence.
- Existing service metadata/defaults still pin several RED OS 8 package
  builds. Repository candidates observed on 7.3 include Keepalived 2.3.4,
  PostgreSQL 12.22, Redis 8.10.1, Vault 2.0.4 and Docker Compose 5.0.2.
  These candidates have not been proven with their roles and must not be
  recorded as accepted service combinations yet.
- Direct service install, verify and idempotent-repeat runs remain open for all
  ten services. The bundle proves the Ansible/Python bootstrap and Core
  capability boundary only.

## Environment cleanup

The temporary QA SSH key was removed from the VM and local secret storage; its
temporary SSH config alias was removed. QA source workspaces, downloaded
runtime closure and remote bundle-build workspace were removed. The explicitly
requested Ansible packages remain installed on the VM.

## Independent review

The required FULL DIFF review returned **BLOCK**. `REDOS73-DIFF-01` is open
because the submitted worktree fingerprint did not match the reviewer's
recomputed fingerprint (`sha256:050425437295146d503dff0351ce7f13952af4138a3388af6435c10d3f6fa4b4`).
`REDOS73-QA-01` is open because isolated service install, Verify and repeat
checks were not completed. `REDOS73-DIFF-02` is a non-blocking test-quality
finding: strengthen the Keepalived contract test to assert the exact systemd
module key. The bundle/Core bootstrap evidence is complete, but the milestone
remains IN PROGRESS and does not establish service support.
