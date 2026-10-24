#!/bin/sh
set -eu
umask 077

fail() {
  step=900
  if [ -f "${work:-/nonexistent}/failure-step" ]; then
    recorded_step=$(cat "$work/failure-step")
    case "$recorded_step" in
      ''|*[!0-9]*|??????*) ;;
      *) [ "$recorded_step" -le 65535 ] && step=$recorded_step;;
    esac
  fi
  printf '{"status":"error","step":%s}\n' "$step"
  printf '%s\n' "$1" >&2
  exit 1
}
compose() {
  docker compose --project-name "$compose_project" \
    --project-directory "$instance_path" \
    --env-file "$library_path/.env" \
    -f "$instance_path/compose.yml" "$@"
}

[ "$#" -eq 12 ] && [ "$1" = '--realm' ] && [ "$2" = master ] &&
  [ "$3" = '--keycloak-url' ] && [ "$5" = '--project' ] &&
  [ "$7" = '--library' ] && [ "$9" = '--instance' ] &&
  [ "${11}" = '--host' ] || fail APPLICATION_KEYCLOAK_ADMIN_ARGUMENT_INVALID
case "$4" in https://*) ;; *) fail APPLICATION_KEYCLOAK_ADMIN_ENDPOINT_INVALID;; esac
project_id=$6
library_id=$8
instance_id=${10}
host_id=${12}
for value in "$project_id" "$library_id" "$instance_id" "$host_id"; do
  case "$value" in *[!a-zA-Z0-9_-]*|'') fail APPLICATION_KEYCLOAK_ADMIN_ARGUMENT_INVALID;; esac
done
instance_path=$(pwd -P)
library_path=$(dirname "$instance_path")
compose_project="$project_id-$library_id-$instance_id-$host_id"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
: "${PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE:?}"
: "${PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE:?}"
work="$instance_path/.scripts/.admin-work"
wrapper="$instance_path/.scripts/keycloak-create-admin-wrapper.sh"
trace_wrapper="$instance_path/.scripts/keycloak-admin-trace.sh"
diagnostic_directory="$instance_path/.scripts/diagnostics"
mkdir -p "$diagnostic_directory"
diagnostic_log="$diagnostic_directory/create-admin-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
rm -rf "$work"
mkdir -m 700 "$work"
trap 'rm -f "$wrapper" "$trace_wrapper"; rm -rf "$work"' EXIT HUP INT TERM
cat > "$trace_wrapper" <<'TRACE'
#!/bin/sh
set -eu
umask 077
fifo=/run/platform-admin-work/trace-pipe
mkfifo "$fifo"
# Raw xtrace exists only in this pipe. Never persist it before redaction.
jq -Rrs --rawfile admin /run/platform-admin-password \
  --rawfile bootstrap /run/platform-bootstrap-secret '
  def variants: ., @sh, (@json | .[1:-1]), @uri;
  ([ $admin, $bootstrap ] | map(., split("\n")[]) | map(select(length > 0) | variants)
    | unique | sort_by(length) | reverse) as $secrets
  | reduce $secrets[] as $secret (. ; split($secret) | join("[REDACTED]"))
  | gsub("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"; "[REDACTED_JWT]")
' < "$fifo" >&2 &
redactor=$!
set +e
PS4='+ keycloak-admin trace: ' /bin/sh -x /run/platform-admin-wrapper "$@" > "$fifo" 2>&1
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
umask 077
fail() { printf '%s' "${1:-10}" > /run/platform-admin-work/failure-step; exit 1; }
kc=/usr/lib/keycloak/bin/kcadm.sh
config=/run/platform-admin-work/kcadm.config
url=$1
password=$(cat /run/platform-admin-password)
[ -s /run/platform-bootstrap-secret ] && [ -n "$password" ] || fail

# The CLI uses a private truststore; TLS name checking remains enabled.
keytool -importcert -noprompt -alias platform-ca -file /opt/application/pki/ca-chain.pem \
  -keystore /run/platform-admin-work/truststore.p12 -storetype PKCS12 \
  -storepass platform-trust || fail 20
for client_config in "$config" /run/platform-admin-work/permanent.config; do
  "$kc" config truststore --trustpass platform-trust \
    /run/platform-admin-work/truststore.p12 --config "$client_config" || fail 30
done

if ! KC_CLI_CLIENT_SECRET="$(cat /run/platform-bootstrap-secret)" \
  "$kc" config credentials --server "$url" --realm master --client temp-admin \
  --config "$config"; then
  KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
    --client admin-cli --user admin --config "$config" || fail 50
  raw_clients=$("$kc" get clients -r master -q clientId=temp-admin --fields id \
    --format csv --noquotes --config "$config") || fail 60
  clients=$(printf '%s\n' "$raw_clients" | grep -E '^[0-9a-fA-F-]{36}$' || true)
  [ -z "$clients" ] || fail 61
  printf 'unchanged' > /run/platform-admin-work/result
  exit 0
fi

raw_users=$("$kc" get users -r master -q username=admin -q exact=true --fields id \
  --format csv --noquotes --config "$config") || fail 70
users=$(printf '%s\n' "$raw_users" | grep -E '^[0-9a-fA-F-]{36}$' || true)
case "$users" in *'
'*) fail 71;; esac
new_admin=false
if [ -z "$users" ]; then
  new_admin=true
  printf '%s\n' '{"username":"admin","enabled":true,"attributes":{"platform.installer.bootstrap":["szi"]}}' \
    > /run/platform-admin-work/admin.json
  "$kc" create users -r master -f /run/platform-admin-work/admin.json \
    --config "$config" || fail 80
  raw_users=$("$kc" get users -r master -q username=admin -q exact=true --fields id \
    --format csv --noquotes --config "$config") || fail 90
  users=$(printf '%s\n' "$raw_users" | grep -E '^[0-9a-fA-F-]{36}$' || true)
  [ -n "$users" ] || fail 91
else
  if ! KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
    --client admin-cli --user admin --config /run/platform-admin-work/permanent.config; then
    attributes=$("$kc" get "users/$users" -r master --fields attributes --config "$config") || fail 100
    printf '%s\n' "$attributes" | grep -F '"platform.installer.bootstrap"' >/dev/null || fail 101
    printf '%s\n' "$attributes" | grep -F '"szi"' >/dev/null || fail 101
  fi
fi

roles=$("$kc" get-roles -r master --uusername admin --fields name --format csv --noquotes \
  --config "$config") || fail 110
if ! printf '%s\n' "$roles" | grep -qx admin; then
  "$kc" add-roles -r master --uusername admin --rolename admin \
    --config "$config" || fail 120
fi

if [ "$new_admin" = true ] || ! KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
  --client admin-cli --user admin --config /run/platform-admin-work/permanent.config; then
  KC_CLI_PASSWORD=$password "$kc" set-password -r master --username admin \
    --config "$config" || fail 130
  KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
    --client admin-cli --user admin --config /run/platform-admin-work/permanent.config || fail 140
fi

raw_clients=$("$kc" get clients -r master -q clientId=temp-admin --fields id \
  --format csv --noquotes --config /run/platform-admin-work/permanent.config) || fail 150
clients=$(printf '%s\n' "$raw_clients" | grep -E '^[0-9a-fA-F-]{36}$' || true)
case "$clients" in *'
'*|'') fail 151;; esac
"$kc" delete "clients/$clients" -r master --config /run/platform-admin-work/permanent.config \
  || fail 160
printf 'changed' > /run/platform-admin-work/result
WRAPPER
chmod 0600 "$wrapper"
printf 'create-admin start=%s endpoint=%s host=%s\n' "$(date -u +%FT%TZ)" "$4" "$host_id" > "$diagnostic_log"
compose_result=0
compose run --rm --no-deps --pull never -T --user 0:0 \
  --entrypoint /bin/sh \
  -v "$wrapper:/run/platform-admin-wrapper:ro" \
  -v "$trace_wrapper:/run/platform-trace-wrapper:ro" \
  -v "$PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE:/run/platform-bootstrap-secret:ro" \
  -v "$PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE:/run/platform-admin-password:ro" \
  -v "$work:/run/platform-admin-work" \
  "$instance_id" /run/platform-trace-wrapper "$4" \
  >> "$diagnostic_log" 2>&1 || compose_result=$?
printf 'create-admin finish=%s compose_rc=%s\n' "$(date -u +%FT%TZ)" "$compose_result" >> "$diagnostic_log"
cat "$diagnostic_log" >&2
[ "$compose_result" -eq 0 ] || fail APPLICATION_KEYCLOAK_ADMIN_FAILED
case "$(cat "$work/result")" in
  changed) printf '{"status":"ok","changed":true}\n';;
  unchanged) printf '{"status":"ok","changed":false}\n';;
  *) fail APPLICATION_KEYCLOAK_ADMIN_RESULT_INVALID;;
esac
