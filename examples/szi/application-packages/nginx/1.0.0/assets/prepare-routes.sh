#!/bin/sh
set -eu
umask 077
fail() { printf '%s\n' APPLICATION_ROUTES_APPLY_FAILED >&2; exit 1; }
[ "$#" -eq 4 ] || fail
project=$1; library=$2; instance=$3; host=$4
for value in "$project" "$library" "$instance" "$host"; do
  case "$value" in ''|*[!a-zA-Z0-9_.-]*) fail;; esac
done
path=$(pwd -P)
diagnostic_directory="$path/.scripts/diagnostics"
mkdir -p "$diagnostic_directory"
diagnostic_log="$diagnostic_directory/prepare-routes-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
step=0
finish() {
  result=$?
  set +x
  [ -z "${write_override:-}" ] || rm -f "$write_override"
  exec 2>&3
  cat "$diagnostic_log" >&3
  printf 'prepare-routes finish=%s rc=%s step=%s log=%s\n' "$(date -u +%FT%TZ)" "$result" "$step" "$diagnostic_log" >&3
  if [ "$result" -ne 0 ]; then printf '{"status":"error","step":%s}\n' "$step"; fi
  exit "$result"
}
exec 3>&2
trap finish EXIT
exec 2>> "$diagnostic_log"
# This script has no credential inputs; trace argv and nginx diagnostics in full.
PS4='+ prepare-routes trace: '
set -x
mkdir -p "$path/routes"
chmod 0755 "$path/routes"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
compose() {
  docker compose --project-name "$project-$library-$instance-$host" \
    --project-directory "$path" --env-file "$(dirname "$path")/.env" -f "$path/compose.yml" "$@"
}
step=10
write_override=$(mktemp "$path/.scripts/routes-write-XXXXXX.yml")
printf 'services:\n  "%s":\n    volumes:\n      - ./routes:/var/lib/nginx/routes:rw\n' "$instance" > "$write_override"
compose -f "$write_override" run --rm --no-deps --pull never -T --user 0:0 --entrypoint /usr/local/openresty/nginx/sbin/nginx \
  "$instance" \
  -c /etc/nginx/routes-upsert.conf >> "$diagnostic_log" 2>&1 || fail
step=20
compose run --rm --no-deps --pull never -T --entrypoint /usr/local/openresty/nginx/sbin/nginx "$instance" -t -c /etc/nginx/nginx.conf >> "$diagnostic_log" 2>&1 || fail
step=30
cat "$path/routes/result.json"
printf '\n'
