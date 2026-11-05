#!/usr/bin/env bash
# Run on the host where create-admin failed.
set -euo pipefail

if (( $# > 1 )); then
    echo "Usage: sudo bash $0 [runtime-directory]" >&2
    exit 2
fi

root=${1:-/home/scada-docker}
if [[ ! -d "$root" ]]; then
    printf 'SEARCH_DIRECTORY_NOT_FOUND: %s\n' "$root" >&2
    exit 1
fi
root=$(realpath -- "$root")

latest=$(find "$root" -type f -path '*/.scripts/diagnostics/create-admin-*.log' \
    -printf '%T@\t%p\0' | sort -z -k1,1n | tail -z -n 1 | tr -d '\000')
if [[ -z "$latest" ]]; then
    printf 'CREATE_ADMIN_LOG_NOT_FOUND: %s\n' "$root" >&2
    exit 1
fi
log=${latest#*$'\t'}
printf 'LOG: %s\n' "$log"
stat -c 'MODIFIED: %y' -- "$log"

pattern='HTTP( Error| status)?[ :]+[0-9]{3}|[0-9]{3} (Forbidden|Unauthorized)|forbidden|unauthorized|invalid_grant|invalid_client|connection refused|timed out|PKIX|certificate verify failed'
if matches=$(grep -Eoi -- "$pattern" "$log"); then
    printf '%s\n' "$matches" | sort -fu
else
    status=$?
    if (( status != 1 )); then
        exit "$status"
    fi
    echo NO_KNOWN_ERROR_MARKERS
fi
