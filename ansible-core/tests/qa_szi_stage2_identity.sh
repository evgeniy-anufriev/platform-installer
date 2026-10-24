#!/bin/sh
# Isolated REST package acceptance: ephemeral loopback port, no installed DB/project.
set -eu
umask 077
[ "${PLATFORM_QA_SZI2_ALLOW_FIXTURE:-}" = 1 ] && [ "$#" -eq 1 ] || exit 2
source_script=$1
account=platform-docker
uid=$(id -u "$account")
account_home=$(getent passwd "$account" | cut -d: -f6)
image=evoscada-docker.artifacts.tn.tngrp.ru/alt/c10f/keycloak:26.4.0-05082026-1220-92d3b787-vault
docker() { sudo -n -u "$account" env XDG_RUNTIME_DIR="/run/user/$uid" DOCKER_HOST="unix:///run/user/$uid/docker.sock" /usr/bin/docker "$@"; }
docker image inspect "$image" >/dev/null
work=$(sudo -n -u "$account" sh -c 'umask 077; mkdir -p "$HOME/.runtime/secrets"; mktemp -d "$HOME/.runtime/secrets/szi2-native-XXXXXXXX"')
case "$work" in "$account_home"/.runtime/secrets/szi2-native-*) ;; *) exit 2;; esac
diagnostic=$(mktemp)
name=qa-$(basename "$work")
phase=setup
cleanup() {
  if [ "$(docker inspect --format '{{index .Config.Labels "platform.qa.szi2"}}' "$name" 2>/dev/null || true)" = "$name" ]; then
    docker rm -f "$name" >/dev/null 2>&1 || true
  fi
  rm -f -- "$diagnostic"
  sudo -n -u "$account" rm -rf -- "$work"
}
finish() {
  code=$?
  if [ "$code" -ne 0 ]; then
    printf 'SZI2_NATIVE_FAILED phase=%s\n' "$phase" >&2
    for marker in 'Invalid option' 'No server specified' 'HTTP 401' 'HTTP 403' 'HTTP 404' 'OutOfMemoryError' 'jq: error' 'invalid_grant' 'Not Found' 'Failed to' 'SEED_ATTRIBUTE_MISSING' 'SEED_ID_QUERY_FAILED'; do
      if grep -Fq "$marker" "$diagnostic"; then printf 'SZI2_NATIVE_DIAGNOSTIC class=%s\n' "$marker" >&2; fi
    done
  fi
  cleanup
  exit "$code"
}
trap finish EXIT
trap 'exit 1' HUP INT TERM
sudo -n install -o "$account" -g "$account" -m 0600 "$source_script" "$work/integration.sh"
sudo -n -u "$account" sh -s -- "$work" <<'SETUP'
set -eu
umask 077
work=$1
openssl rand -base64 24 | tr -d '\n' > "$work/admin-password"
openssl rand -base64 24 | tr -d '\n' > "$work/user-password"
openssl rand -base64 24 | tr -d '\n' > "$work/client-secret"
printf 'KC_BOOTSTRAP_ADMIN_USERNAME=admin\nKC_BOOTSTRAP_ADMIN_PASSWORD=%s\n' "$(cat "$work/admin-password")" > "$work/env"
openssl req -new -newkey rsa:2048 -nodes -x509 -days 1 -subj /CN=localhost \
  -addext 'subjectAltName=DNS:localhost' -keyout "$work/leaf.key" -out "$work/ca-chain.pem" >/dev/null 2>&1
mkdir -m 700 "$work/results"
SETUP
docker run -d --pull never --name "$name" --label "platform.qa.szi2=$name" \
  --publish 127.0.0.1::8443 --memory 1g --cpus 1 --user 0:0 --env-file "$work/env" \
  --env JAVA_OPTS_KC_HEAP=-Xms128m\ -Xmx512m \
  --tmpfs /usr/lib/keycloak/data --tmpfs /tmp \
  -v "$work:/run/qa" -v "$work/results:/run/identity-work" \
  -v "$work/ca-chain.pem:/opt/application/pki/ca-chain.pem:ro" \
  -v "$work/admin-password:/run/identity-admin-password:ro" \
  -v "$work/client-secret:/run/identity-client-secret:ro" \
  --entrypoint /usr/lib/keycloak/bin/kc.sh "$image" \
  start-dev --db=dev-file --cache=local --hostname-strict=false \
  --https-port=8443 --https-certificate-file=/run/qa/ca-chain.pem --https-certificate-key-file=/run/qa/leaf.key \
  --health-enabled=false --metrics-enabled=false >/dev/null
phase=readiness
attempt=0
until docker exec "$name" curl -fsS --cacert /run/qa/ca-chain.pem \
    https://localhost:8443/realms/master/.well-known/openid-configuration >/dev/null 2>&1; do
  attempt=$((attempt+1)); [ "$attempt" -le 90 ] || { printf '%s\n' SZI2_NATIVE_SERVER_NOT_READY >&2; exit 1; }
  sleep 2
done
# Only fixture setup/readback uses the image CLI; production integration runs on the host.
docker exec "$name" /bin/sh -c '
 set -eu
 export KC_OPTS="-Xms16m -Xmx128m"
 cli=/usr/lib/keycloak/bin/kcadm.sh
 keytool -importcert -noprompt -alias qa -file /run/qa/ca-chain.pem -keystore /run/identity-work/truststore.p12 -storetype PKCS12 -storepass qa-trust >/dev/null 2>&1
 $cli config truststore --trustpass qa-trust /run/identity-work/truststore.p12 --config /run/identity-work/admin.config >/dev/null 2>&1
 KC_CLI_PASSWORD="$(cat /run/qa/admin-password)" $cli config credentials --server https://localhost:8443 --realm master --client admin-cli --user admin --config /run/identity-work/admin.config >/dev/null 2>&1
' >"$diagnostic" 2>&1
port=$(docker port "$name" 8443/tcp | sed 's/.*://')
apply() {
  if docker exec "$name" test -s /run/identity-accounts; then
    docker exec "$name" cat /run/identity-accounts > "$work/accounts"
  fi
  CURL_CA_BUNDLE="$work/ca-chain.pem" \
  PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE="$work/admin-password" \
  PLATFORM_SCRIPT_SECRET_CLIENT_SECRET_FILE="$work/client-secret" \
  PLATFORM_SCRIPT_SECRET_ACCOUNT_BATCH_FILE="$work/accounts" \
  /bin/sh "$work/integration.sh" "$1" "https://localhost:$port" master admin \
    qa-client https://qa-client.example.test https://proxy.example.test "$2" >"$diagnostic" 2>&1 || {
      jq -c 'select(.status=="error") | {status,step,http_status,curl_exit}' "$diagnostic" >&2 || true
      return 1
    }
}
expect_result() {
  expected=false; [ "$1" != changed ] || expected=true
  jq -e --argjson expected "$expected" '.status=="ok" and .changed==$expected' "$diagnostic" >/dev/null
  printf "SZI2_NATIVE_PASS phase=%s\n" "$phase"
}
phase=groups-create
apply groups '["QA operators"]'; expect_result changed
phase=groups-repeat
apply groups '["QA operators"]'; expect_result unchanged
phase=cyrillic-group-create
apply groups '["ТУЗ"]'; expect_result changed
phase=cyrillic-group-repeat
apply groups '["ТУЗ"]'; expect_result unchanged
phase=seed-group-setup
docker exec "$name" /bin/sh -c '
  cli=/usr/lib/keycloak/bin/kcadm.sh
  printf "{\"name\":\"QA seed\",\"attributes\":{\"seed\":[\"preserve\"]}}" > /run/identity-work/seed.json
  $cli create groups -r master -f /run/identity-work/seed.json --config /run/identity-work/admin.config >/dev/null
' >"$diagnostic" 2>&1
phase=seed-group-adopt
apply groups '["QA seed"]'; expect_result unchanged
phase=seed-group-repeat
apply groups '["QA seed"]'; expect_result unchanged
phase=seed-group-readback
docker exec "$name" /bin/sh -c '
  set -eu
  export KC_OPTS="-Xms16m -Xmx128m"
  cli=/usr/lib/keycloak/bin/kcadm.sh
  config=/run/identity-work/admin.config
  id=$($cli get groups -r master -q search="QA seed" --config "$config" | jq -er ".[]|select(.name==\"QA seed\")|.id") || { printf "SEED_ID_QUERY_FAILED\n" >&2; exit 1; }
  $cli get "groups/$id" -r master --config "$config" | jq -e ".attributes.seed == [\"preserve\"]" >/dev/null || { printf "SEED_ATTRIBUTE_MISSING\n" >&2; exit 1; }
  printf "{\"name\":\"QA seed\",\"attributes\":{\"platform.installer.owner\":[\"foreign\"]}}" > /run/identity-work/foreign-group.json
  $cli update "groups/$id" -r master -f /run/identity-work/foreign-group.json --config "$config" >/dev/null
' >"$diagnostic" 2>&1
phase=foreign-group
apply groups '["QA seed"]'; expect_result unchanged
phase=client-create
apply client '{"publicClient":false,"directAccessGrantsEnabled":true}'; expect_result changed
phase=client-repeat
apply client '{"publicClient":false,"directAccessGrantsEnabled":true}'; expect_result unchanged
phase=group-roles-create
apply group-roles '[{"name":"QA operators","roles_file":{"realm_roles":["qa-realm-reader"],"client_roles":{"qa-client":["qa-client-reader"]}}}]'; expect_result changed
phase=group-roles-repeat
apply group-roles '[{"name":"QA operators","roles_file":{"realm_roles":["qa-realm-reader"],"client_roles":{"qa-client":["qa-client-reader"]}}}]'; expect_result unchanged
phase=group-roles-retain
apply group-roles '[{"name":"QA operators","roles_file":{"realm_roles":[],"client_roles":{}}}]'; expect_result unchanged
phase=group-roles-retained-readback
apply group-roles '[{"name":"QA operators","roles_file":{"realm_roles":["qa-realm-reader"],"client_roles":{"qa-client":["qa-client-reader"]}}}]'; expect_result unchanged
docker exec "$name" /bin/sh -c '
  set -eu; umask 077
  jq -n --rawfile password /run/qa/user-password \
    "{accounts:[{id:\"qa-library/consumer/identity\",mode:\"managed\",username:\"qa-user\",parameters:{groups:[\"QA operators\"],roles_file:{realm_roles:[\"qa-user-reader\"],client_roles:{\"qa-client\":[\"qa-user-client-reader\"]}}}}],passwords:{\"qa-library/consumer/identity\":\$password}}" \
    > /run/identity-accounts
'
phase=accounts-create
apply accounts '{}'; expect_result changed
phase=accounts-repeat
apply accounts '{}'; expect_result unchanged
# Password rotation must update only the owned user, then become no-change.
docker exec "$name" /bin/sh -c 'jq ".passwords[\"qa-library/consumer/identity\"] += \"-rotated\"" /run/identity-accounts > /tmp/accounts.new; mv /tmp/accounts.new /run/identity-accounts'
phase=password-rotation
apply accounts '{}'; expect_result changed
phase=password-repeat
apply accounts '{}'; expect_result unchanged
# Existing mode with a wrong password is a failure, never a password reset.
docker exec "$name" /bin/sh -c 'jq ".accounts[0].mode=\"existing\" | .passwords[\"qa-library/consumer/identity\"] += \"-wrong\"" /run/identity-accounts > /tmp/accounts.new; mv /tmp/accounts.new /run/identity-accounts'
phase=existing-wrong-password
if apply accounts '{}'; then printf '%s\n' SZI2_EXISTING_PASSWORD_WAS_ACCEPTED >&2; exit 1; fi
docker exec "$name" /bin/sh -c 'jq ".passwords[\"qa-library/consumer/identity\"] |= sub(\"-wrong$\";\"\")" /run/identity-accounts > /tmp/accounts.new; mv /tmp/accounts.new /run/identity-accounts'
phase=existing-good-password
apply accounts '{}'; expect_result unchanged
# Managed users reconcile without an Installer ownership marker.
docker exec "$name" /bin/sh -c '
  set -eu
  cli=/usr/lib/keycloak/bin/kcadm.sh; config=/run/identity-work/admin.config
  id=$($cli get users -r master -q username=qa-user -q exact=true --config "$config" | jq -r ".[0].id")
  printf "{\"attributes\":{}}" > /run/identity-work/foreign.json
  $cli update "users/$id" -r master -f /run/identity-work/foreign.json --config "$config" >/dev/null
  jq ".accounts[0].mode=\"managed\"" /run/identity-accounts > /tmp/accounts.new; mv /tmp/accounts.new /run/identity-accounts
' >/dev/null 2>&1
phase=foreign-user
apply accounts '{}'; expect_result unchanged
printf '{"status":"PASS","groups_repeat":true,"client_repeat":true,"accounts_repeat":true,"rotation":true,"existing_password_guard":true,"unmarked_user_update":true}\n'
