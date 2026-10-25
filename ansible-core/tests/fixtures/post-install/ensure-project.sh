#!/bin/sh
# QA fixture: data-manager's real GET/POST /v1/project API.
set -eu
endpoint=${1%/}
project_id=$2
project_name=$3
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
  "$endpoint/v1/project" > "$work/projects.json"
if jq -e --argjson id "$project_id" 'any(.[]; .id == $id)' "$work/projects.json" >/dev/null; then
  printf '%s\n' '{"status":"ok","changed":false}'
  exit 0
fi
jq -n --argjson id "$project_id" --arg name "$project_name" '{id:$id,name:$name}' > "$work/project.json"
curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
  --header 'Content-Type: application/json' --data-binary "@$work/project.json" \
  "$endpoint/v1/project" > "$work/created.json"
jq -e --argjson id "$project_id" '.id == $id' "$work/created.json" >/dev/null
printf '%s\n' '{"status":"ok","changed":true}'
