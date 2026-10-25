#!/bin/sh
set -eu
umask 077
fail() { printf '%s\n' APPLICATION_ROUTES_APPLY_FAILED >&2; exit 1; }
[ "$#" -eq 4 ] || [ "$#" -eq 5 ] || fail
project=$1; library=$2; instance=$3
path=$(pwd -P)
diagnostic_directory="$path/.scripts/diagnostics"
mkdir -p "$diagnostic_directory"
diagnostic_log="$diagnostic_directory/prepare-routes-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
step=0
finish() {
  result=$?
  set +x
  [ -z "${stage:-}" ] || rm -rf "$stage"
  exec 2>&3
  cat "$diagnostic_log" >&3
  printf 'prepare-routes finish=%s rc=%s step=%s log=%s\n' "$(date -u +%FT%TZ)" "$result" "$step" "$diagnostic_log" >&3
  if [ "$result" -ne 0 ]; then printf '{"status":"error","step":%s}\n' "$step"; fi
  exit "$result"
}
exec 3>&2
trap finish EXIT
exec 2>> "$diagnostic_log"
PS4='+ prepare-routes trace: '
set -x
mkdir -p "$path/routes"
chmod 0755 "$path/routes"
stage=$(mktemp -d "$path/.scripts/routes-input-XXXXXX")
step=10
if [ "$#" -eq 5 ]; then
  printf '%s' "$5" > "$stage/consumers.json"
  jq --arg owner "platform.application.routes/v1:$project:$library:$instance" '
    {owner: $owner, routes: (reduce .[] as $consumer ({};
      ($consumer.placements | to_entries | sort_by(.key) |
        map(.value | select(.endpointUrl != null)) | first) as $placement |
      if $placement == null then . else
        .[$consumer.applicationId] = {endpoint: $placement.endpointUrl,
          subpath: ("/" + $consumer.applicationId),
          parameters: ($placement.parameters.IDENTITY_ROUTE // {})}
      end))}
  ' "$stage/consumers.json" > "$stage/requested.json"
else
  cp "$path/config/routes.requested.json" "$stage/requested.json"
fi
step=20
if [ -f "$path/routes/routes.effective.json" ]; then
  cp "$path/routes/routes.effective.json" "$stage/previous.json"
else
  printf 'null\n' > "$stage/previous.json"
fi
jq --slurpfile requested "$stage/requested.json" '
  . as $previous | $requested[0] as $requested |
  ($previous // {owner: $requested.owner, routes: {}}) as $existing |
  if ($requested.owner | type) != "string" or ($requested.routes | type) != "object" then
    error("APPLICATION_ROUTES_INPUT_INVALID")
  elif $existing.owner != $requested.owner or ($existing.routes | type) != "object" then
    error("APPLICATION_ROUTES_OWNER_INVALID")
  elif (all($requested.routes | to_entries[];
    (.key | test("^[a-z][a-z0-9_.-]*$")) and (.value | type) == "object" and
    .value.subpath == ("/" + .key) and (.value.endpoint | type) == "string" and
    (.value.endpoint | test("^https?://[^/\\s]+$"))) | not) then
    error("APPLICATION_ROUTES_INPUT_INVALID")
  else
    ($existing + {routes: ($existing.routes + $requested.routes)}) as $effective |
    {effective: $effective, changed: ($previous != $effective)}
  end
' "$stage/previous.json" > "$stage/merged.json"
step=30
if jq -e .changed "$stage/merged.json" >/dev/null; then
  jq .effective "$stage/merged.json" > "$stage/routes.effective.json"
  chmod 0644 "$stage/routes.effective.json"
  mv "$stage/routes.effective.json" "$path/routes/routes.effective.json"
fi
jq '{status: "ok", changed: .changed}' "$stage/merged.json" > "$stage/result.json"
chmod 0644 "$stage/result.json"
mv "$stage/result.json" "$path/routes/result.json"
cat "$path/routes/result.json"
printf '\n'
