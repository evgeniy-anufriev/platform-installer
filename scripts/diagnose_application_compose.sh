#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash diagnose_application_compose.sh DOCKER_USER INSTANCE_DIR COMPOSE_PROJECT SERVICE [--up]

Run on the application host. By default, check the rendered Compose configuration.
--up also runs the Installer's first Compose start for the named service.
It can start or recreate that container. Run it after the Installer finishes.
Command output is saved in a private temporary file.
EOF
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  usage
  exit 0
fi
if [[ $# -lt 4 || $# -gt 5 || ( $# -eq 5 && $5 != --up ) ]]; then
  usage >&2
  exit 2
fi

docker_user=$1
instance=$(realpath -e -- "$2")
project=$3
service=$4
if [[ ! $project =~ ^[a-z0-9][a-z0-9_-]*$ || ! $service =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]]; then
  printf 'Invalid Compose project or service name.\n' >&2
  exit 2
fi
library=$(dirname -- "$instance")
if [[ ! -f "$instance/compose.yml" || ! -f "$library/.env" ]]; then
  printf 'Expected %s and %s.\n' "$instance/compose.yml" "$library/.env" >&2
  exit 2
fi

docker_uid=$(id -u -- "$docker_user")
runtime_dir="/run/user/$docker_uid"
if [[ ! -S "$runtime_dir/docker.sock" ]]; then
  printf 'Docker socket not found: %s/docker.sock\n' "$runtime_dir" >&2
  exit 2
fi

as_docker_user=()
if [[ $(id -u) != "$docker_uid" ]]; then
  as_docker_user=(sudo -H -u "$docker_user" --)
fi
compose=("${as_docker_user[@]}" env -u DOCKER_CONTEXT
  "XDG_RUNTIME_DIR=$runtime_dir" "DOCKER_HOST=unix://$runtime_dir/docker.sock"
  docker compose --project-name "$project" --project-directory "$instance"
  --env-file "$library/.env" -f "$instance/compose.yml")

umask 077
log=$(mktemp /tmp/installer-compose.XXXXXXXX)
printf 'Log: %s\n' "$log"

run_compose() {
  local stage=$1 rc
  if "${compose[@]}" "$@" >>"$log" 2>&1; then
    rc=0
  else
    rc=$?
  fi
  printf '%s rc=%s\n' "$stage" "$rc"
  return "$rc"
}

run_compose config --quiet
if [[ ${5:-} == --up ]]; then
  run_compose up -d --no-build --pull never --no-deps "$service"
fi
