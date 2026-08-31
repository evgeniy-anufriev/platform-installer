#!/usr/bin/env bash
# SERVICE-01D centralized acceptance runner. Run on the selected Execution Node.
set -Eeuo pipefail

root="${PLATFORM_QA_PROJECT_ROOT:?set PLATFORM_QA_PROJECT_ROOT}"
inventory="${PLATFORM_QA_INVENTORY:?set PLATFORM_QA_INVENTORY}"
ssh_key="${PLATFORM_QA_SSH_KEY:?set PLATFORM_QA_SSH_KEY}"
qa_dir="${PLATFORM_QA_LOG_DIR:-$root/.runtime/qa/kafka/service-01d}"
apply="$root/services/kafka/playbooks/apply.yml"
verify="$root/services/kafka/playbooks/verify.yml"
mkdir -p "$qa_dir"

stage="preflight"
completed=""
started_at="$(date -u +%FT%TZ)"
status_file="$qa_dir/status.json"

write_status() {
  python3 - "$status_file" "$stage" "$1" "$started_at" "$completed" "${2:-}" <<'PY'
import json, pathlib, sys
path, stage, status, started, completed, failed = sys.argv[1:]
pathlib.Path(path).write_text(json.dumps({"scenario":"SERVICE-01D","stage":stage,"status":status,
 "startedAt":started,"completedStages":[x for x in completed.split(',') if x],
 "failedStage":failed or None,"logDirectory":str(pathlib.Path(path).parent)}, indent=2)+"\n")
PY
}

run_stage() {
  stage="$1"; shift
  local log="$qa_dir/${stage}.log"
  write_status RUNNING
  { printf 'COMMAND:'; printf ' %q' "$@"; printf '\n'; "$@"; } >"$log" 2>&1 || {
    write_status FAILED "$stage"
    exit 1
  }
  completed="${completed:+$completed,}$stage"
  write_status RUNNING
}

expect_failure() {
  stage="$1"; shift
  local log="$qa_dir/${stage}.log"
  write_status RUNNING
  { printf 'COMMAND:'; printf ' %q' "$@"; printf '\n'; "$@"; } >"$log" 2>&1 && {
    write_status FAILED "$stage"; exit 1;
  }
  completed="${completed:+$completed,}$stage"
  write_status RUNNING
}

ansible_playbook=(ansible-playbook -i "$inventory")
ansible_common=(-e "ansible_ssh_private_key_file=$ssh_key")
trap 'write_status FAILED "$stage"' ERR

run_stage syntax-apply ansible-playbook --syntax-check -i "$inventory" "$apply"
run_stage syntax-verify ansible-playbook --syntax-check -i "$inventory" "$verify"
run_stage apply "${ansible_playbook[@]}" "$apply" "${ansible_common[@]}"
run_stage verify "${ansible_playbook[@]}" "$verify" "${ansible_common[@]}"
run_stage repeat-apply "${ansible_playbook[@]}" "$apply" "${ansible_common[@]}"
grep -Eq '^node[123].*changed=0.*failed=0' "$qa_dir/repeat-apply.log" || { stage=repeat-apply; write_status FAILED "$stage"; exit 1; }
run_stage broker-stop ansible node3 -i "$inventory" -b -m ansible.builtin.systemd -a 'name=kafka@kafka-broker-3 state=stopped' "${ansible_common[@]}"
expect_failure broker-degraded-verify "${ansible_playbook[@]}" "$verify" "${ansible_common[@]}"
run_stage broker-recovery "${ansible_playbook[@]}" "$apply" --limit node3 "${ansible_common[@]}"
run_stage broker-recovered-verify "${ansible_playbook[@]}" "$verify" "${ansible_common[@]}"
run_stage controller-stop ansible node3 -i "$inventory" -b -m ansible.builtin.systemd -a 'name=kafka@kafka-controller-3 state=stopped' "${ansible_common[@]}"
expect_failure controller-degraded-verify "${ansible_playbook[@]}" "$verify" "${ansible_common[@]}"
run_stage controller-recovery "${ansible_playbook[@]}" "$apply" --limit node3 "${ansible_common[@]}"
run_stage final-verify "${ansible_playbook[@]}" "$verify" "${ansible_common[@]}"
stage=complete; write_status PASS
