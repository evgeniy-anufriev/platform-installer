# Runtime bundle and artifact procedure

Read before acquiring, building, validating, publishing, rebinding or activating a bundle, or bundle-dependent UI QA.
These are mandatory procedures routed by [AGENTS.md](../../AGENTS.md).
They do not authorize a new milestone or target mutation.

The runtime bundle derives `catalog/service-catalog.yml` from its copied
`services/*/service.yml` manifests. It does not consume or validate the fixture
catalog under repository-root `examples/`. The required source roots are
`ansible-core/`, `services/` and `contracts/`, plus the explicit runtime input.
Service schema/compatibility references and bundle checksums remain mandatory.

Service payloads supplied under `runtime-input/artifacts/<service>/` are
inspected before catalog generation. The builder rewrites only staged copies
of artifact metadata/defaults, then compiles local artifact refs into the
existing runtime catalog. Explicit `--platform` supplies the artifact OS and
architecture; conflicting OS/architecture pairs cannot select one metadata
identity. Kafka supports Apache plus separate Registry and a single combined
Confluent archive. No downloads or source/defaults mutation occur. See
[artifact projection](../work/runtime-bundle/artifact-input-projection-plan.md).

EMPTY-PACKAGES-BOOTSTRAP-01 allows an existing empty `--runtime-input` directory.
Compatibility then comes from repeatable `--platform OS:VERSION:ARCH`, or from
the Linux build host's `/etc/os-release` and `uname -m`. The output retains the
fixed runtime/packages and runtime/python directories; manifest platforms and
component checksums remain mandatory. For a different target OS/version, supply
its explicit identity rather than using the acquisition host's identity.

Selected-node preparation uses installed prerequisites, then verified bundle
RPMs, then existing configured approved DNF repositories for packages missing
from both. It does not repair a corrupt RPM or incomplete offline closure by
silently retrying online. This owner-approved fixed runtime prerequisite
exception does not change service `requiredOffline` or deployment source policy.
No repository is added/enabled, and the distributed bundle remains immutable.

Owner clarification (2026-10-13, EMPTY-PACKAGES-BOOTSTRAP-01): DNF may update
already installed dependencies while installing missing runtime prerequisites.
When all prerequisites are installed, preparation performs no package transaction.
Actual React/Wails Prepare/READY acceptance is outside this implementation stage;
its absence does not constitute verified application-flow acceptance.

### S11 runtime-bundle acquisition host

For SI11 bundle acquisition/builds, use the trusted RED OS acquisition host
`node2` at `192.168.56.102`, not the selected installation Execution Node
`node1` at `192.168.56.101`. Before each use, confirm strict SSH host-key
validation against the existing trusted `known_hosts` entry and confirm that
the host already has the required Python/Core build runtime. Do not disable
host-key checking or bootstrap Python/Core on the acquisition host as part of
this workflow. Sync only the current required source tree into a unique
temporary QA workspace, build there from the current worktree and approved
runtime inputs, then validate and publish the exact resulting bundle through
the standard publisher. This is a bundle-build location rule only; it does not
change the configured EXEC-01 connection or authorize service installation on
node2.

## Local Test Artifacts

The local cache retains only the current immutable offline bundle under
`cache/<digest>/`; publishing a replacement prunes the prior local digest.
Its service payloads live inside the verified
bundle at `runtime/artifacts/<service>/`. A DEV import source is runtime-only
input under `.runtime/artifacts/<service>/`, never a second subtree of
`cache/`.

They are local test inputs and must not be committed.

For any Wails/UI test that depends on a newly acquired, built or otherwise
updated bundle, a QA cache is staging only. After bundle validation succeeds,
publish that exact verified bundle with the standard `publish-bundle` command
into the active repository-root `cache/` before launching/restarting Wails
or running Verify, Execution Node preparation, Plan or Start. Confirm the
publisher's returned digest equals the bundle digest locked by the project;
do not proceed on a mismatch. Publishing replaces the active cache and prunes
its previous digest, so preserve any still-needed prior bundle in an approved
QA cache before publication. Never substitute a manual copy into `cache/`.
The customer-supplied `<project>/bundle/` is an import source, not this cache.
For existing local installations, the old repository-root `bundle/` cache is
read-only fallback when `cache/` has no verified bundle; do not delete it as
part of a rename.

Do not search Downloads/Desktop or download artifacts automatically during QA
or production execution when the expected artifact is missing. Report the
missing expected path instead. A separately authorized DEV acquisition may
download and verify an official artifact into `.runtime/artifacts/`, then
publish it into a new immutable bundle; production roles and production
execution must use only approved local artifacts, repositories or payloads and
must never download from the Internet.
