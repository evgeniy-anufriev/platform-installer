# A2 standalone runtime fixture

This no-account/no-Agent fixture uses pinned public `docker.io/library/nginx:1.28.0-alpine`.
It contains two libraries and ordinary inventory placements; provider provisioning
and endpoint publication are disabled. Nginx reads the mounted readonly default.conf
at startup. HTTP `/status` returns the derived instance ID and configured log_level;
it proves configuration activation, not connections to infrastructure services.

`platform_artifact_lock` is the Ansible-native form of the existing `artifactLock`
slot. Its existing v1alpha1 `x-container-images` extension contains typed image
records, checked against `contracts/artifact-source/v1alpha2/image-lock.schema.json`.
If project.yml also contains artifactLock, both values must agree. There is no
additional image lock file. Lock/group_vars/package bytes participate in revision.

Archive digest/size and bundle digest are placeholders: replace them with the
exact approved bundle/component metadata before offline Apply. Set
`platform_execution_bundle_root` only when offline delivery is selected. An available
approved registry does not require its optional fallback bundle/archive bytes.
Public QA pull of this exact image is owner-authorized; no image build is performed.
The locked platform manifest/config identity is checked after acquisition.
`qa_application_runtime.py` exports this same image to a private synthetic delivery
bundle for offline checks, then exercises approved public registry delivery.
It does not publish an Installer bundle or exercise bootstrap acceptance.

Apply/Verify entrypoints are `ansible-core/playbooks/applications/apply.yml`
and `applications/verify.yml`. Set the project root and service catalog
explicitly. Include `localhost` as a normal inventory host so controller tasks
receive group_vars. With `--limit`, include `localhost` and the selected targets;
excluded placements do not count as verified. Verify never loads or starts images.

The runtime uses the selected Docker account, its discovered HOME/UID and Unix
socket. Files live under `<HOME>/.local/share/platform-installer/applications/`;
`platform_application_root_relative` is an ordinary role default/override.
One `.env` and base Compose exist per library/host. Config digests and ownership
labels are machine-owned; the operator does not set or override a digest.
The managed image reference is automatically platform-application:sha256-<full image ID>.
Omit localReference from image records; a supplied value must equal that derived name.
Distinct image IDs cannot share a startup reference, including parallel library runs.

Registry sources require a locked **platform manifest**, an explicit node-scoped
`platform_application_approved_registries` entry and the same image identity.
Registry authentication uses an existing private runtime Docker config directory
through `platform_application_registry_config_directory`; role tasks never run
login or persist passwords. The runtime credential owner creates and cleans that
directory. Registry transport/authentication errors block instead of hiding behind
offline fallback. RPM source contracts and defaults remain unchanged.
