#!/usr/bin/env python3
"""Fixed JSON protocol for the activated Execution Node runtime.

stdin and stdout are the protocol.  The only subprocesses are the fixed
systemd controller and fixed systemctl ownership checks below.
"""
from __future__ import print_function

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile

from execution_lifecycle import ACTIVE, Journal, LifecycleError, digest, recover, validate_ownership


OPERATIONS = ("GetCapabilities", "ValidateProject", "BuildDeploymentPlan", "StartExecution", "GetExecution", "GetEvents", "CancelExecution")


class CoreOperationError(LifecycleError):
    def __init__(self, code, diagnostic=None):
        super().__init__(code)
        self.code = code
        self.diagnostic = diagnostic if isinstance(diagnostic, dict) else None


def reply(payload):
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def unit_name(run_id):
    return "platform-installer-run-%s.service" % run_id


def active(unit, metadata):
    if not isinstance(metadata, dict) or metadata.get("unit") != unit:
        return False
    return subprocess.call(["systemctl", "is-active", "--quiet", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def owned(journal):
    """Verify the complete non-PID ownership tuple before querying/stopping."""
    return validate_ownership(journal)


def request():
    value = json.load(sys.stdin)
    if not isinstance(value, dict) or value.get("apiVersion") != "platform.installer/execution-runtime/v1alpha1":
        raise LifecycleError("EXECUTION_PROTOCOL_INVALID")
    if value.get("operation") not in OPERATIONS:
        raise LifecycleError("EXECUTION_OPERATION_UNSUPPORTED")
    return value


def start(value, state_root, runtime_release, controller, active_bundle_digest=""):
    run_id = value.get("runId")
    journal = Journal(state_root, run_id)
    manifest_path = os.path.join(journal.directory, "manifest.json")
    if not os.path.isfile(manifest_path) or os.path.islink(manifest_path):
        raise LifecycleError("EXECUTION_MANIFEST_MISSING")
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    expected = ("projectIdentity", "planFingerprint", "runtimeRelease")
    if any(manifest.get(key) != value.get(key) for key in expected):
        raise LifecycleError("EXECUTION_IDENTITY_MISMATCH")
    if manifest.get("runtimeRelease", {}).get("bundleDigest") != value.get("runtimeRelease", {}).get("bundleDigest"):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_MISMATCH")
    if active_bundle_digest and value.get("runtimeRelease", {}).get("bundleDigest") != active_bundle_digest:
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_MISMATCH")
    if not isinstance(manifest.get("operations"), list):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    metadata = {"runId": run_id, "projectIdentity": value["projectIdentity"], "planFingerprint": value["planFingerprint"], "manifestDigest": digest(manifest), "runtimeRelease": value["runtimeRelease"]["bundleDigest"], "unit": unit_name(run_id)}
    os.makedirs(state_root, mode=0o700, exist_ok=True)
    active_lock = os.open(os.path.join(state_root, ".active-runs.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(active_lock, fcntl.LOCK_EX)
    lock = journal.lock()
    try:
        if os.path.exists(journal.metadata_path):
            journal.initialize(metadata)
            owned(journal)
            return {"run": journal.status(), "idempotent": True}
        runs = os.path.join(state_root, "runs")
        for candidate in os.listdir(runs):
            if candidate == run_id: continue
            other = Journal(state_root, candidate)
            try:
                status, other_meta = other.status(), other.metadata()
                if status.get("state") in ACTIVE and other_meta.get("projectIdentity") == metadata["projectIdentity"]:
                    raise LifecycleError("ACTIVE_RUN_EXISTS:%s" % candidate)
            except FileNotFoundError:
                continue
        journal.initialize(metadata)
        journal.transition("STARTING", "Detached controller accepted")
        # The bundle intentionally stores content with deterministic bytes, not
        # host executable bits.  Interpreter and controller are both fixed by
        # this node-side protocol, never supplied by a client.
        subprocess.check_call(["systemd-run", "--unit=" + metadata["unit"], "--collect", "--property=KillMode=control-group", "--property=NoNewPrivileges=yes", sys.executable, controller, "--state-root", state_root, "--run-id", run_id, "--runtime-release", runtime_release, "--bundle-digest", metadata["runtimeRelease"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"run": journal.status(), "idempotent": False, "runtimeRelease": runtime_release}
    finally:
        os.close(lock)
        os.close(active_lock)


def core_operation(value, state_root, runtime_release, operation):
    """Run one fixed Core playbook against already trusted run staging."""
    journal = Journal(state_root, value["runId"])
    project = os.path.join(journal.directory, "project")
    if not os.path.isdir(project) or os.path.islink(project):
        raise LifecycleError("EXECUTION_PROJECT_STAGING_MISSING")
    release = os.path.realpath(runtime_release)
    if not os.path.isdir(release) or os.path.islink(runtime_release):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    if operation == "ValidateProject":
        playbook, inventory = "validate.yml", os.path.join(project, "inventory", "hosts.yml")
        extra = {"platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_validation_artifact": os.path.join(journal.directory, "validation.json")}
    else:
        # Core remains target-free (the playbook runs on localhost), but it must
        # load the staged project inventory so snapshot receives its canonical
        # desired state, groups and host variables.
        playbook, inventory = "deployment-plan-machine.yml", os.path.join(project, "inventory", "hosts.yml")
        extra = {"platform_project_root": project, "platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_service_catalog_path": os.path.join(release, "catalog", "service-catalog.yml"), "platform_execution_runtime_release": value["runtimeRelease"]}
    diagnostic_path = os.path.join(journal.directory, "core-diagnostic.json")
    descriptor, vars_path = tempfile.mkstemp(prefix=".execution-vars-", dir=journal.directory)
    try:
        os.write(descriptor, json.dumps(extra, ensure_ascii=True, sort_keys=True).encode("utf-8")); os.close(descriptor)
        os.chmod(vars_path, 0o600)
        environment = dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=os.path.join(release, "ansible-core", "collections"), ANSIBLE_CALLBACKS_ENABLED="platform.core.deployment_plan_json", PLATFORM_DEPLOYMENT_PLAN_OUTPUT=os.path.join(journal.directory, "deployment-plan.json"), PLATFORM_EXECUTION_MANIFEST_OUTPUT=os.path.join(journal.directory, "manifest.json"), PLATFORM_CORE_DIAGNOSTIC_OUTPUT=diagnostic_path)
        command = ["ansible-playbook", "-i", inventory, os.path.join(release, "ansible-core", "playbooks", playbook), "-e", "@" + vars_path]
        completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
        if completed.returncode:
            diagnostic = None
            if os.path.isfile(diagnostic_path) and not os.path.islink(diagnostic_path):
                with open(diagnostic_path, "r", encoding="utf-8") as stream:
                    diagnostic = json.load(stream)
            code = diagnostic.get("errorCode") if isinstance(diagnostic, dict) else None
            raise CoreOperationError(code or "CORE_OPERATION_FAILED", diagnostic)
    finally:
        if os.path.exists(vars_path): os.unlink(vars_path)
    if operation == "BuildDeploymentPlan":
        with open(os.path.join(journal.directory, "deployment-plan.json"), "r", encoding="utf-8") as stream:
            plan = json.load(stream)
        if plan.get("status") == "BLOCKED":
            return {"deploymentPlan": plan, "executionManifestDigest": None}
        if plan.get("status") != "EXECUTABLE" or not os.path.isfile(os.path.join(journal.directory, "manifest.json")):
            raise LifecycleError("EXECUTION_MANIFEST_MISSING")
        with open(os.path.join(journal.directory, "manifest.json"), "r", encoding="utf-8") as stream:
            return {"deploymentPlan": plan, "executionManifestDigest": digest(json.load(stream))}
    return {"validation": "PASS"}


def get(value, state_root):
    journal = Journal(state_root, value["runId"])
    metadata = owned(journal)
    recover(state_root, active)
    result = {"run": journal.status(), "metadata": metadata}
    if os.path.exists(journal.result_path):
        with open(journal.result_path, "r", encoding="utf-8") as stream:
            result["result"] = json.load(stream)
    return result


def events(value, state_root):
    journal = Journal(state_root, value["runId"])
    owned(journal)
    after = value.get("afterSequence", 0)
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise LifecycleError("EXECUTION_EVENTS_INPUT_INVALID")
    limit = value.get("limit")
    if limit is None:
        selected = journal.events(after)
        return {"run": journal.status(), "events": selected, "nextSequence": selected[-1]["sequence"] if selected else after, "hasMore": False}
    page = journal.event_page(after, limit)
    page["run"] = journal.status()
    return page


def cancel(value, state_root):
    journal = Journal(state_root, value["runId"])
    lock = journal.lock()
    try:
        metadata, status = owned(journal), journal.status()
        if status.get("state") not in ACTIVE:
            return {"run": status, "idempotent": True}
        if not active(metadata.get("unit"), metadata):
            journal.terminal("INTERRUPTED", "CONTROLLER_INTERRUPTED", "Owned controller is no longer active")
            return {"run": journal.status(), "idempotent": True}
        # Commit cancellation before asking systemd to terminate the whole
        # owned cgroup.  The controller can then never race a child SIGTERM
        # into a contradictory FAILED terminal result.
        journal.terminal("CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        subprocess.check_call(["systemctl", "stop", metadata["unit"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"run": journal.status(), "idempotent": False}
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", default="/var/lib/platform-installer/execution")
    parser.add_argument("--runtime-release", required=True)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--bundle-digest", default="")
    args = parser.parse_args()
    value = request()
    operation = value["operation"]
    if operation == "GetCapabilities": return reply({"supportedOperations": list(OPERATIONS)})
    if operation in ("ValidateProject", "BuildDeploymentPlan"): return reply(core_operation(value, args.state_root, args.runtime_release, operation))
    if operation == "StartExecution": return reply(start(value, args.state_root, args.runtime_release, args.controller, args.bundle_digest))
    if operation == "GetExecution": return reply(get(value, args.state_root))
    if operation == "GetEvents": return reply(events(value, args.state_root))
    if operation == "CancelExecution": return reply(cancel(value, args.state_root))
    raise LifecycleError("EXECUTION_OPERATION_NOT_IMPLEMENTED")


if __name__ == "__main__":
    try: main()
    except CoreOperationError as error:
        payload = {"apiVersion": "platform.installer/execution-runtime/v1alpha1", "status": "FAILED", "error": error.code}
        if error.diagnostic:
            payload["diagnostic"] = error.diagnostic
        reply(payload)
        raise SystemExit(2)
    except (OSError, ValueError, LifecycleError, subprocess.CalledProcessError) as error:
        reply({"apiVersion": "platform.installer/execution-runtime/v1alpha1", "status": "FAILED", "error": str(error).split("\n", 1)[0][:256]})
        raise SystemExit(2)
