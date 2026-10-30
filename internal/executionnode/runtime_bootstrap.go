package executionnode

import (
	"fmt"
	"strings"

	"platform-installer/internal/executionbundle"
)

const runtimeBootstrapComponent = "ansible-core/tools/bootstrap_execution_runtime.sh"

func shellLiteral(value string) string { return "'" + strings.ReplaceAll(value, "'", "'\"'\"'") + "'" }

// Both phases recheck immutable bytes under root ownership. Bootstrap has no
// activation side effects: cancelling its SSH call cannot later switch current.
func runtimePreparationScripts(bundle executionbundle.Verified) (string, string) {
	var checks strings.Builder
	fmt.Fprintf(&checks, "[ \"$actual_files\" = %d ]\n", len(bundle.Manifest.Components)+1)
	fmt.Fprintf(&checks, "printf '%%s  %%s\\n' %s manifest.yaml | sha256sum -c - >/dev/null\n", shellLiteral(strings.TrimPrefix(bundle.Digest, "sha256:")))
	for _, component := range bundle.Manifest.Components {
		file := shellLiteral(component.Path)
		fmt.Fprintf(&checks, "[ -f %s ] && [ ! -L %s ] && [ \"$(stat -c %%u -- %s)\" = 0 ]\n", file, file, file)
		fmt.Fprintf(&checks, "[ \"$(wc -c < %s)\" = %d ]\nprintf '%%s  %%s\\n' %s %s | sha256sum -c - >/dev/null\n", file, component.Size, shellLiteral(strings.TrimPrefix(component.SHA256, "sha256:")), file)
	}
	common := strings.Replace(runtimePreparationCommon, "__COMPONENT_CHECKS__", checks.String(), 1)
	return common + runtimeBootstrapPhase, common + runtimeActivationPhase
}

const runtimePreparationCommon = `set -eu
fail() { printf '%s\n' "$1" >&2; exit 78; }
[ "$#" = 8 ] || fail EXECUTION_RUNTIME_ARGUMENTS_INVALID
stage=$1; root=$2; bundle_digest=$3; bundle_version=$4; core_version=$5; protocol=$6; platforms=$7; bootstrap=$8
case "$stage:$root" in /var/tmp/platform-installer-bootstrap-*:/var/lib/platform-installer/runtime) ;; *) fail EXECUTION_BUNDLE_STAGE_INVALID ;; esac
nonce=${stage##*-}
id=${bundle_digest#sha256:}
case "$nonce:$id" in *[!0-9a-f:]*|:*) fail EXECUTION_BUNDLE_DIGEST_INVALID ;; esac
[ "${#nonce}" = 32 ] && [ "${#id}" = 64 ] && [ "$bundle_digest" = "sha256:$id" ] || fail EXECUTION_BUNDLE_DIGEST_INVALID
candidate=$root/releases/.prepare-$nonce
release=$root/releases/$id
[ "$(id -u)" = 0 ] || fail EXECUTION_BOOTSTRAP_NOT_ROOT
for directory in /var/lib/platform-installer "$root" "$root/releases" "$root/state"; do
    [ ! -L "$directory" ] || fail EXECUTION_RUNTIME_DIRECTORY_UNSAFE
    if [ -e "$directory" ]; then
        [ -d "$directory" ] && [ "$(stat -c %u "$directory")" = 0 ] || fail EXECUTION_RUNTIME_DIRECTORY_UNSAFE
        mode=$(stat -c %a "$directory")
        [ "$((0$mode & 022))" = 0 ] || fail EXECUTION_RUNTIME_DIRECTORY_UNSAFE
    else
        install -d -m 0750 "$directory"
    fi
done
command -v flock >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_LOCK_TOOL_MISSING
[ ! -L "$root/state/prepare.lock" ] || fail EXECUTION_RUNTIME_LOCK_UNSAFE
if [ -e "$root/state/prepare.lock" ]; then
    [ -f "$root/state/prepare.lock" ] && [ "$(stat -c %u "$root/state/prepare.lock")" = 0 ] && [ "$(stat -c %h "$root/state/prepare.lock")" = 1 ] || fail EXECUTION_RUNTIME_LOCK_UNSAFE
    mode=$(stat -c %a "$root/state/prepare.lock")
    [ "$((0$mode & 022))" = 0 ] || fail EXECUTION_RUNTIME_LOCK_UNSAFE
fi
umask 077
exec 9>"$root/state/prepare.lock"
flock -n 9 || fail EXECUTION_RUNTIME_PREPARATION_BUSY
verify_bundle() (
    directory=$1
    allow_cache=${2-0}
    [ -d "$directory" ] && [ ! -L "$directory" ] && [ "$(stat -c %u "$directory")" = 0 ] || exit 78
    cd -- "$directory"
    [ -z "$(find . -type l -o \( ! -type f -a ! -type d \) -print -quit)" ] || exit 78
    [ -z "$(find . -perm /022 -print -quit)" ] || exit 78
    [ -z "$(find . ! -uid 0 -print -quit)" ] || exit 78
    if [ "$allow_cache" = 1 ]; then
        actual_files=$(find . -type f ! -path '*/__pycache__/*.pyc' -printf . | wc -c)
    else
        actual_files=$(find . -type f -printf . | wc -c)
    fi
    __COMPONENT_CHECKS__
)
`

const runtimeBootstrapPhase = `
[ -d "$stage" ] && [ ! -L "$stage" ] || fail EXECUTION_BUNDLE_STAGE_INVALID
[ ! -e "$candidate" ] && [ ! -L "$candidate" ] || fail EXECUTION_RUNTIME_CANDIDATE_EXISTS
success=0
diagnostic_code=EXECUTION_RUNTIME_CANDIDATE_COPY_FAILED
cleanup() { if [ "$success" = 0 ]; then printf '%s\n' "$diagnostic_code" >&2; rm -rf -- "$candidate"; fi; }
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
install -d -m 0700 "$candidate"
cp -R --no-dereference -- "$stage/." "$candidate/"
[ -z "$(find "$candidate" -type l -o \( ! -type f -a ! -type d \) -print -quit)" ] || fail EXECUTION_RUNTIME_CANDIDATE_UNSAFE
chown -R root:root -- "$candidate"
find "$candidate" -type d -exec chmod 0750 {} +
find "$candidate" -type f -exec chmod 0640 {} +
verify_bundle "$candidate" || fail EXECUTION_RUNTIME_CANDIDATE_INVALID
if [ "$bootstrap" = 1 ]; then
    diagnostic_code=EXECUTION_BOOTSTRAP_COMMAND_FAILED
    sh "$candidate/ansible-core/tools/bootstrap_execution_runtime.sh" "$candidate" "$platforms"
else
    # Legacy bundles remain usable with manually installed prerequisites.
    command -v python3 >/dev/null 2>&1 && command -v ansible-playbook >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_LEGACY_PREREQUISITES_MISSING
fi
success=1
`

const runtimeActivationPhase = `
verify_bundle "$candidate" || fail EXECUTION_RUNTIME_CANDIDATE_INVALID
created=0; switching=0; success=0
diagnostic_code=EXECUTION_RUNTIME_STATE_INITIALIZATION_FAILED
backup=$root/state/.prepare-$nonce
[ ! -e "$backup" ] && [ ! -L "$backup" ] || fail EXECUTION_RUNTIME_BACKUP_EXISTS
install -d -m 0700 "$backup"
cleanup() {
    if [ "$success" = 0 ]; then printf '%s\n' "$diagnostic_code" >&2; fi
    if [ "$success" = 0 ] && [ "$switching" = 1 ]; then
        if [ -L "$backup/current" ]; then mv -Tf -- "$backup/current" "$root/current"; else rm -f -- "$root/current"; fi
        if [ -f "$backup/active" ]; then mv -f -- "$backup/active" "$root/state/active"; else rm -f -- "$root/state/active"; fi
    fi
    rm -rf -- "$candidate" "$backup"
    if [ "$success" = 0 ] && [ "$created" = 1 ]; then rm -rf -- "$release"; fi
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
if [ -e "$root/current" ] || [ -L "$root/current" ]; then
    [ -L "$root/current" ] || fail EXECUTION_RUNTIME_CURRENT_UNSAFE
    previous=$(readlink "$root/current")
    case "$previous" in "$root/releases/"*) ;; *) fail EXECUTION_RUNTIME_CURRENT_UNSAFE ;; esac
    cp -P -- "$root/current" "$backup/current"
fi
if [ -e "$root/state/active" ] || [ -L "$root/state/active" ]; then
    [ -f "$root/state/active" ] && [ ! -L "$root/state/active" ] && [ "$(stat -c %u "$root/state/active")" = 0 ] || fail EXECUTION_RUNTIME_ACTIVE_UNSAFE
    cp -p -- "$root/state/active" "$backup/active"
fi
if [ -e "$release" ] || [ -L "$release" ]; then
    verify_bundle "$release" 1 || fail EXECUTION_RUNTIME_EXISTING_RELEASE_INVALID
else
    mv -- "$candidate" "$release"
    created=1
fi
diagnostic_code=EXECUTION_RUNTIME_PYTHON_INITIALIZATION_FAILED
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$release/ansible-core/tools" python3 -c 'from execution_secret_output import _directory; from execution_lifecycle import EXECUTION_STATE_ROOT; exec("with _directory(EXECUTION_STATE_ROOT, create=True):\n    pass")'
diagnostic_code=EXECUTION_RUNTIME_CAPABILITY_CHECK_FAILED
env PYTHONDONTWRITEBYTECODE=1 ANSIBLE_CONFIG="$release/ansible-core/ansible.cfg" ANSIBLE_COLLECTIONS_PATH="$release/ansible-core/collections" ansible-playbook -i localhost, "$release/ansible-core/playbooks/execution-capabilities.yml" -e "platform_execution_runtime_root=$release" -e "platform_execution_bundle_digest=$bundle_digest" >/dev/null
printf 'BUNDLE_VERSION=%s\nBUNDLE_DIGEST=%s\nCORE_VERSION=%s\nPROTOCOL=%s\nANSIBLE=yes\nCAPABILITIES=yes\n' "$bundle_version" "$bundle_digest" "$core_version" "$protocol" > "$backup/new-active"
ln -s -- "$release" "$backup/new-current"
diagnostic_code=EXECUTION_RUNTIME_SWITCH_FAILED
switching=1
mv -Tf -- "$backup/new-current" "$root/current"
mv -f -- "$backup/new-active" "$root/state/active"
success=1
`

const runtimeCandidateCleanupScript = `set -eu
stage=$1
case "$stage" in /var/tmp/platform-installer-bootstrap-*) ;; *) exit 64 ;; esac
nonce=${stage##*-}
case "$nonce" in ''|*[!0-9a-f]*) exit 64 ;; esac
[ "${#nonce}" = 32 ] || exit 64
root=/var/lib/platform-installer/runtime
[ -d "$root/state" ] && [ ! -L "$root/state" ] && [ "$(stat -c %u "$root/state")" = 0 ] || exit 64
[ -f "$root/state/prepare.lock" ] && [ ! -L "$root/state/prepare.lock" ] || exit 64
exec 9>"$root/state/prepare.lock"
flock -n 9 || exit 75
candidate=$root/releases/.prepare-$nonce
[ ! -L "$root/releases" ] && [ ! -L "$candidate" ] || exit 64
if [ -e "$candidate" ]; then
    [ -d "$candidate" ] && [ "$(stat -c %u "$candidate")" = 0 ] || exit 64
    rm -rf -- "$candidate"
fi
`
