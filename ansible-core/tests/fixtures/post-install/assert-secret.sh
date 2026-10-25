#!/bin/sh
# QA fixture: compare restored published input to a separate session input.
set -eu
test -s "$PLATFORM_SCRIPT_SECRET_PASSWORD_FILE"
test -s "$PLATFORM_SCRIPT_SECRET_EXPECTED_FILE"
cmp -s "$PLATFORM_SCRIPT_SECRET_PASSWORD_FILE" "$PLATFORM_SCRIPT_SECRET_EXPECTED_FILE"
printf '%s\n' '{"status":"ok","changed":false}'
