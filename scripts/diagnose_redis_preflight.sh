#!/usr/bin/env bash
# Run on the Execution Node. Only safe error codes and connection metadata are printed.
set -euo pipefail

if (( $# > 1 )); then
    echo "Usage: sudo bash $0 [runs-directory]" >&2
    exit 2
fi

root=${1:-/var/lib/platform-installer/execution/runs}
[[ -d "$root" ]] || { echo "RUN_DIRECTORY_NOT_FOUND" >&2; exit 1; }
command -v jq >/dev/null || { echo "JQ_REQUIRED" >&2; exit 1; }

latest=$(find "$root" -type f -name events.jsonl -printf '%T@\t%p\0' |
    sort -z -k1,1n | tail -z -n 1 | tr -d '\000')
[[ -n "$latest" ]] || { echo "EXECUTION_LOG_NOT_FOUND" >&2; exit 1; }
log=${latest#*$'\t'}
printf 'RUN: %s\n' "$(basename "$(dirname "$log")")"

errors=$(jq -c '
    select(.task.role? == "platform.redis.application_provider")
    | (.ansibleOutput? // empty)
    | (if type == "string" then fromjson? else . end)
    | .results[]?
    | select(.failed == true)
    | {
        error: (if (.msg | type) == "string" and
                   (.msg | test("^(REDIS|APPLICATION)_[A-Z0-9_]+$"))
                then .msg else "REDIS_DIAGNOSTIC_MESSAGE_REDACTED" end),
        address: .invocation.module_args.address,
        port: .invocation.module_args.port,
        listener: .invocation.module_args.listener
      }
' "$log")

if [[ -z "$errors" ]]; then
    failures=$(jq -c '
        select(.task.role? == "platform.redis.application_provider" and .status == "FAILED")
        | {
            error: (if (.error.code? // "" | test("^[A-Z][A-Z0-9_]+$"))
                    then .error.code else "REDIS_TASK_FAILED" end),
            diagnostic: (if (.ansibleOutput? // "" | type) == "string" and
                            (.ansibleOutput? // "" | contains("[truncated]"))
                         then "ANSIBLE_OUTPUT_TRUNCATED_FAILED_ITEM_UNAVAILABLE"
                         elif (.ansibleOutput? // "") == ""
                         then "ANSIBLE_OUTPUT_HIDDEN_OR_MISSING"
                         else "FAILED_ITEM_NOT_AVAILABLE_IN_OUTPUT" end)
          }
    ' "$log")
    if [[ -n "$failures" ]]; then
        printf '%s\n' "$failures"
        exit 1
    fi
    echo "REDIS_FAILED_ITEM_NOT_FOUND: latest run has no visible failed Redis/Sentinel item."
    exit 1
fi
printf '%s\n' "$errors"
