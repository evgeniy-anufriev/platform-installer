#!/bin/sh
set -eu
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
compose() {
  docker compose --project-name "$compose_project" \
    --project-directory "$instance_path" \
    --env-file "$library_path/.env" \
    -f "$instance_path/compose.yml" "$@"
}
label() { docker container inspect --format "{{ index .Config.Labels \"$1\" }}" "$2"; }
owned() {
  [ "$(label platform.installer.project "$1")" = "$project_id" ] &&
  [ "$(label platform.installer.library "$1")" = "$library_id" ] &&
  [ "$(label platform.installer.instance "$1")" = "$instance_id" ] &&
  [ "$(label platform.installer.host "$1")" = "$host_id" ]
}

[ "$#" -eq 12 ] && [ "$1" = '--realm' ] && [ "$2" = 'master' ] &&
  [ "$3" = '--db-user' ] && [ "$5" = '--project' ] &&
  [ "$7" = '--library' ] && [ "$9" = '--instance' ] &&
  [ "${11}" = '--host' ] || fail APPLICATION_KEYCLOAK_BOOTSTRAP_ARGUMENT_INVALID
db_user=$4
project_id=$6
library_id=$8
instance_id=${10}
host_id=${12}
case "$db_user" in *[!a-zA-Z0-9_]*|'') fail APPLICATION_KEYCLOAK_BOOTSTRAP_ARGUMENT_INVALID;; esac
for value in "$project_id" "$library_id" "$instance_id" "$host_id"; do
  case "$value" in *[!a-zA-Z0-9_-]*|'') fail APPLICATION_KEYCLOAK_BOOTSTRAP_ARGUMENT_INVALID;; esac
done
instance_path=$(pwd -P)
library_path=$(dirname "$instance_path")
compose_project="$project_id-$library_id-$instance_id-$host_id"
container_name="$instance_id-$host_id"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
: "${PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE:?}"
: "${PLATFORM_SCRIPT_SECRET_DB_PASSWORD_FILE:?}"

if docker container inspect "$container_name" >/dev/null 2>&1; then
  owned "$container_name" || fail APPLICATION_KEYCLOAK_CONTAINER_OWNERSHIP_INVALID
  printf '{"status":"ok","changed":false}\n'
  exit 0
fi

temporary_name="${instance_id}-platform-bootstrap"
if docker container inspect "$temporary_name" >/dev/null 2>&1; then
  owned "$temporary_name" || fail APPLICATION_KEYCLOAK_BOOTSTRAP_CONTAINER_CONFLICT
  [ "$(docker container inspect --format '{{.State.Running}}' "$temporary_name")" = false ] ||
    fail APPLICATION_KEYCLOAK_BOOTSTRAP_CONTAINER_CONFLICT
  docker container rm "$temporary_name" >/dev/null || fail APPLICATION_KEYCLOAK_BOOTSTRAP_CLEANUP_FAILED
fi

wrapper="$instance_path/.scripts/keycloak-bootstrap-wrapper.sh"
trace_wrapper="$instance_path/.scripts/keycloak-bootstrap-trace.sh"
work="$instance_path/.scripts/.bootstrap-work"
diagnostic_directory="$instance_path/.scripts/diagnostics"
mkdir -p "$diagnostic_directory"
diagnostic_log="$diagnostic_directory/bootstrap-admin-$(date -u +%Y%m%dT%H%M%SZ)-$.log"
mkdir -p "$work"
trap 'rm -f "$wrapper" "$trace_wrapper"; rm -rf "$work"' EXIT HUP INT TERM
cat > "$trace_wrapper" <<'TRACE'
#!/bin/sh
set -eu
umask 077
fifo=/run/platform-admin-work/trace-pipe
mkfifo "$fifo"
# Raw xtrace exists only in this pipe. Never persist it before redaction.
jq -Rrs --rawfile admin /run/platform-db-password \
  --rawfile bootstrap /run/platform-bootstrap-secret '
  def variants: ., @sh, (@json | .[1:-1]), @uri;
  ([ $admin, $bootstrap ] | map(., split("\n")[]) | map(select(length > 0) | variants)
    | unique | sort_by(length) | reverse) as $secrets
  | reduce $secrets[] as $secret (. ; split($secret) | join("[REDACTED]"))
  | gsub("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"; "[REDACTED_JWT]")
' < "$fifo" >&2 &
redactor=$!
set +e
PS4='+ keycloak-bootstrap trace: ' /bin/sh -x /run/platform-bootstrap-wrapper "$@" > "$fifo" 2>&1
result=$?
wait "$redactor"
redaction_result=$?
set -e
rm -f "$fifo"
[ "$redaction_result" -eq 0 ] || exit 1
exit "$result"
TRACE
cat > "$wrapper" <<'WRAPPER'
#!/bin/sh
set -eu
export KC_DB_USERNAME="$1"
export KC_DB_PASSWORD="$(cat /run/platform-db-password)"
export PLATFORM_BOOTSTRAP_SECRET="$(cat /run/platform-bootstrap-secret)"
# This offline CLI has no published ports and does not run the Vault Agent.
# Keep its management interface on HTTP; production TLS is configured by Agent.
unset KC_HTTPS_KEY_STORE_FILE KC_HTTPS_KEY_STORE_TYPE
unset KC_HTTPS_CERTIFICATE_FILE KC_HTTPS_CERTIFICATE_KEY_FILE
export KC_HTTP_ENABLED=true
export KC_HTTP_MANAGEMENT_SCHEME=http
exec /usr/lib/keycloak/bin/kc.sh bootstrap-admin service --client-id temp-admin \
  --client-secret:env=PLATFORM_BOOTSTRAP_SECRET --no-prompt
WRAPPER
chmod 0600 "$wrapper"

printf 'bootstrap-admin start=%s host=%s\n' "$(date -u +%FT%TZ)" "$host_id" > "$diagnostic_log"
compose_result=0
compose run --rm --no-deps --pull never -T --name "$temporary_name" \
  --user 0:0 --entrypoint /bin/sh \
  -v "$wrapper:/run/platform-bootstrap-wrapper:ro" \
  -v "$trace_wrapper:/run/platform-trace-wrapper:ro" \
  -v "$work:/run/platform-admin-work" \
  -v "$PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE:/run/platform-bootstrap-secret:ro" \
  -v "$PLATFORM_SCRIPT_SECRET_DB_PASSWORD_FILE:/run/platform-db-password:ro" \
  "$instance_id" /run/platform-trace-wrapper "$db_user" \
  >> "$diagnostic_log" 2>&1 || compose_result=$?
printf 'bootstrap-admin finish=%s compose_rc=%s\n' "$(date -u +%FT%TZ)" "$compose_result" >> "$diagnostic_log"
cat "$diagnostic_log" >&2
[ "$compose_result" -eq 0 ] || fail APPLICATION_KEYCLOAK_BOOTSTRAP_FAILED
printf '{"status":"ok","changed":true}\n'
