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
rm -rf "$work"
mkdir -m 700 "$work"
trap 'rm -f "$wrapper"; rm -rf "$work"' EXIT HUP INT TERM
cat > "$wrapper" <<'WRAPPER'
#!/bin/sh
set -eu
umask 077
fail() { exit 1; }
kc=/usr/lib/keycloak/bin/kcadm.sh
config=/run/platform-admin-work/kcadm.config
url=$1
password=$(cat /run/platform-admin-password)
[ -s /run/platform-bootstrap-secret ] && [ -n "$password" ] || fail

# The CLI uses a private truststore; TLS name checking remains enabled.
keytool -importcert -noprompt -alias platform-ca -file /opt/application/pki/ca-chain.pem \
  -keystore /run/platform-admin-work/truststore.p12 -storetype PKCS12 \
  -storepass platform-trust >/dev/null 2>&1 || fail
for client_config in "$config" /run/platform-admin-work/permanent.config; do
  "$kc" config truststore --trustpass platform-trust \
    /run/platform-admin-work/truststore.p12 --config "$client_config" >/dev/null 2>&1 || fail
done

if ! KC_CLI_CLIENT_SECRET="$(cat /run/platform-bootstrap-secret)" \
  "$kc" config credentials --server "$url" --realm master --client temp-admin \
  --config "$config" >/dev/null 2>&1; then
  KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
    --client admin-cli --user admin --config "$config" >/dev/null 2>&1 || fail
  raw_clients=$("$kc" get clients -r master -q clientId=temp-admin --fields id \
    --format csv --noquotes --config "$config" 2>/dev/null) || fail
  clients=$(printf '%s\n' "$raw_clients" | grep -E '^[0-9a-fA-F-]{36}$' || true)
  [ -z "$clients" ] || fail
  printf 'unchanged' > /run/platform-admin-work/result
  exit 0
fi

raw_users=$("$kc" get users -r master -q username=admin -q exact=true --fields id \
  --format csv --noquotes --config "$config" 2>/dev/null) || fail
users=$(printf '%s\n' "$raw_users" | grep -E '^[0-9a-fA-F-]{36}$' || true)
case "$users" in *'
'*) fail;; esac
if [ -z "$users" ]; then
  printf '%s\n' '{"username":"admin","enabled":true,"attributes":{"platform.installer.bootstrap":["szi"]}}' \
    > /run/platform-admin-work/admin.json
  "$kc" create users -r master -f /run/platform-admin-work/admin.json \
    --config "$config" >/dev/null 2>&1 || fail
  raw_users=$("$kc" get users -r master -q username=admin -q exact=true --fields id \
    --format csv --noquotes --config "$config" 2>/dev/null) || fail
  users=$(printf '%s\n' "$raw_users" | grep -E '^[0-9a-fA-F-]{36}$' || true)
  [ -n "$users" ] || fail
else
  if ! KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
    --client admin-cli --user admin --config /run/platform-admin-work/permanent.config >/dev/null 2>&1; then
    attributes=$("$kc" get "users/$users" -r master --fields attributes --config "$config" 2>/dev/null) || fail
    printf '%s\n' "$attributes" | grep -F '"platform.installer.bootstrap"' >/dev/null || fail
    printf '%s\n' "$attributes" | grep -F '"szi"' >/dev/null || fail
  fi
fi

roles=$("$kc" get-roles -r master --uusername admin --fields name --format csv --noquotes \
  --config "$config" 2>/dev/null) || fail
if ! printf '%s\n' "$roles" | grep -qx admin; then
  "$kc" add-roles -r master --uusername admin --rolename admin \
    --config "$config" >/dev/null 2>&1 || fail
fi

if ! KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
  --client admin-cli --user admin --config /run/platform-admin-work/permanent.config >/dev/null 2>&1; then
  KC_CLI_PASSWORD=$password "$kc" set-password -r master --username admin \
    --config "$config" >/dev/null 2>&1 || fail
  KC_CLI_PASSWORD=$password "$kc" config credentials --server "$url" --realm master \
    --client admin-cli --user admin --config /run/platform-admin-work/permanent.config >/dev/null 2>&1 || fail
fi

raw_clients=$("$kc" get clients -r master -q clientId=temp-admin --fields id \
  --format csv --noquotes --config /run/platform-admin-work/permanent.config 2>/dev/null) || fail
clients=$(printf '%s\n' "$raw_clients" | grep -E '^[0-9a-fA-F-]{36}$' || true)
case "$clients" in *'
'*|'') fail;; esac
"$kc" delete "clients/$clients" -r master --config /run/platform-admin-work/permanent.config \
  >/dev/null 2>&1 || fail
printf 'changed' > /run/platform-admin-work/result
WRAPPER
chmod 0600 "$wrapper"

compose run --rm --no-deps --pull never -T --user 0:0 \
  --entrypoint /bin/sh \
  -v "$wrapper:/run/platform-admin-wrapper:ro" \
  -v "$PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE:/run/platform-bootstrap-secret:ro" \
  -v "$PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE:/run/platform-admin-password:ro" \
  -v "$work:/run/platform-admin-work" \
  "$instance_id" /run/platform-admin-wrapper "$4" \
  >/dev/null 2>&1 || fail APPLICATION_KEYCLOAK_ADMIN_FAILED
case "$(cat "$work/result")" in
  changed) printf '{"status":"ok","changed":true}\n';;
  unchanged) printf '{"status":"ok","changed":false}\n';;
  *) fail APPLICATION_KEYCLOAK_ADMIN_RESULT_INVALID;;
esac
