#!/bin/sh
set -eu
endpoint=${1%/}
project_name=$2
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
  "$endpoint/v1/project" > "$work/projects.json"
if jq -e --arg name "$project_name" 'any(.[]; .name == $name)' "$work/projects.json" >/dev/null; then
  printf '%s\n' '{"status":"ok","changed":false}'
  exit 0
fi
project_id=$(jq '([.[].id] | max // 0) + 1' "$work/projects.json")
jq -n --argjson id "$project_id" --arg name "$project_name" '{id:$id,name:$name}' > "$work/project.json"
curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
  --header 'Content-Type: application/json' --data-binary "@$work/project.json" \
  "$endpoint/v1/project" > "$work/created.json"
jq -e --arg name "$project_name" '.name == $name' "$work/created.json" >/dev/null
printf '%s\n' '{"status":"ok","changed":true}'
