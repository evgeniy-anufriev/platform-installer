#!/bin/sh
# Fixed pre-Python runtime bootstrap. Executed only from a verified root-owned bundle.
set -eu
release=$1
platforms=$2
fail() { printf '%s\n' "$1" >&2; exit 78; }
[ "$(id -u)" = 0 ] || fail EXECUTION_BOOTSTRAP_NOT_ROOT
[ -r /etc/os-release ] || fail EXECUTION_BOOTSTRAP_OS_RELEASE_MISSING
. /etc/os-release
architecture=$(uname -m)
case "${ID-}:${VERSION_ID-}:$architecture" in *[!A-Za-z0-9._:-]*|::*|*:..:*|*:.:*) fail EXECUTION_BOOTSTRAP_PLATFORM_INVALID ;; esac
case "${ID-}:$architecture" in redos:x86_64) ;; *) fail EXECUTION_BOOTSTRAP_OS_UNSUPPORTED ;; esac
case " $platforms " in *" $ID:$VERSION_ID:$architecture "*) ;; *) fail EXECUTION_BOOTSTRAP_PLATFORM_MISMATCH ;; esac
for tool in rpm dnf; do command -v "$tool" >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_PACKAGE_TOOL_MISSING; done
missing=''
for package in python3 ansible-core openssl ca-certificates tar gzip; do
    if rpm -q "$package" >/dev/null 2>&1; then
        case "$package" in ansible-core) command=ansible-playbook ;; ca-certificates) command='' ;; *) command=$package ;; esac
        if [ -n "$command" ]; then command -v "$command" >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_INSTALLED_PACKAGE_BROKEN; fi
    else
        missing="$missing $package"
    fi
done
if [ -z "$missing" ]; then printf '%s\n' BOOTSTRAP_SOURCE=INSTALLED; exit 0; fi
directory=$release/runtime/packages/$ID/$VERSION_ID/$architecture
local_names=''
set --
for artifact in "$directory"/*.rpm; do
    if [ ! -e "$artifact" ] && [ ! -L "$artifact" ]; then continue; fi
    [ -f "$artifact" ] && [ ! -L "$artifact" ] || fail EXECUTION_BOOTSTRAP_RPM_UNSAFE
    name=$(rpm -qp --qf '%{NAME}' "$artifact" 2>/dev/null) || fail EXECUTION_BOOTSTRAP_RPM_INVALID
    case "$name" in ''|-*|*[!A-Za-z0-9._+-]*) fail EXECUTION_BOOTSTRAP_RPM_INVALID ;; esac
    case " $local_names " in *" $name "*) fail EXECUTION_BOOTSTRAP_RPM_AMBIGUOUS ;; esac
    local_names="$local_names $name"
    if ! rpm -q "$name" >/dev/null 2>&1; then set -- "$@" "$artifact"; fi
done
repository=''
for package in $missing; do
    case " $local_names " in *" $package "*) ;; *) repository="$repository $package" ;; esac
done
if [ -z "$repository" ]; then
    dnf -q -y --disablerepo='*' --setopt=install_weak_deps=False install "$@" >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_OFFLINE_INSTALL_FAILED
    source=OFFLINE_BUNDLE
else
    for package in $repository; do set -- "$@" "$package"; done
    dnf -q -y --setopt=install_weak_deps=False install "$@" >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_REPOSITORY_INSTALL_FAILED
    source=REPOSITORY_OR_MIXED
fi
for package in $missing; do rpm -q "$package" >/dev/null 2>&1 || fail EXECUTION_BOOTSTRAP_PACKAGE_NOT_INSTALLED; done
printf 'BOOTSTRAP_SOURCE=%s\n' "$source"
