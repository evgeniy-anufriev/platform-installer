#!/usr/bin/env python3
"""Fixed Execution Node controller.  It never accepts a command or playbook."""
from __future__ import print_function

import argparse
import json
import os
import signal
import subprocess
import sys
import time

from execution_lifecycle import Journal, LifecycleError, digest, retain


SERVICE_TYPES = frozenset(("kafka", "keepalived", "postgresql", "bind", "haproxy", "dns-client"))


def _safe_service(value):
    return isinstance(value, str) and value in SERVICE_TYPES


def _command(release, journal, operation):
    kind = operation.get("operation")
    if kind == "PKI_APPLY":
        return ["ansible-playbook", "-i", os.path.join(journal.directory, "project", "inventory"), os.path.join(release, "ansible-core", "playbooks", "pki-apply.yml")]
    if kind in ("SERVICE_APPLY", "SERVICE_VERIFY") and _safe_service(operation.get("serviceType")):
        action = "apply" if kind == "SERVICE_APPLY" else "verify"
        projection = os.path.join(journal.directory, "runtime-projection.json")
        if not os.path.isfile(projection) or os.path.islink(projection):
            raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_MISSING")
        return ["ansible-playbook", "-i", os.path.join(journal.directory, "project", "inventory"), os.path.join(release, "services", operation["serviceType"], "playbooks", action + ".yml"), "-e", "@" + projection]
    if kind == "CORE_DELAY" and operation.get("operationId") == "core:delay":
        # A Core-owned, bounded safe fixture used only to prove detached unit
        # and process-group semantics; it is not supplied by a client.
        return [sys.executable, "-c", "import time; time.sleep(8)"]
    raise LifecycleError("EXECUTION_OPERATION_UNKNOWN")


def _environment(release):
    collections = [os.path.join(release, "ansible-core", "collections")]
    service_root = os.path.join(release, "services")
    if os.path.isdir(service_root):
        collections.extend(os.path.join(service_root, name, "ansible_collections") for name in sorted(os.listdir(service_root)) if os.path.isdir(os.path.join(service_root, name, "ansible_collections")))
    return dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(collections))


def _dispatch(release, journal, manifest, stopped):
    operations = manifest.get("operations")
    if not isinstance(operations, list) or not operations:
        raise LifecycleError("EXECUTION_MANIFEST_NOT_EXECUTABLE")
    identifiers = set()
    commands = []
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("operationId"), str) or operation["operationId"] in identifiers:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        identifiers.add(operation["operationId"])
        commands.append((operation, _command(release, journal, operation)))
    for operation, command in commands:
        if stopped[0]:
            return "CANCELLED"
        journal.event("ACTION_STARTED", "RUNNING", "Trusted operation started", phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_environment(release))
        while process.poll() is None:
            if stopped[0]:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill()
                return "CANCELLED"
            time.sleep(0.1)
        if process.returncode:
            raise LifecycleError("EXECUTION_OPERATION_FAILED")
        journal.event("ACTION_COMPLETED", "SUCCESS", "Trusted operation completed", phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
    return "SUCCEEDED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runtime-release", required=True)
    parser.add_argument("--bundle-digest", required=True)
    args = parser.parse_args()
    journal = Journal(args.state_root, args.run_id)
    lock = journal.lock()
    try:
        metadata = journal.metadata()
        manifest_path = os.path.join(journal.directory, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as stream:
            manifest = json.load(stream)
        if metadata.get("manifestDigest") != digest(manifest):
            return journal.terminal("FAILED", "EXECUTION_MANIFEST_TAMPERED", "Private execution manifest digest does not match") and 2
        if manifest.get("projectIdentity") != metadata.get("projectIdentity") or manifest.get("planFingerprint") != metadata.get("planFingerprint") or manifest.get("runtimeRelease", {}).get("bundleDigest") != args.bundle_digest or metadata.get("runtimeRelease") != args.bundle_digest:
            return journal.terminal("FAILED", "EXECUTION_IDENTITY_MISMATCH", "Manifest identity does not match run ownership") and 2
        if not os.path.isdir(args.runtime_release) or os.path.islink(args.runtime_release):
            return journal.terminal("FAILED", "EXECUTION_RUNTIME_RELEASE_MISMATCH", "Immutable runtime release is unavailable") and 2
        journal.transition("RUNNING", "Fixed Core controller started")
    finally:
        os.close(lock)
    cancelled = [False]
    def stop(_signal, _frame):
        cancelled[0] = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    journal.event("RUN_STARTED", "RUNNING", "Execution controller is running", planFingerprint=metadata["planFingerprint"])
    if cancelled[0]:
        journal.terminal("CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        return 0
    try:
        terminal = _dispatch(args.runtime_release, journal, manifest, cancelled)
        if terminal == "CANCELLED":
            journal.terminal("CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        else:
            journal.terminal("SUCCEEDED", "", "Execution controller completed")
        retain(args.state_root)
        return 0
    except LifecycleError as error:
        journal.terminal("FAILED", str(error), "Trusted operation failed before completion")
        retain(args.state_root)
        return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, LifecycleError) as error:
        print("EXECUTION_CONTROLLER_FAILED: %s" % error, file=sys.stderr)
        raise SystemExit(2)
