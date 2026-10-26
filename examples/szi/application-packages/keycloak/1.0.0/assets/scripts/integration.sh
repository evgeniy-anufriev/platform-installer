#!/bin/sh
# Provider-owned REST client. Core supplies argv and private input files only.
set -eu
umask 077
exec 3>&1
identity_step=0
http_status=0
curl_exit=0
fail() { exit 1; }
finish() {
  result=$?
  set +x
  if [ -n "${work:-}" ] && [ -f "$work/http-status" ]; then
    read -r http_status curl_exit < "$work/http-status"
  fi
  if [ -n "${trace_pid:-}" ]; then
    exec 2>&4
    wait "$trace_pid" || result=1
    cat "$diagnostic_log" >&4
    printf 'integration finish=%s rc=%s step=%s http_status=%s curl_exit=%s log=%s\n' \
      "$(date -u +%FT%TZ)" "$result" "$identity_step" "$http_status" "$curl_exit" "$diagnostic_log" >&4
  fi
  if [ "$result" -ne 0 ]; then
    printf '{"status":"error","step":%s,"http_status":%s,"curl_exit":%s}\n' "$identity_step" "$http_status" "$curl_exit" >&3
  fi
  [ -z "${work:-}" ] || rm -rf "$work"
  exit "$result"
}
trap finish EXIT
trap 'exit 1' HUP INT TERM
bind_invocation() {
  [ "$#" -eq 8 ] || fail
  operation=$1; url=${2%/}; realm=$3; admin_user=$4
  instance=$5; endpoint=$6; proxy=$7; payload=$8
}
batch_file=${PLATFORM_SCRIPT_BATCH_FILE:-}
invocation_index=0
load_batch_invocation() {
  set -- "$(jq -er --argjson i "$invocation_index" '.[$i][0]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][1]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][2]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][3]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][4]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][5]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][6]' "$batch_file")" \
    "$(jq -er --argjson i "$invocation_index" '.[$i][7]' "$batch_file")"
  bind_invocation "$@"
}
if [ -n "$batch_file" ]; then
  [ "$#" -eq 0 ] || fail
  invocation_count=$(jq -er 'length | select(. > 0)' "$batch_file") || fail
  jq -e 'all(.[]; length == 8) and (.[0][1:4] as $auth | all(.[]; .[1:4] == $auth))' "$batch_file" >/dev/null || fail
  load_batch_invocation
else
  bind_invocation "$@"
  invocation_count=1
fi
batch_url=$url; batch_realm=$realm; batch_admin=$admin_user
command -v curl >/dev/null || fail
command -v jq >/dev/null || fail
case "$url" in https://*) ;; *) fail;; esac
work=$(mktemp -d)
admin_password=${PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE:?}
client_secret=${PLATFORM_SCRIPT_SECRET_CLIENT_SECRET_FILE:-$work/no-input}
accounts=${PLATFORM_SCRIPT_SECRET_ACCOUNT_BATCH_FILE:-$work/no-input}
diagnostic_directory="$PWD/.scripts/diagnostics"
mkdir -p "$diagnostic_directory"
diagnostic_log="$diagnostic_directory/integration-$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
trace_client=$client_secret; [ -f "$trace_client" ] || trace_client=/dev/null
trace_accounts=$accounts; [ -f "$trace_accounts" ] || trace_accounts=/dev/null
mkfifo "$work/trace-pipe"
exec 4>&2
# Retain full shell/curl diagnostics; redact in memory before writing the log.
jq -Rrs --rawfile admin "$admin_password" --rawfile client "$trace_client" \
  --rawfile batch "$trace_accounts" '
  def variants: ., @sh, (@json | .[1:-1]), @uri;
  ([$admin, $client, ($batch | fromjson? | .passwords? // {} | .. | strings)]
    | map(., split("\n")[]) | map(select(length > 0) | variants)
    | unique | sort_by(length) | reverse) as $secrets
  | reduce $secrets[] as $secret (. ; split($secret) | join("[REDACTED]"))
  | gsub("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"; "[REDACTED_JWT]")
' < "$work/trace-pipe" > "$diagnostic_log" &
trace_pid=$!
exec 2> "$work/trace-pipe"
PS4='+ szi-integration trace: '
set -x
printf 'integration start=%s operation=%s endpoint=%s realm=%s\n' "$(date -u +%FT%TZ)" "$operation" "$url" "$realm" >&2
changed=false
# curl uses the installed system CA trust; an explicit CA may be supplied by the caller.
transport() {
  curl_exit=0
  http_status=$(curl --silent --show-error --connect-timeout 10 --max-time 60 "$@") || curl_exit=$?
  case "$http_status" in [0-9][0-9][0-9]) http_status=$((1$http_status-1000));; *) http_status=0;; esac
  printf '%s %s\n' "$http_status" "$curl_exit" > "$work/http-status"
  [ "$curl_exit" -eq 0 ] || fail
}
token() {
  token_realm=$1; token_user=$2; token_password=$3
  token_realm_path=$(printf '%s' "$token_realm" | jq -sRr @uri)
  jq -njr --arg user "$token_user" --rawfile password "$token_password" \
    '"client_id=admin-cli&grant_type=password&username="+($user|@uri)+"&password="+($password|@uri)' > "$work/form"
  transport --output "$work/token.json" --write-out '%{http_code}' \
    --header 'Content-Type: application/x-www-form-urlencoded' --data-binary @"$work/form" \
    "$url/realms/$token_realm_path/protocol/openid-connect/token"
  [ "$http_status" -eq 200 ] && jq -e '.access_token | type == "string" and length > 0' "$work/token.json" >/dev/null
}
admin_token() {
  token master "$admin_user" "$admin_password" || fail
  jq -er '.access_token | "header = " + ("Authorization: Bearer " + . | @json)' "$work/token.json" > "$work/admin-curl.conf" || fail
}
identity_step=1
admin_token
realm_path=$(printf '%s' "$realm" | jq -sRr @uri)
kc() {
  method=$1; resource=$2; shift 2
  case "$method" in get) method=GET;; create) method=POST;; update) method=PUT;; delete) method=DELETE;; *) fail;; esac
  query=''; body=''
  while [ "$#" -gt 0 ]; do
    case "$1" in
      -r) shift 2;;
      -q) key=${2%%=*}; value=${2#*=}; encoded=$(printf '%s' "$value" | jq -sRr @uri); query="$query&$key=$encoded"; shift 2;;
      -f) body=$2; shift 2;;
      -n) shift;;
      *) fail;;
    esac
  done
  set -- --config "$work/admin-curl.conf" --request "$method" --output "$work/response" --write-out '%{http_code}'
  if [ -n "$body" ]; then set -- "$@" --header 'Content-Type: application/json' --data-binary "@$body"; fi
  auth_retry=0
  while :; do
    transport "$@" "$url/admin/realms/$realm_path/$resource?${query#&}"
    [ "$http_status" -eq 401 ] && [ "$auth_retry" -eq 0 ] || break
    admin_token
    auth_retry=1
  done
  case "$http_status" in 2??) ;; *) fail;; esac
  cat "$work/response"
}
get_exact() {
  resource=$1; field=$2; name=$3
  if [ "$resource" = groups ]; then
    kc get groups -r "$realm" -q search="$name" -q exact=true > "$work/matches.json" || fail
  else
    kc get "$resource" -r "$realm" -q "$field=$name" -q exact=true > "$work/matches.json" || fail
  fi
  jq --arg field "$field" --arg value "$name" '[.[] | select(.[$field] == $value)]' "$work/matches.json" > "$work/exact.json" || fail
  jq -r '.[0].id // empty' "$work/exact.json"
}
group() {
  identity_step=10
  name=$1
  id=$(get_exact groups name "$name")
  if [ -n "$id" ]; then
    identity_step=11
    kc get "groups/$id" -r "$realm" > "$work/group.json" || fail
  else
    identity_step=12
    jq -n --arg name "$name" '{name:$name}' > "$work/group.json"
    kc create groups -r "$realm" -f "$work/group.json" >/dev/null || fail
    changed=true
    id=$(get_exact groups name "$name")
    [ -n "$id" ] || fail
    kc get "groups/$id" -r "$realm" > "$work/group.json" || fail
  fi
}

principal_roles() {
  identity_step=13
  principal_resource=$1
  principal_id=$id
  jq -e 'def name: type == "string" and length > 0 and (test("[\u0000-\u001f]") | not);
    type == "object" and (.realm_roles | type == "array" and all(.[]; name)) and
    (.client_roles | type == "object" and all(to_entries[]; (.key | name) and (.value | type == "array" and all(.[]; name))))' \
    "$work/role-file.json" >/dev/null || fail
  jq -r '.client_roles | to_entries[] | select(.value | length > 0) | .key' "$work/role-file.json" > "$work/role-clients"
  reconcile_roles roles "$principal_resource/$principal_id/role-mappings/realm" realm
  while IFS= read -r client_id; do
    client_uuid=$(get_exact clients clientId "$client_id")
    [ -n "$client_uuid" ] || fail
    kc get "clients/$client_uuid" -r "$realm" > "$work/role-client.json" || fail
    reconcile_roles "clients/$client_uuid/roles" "$principal_resource/$principal_id/role-mappings/clients/$client_uuid" client
  done < "$work/role-clients"
}

reconcile_roles() {
  identity_step=14
  role_resource=$1; mapping_resource=$2; role_kind=$3
  if [ "$role_kind" = realm ]; then
    jq '.realm_roles | unique' "$work/role-file.json" > "$work/required-roles.json"
  else
    jq --arg client "$client_id" '.client_roles[$client] | unique' "$work/role-file.json" > "$work/required-roles.json"
  fi
  [ "$(jq length "$work/required-roles.json")" -gt 0 ] || return 0
  kc get "$role_resource" -r "$realm" > "$work/available-roles.json" || fail
  jq -r --slurpfile available "$work/available-roles.json" '. - [$available[0][].name] | .[]' \
    "$work/required-roles.json" > "$work/missing-role-names" || fail
  if [ -s "$work/missing-role-names" ]; then
    while IFS= read -r role_name; do
      jq -n --arg name "$role_name" \
        '{name:$name}' > "$work/new-role.json"
      kc create "$role_resource" -r "$realm" -f "$work/new-role.json" >/dev/null || fail
      changed=true
    done < "$work/missing-role-names"
    kc get "$role_resource" -r "$realm" > "$work/available-roles.json" || fail
  fi
  jq --slurpfile names "$work/required-roles.json" \
    '[.[] | select(.name as $name | $names[0] | index($name))]' \
    "$work/available-roles.json" > "$work/selected-roles.json" || fail
  [ "$(jq length "$work/selected-roles.json")" = "$(jq length "$work/required-roles.json")" ] || fail
  kc get "$mapping_resource" -r "$realm" > "$work/role-mappings.json" || fail
  jq --slurpfile current "$work/role-mappings.json" \
    '[.[] | select(.id as $id | [$current[0][].id] | index($id) | not)]' \
    "$work/selected-roles.json" > "$work/missing-mappings.json" || fail
  if [ "$(jq length "$work/missing-mappings.json")" -gt 0 ]; then
    kc create "$mapping_resource" -r "$realm" -f "$work/missing-mappings.json" >/dev/null || fail
    changed=true
    kc get "$mapping_resource" -r "$realm" > "$work/role-mappings.json" || fail
  fi
  jq -e --slurpfile required "$work/selected-roles.json" \
    '([ $required[0][].id ] - [ .[].id ]) | length == 0' "$work/role-mappings.json" >/dev/null || fail
}

dispatch_invocation() {
printf '%s' "$payload" > "$work/payload.json"
case "$operation" in
  groups|group-roles)
    jq 'if type == "array" then {groups: .} else . end' "$work/payload.json" > "$work/groups-payload.json" || fail
    jq -e '.groups | type == "array" and all(.[]; (if type == "object" then .name else . end) |
      type == "string" and length > 0 and (test("[\r\n]") | not))' "$work/groups-payload.json" >/dev/null || fail
    jq -c '.groups[] | if type == "string" then {name:.,roles_file:{realm_roles:[],client_roles:{}}} else . end' \
      "$work/groups-payload.json" > "$work/groups"
    while IFS= read -r group_json; do
      printf '%s' "$group_json" > "$work/group-input.json"
      name=$(jq -r '.name' "$work/group-input.json")
      group "$name"
      if [ "$operation" = group-roles ]; then
        jq '.roles_file' "$work/group-input.json" > "$work/role-file.json"
        principal_roles groups
      fi
    done < "$work/groups"
    ;;
  client)
    identity_step=20
    case "$endpoint" in https://*|http://*) ;; *) fail;; esac
    case "$proxy" in https://*) ;; *) fail;; esac
    jq --arg id "$instance" --arg endpoint "$endpoint" --arg proxy "$proxy" '
      {protocol:"openid-connect",enabled:true,standardFlowEnabled:true,
       directAccessGrantsEnabled:false,publicClient:true,serviceAccountsEnabled:false,
       rootUrl:($proxy+"/"+$id+"/"),baseUrl:($proxy+"/"+$id+"/"),webOrigins:[$proxy]} + . |
      .clientId=$id | .name=$id | .description=$endpoint |
      .redirectUris=(.redirectUris // [($proxy+"/"+$id+"/*")]) | del(.id,.secret)' "$work/payload.json" > "$work/client-model.json"
    jq 'del(.clientRoles,.authorizationSettings)' "$work/client-model.json" > "$work/client.json"
    model_matches='def matches($a;$d):
      if ($d|type)=="object" then ($a|type)=="object" and
        all($d|to_entries[]|select(.key!="id" and .key!="_id"); matches($a[.key];.value))
      elif ($d|type)=="array" then ($a|type)=="array" and ($a|length)==($d|length) and
        all($d[]; . as $v | any($a[]; matches(.;$v)))
      elif ($d|type)=="string" and ($a|type)=="string" and ($d|test("^[\\[{]")) then
        try matches(($a|fromjson);($d|fromjson)) catch ($a==$d)
      else $a==$d end;
      matches(.;$desired[0])'
    if [ "$(jq -r '.publicClient' "$work/client.json")" = false ] && [ -s "$client_secret" ]; then
      jq --rawfile secret "$client_secret" '.secret=$secret' "$work/client.json" > "$work/next.json"
      mv "$work/next.json" "$work/client.json"
    fi
    new_authorization=false
    id=$(get_exact clients clientId "$instance")
    if [ -z "$id" ]; then
      new_authorization=$(jq -r '.authorizationServicesEnabled // false' "$work/client.json")
      kc create clients -r "$realm" -f "$work/client.json" >/dev/null || fail
      changed=true
    else
      kc get "clients/$id" -r "$realm" > "$work/current.json" || fail
      if [ "$(jq -r '.authorizationServicesEnabled // false' "$work/client.json")" = true ] &&
        [ "$(jq -r '.authorizationServicesEnabled // false' "$work/current.json")" = false ]; then
        new_authorization=true
      fi
      jq --slurpfile current "$work/current.json" '.attributes=($current[0].attributes + .attributes)' "$work/client.json" > "$work/next.json"
      mv "$work/next.json" "$work/client.json"
      # The secret endpoint is private and never a script output.
      if [ "$(jq -r '.publicClient' "$work/client.json")" = false ] && [ -s "$client_secret" ]; then
        kc get "clients/$id/client-secret" -r "$realm" > "$work/secret.json" || fail
        jq --slurpfile secret "$work/secret.json" '.secret=$secret[0].value' "$work/current.json" > "$work/next.json"
        mv "$work/next.json" "$work/current.json"
      fi
      if ! jq -e --slurpfile desired "$work/client.json" "$model_matches" "$work/current.json" >/dev/null; then
        kc update "clients/$id" -r "$realm" -f "$work/client.json" >/dev/null || fail
        changed=true
      fi
    fi
    id=$(get_exact clients clientId "$instance")
    [ -n "$id" ] || fail
    identity_step=22
    for scope_kind in default optional; do
      case "$scope_kind" in default) scope_field=defaultClientScopes;; optional) scope_field=optionalClientScopes;; esac
      if jq -e --arg field "$scope_field" 'has($field)' "$work/client-model.json" >/dev/null; then
        jq --arg field "$scope_field" '.[$field]' "$work/client-model.json" > "$work/desired-scopes.json"
        kc get "clients/$id/$scope_kind-client-scopes" -r "$realm" > "$work/current-scopes.json" || fail
        jq -r --slurpfile desired "$work/desired-scopes.json" '.[]|select(.name as $name|$desired[0]|index($name)|not)|.id' \
          "$work/current-scopes.json" > "$work/remove-scopes"
        while IFS= read -r scope_id; do
          kc delete "clients/$id/$scope_kind-client-scopes/$scope_id" -r "$realm" >/dev/null || fail
          changed=true
        done < "$work/remove-scopes"
        kc get client-scopes -r "$realm" > "$work/realm-scopes.json" || fail
        jq -r --slurpfile current "$work/current-scopes.json" '.[]|select(. as $name|[$current[0][].name]|index($name)|not)' \
          "$work/desired-scopes.json" > "$work/add-scopes"
        while IFS= read -r scope_name; do
          scope_id=$(jq -r --arg name "$scope_name" '.[]|select(.name==$name)|.id' "$work/realm-scopes.json")
          [ -n "$scope_id" ] || fail
          kc update "clients/$id/$scope_kind-client-scopes/$scope_id" -r "$realm" >/dev/null || fail
          changed=true
        done < "$work/add-scopes"
      fi
    done
    # Client roles must exist before authorization policies resolve their named references.
    jq -c '.clientRoles[]?' "$work/client-model.json" > "$work/client-roles"
    while IFS= read -r role; do
      printf '%s' "$role" > "$work/client-role.json"
      role_name=$(jq -r .name "$work/client-role.json")
      kc get "clients/$id/roles" -r "$realm" -q briefRepresentation=false > "$work/current-roles.json" || fail
      jq --arg name "$role_name" '.[] | select(.name==$name)' "$work/current-roles.json" > "$work/current-role.json"
      if [ ! -s "$work/current-role.json" ]; then
        kc create "clients/$id/roles" -r "$realm" -f "$work/client-role.json" >/dev/null || fail
        changed=true
      elif ! jq -e --slurpfile desired "$work/client-role.json" "$model_matches" "$work/current-role.json" >/dev/null; then
        role_path=$(printf '%s' "$role_name" | jq -sRr @uri)
        kc update "clients/$id/roles/$role_path" -r "$realm" -f "$work/client-role.json" >/dev/null || fail
        changed=true
      fi
    done < "$work/client-roles"
    if jq -e '.authorizationSettings != null' "$work/client-model.json" >/dev/null; then
      identity_step=21
      jq '.authorizationSettings' "$work/client-model.json" > "$work/authorization.json"
      # Only the defaults generated by this transition are removed; existing authored settings remain.
      if [ "$new_authorization" = true ]; then
        for kind in policy resource; do
          kc get "clients/$id/authz/resource-server/$kind" -r "$realm" > "$work/generated-defaults.json" || fail
          jq -r '.[]|select(.name=="Default Permission" or .name=="Default Policy" or .name=="Default Resource")|.id // ._id' \
            "$work/generated-defaults.json" > "$work/generated-default-ids"
          while IFS= read -r default_id; do
            kc delete "clients/$id/authz/resource-server/$kind/$default_id" -r "$realm" >/dev/null || fail
          done < "$work/generated-default-ids"
        done
      fi
      kc get "clients/$id/authz/resource-server/settings" -r "$realm" > "$work/current-authorization.json" || fail
      if ! jq -e --slurpfile desired "$work/authorization.json" "$model_matches" "$work/current-authorization.json" >/dev/null; then
        kc create "clients/$id/authz/resource-server/import" -r "$realm" -f "$work/authorization.json" >/dev/null || fail
        changed=true
      fi
      kc get "clients/$id/authz/resource-server/settings" -r "$realm" > "$work/current-authorization.json" || fail
      jq -e --slurpfile desired "$work/authorization.json" "$model_matches" "$work/current-authorization.json" >/dev/null || fail
    fi
    kc get "clients/$id" -r "$realm" > "$work/current.json" || fail
    # Secrets are checked independently of the normal client representation.
    jq 'del(.secret)' "$work/client.json" > "$work/check.json"
    jq -e --slurpfile desired "$work/check.json" "$model_matches" "$work/current.json" >/dev/null || fail
    if [ "$(jq -r '.publicClient' "$work/client.json")" = false ]; then
      kc get "clients/$id/client-secret" -r "$realm" > "$work/secret.json" || fail
      if ! jq -e '.value | type=="string" and length>0' "$work/secret.json" >/dev/null; then
        kc create "clients/$id/client-secret" -r "$realm" > "$work/secret.json" || fail
        changed=true
      fi
      if [ -s "$client_secret" ]; then
        jq -e --rawfile expected "$client_secret" '.value == $expected' "$work/secret.json" >/dev/null || fail
      fi
    fi
    ;;
  accounts)
    [ -s "$accounts" ] || fail
    jq -e '.accounts | type == "array"' "$accounts" >/dev/null || fail
    identity_step=30
    count=$(jq '.accounts | length' "$accounts")
    index=0
    while [ "$index" -lt "$count" ]; do
      jq --argjson index "$index" '.accounts[$index] as $a | $a + {password:.passwords[$a.id]}' "$accounts" > "$work/account.json"
      username=$(jq -r '.username' "$work/account.json")
      mode=$(jq -r '.mode' "$work/account.json")
      new_account=false
      id=$(get_exact users username "$username")
      if [ -n "$id" ]; then
        kc get "users/$id" -r "$realm" > "$work/user.json" || fail
      else
        [ "$mode" = managed ] || fail
        new_account=true
        jq '{username:.username,enabled:true}' "$work/account.json" > "$work/user.json"
        kc create users -r "$realm" -f "$work/user.json" >/dev/null || fail
        changed=true
        id=$(get_exact users username "$username")
        [ -n "$id" ] || fail
        kc get "users/$id" -r "$realm" > "$work/user.json" || fail
      fi
      # Set the initial password before the first login; probe existing accounts for idempotency.
      jq -jr .password "$work/account.json" > "$work/user-password"
      if [ "$new_account" = true ] || ! token "$realm" "$username" "$work/user-password"; then
        [ "$mode" = managed ] || fail
        jq '{type:"password",value:.password,temporary:false}' "$work/account.json" > "$work/credential.json"
        kc update "users/$id/reset-password" -r "$realm" -f "$work/credential.json" >/dev/null || fail
        changed=true
      fi
      token "$realm" "$username" "$work/user-password" || fail
      if [ "$mode" = managed ]; then
        jq -r '.parameters.groups[]? ' "$work/account.json" > "$work/groups"
        while IFS= read -r name; do
          group_id=$(get_exact groups name "$name"); [ -n "$group_id" ] || fail
          kc get "users/$id/groups" -r "$realm" > "$work/memberships.json" || fail
          if ! jq -e --arg id "$group_id" 'any(.[]; .id == $id)' "$work/memberships.json" >/dev/null; then
            kc update "users/$id/groups/$group_id" -r "$realm" -n >/dev/null || fail
            changed=true
          fi
          kc get "users/$id/groups" -r "$realm" > "$work/memberships.json" || fail
          jq -e --arg id "$group_id" 'any(.[]; .id == $id)' "$work/memberships.json" >/dev/null || fail
        done < "$work/groups"
        jq '.parameters as $p | ($p.roles_file // {realm_roles:[],client_roles:{}}) |
          .realm_roles = ((.realm_roles // []) + ($p.roles // []) | unique)' \
          "$work/account.json" > "$work/role-file.json" || fail
        principal_roles users
      fi
      index=$((index+1))
    done
    ;;
  *) fail;;
esac
}
while [ "$invocation_index" -lt "$invocation_count" ]; do
  if [ -n "$batch_file" ]; then load_batch_invocation; fi
  [ "$url" = "$batch_url" ] && [ "$realm" = "$batch_realm" ] && [ "$admin_user" = "$batch_admin" ] || fail
  dispatch_invocation
  invocation_index=$((invocation_index+1))
done
printf '{"status":"ok","changed":%s}\n' "$changed"
