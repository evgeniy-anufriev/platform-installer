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

awk '
    BEGIN { phase = "BEFORE_LOGIN" }
    /keycloak-admin trace: .*config credentials.*--client temp-admin([[:space:]]|$)/ {
        phase = "LOGIN_TEMP_ADMIN"; next
    }
    /keycloak-admin trace: .*config credentials.*--client admin-cli([[:space:]]|$)/ {
        phase = "LOGIN_ADMIN_CLI"; next
    }
    /keycloak-admin trace: .*get clients.*clientId=temp-admin([[:space:]]|$)/ {
        phase = "GET_CLIENTS"; next
    }
    /keycloak-admin trace: .*fail 60([[:space:]]|$)/ { print NR, "STEP_60"; next }
    /keycloak-admin trace:/ { next }
    {
        line = tolower($0)
        while (match(line, /http( error| status)?[ :]+[0-9][0-9][0-9]|[0-9][0-9][0-9] (unauthorized|forbidden)|invalid_client|invalid_grant|unauthorized|forbidden|connection refused|timed out|pkix|certificate verify failed|failed to send request/)) {
            print NR, phase, substr(line, RSTART, RLENGTH)
            found = 1
            line = substr(line, RSTART + RLENGTH)
        }
    }
    END { if (!found) print "NO_KNOWN_ERROR_MARKERS" }
' "$log"
