#!/usr/bin/env python3
"""Fixed JSON protocol for the activated Execution Node runtime.

stdin and stdout are the protocol.  The only subprocesses are the fixed
systemd controller and fixed systemctl ownership checks below.
"""
from __future__ import print_function

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
import yaml

from execution_lifecycle import ACTIVE, Journal, LifecycleError, digest, recover, validate_ownership
import execution_secret_lease
import execution_target_trust
import execution_image_preparation as image_preparation
import infrastructure_verification as infra


OPERATIONS = ("GetCapabilities", "ValidateProject", "BuildProjectSnapshot", "BuildServiceConfigurationPreview", "BuildRuntimeSecretDescriptors", "BuildDeploymentPlan", "StartExecution", "GetExecution", "GetEvents", "CancelExecution", "PutRuntimeSecretLease")
DEPLOYMENT_PLAN_REQUEST_VERSION = "platform.installer/execution-runtime/v1alpha2"
APPLICATION_PLAN_REQUEST_VERSION = 'platform.installer/execution-runtime/v1alpha3'
B0_PLAN_REQUEST_VERSION = 'platform.installer/execution-runtime/v1alpha4'
SKIP_PLAN_REQUEST_VERSION = 'platform.installer/execution-runtime/v1alpha5'
MAX_DEPLOYMENT_ORDER = 256
SNAPSHOT_REQUEST_VERSION = "platform.installer/project-snapshot-request/v1alpha1"
SNAPSHOT_OWNER_FILE = ".snapshot-owner.json"
MAX_CANDIDATE_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_CANDIDATE_FILES = 4096
MAX_CANDIDATE_FILE_BYTES = 4 * 1024 * 1024
MAX_CANDIDATE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_CANDIDATE_PATH_BYTES = 512
APPROVED_CANDIDATE_ANSIBLE_CONFIG = (
    b"# Managed by Platform Installer.\n"
    b"# This is standard Ansible configuration; formatting may be normalized.\n"
    b"[defaults]\n"
    b"inventory = ./inventory/hosts.yml\n"
    b"retry_files_enabled = False\n"
    b"host_key_checking = True\n"
    b"interpreter_python = auto_silent\n"
    b"hash_behaviour = merge\n"
)


class CoreOperationError(LifecycleError):
    def __init__(self, code, diagnostic=None):
        super().__init__(code)
        self.code = code
        self.diagnostic = diagnostic if isinstance(diagnostic, dict) else None


def reply(payload):
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def runtime_evidence(args):
    """Return only immutable identity read from the active runtime release."""
    try:
        with open(os.path.join(args.runtime_release, "manifest.yaml"), "r", encoding="utf-8") as stream:
            manifest = yaml.safe_load(stream)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    if not isinstance(manifest, dict):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    core_version = manifest.get("coreVersion")
    catalog_digest = manifest.get("catalogDigest")
    planning_protocol = manifest.get("bootstrapProtocol")
    if not isinstance(core_version, str) or not core_version or len(core_version) > 256 or not isinstance(catalog_digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", catalog_digest) is None or not isinstance(planning_protocol, str) or not planning_protocol or len(planning_protocol) > 256 or re.fullmatch(r"sha256:[0-9a-f]{64}", args.bundle_digest or "") is None:
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    return {"bundleDigest": args.bundle_digest, "coreVersion": core_version, "catalogDigest": catalog_digest, "protocol": planning_protocol}


def unit_name(run_id):
    return "platform-installer-run-%s.service" % run_id


def active(unit, metadata):
    if not isinstance(metadata, dict) or metadata.get("unit") != unit:
        return False
    try:
        result = subprocess.run(["systemctl", "show", "--property=ActiveState", "--value", unit],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    except OSError:
        raise LifecycleError("EXECUTION_UNIT_STATUS_UNAVAILABLE")
    if result.returncode != 0:
        raise LifecycleError("EXECUTION_UNIT_STATUS_UNAVAILABLE")
    state = result.stdout.strip()
    if state in ("active", "activating", "deactivating", "reloading"):
        return True
    if state in ("inactive", "failed"):
        return False
    raise LifecycleError("EXECUTION_UNIT_STATUS_UNAVAILABLE")


def owned(journal):
    """Verify the complete non-PID ownership tuple before querying/stopping."""
    return validate_ownership(journal)


def request():
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise LifecycleError("EXECUTION_PROTOCOL_INVALID")
            value[key] = item
        return value
    def reject_constant(_value):
        raise LifecycleError("EXECUTION_PROTOCOL_INVALID")
    value = json.load(sys.stdin, object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)
    if isinstance(value, dict) and value.get("apiVersion") == "platform.installer/execution-start/v1alpha2" and value.get("kind") == "StartExecutionRequest":
        return value
    if isinstance(value, dict) and value.get("apiVersion") in ("platform.installer/runtime-secret-lease/v1alpha1", "platform.installer/runtime-secret-lease/v1alpha2") and value.get("kind") == "PutRuntimeSecretLeaseRequest":
        return value
    if not isinstance(value, dict) or value.get("apiVersion") not in ("platform.installer/execution-runtime/v1alpha1", DEPLOYMENT_PLAN_REQUEST_VERSION, APPLICATION_PLAN_REQUEST_VERSION, B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION, image_preparation.REQUEST_VERSION):
        raise LifecycleError("EXECUTION_PROTOCOL_INVALID")
    if value.get("operation") not in OPERATIONS + ('PrepareApplicationImages',):
        raise LifecycleError("EXECUTION_OPERATION_UNSUPPORTED")
    if value.get('operation') == 'PrepareApplicationImages':
        if value.get('apiVersion') != image_preparation.REQUEST_VERSION:
            raise LifecycleError('APPLICATION_IMAGE_RUNTIME_UNSUPPORTED')
        fields = {'apiVersion', 'operation', 'runId', 'runtimeRelease', 'phase'}
        if value.get('phase') == 'DESCRIBE':
            fields.update(('executionMode', 'deploymentOrder', 'skipInfrastructureVerify'))
        elif value.get('phase') == 'PREPARE':
            fields.add('inputsDigest')
            if 'preparationLease' in value:
                fields.add('preparationLease')
        else:
            raise LifecycleError('APPLICATION_IMAGE_REQUEST_INVALID')
        if set(value) != fields:
            raise LifecycleError('APPLICATION_IMAGE_REQUEST_INVALID')
    if value.get("operation") == "BuildDeploymentPlan":
        if value.get("apiVersion") not in (DEPLOYMENT_PLAN_REQUEST_VERSION, APPLICATION_PLAN_REQUEST_VERSION, B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION, image_preparation.REQUEST_VERSION):
            raise LifecycleError("DEPLOYMENT_ORDER_REQUEST_VERSION_REQUIRED")
        expected = {"apiVersion", "operation", "runId", "project", "runtimeRelease", "deploymentOrder"}
        if value['apiVersion'] in (APPLICATION_PLAN_REQUEST_VERSION, B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION, image_preparation.REQUEST_VERSION):
            expected.add('applicationVaultSources')
            sources = value.get('applicationVaultSources')
            if (not isinstance(sources, dict) or len(sources) > 16 or
                    any(not isinstance(key, str) or re.fullmatch(r'[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*', key) is None or
                        kind not in ('RUNTIME_INPUT', 'CURRENT_RUN_BOOTSTRAP') for key, kind in sources.items())):
                raise LifecycleError('APPLICATION_VAULT_SOURCE_INVALID')
        if value['apiVersion'] in (B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION, image_preparation.REQUEST_VERSION):
            expected.add('executionMode')
            if value.get('executionMode') not in infra.MODES:
                raise LifecycleError('EXECUTION_MODE_UNSUPPORTED')
        if value['apiVersion'] in (SKIP_PLAN_REQUEST_VERSION, image_preparation.REQUEST_VERSION):
            expected.add('skipInfrastructureVerify')
            if type(value.get('skipInfrastructureVerify')) is not bool or value['skipInfrastructureVerify'] and value['executionMode'] != 'APPLICATION_LIBRARIES_ONLY':
                raise LifecycleError('INFRA_VERIFY_SKIP_INVALID')
        if value['apiVersion'] == image_preparation.REQUEST_VERSION:
            expected.add('applicationImagePreparation')
            if not isinstance(value.get('applicationImagePreparation'), str) or re.fullmatch('sha256:[a-f0-9]{64}', value['applicationImagePreparation']) is None:
                raise LifecycleError('APPLICATION_IMAGE_PREPARATION_REQUIRED')
        order = value.get("deploymentOrder")
        if (set(value) != expected or not isinstance(order, list) or len(order) > MAX_DEPLOYMENT_ORDER or
                any(not isinstance(item, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", item) is None for item in order) or
                len(order) != len(set(order))):
            raise LifecycleError("DEPLOYMENT_ORDER_REQUEST_INVALID")
    return value


def _capabilities_v4(args):
    try:
        with open(os.path.join(args.runtime_release, "manifest.yaml"), "r", encoding="utf-8") as stream:
            manifest = yaml.safe_load(stream)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    required = ("bundleVersion", "bootstrapProtocol", "coreVersion", "catalogDigest", "schemaDigest")
    if not isinstance(manifest, dict) or any(not isinstance(manifest.get(key), str) or not manifest[key] for key in required) or not re.fullmatch(r"sha256:[0-9a-f]{64}", args.bundle_digest or ""):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    return {"apiVersion": "platform.installer/execution-capabilities/v1alpha6", "kind": "ExecutionCapabilities", "bootstrapProtocol": manifest["bootstrapProtocol"], "coreVersion": manifest["coreVersion"], "catalogDigest": manifest["catalogDigest"], "schemaDigest": manifest["schemaDigest"], "runtime": {"bundleVersion": manifest["bundleVersion"], "bundleDigest": args.bundle_digest}, "supportedOperations": list(OPERATIONS), "executionStart": {"protocol": "StartExecution/v1alpha2"}, "targetCredentialLease": {"protocol": execution_secret_lease.LEASE_PROTOCOL, "payloadVersions": [execution_secret_lease.TYPED_RUNTIME_SECRET_PAYLOAD_VERSION], "maxPayloadBytes": execution_secret_lease.MAX_PAYLOAD_BYTES, "requiredStartProtocol": "StartExecution/v1alpha2"}, "runtimeSecretDescriptors": {"protocol": "BuildRuntimeSecretDescriptors/v1alpha2", "maxDescriptors": 16, "maxHostsPerDescriptor": 256, "maxResponseBytes": 65536}, "serviceConfigurationPreview": {"protocol": "BuildServiceConfigurationPreview/v1alpha1", "maxResponseBytes": 1048576}, "deploymentPlanRequestVersions": [DEPLOYMENT_PLAN_REQUEST_VERSION], "projectSnapshotRequestVersions": [SNAPSHOT_REQUEST_VERSION]}


def _application_capabilities(args):
    result = _capabilities_v4(args)
    result['apiVersion'] = 'platform.installer/execution-capabilities/v1alpha7'
    result['deploymentPlanRequestVersions'] = [DEPLOYMENT_PLAN_REQUEST_VERSION, APPLICATION_PLAN_REQUEST_VERSION]
    result['runtimeSecretDescriptors']['protocol'] = 'BuildRuntimeSecretDescriptors/v1alpha3'
    result['runtimeSecretDescriptors'].pop('maxDescriptors', None)
    result['applicationExecution'] = {'manifestContract': 'platform.installer/execution-manifest/v1alpha2',
                                     'planContract': 'platform.installer/plan/v1alpha4',
                                     'requiredPlanRequestVersion': APPLICATION_PLAN_REQUEST_VERSION}
    return result


def _b0_capabilities(args, skip=False):
    result = _application_capabilities(args)
    result['apiVersion'] = 'platform.installer/execution-capabilities/v1alpha8'
    result['deploymentPlanRequestVersions'].append(B0_PLAN_REQUEST_VERSION)
    result['infrastructureVerification'] = dict(protocol='InfrastructureVerification/v1alpha1',
        executionModes=list(infra.MODES), requiredPlanRequestVersion=B0_PLAN_REQUEST_VERSION,
        manifestContract=infra.MANIFEST_VERSION, planContract=infra.PLAN_VERSION)
    if skip:
        result['apiVersion'] = 'platform.installer/execution-capabilities/v1alpha9'
        result['deploymentPlanRequestVersions'].append(SKIP_PLAN_REQUEST_VERSION)
        result['skipInfrastructureVerify'] = True
    return result


def _image_capabilities(args):
    result = _b0_capabilities(args, True)
    result['apiVersion'] = 'platform.installer/execution-capabilities/v1alpha10'
    result['supportedOperations'].append('PrepareApplicationImages')
    result['deploymentPlanRequestVersions'].append(image_preparation.REQUEST_VERSION)
    result['applicationImages'] = dict(protocol='PrepareApplicationImages/v1alpha1',
        leaseProtocol=image_preparation.LEASE_VERSION,
        planContract='platform.installer/plan/v1alpha7', manifestContract='platform.installer/execution-manifest/v1alpha5')
    result['runtimeSecretDescriptors']['protocol'] = 'BuildRuntimeSecretDescriptors/v1alpha4'
    return result


def _v2_start_request(value):
    required = {"apiVersion", "kind", "startAttemptId", "projectIdentity", "projectRevision", "planFingerprint", "executionManifestDigest", "runtimeRelease", "leaseId"}
    if not isinstance(value, dict) or set(value) not in (required, required - {"leaseId"}) or value.get("apiVersion") != "platform.installer/execution-start/v1alpha2" or value.get("kind") != "StartExecutionRequest":
        raise LifecycleError("START_REQUEST_INVALID")
    if re.fullmatch(r"[0-9a-f]{32}", value.get("startAttemptId", "")) is None or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", value.get("projectIdentity", "")) is None:
        raise LifecycleError("START_REQUEST_INVALID")
    for key in ("projectRevision", "planFingerprint", "executionManifestDigest"):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value.get(key, "")):
            raise LifecycleError("START_REQUEST_INVALID")
    release = value.get("runtimeRelease")
    if not isinstance(release, dict) or set(release) != {"bundleDigest", "coreVersion", "catalogDigest", "planningProtocol"} or not re.fullmatch(r"sha256:[0-9a-f]{64}", release.get("bundleDigest", "")) or not re.fullmatch(r"sha256:[0-9a-f]{64}", release.get("catalogDigest", "")):
        raise LifecycleError("START_REQUEST_INVALID")
    if any(not isinstance(release.get(key), str) or not release[key] or len(release[key]) > 256 for key in ("coreVersion", "planningProtocol")):
        raise LifecycleError("START_REQUEST_INVALID")
    if "leaseId" in value and not re.fullmatch(r"[0-9a-f]{32}", value["leaseId"]):
        raise LifecycleError("START_REQUEST_INVALID")
    return value


def _start_v2(value, state_root, runtime_release, controller, active_bundle_digest):
    value = _v2_start_request(value)
    attempt_binding = {"projectIdentity": value["projectIdentity"], "projectRevision": value["projectRevision"], "planFingerprint": value["planFingerprint"], "executionManifestDigest": value["executionManifestDigest"], "runtimeRelease": value["runtimeRelease"], "leaseId": value.get("leaseId")}
    prepared = execution_secret_lease.prepared_start(state_root, value["startAttemptId"], attempt_binding)
    if prepared is not None:
        _, published = execution_secret_lease.attempt(state_root, value["startAttemptId"], attempt_binding)
        if not published:
            _rollback_prepared_start(state_root, prepared)
            execution_secret_lease.rollback_prepared_start(state_root, value["startAttemptId"], attempt_binding)
    previous_run, known_attempt = execution_secret_lease.attempt(state_root, value["startAttemptId"], attempt_binding)
    if known_attempt:
        return {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionResponse", "status": "ALREADY_STARTED", "startAttemptId": value["startAttemptId"], "runId": previous_run}
    plan = execution_secret_lease.resolve_plan(state_root, value)
    staging_id = plan.get("stagingId")
    staging_dir = os.path.join(state_root, "runs", staging_id)
    manifest_path = os.path.join(staging_dir, "manifest.json")
    if not isinstance(staging_id, str) or not os.path.isfile(manifest_path) or os.path.islink(manifest_path): raise LifecycleError("EXECUTION_MANIFEST_MISSING")
    with open(manifest_path, "r", encoding="utf-8") as stream: manifest = json.load(stream)
    if digest(manifest) != value["executionManifestDigest"] or manifest.get("projectIdentity") != value["projectIdentity"] or manifest.get("planFingerprint") != value["planFingerprint"] or manifest.get("runtimeRelease") != value["runtimeRelease"]: raise LifecycleError("EXECUTION_IDENTITY_MISMATCH")
    from execution_controller import validate_application_manifest
    validate_application_manifest(manifest)
    if execution_target_trust.required(manifest):
        execution_target_trust.verify(state_root, staging_id, manifest)
    requirements = manifest.get("runtimeSecretRequirements", [])
    typed_requirements = manifest.get("runtimeSecretInputs", [])
    if not isinstance(requirements, list):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    execution_secret_lease._validate_typed_secret_requirements(typed_requirements)
    pki, service = [], []
    references, requirement_refs = set(), set()
    for requirement in requirements:
        reference = requirement.get("runtimeReference") if isinstance(requirement, dict) else None
        requirement_ref = requirement.get("requirementRef") if isinstance(requirement, dict) else None
        scoped_reference = (requirement.get('serviceDeployment'), reference) if isinstance(requirement, dict) else None
        if not isinstance(requirement, dict) or not isinstance(requirement.get("hosts"), list) or len(requirement["hosts"]) > 256 or not isinstance(reference, str) or not isinstance(requirement_ref, str) or (requirement.get('serviceDeployment') is not None and not isinstance(requirement.get('serviceDeployment'), str)) or scoped_reference in references or requirement_ref in requirement_refs:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        references.add(scoped_reference); requirement_refs.add(requirement_ref)
        if requirement.get("purpose") == "PKI_STORE_PASSWORD" and set(requirement) == {"requirementRef", "purpose", "hosts", "runtimeReference"} and requirement.get("requirementRef") == "pki-store-password" and requirement.get("runtimeReference") == "runtime:pki-store-password":
            pki.append(requirement)
        elif requirement.get("purpose") == "SERVICE_PASSWORD" and set(requirement) == {"requirementRef", "purpose", "hosts", "runtimeReference", "serviceDeployment"} and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", requirement.get("requirementRef", "")) and re.fullmatch(r"runtime:[a-z][a-z0-9-]{0,127}", requirement.get("runtimeReference", "")) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", requirement.get("serviceDeployment", "")):
            service.append(requirement)
        else:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    if len(pki) > 1:
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    app_inputs = [item for item in manifest.get('applicationSecretRequirements', []) if item['source'] == 'RUNTIME_INPUT']
    service.extend(app_inputs)
    if pki and not value.get("leaseId"):
        raise LifecycleError("PKI_STORE_PASSWORD_RUNTIME_SECRET_REQUIRED")
    if service and not value.get("leaseId"):
        raise LifecycleError("RUNTIME_SECRET_VALUES_REQUIRED")
    if value.get("leaseId"):
        if pki:
            execution_secret_lease.validate_staged_pki_store_password(
                state_root, value["leaseId"], allow_service_values=bool(service),
                allow_typed_inputs=bool(typed_requirements))
        else:
            execution_secret_lease.validate_staged_payload_without_pki_store_password(
                state_root, value["leaseId"], allow_typed_inputs=bool(typed_requirements),
                allow_service_values=bool(service))
        if service:
            execution_secret_lease.validate_staged_runtime_secret_values(state_root, value["leaseId"], service)
        provided = execution_secret_lease.validate_staged_runtime_secret_inputs(state_root, value["leaseId"], typed_requirements)
        app_tokens = {item['providerDeployment']: item for item in manifest.get('applicationSecretRequirements', [])
                      if item['purpose'] == 'APPLICATION_VAULT_ADMIN_TOKEN'}
        for item in provided:
            requirement = app_tokens.get(item['serviceDeployment'])
            if item['purpose'] == 'SERVICE_ADMIN_TOKEN' and requirement:
                if requirement['source'] == 'CURRENT_RUN_BOOTSTRAP':
                    raise LifecycleError('APPLICATION_VAULT_SOURCE_AMBIGUOUS')
                payload_path = os.path.join(execution_secret_lease._lease_dir(
                    execution_secret_lease._root(state_root), value['leaseId']), 'payload.json')
                payload = execution_secret_lease._read(payload_path)
                if item['value'] != payload['runtimeSecretValues'][requirement['requirementRef']]:
                    raise LifecycleError('APPLICATION_VAULT_SOURCE_AMBIGUOUS')
    # The node, not planning or the caller, creates the authoritative run id.
    run_id = "installer-" + os.urandom(16).hex()
    run_dir = os.path.join(state_root, "runs", run_id)
    if value.get("leaseId"):
        binding = {"requestId": None, "startAttemptId": value["startAttemptId"], "projectIdentity": value["projectIdentity"], "projectRevision": value["projectRevision"], "planFingerprint": value["planFingerprint"], "executionManifestDigest": value["executionManifestDigest"], "runtimeRelease": value["runtimeRelease"]}
        # requestId is intentionally not known to Start; compare the immutable
        # lease fields apart from that PUT-only idempotency key.
        record = execution_secret_lease._read(os.path.join(execution_secret_lease._lease_dir(execution_secret_lease._root(state_root), value["leaseId"]), "record.json"))
        stored = record.get("binding") if isinstance(record, dict) else None
        if not isinstance(stored, dict) or any(stored.get(key) != binding[key] for key in binding if key != "requestId"):
            raise LifecycleError("LEASE_BINDING_MISMATCH")
    else: stored = None
    committed = [False]
    def commit_binding(_metadata, _journal):
        execution_secret_lease.commit_start(state_root, value["startAttemptId"], attempt_binding, run_id, staging_id, value.get("leaseId"), stored)
        committed[0] = True
    try:
        os.replace(staging_dir, run_dir)
        # start() serializes active-run admission, persists the immutable
        # journal binding, then invokes this callback before controller launch.
        result = start({"runId": run_id, "projectIdentity": value["projectIdentity"], "planFingerprint": value["planFingerprint"], "runtimeRelease": value["runtimeRelease"]}, state_root, runtime_release, controller, active_bundle_digest, prelaunch=commit_binding)
    except Exception:
        if committed[0]:
            # From this point a durable node-owned run exists. Every ordinary
            # launch failure, not only CalledProcessError, becomes lifecycle
            # evidence for that same id; retry resolves the mapping.
            Journal(state_root, run_id).terminal("FAILED", "EXECUTION_CONTROLLER_START_FAILED", "Controller launch failed")
            result = {"idempotent": False}
        else:
            # No durable attempt/run association exists yet. Remove only
            # lifecycle files created by start(), retaining the already
            # validated private plan staging for an allowed retry.
            _rollback_uncommitted_start(run_dir)
            if os.path.isdir(run_dir) and not os.path.exists(staging_dir):
                os.replace(run_dir, staging_dir)
            raise
    status = "ALREADY_STARTED" if result.get("idempotent") else "STARTED"
    return {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionResponse", "status": status, "startAttemptId": value["startAttemptId"], "runId": run_id}


def _rollback_uncommitted_start(run_dir):
    """Remove only journal artifacts made before an uncommitted Start.

    The directory still contains the original verified staging manifest and
    project.  All removed names are fixed Journal-owned files; a symlink or an
    unexpected directory fails closed rather than deleting an unproven path.
    """
    names = ("metadata.json", "status.json", "events.jsonl", "result.json", ".lock", ".events.lock", "task-observability.json", ".task-observability.reported")
    for name in names:
        path = os.path.join(run_dir, name)
        if not os.path.lexists(path):
            continue
        details = os.lstat(path)
        if os.path.islink(path) or not os.path.isfile(path):
            raise LifecycleError("EXECUTION_START_ROLLBACK_UNSAFE")
        os.unlink(path)


def _rollback_prepared_start(state_root, prepared):
    """Restore exact pre-start staging for a PREPARED, uncommitted record."""
    run_id, staging_id = prepared["runId"], prepared["stagingId"]
    run_dir = os.path.join(state_root, "runs", run_id)
    staging_dir = os.path.join(state_root, "runs", staging_id)
    if os.path.isdir(run_dir):
        _rollback_uncommitted_start(run_dir)
        if not os.path.exists(staging_dir):
            os.replace(run_dir, staging_dir)


def _validated_snapshot_request(value):
    snapshot_request = value.get("snapshotRequest")
    if snapshot_request is None:
        return None
    required = {"apiVersion", "kind", "requestId", "projectIdentity", "candidateProjectRevision", "projectArchiveDigest", "artifactLockDigest", "catalogLockDigest", "installerOwnedLogicalPaths", "projectContract", "snapshotContract", "editContract"}
    if not isinstance(snapshot_request, dict) or set(snapshot_request) != required or snapshot_request.get("apiVersion") != SNAPSHOT_REQUEST_VERSION or snapshot_request.get("kind") != "BuildProjectSnapshotRequest" or snapshot_request.get("projectContract") != "v2alpha1" or snapshot_request.get("snapshotContract") != "v1alpha1" or snapshot_request.get("editContract") != "v1alpha2":
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    request_id = snapshot_request.get("requestId")
    project_identity = snapshot_request.get("projectIdentity")
    if not isinstance(request_id, str) or re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    if not isinstance(project_identity, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", project_identity) is None:
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    for field in ("candidateProjectRevision", "projectArchiveDigest", "artifactLockDigest", "catalogLockDigest"):
        field_value = snapshot_request.get(field)
        if not isinstance(field_value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", field_value) is None:
            raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    owned_paths = snapshot_request.get("installerOwnedLogicalPaths")
    owned_pattern = re.compile(r"^(ansible\.cfg|inventory/hosts\.yml|inventory/group_vars/all/platform-installer\.yml|inventory/host_vars/[a-z0-9][a-z0-9-]{0,62}/platform-installer\.yml)$")
    if not isinstance(owned_paths, list) or len(owned_paths) > 1026 or any(not isinstance(item, str) or owned_pattern.fullmatch(item) is None for item in owned_paths) or len(set(owned_paths)) != len(owned_paths):
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    return snapshot_request


def _candidate_logical_path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        return False
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if len(encoded) > MAX_CANDIDATE_PATH_BYTES or name.startswith("/"):
        return False
    parts = name.split("/")
    if any(not part or part in (".", "..") or any(ord(character) < 32 for character in part) for part in parts):
        return False
    if name in ("project.yml", "ansible.cfg", "inventory/hosts.yml"):
        return True
    if len(parts) >= 4 and parts[0] in ("application-packages", "library-packages"):
        if (re.fullmatch(r'[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*', parts[1]) is None or
                re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', parts[2]) is None or
                any(re.fullmatch(r'[A-Za-z0-9_.-]+', part) is None or part.endswith('.') for part in parts)):
            return False
        kind = parts[0][:-9]
        relative = '/'.join(parts[3:])
        role = 'roles/%s_%s/' % (kind, parts[1])
        if relative == kind + '.yml' or relative == role + 'defaults/main.yml':
            return True
        if kind == 'library' and relative == 'files/.env':
            return True
        return relative.startswith((role + 'templates/', 'configuration/', 'assets/'))
    if len(parts) < 3 or parts[0] != "inventory" or parts[1] not in ("group_vars", "host_vars"):
        return False
    return os.path.splitext(parts[-1])[1].lower() in (".yml", ".yaml", ".json")


def _candidate_members(archive):
    members = archive.getmembers()
    if len(members) > MAX_CANDIDATE_FILES:
        raise LifecycleError("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
    total = 0
    names = set()
    folded = set()
    for member in members:
        if not member.isreg() or member.linkname or member.sparse is not None or not _candidate_logical_path(member.name):
            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
        limit = MAX_CANDIDATE_TOTAL_BYTES if member.name.startswith(('application-packages/', 'library-packages/')) else MAX_CANDIDATE_FILE_BYTES
        if member.size < 0 or member.size > limit:
            raise LifecycleError("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
        total += member.size
        if total > MAX_CANDIDATE_TOTAL_BYTES:
            raise LifecycleError("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
        folded_name = member.name.casefold()
        if member.name in names or folded_name in folded:
            raise LifecycleError("PROJECT_CANDIDATE_CASE_COLLISION")
        names.add(member.name)
        folded.add(folded_name)
    if not {"project.yml", "ansible.cfg", "inventory/hosts.yml"}.issubset(names):
        raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_INCOMPLETE")
    return members


def _safe_candidate_parent(root, logical):
    current = root
    for part in logical.split("/")[:-1]:
        current = os.path.join(current, part)
        try:
            os.mkdir(current, 0o700)
        except FileExistsError:
            if os.path.islink(current) or not os.path.isdir(current):
                raise LifecycleError("PROJECT_CANDIDATE_EXTRACTION_UNSAFE")
    return current


def _write_all(descriptor, value):
    offset = 0
    while offset < len(value):
        written = os.write(descriptor, value[offset:])
        if written <= 0:
            raise OSError("short write")
        offset += written


def _candidate_archive_path(run_id):
    return os.path.join("/var/tmp/platform-installer/execution-plan", run_id, "project.tar")


def _write_snapshot_owner(journal, value):
    path = os.path.join(journal.directory, SNAPSHOT_OWNER_FILE)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _snapshot_stage_identity(value, journal):
    try:
        directory_info = os.lstat(journal.directory)
        if not os.path.isdir(journal.directory) or os.path.islink(journal.directory):
            return None
    except OSError:
        return None
    path = os.path.join(journal.directory, SNAPSHOT_OWNER_FILE)
    try:
        info = os.lstat(path)
        if not os.path.isfile(path) or os.path.islink(path) or info.st_size > 1024:
            return None
        with open(path, "r", encoding="ascii") as stream:
            marker = json.load(stream)
    except (OSError, ValueError, UnicodeError):
        return None
    request = value.get("snapshotRequest")
    if request is None:
        expected = {"kind": "readonly", "runId": value.get("runId")}
    elif isinstance(request, dict):
        expected = {"kind": "candidate", "runId": value.get("runId"), "requestId": request.get("requestId"), "archiveDigest": request.get("projectArchiveDigest")}
    else:
        return None
    if marker != expected:
        return None
    try:
        verified = os.lstat(journal.directory)
    except OSError:
        return None
    identity = (directory_info.st_dev, directory_info.st_ino)
    return identity if identity == (verified.st_dev, verified.st_ino) else None


def _cleanup_snapshot_staging(value, journal, expected_identity):
    if expected_identity is None or _snapshot_stage_identity(value, journal) != expected_identity:
        return False
    # Repeat the marker and directory identity proof immediately before the
    # recursive delete. A mismatch is preserved for operator diagnostics.
    if _snapshot_stage_identity(value, journal) != expected_identity:
        return False
    shutil.rmtree(journal.directory)
    return True


def _copy_verified_candidate_archive(source_path, destination_path, expected_digest, expected_info):
    source_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        source_flags |= os.O_NOFOLLOW
    source = os.open(source_path, source_flags)
    destination = None
    try:
        opened_info = os.fstat(source)
        expected_identity = (expected_info.st_dev, expected_info.st_ino, expected_info.st_size)
        if (opened_info.st_dev, opened_info.st_ino, opened_info.st_size) != expected_identity:
            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_REPLACED")
        destination = os.open(destination_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        archive_digest = hashlib.sha256()
        copied = 0
        while True:
            block = os.read(source, min(1024 * 1024, MAX_CANDIDATE_ARCHIVE_BYTES + 1 - copied))
            if not block:
                break
            copied += len(block)
            if copied > MAX_CANDIDATE_ARCHIVE_BYTES:
                raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
            archive_digest.update(block)
            _write_all(destination, block)
        final_info = os.fstat(source)
        if copied != opened_info.st_size or (final_info.st_dev, final_info.st_ino, final_info.st_size) != expected_identity:
            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_REPLACED")
        if "sha256:" + archive_digest.hexdigest() != expected_digest:
            raise LifecycleError("PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISMATCH")
        os.fsync(destination)
    finally:
        os.close(source)
        if destination is not None:
            os.close(destination)


def stage_candidate_archive(archive_path, run_id, request_id, expected_digest, state_root):
    journal = Journal(state_root, run_id)
    expected_archive = _candidate_archive_path(run_id)
    if os.path.abspath(archive_path) != expected_archive or not re.fullmatch(r"[0-9a-f]{32}", request_id or "") or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_digest or ""):
        raise LifecycleError("PROJECT_CANDIDATE_STAGING_INVALID")
    archive_info = os.lstat(archive_path)
    if not os.path.isfile(archive_path) or os.path.islink(archive_path) or archive_info.st_size > MAX_CANDIDATE_ARCHIVE_BYTES:
        raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
    if os.path.lexists(journal.directory):
        raise LifecycleError("PROJECT_CANDIDATE_STAGING_EXISTS")

    cleanup_value = {"runId": run_id, "snapshotRequest": {"requestId": request_id, "projectArchiveDigest": expected_digest}}
    stage_identity = None
    try:
        os.makedirs(journal.directory, mode=0o700)
        _write_snapshot_owner(journal, {"kind": "candidate", "runId": run_id, "requestId": request_id, "archiveDigest": expected_digest})
        stage_identity = _snapshot_stage_identity(cleanup_value, journal)
        if stage_identity is None:
            raise LifecycleError("PROJECT_CANDIDATE_STAGING_NOT_OWNED")
        verified_archive = os.path.join(journal.directory, ".candidate-archive.tar")
        _copy_verified_candidate_archive(archive_path, verified_archive, expected_digest, archive_info)
        temporary = os.path.join(journal.directory, ".project-staging")
        os.mkdir(temporary, 0o700)
        with tarfile.open(verified_archive, mode="r:") as archive:
            members = _candidate_members(archive)
            config_member = next(member for member in members if member.name == "ansible.cfg")
            config_stream = archive.extractfile(config_member)
            if config_stream is None or config_stream.read(MAX_CANDIDATE_FILE_BYTES + 1) != APPROVED_CANDIDATE_ANSIBLE_CONFIG:
                raise LifecycleError("PROJECT_CANDIDATE_ANSIBLE_CONFIG_UNSAFE")
            for member in members:
                source = archive.extractfile(member)
                if source is None:
                    raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
                parent = _safe_candidate_parent(temporary, member.name)
                target = os.path.join(parent, member.name.rsplit("/", 1)[-1])
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                descriptor = os.open(target, flags, 0o600)
                try:
                    remaining = member.size
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining))
                        if not block:
                            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_TRUNCATED")
                        _write_all(descriptor, block)
                        remaining -= len(block)
                    if source.read(1):
                        raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        os.remove(verified_archive)
        os.replace(temporary, os.path.join(journal.directory, "project"))
        digest_path = os.path.join(journal.directory, "project-archive.digest")
        descriptor = os.open(digest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(descriptor, (expected_digest + "\n").encode("ascii"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except Exception:
        if stage_identity is not None:
            _cleanup_snapshot_staging(cleanup_value, journal, stage_identity)
        raise


def _fixed_ansible_environment(**values):
    environment = {}
    for key in ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP"):
        if key in os.environ:
            environment[key] = os.environ[key]
    environment.update(values)
    environment["ANSIBLE_NOCOLOR"] = "1"
    return environment


def _candidate_ansible_environment(project, release, output_path):
    from execution_controller import _collection_path
    candidate_config = os.path.join(project, "ansible.cfg")
    if os.path.islink(candidate_config) or not os.path.isfile(candidate_config) or Path(candidate_config).read_bytes() != APPROVED_CANDIDATE_ANSIBLE_CONFIG:
        raise LifecycleError("PROJECT_CANDIDATE_ANSIBLE_CONFIG_UNSAFE")
    return _fixed_ansible_environment(
        ANSIBLE_CONFIG=candidate_config,
        ANSIBLE_COLLECTIONS_PATH=_collection_path(release),
        ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json",
        PLATFORM_PROJECT_SNAPSHOT_OUTPUT=output_path,
    )


def start(value, state_root, runtime_release, controller, active_bundle_digest="", prelaunch=None):
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
        infra.assert_admission(state_root, manifest, run_id)
        journal.initialize(metadata)
        journal.transition("STARTING", "Detached controller accepted")
        if prelaunch is not None:
            prelaunch(metadata, journal)
        # The bundle intentionally stores content with deterministic bytes, not
        # host executable bits.  Interpreter and controller are both fixed by
        # this node-side protocol, never supplied by a client.
        subprocess.check_call(["systemd-run", "--unit=" + metadata["unit"], "--collect", "--property=KillMode=control-group", "--property=NoNewPrivileges=yes", sys.executable, controller, "--state-root", state_root, "--run-id", run_id, "--runtime-release", runtime_release, "--bundle-digest", metadata["runtimeRelease"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"run": journal.status(), "idempotent": False, "runtimeRelease": runtime_release}
    finally:
        os.close(lock)
        os.close(active_lock)


def core_operation(value, state_root, runtime_release, operation, runtime_identity=None):
    """Run one fixed Core playbook against already trusted run staging."""
    from execution_controller import _collection_path
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
    elif operation in ("BuildProjectSnapshot", "BuildServiceConfigurationPreview"):
        playbook, inventory = ("project-snapshot.yml" if operation == "BuildProjectSnapshot" else "service-configuration-preview.yml"), os.path.join(project, "inventory", "hosts.yml")
        snapshot_request = _validated_snapshot_request(value)
        if snapshot_request is None:
            owned_paths = []
        else:
            owned_paths = snapshot_request.get("installerOwnedLogicalPaths")
            archive_digest_path = os.path.join(journal.directory, "project-archive.digest")
            if not os.path.isfile(archive_digest_path) or os.path.islink(archive_digest_path):
                raise LifecycleError("PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISSING")
            with open(archive_digest_path, "r", encoding="ascii") as stream:
                if stream.read().strip() != snapshot_request.get("projectArchiveDigest"):
                    raise LifecycleError("PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISMATCH")
            manifest_path = os.path.join(project, "project.yml")
            try:
                with open(manifest_path, "r", encoding="utf-8") as stream:
                    manifest = yaml.safe_load(stream)
            except (OSError, UnicodeError, yaml.YAMLError):
                raise LifecycleError("PROJECT_SNAPSHOT_PROJECT_INVALID")
            metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
            artifact_lock = manifest.get("artifactLock") if isinstance(manifest, dict) else None
            catalog_lock = manifest.get("catalogLock") if isinstance(manifest, dict) else None
            if not isinstance(metadata, dict) or not isinstance(artifact_lock, dict) or not isinstance(catalog_lock, dict) or metadata.get("id") != snapshot_request.get("projectIdentity") or artifact_lock.get("digest") != snapshot_request.get("artifactLockDigest") or catalog_lock.get("digest") != snapshot_request.get("catalogLockDigest"):
                raise LifecycleError("PROJECT_SNAPSHOT_IDENTITY_MISMATCH")
            try:
                with open(os.path.join(release, "manifest.yaml"), "r", encoding="utf-8") as stream:
                    release_manifest = yaml.safe_load(stream)
            except (OSError, UnicodeError, yaml.YAMLError):
                raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
            if not isinstance(release_manifest, dict) or release_manifest.get("catalogDigest") != snapshot_request.get("catalogLockDigest"):
                raise LifecycleError("PROJECT_SNAPSHOT_RUNTIME_MISMATCH")
        extra = {"platform_project_root": project, "platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_service_catalog_path": os.path.join(release, "catalog", "service-catalog.yml"), "platform_installer_owned_paths": owned_paths}
    elif operation == 'PrepareApplicationImages':
        playbook, inventory = 'application-images-inputs.yml', os.path.join(project, 'inventory', 'hosts.yml')
        extra = dict(platform_project_root=project,
                     platform_service_catalog_path=os.path.join(release, 'catalog/service-catalog.yml'),
                     platform_execution_bundle_root=release,
                     platform_execution_mode=value['executionMode'],
                     platform_application_image_inputs_path=os.path.join(journal.directory, 'application-image-inputs.json'))
    elif operation in ("BuildDeploymentPlan", "BuildRuntimeSecretDescriptors"):
        # Core remains target-free (the playbook runs on localhost), but it must
        # load the staged project inventory so snapshot receives its canonical
        # desired state, groups and host variables.
        playbook, inventory = "deployment-plan-machine.yml", os.path.join(project, "inventory", "hosts.yml")
        try:
            with open(os.path.join(release, "manifest.yaml"), "r", encoding="utf-8") as stream:
                bundle_manifest = yaml.safe_load(stream)
        except (OSError, UnicodeError, yaml.YAMLError):
            raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
        sources = bundle_manifest.get("artifactSources", []) if isinstance(bundle_manifest, dict) else None
        if not isinstance(sources, list):
            raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
        extra = {"platform_project_root": project, "platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_service_catalog_path": os.path.join(release, "catalog", "service-catalog.yml"), "platform_execution_runtime_release": value["runtimeRelease"], "platform_execution_bundle_artifact_sources": sources, "platform_execution_state_root": state_root}
        if operation == "BuildDeploymentPlan":
            if value.get('apiVersion') == image_preparation.REQUEST_VERSION:
                prepared = execution_secret_lease._read(os.path.join(journal.directory, 'application-images.json'))
                if digest(prepared) != value['applicationImagePreparation']:
                    raise LifecycleError('APPLICATION_IMAGE_PREPARATION_STALE')
                inputs = image_preparation.read_inputs(journal)
                if any(inputs.get(key) != value.get(key) for key in ('runtimeRelease', 'executionMode', 'deploymentOrder', 'skipInfrastructureVerify')):
                    raise LifecycleError('APPLICATION_IMAGE_PREPARATION_STALE')
                extra.update(platform_prepared_application_images=prepared, platform_application_image_metadata=True)
            extra["platform_execution_deployment_order"] = value["deploymentOrder"]
            extra['platform_execution_application_vault_sources'] = value.get('applicationVaultSources', {})
            if value.get('apiVersion') in (B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION, image_preparation.REQUEST_VERSION):
                extra['platform_execution_mode'] = value['executionMode']
                extra['platform_execution_skip_infrastructure_verify'] = value.get('skipInfrastructureVerify', False)
        if operation == "BuildRuntimeSecretDescriptors":
            playbook = "runtime-secret-descriptors.yml"
    else:
        raise LifecycleError("EXECUTION_OPERATION_UNSUPPORTED")
    diagnostic_path = os.path.join(journal.directory, "core-diagnostic.json")
    descriptor, vars_path = tempfile.mkstemp(prefix=".execution-vars-", dir=journal.directory)
    try:
        os.write(descriptor, json.dumps(extra, ensure_ascii=True, sort_keys=True).encode("utf-8")); os.close(descriptor)
        os.chmod(vars_path, 0o600)
        if operation in ("BuildProjectSnapshot", "BuildServiceConfigurationPreview"):
            candidate = value.get("snapshotRequest") is not None
            if candidate:
                environment = _candidate_ansible_environment(project, release, os.path.join(journal.directory, "project-snapshot.json"))
            else:
                environment = dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=_collection_path(release), ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json", PLATFORM_PROJECT_SNAPSHOT_OUTPUT=os.path.join(journal.directory, "project-snapshot.json"))
        elif operation == "BuildRuntimeSecretDescriptors":
            environment = dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=_collection_path(release), ANSIBLE_CALLBACKS_ENABLED="platform.core.runtime_secret_descriptors_json", PLATFORM_RUNTIME_SECRET_DESCRIPTORS_OUTPUT=os.path.join(journal.directory, "runtime-secret-descriptors.json"), PLATFORM_CORE_DIAGNOSTIC_OUTPUT=diagnostic_path)
        else:
            environment = dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=_collection_path(release), ANSIBLE_CALLBACKS_ENABLED="platform.core.deployment_plan_json", PLATFORM_DEPLOYMENT_PLAN_OUTPUT=os.path.join(journal.directory, "deployment-plan.json"), PLATFORM_EXECUTION_MANIFEST_OUTPUT=os.path.join(journal.directory, "manifest.json"), PLATFORM_CORE_DIAGNOSTIC_OUTPUT=diagnostic_path)
        command = ["ansible-playbook"]
        if operation != "BuildProjectSnapshot" or value.get("snapshotRequest") is None:
            command.extend(["-i", inventory])
        command.extend([os.path.join(release, "ansible-core", "playbooks", playbook), "-e", "@" + vars_path])
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            cwd=project if operation == "BuildProjectSnapshot" and value.get("snapshotRequest") is not None else None,
        )
        if completed.returncode:
            if operation in ("BuildProjectSnapshot", "BuildServiceConfigurationPreview"):
                snapshot_path = os.path.join(journal.directory, "project-snapshot.json")
                if os.path.isfile(snapshot_path) and not os.path.islink(snapshot_path):
                    with open(snapshot_path, "r", encoding="utf-8") as stream:
                        snapshot_error = json.load(stream)
                    if isinstance(snapshot_error, dict) and isinstance(snapshot_error.get("adapterError"), dict):
                        raise CoreOperationError(snapshot_error["adapterError"].get("code") or "PROJECT_SNAPSHOT_FAILED", {"findings": [snapshot_error["adapterError"]]})
            diagnostic = None
            if os.path.isfile(diagnostic_path) and not os.path.islink(diagnostic_path):
                with open(diagnostic_path, "r", encoding="utf-8") as stream:
                    diagnostic = json.load(stream)
            code = diagnostic.get("errorCode") if isinstance(diagnostic, dict) else None
            raise CoreOperationError(code or "CORE_OPERATION_FAILED", diagnostic)
    finally:
        if os.path.exists(vars_path): os.unlink(vars_path)
    if operation in ("BuildProjectSnapshot", "BuildServiceConfigurationPreview"):
        snapshot_path = os.path.join(journal.directory, "project-snapshot.json")
        if not os.path.isfile(snapshot_path) or os.path.islink(snapshot_path):
            raise LifecycleError("PROJECT_SNAPSHOT_RESPONSE_MISSING")
        with open(snapshot_path, "r", encoding="utf-8") as stream:
            snapshot = json.load(stream)
        if isinstance(snapshot, dict) and isinstance(snapshot.get("adapterError"), dict):
            raise CoreOperationError(snapshot["adapterError"].get("code") or "PROJECT_SNAPSHOT_FAILED", {"findings": [snapshot["adapterError"]]})
        if not isinstance(snapshot, dict) or not snapshot.get("projectRevision"):
            raise LifecycleError("PROJECT_SNAPSHOT_RESPONSE_INVALID")
        if operation == "BuildServiceConfigurationPreview":
            if snapshot.get("apiVersion") != "platform.installer/service-configuration-preview/v1alpha1" or snapshot.get("kind") != "ServiceConfigurationPreview" or not isinstance(snapshot.get("services"), dict):
                raise LifecycleError("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
            if runtime_identity is None:
                raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
            return {"serviceConfigurationPreview": snapshot, "runtimeEvidence": runtime_identity}
        request_value = value.get("snapshotRequest")
        if request_value is not None and snapshot.get("projectRevision") != request_value.get("candidateProjectRevision"):
            raise LifecycleError("PROJECT_SNAPSHOT_REVISION_MISMATCH")
        if runtime_identity is None:
            raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
        return {"projectSnapshot": snapshot, "runtimeEvidence": runtime_identity}
    if operation == "BuildRuntimeSecretDescriptors":
        result_path = os.path.join(journal.directory, "runtime-secret-descriptors.json")
        if not os.path.isfile(result_path) or os.path.islink(result_path):
            raise LifecycleError("RUNTIME_SECRET_DESCRIPTORS_RESPONSE_MISSING")
        with open(result_path, "r", encoding="utf-8") as stream:
            result = json.load(stream)
        if not isinstance(result, dict) or not isinstance(result.get("descriptors"), list):
            raise LifecycleError("RUNTIME_SECRET_DESCRIPTORS_RESPONSE_INVALID")
        if runtime_identity is None:
            raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
        return {"runtimeSecretDescriptors": result, "runtimeEvidence": runtime_identity}
    if operation == 'PrepareApplicationImages':
        inputs = image_preparation.read_inputs(journal)
        inputs.update({key: value[key] for key in ('runtimeRelease', 'executionMode', 'deploymentOrder', 'skipInfrastructureVerify')})
        inputs['expiresAt'] = int(time.time()) + 120
        execution_secret_lease._write(os.path.join(journal.directory, 'application-image-inputs.json'), inputs)
        return dict(status='INPUTS_READY', inputsDigest=digest(inputs), inputs=inputs,
                    leaseBinding=image_preparation.binding(journal, inputs, value['runtimeRelease']))
    if operation == "BuildDeploymentPlan":
        with open(os.path.join(journal.directory, "deployment-plan.json"), "r", encoding="utf-8") as stream:
            plan = json.load(stream)
        if plan.get("status") == "BLOCKED":
            return {"deploymentPlan": plan, "executionManifestDigest": None}
        if value.get('apiVersion') == image_preparation.REQUEST_VERSION and plan.get('projectRevision') != image_preparation.read_inputs(journal)['projectRevision']:
            raise LifecycleError('APPLICATION_IMAGE_PREPARATION_STALE')
        if plan.get('apiVersion') == 'platform.installer/plan/v1alpha4' and value.get('apiVersion') not in (APPLICATION_PLAN_REQUEST_VERSION, B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION):
            raise LifecycleError('APPLICATION_PLAN_REQUEST_VERSION_REQUIRED')
        if plan.get("status") != "EXECUTABLE" or not os.path.isfile(os.path.join(journal.directory, "manifest.json")):
            raise LifecycleError("EXECUTION_MANIFEST_MISSING")
        with open(os.path.join(journal.directory, "manifest.json"), "r", encoding="utf-8") as stream:
            manifest = json.load(stream)
        from execution_controller import validate_application_manifest
        validate_application_manifest(manifest)
        manifest_digest = digest(manifest)
        execution_secret_lease.register_plan(state_root, journal.run_id, manifest_digest, manifest)
        return {"deploymentPlan": plan, "executionManifestDigest": manifest_digest}
    return {"validation": "PASS"}


def snapshot(value, state_root, runtime_release, runtime_identity, operation="BuildProjectSnapshot"):
    """Return a Core snapshot and remove the request-owned staging directory."""
    journal = Journal(state_root, value["runId"])
    stage_identity = _snapshot_stage_identity(value, journal)
    if stage_identity is None:
        raise LifecycleError("PROJECT_SNAPSHOT_STAGING_NOT_OWNED")
    try:
        return core_operation(value, state_root, runtime_release, operation, runtime_identity)
    finally:
        _cleanup_snapshot_staging(value, journal, stage_identity)


def runtime_secret_descriptors(value, state_root, runtime_release, runtime_identity):
    """Read only the request-owned staged project and always remove it."""
    journal = Journal(state_root, value["runId"])
    stage_identity = _snapshot_stage_identity(value, journal)
    if stage_identity is None:
        raise LifecycleError("RUNTIME_SECRET_DESCRIPTORS_STAGING_NOT_OWNED")
    try:
        return core_operation(value, state_root, runtime_release, "BuildRuntimeSecretDescriptors", runtime_identity)
    finally:
        _cleanup_snapshot_staging(value, journal, stage_identity)


def put_runtime_secret_lease(value, state_root):
    """Admit only the payload generation authorized by each fixed request version."""
    fields = {"apiVersion", "kind", "requestId", "startAttemptId", "projectIdentity", "projectRevision", "planFingerprint", "executionManifestDigest", "runtimeRelease", "payload"}
    version = value.get("apiVersion") if isinstance(value, dict) else None
    if not isinstance(value, dict) or set(value) != fields or value.get("kind") != "PutRuntimeSecretLeaseRequest":
        raise LifecycleError("LEASE_REQUEST_INVALID")
    payload = value.get("payload")
    payload_version = payload.get("apiVersion") if isinstance(payload, dict) else None
    if version == "platform.installer/runtime-secret-lease/v1alpha2":
        if payload_version != execution_secret_lease.TYPED_RUNTIME_SECRET_PAYLOAD_VERSION:
            raise LifecycleError("LEASE_PAYLOAD_INVALID")
    elif version == "platform.installer/runtime-secret-lease/v1alpha1":
        if payload_version == execution_secret_lease.TYPED_RUNTIME_SECRET_PAYLOAD_VERSION:
            raise LifecycleError("LEASE_PAYLOAD_INVALID")
    else:
        raise LifecycleError("LEASE_REQUEST_INVALID")
    metadata = {key: value.get(key) for key in ("requestId", "startAttemptId", "projectIdentity", "projectRevision", "planFingerprint", "executionManifestDigest", "runtimeRelease")}
    return execution_secret_lease.put(state_root, metadata, payload)


def get(value, state_root):
    journal = Journal(state_root, value["runId"])
    metadata = owned(journal)
    recover(state_root, active)
    result = {"run": journal.status(), "metadata": metadata}
    if result["run"].get("state") not in ACTIVE:
        if not active(metadata.get("unit"), metadata):
            journal.cleanup_runtime_secret_inputs()
            execution_secret_lease.cleanup_run(state_root, journal.run_id)
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
            unit_active = active(metadata.get("unit"), metadata)
            if status.get("state") == "CANCELLED" and unit_active:
                subprocess.check_call(["systemctl", "stop", metadata["unit"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                unit_active = active(metadata.get("unit"), metadata)
                if unit_active:
                    raise LifecycleError("EXECUTION_CANCEL_NOT_STOPPED")
            if not unit_active:
                journal.cleanup_runtime_secret_inputs()
                journal.cleanup_runtime_connection_credentials()
            return {"run": status, "idempotent": True}
        if not active(metadata.get("unit"), metadata):
            journal.terminal("INTERRUPTED", "CONTROLLER_INTERRUPTED", "Owned controller is no longer active")
            journal.cleanup_runtime_secret_inputs()
            journal.cleanup_runtime_connection_credentials()
            return {"run": journal.status(), "idempotent": True}
        # Commit cancellation before asking systemd to terminate the whole
        # owned cgroup.  The controller can then never race a child SIGTERM
        # into a contradictory FAILED terminal result.
        journal.terminal("CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        subprocess.check_call(["systemctl", "stop", metadata["unit"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if active(metadata.get("unit"), metadata):
            raise LifecycleError("EXECUTION_CANCEL_NOT_STOPPED")
        journal.cleanup_runtime_secret_inputs()
        journal.cleanup_runtime_connection_credentials()
        return {"run": journal.status(), "idempotent": False}
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", default="/var/lib/platform-installer/execution")
    parser.add_argument("--runtime-release", required=True)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--bundle-digest", default="")
    parser.add_argument("--stage-candidate-archive")
    parser.add_argument("--stage-run-id")
    parser.add_argument("--stage-request-id")
    parser.add_argument("--expected-archive-digest")
    parser.add_argument("--stage-target-host-trust", action="store_true")
    parser.add_argument("--cleanup-snapshot-run-id")
    parser.add_argument("--cleanup-request-id")
    parser.add_argument("--cleanup-archive-digest")
    args = parser.parse_args()
    if args.stage_target_host_trust:
        def unique_pairs(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise LifecycleError("TARGET_HOST_TRUST_INVALID")
                value[key] = item
            return value
        data = sys.stdin.buffer.read(65537)
        if len(data) > 65536:
            raise LifecycleError("TARGET_HOST_TRUST_INVALID")
        execution_target_trust.stage(args.state_root, json.loads(data, object_pairs_hook=unique_pairs))
        return reply({"status": "STAGED"})
    if args.stage_candidate_archive is not None:
        if not args.stage_run_id or not args.stage_request_id or not args.expected_archive_digest:
            raise LifecycleError("PROJECT_CANDIDATE_STAGING_INVALID")
        stage_candidate_archive(args.stage_candidate_archive, args.stage_run_id, args.stage_request_id, args.expected_archive_digest, args.state_root)
        return reply({"status": "STAGED"})
    if args.cleanup_snapshot_run_id is not None:
        if not args.cleanup_request_id or not args.cleanup_archive_digest:
            raise LifecycleError("PROJECT_CANDIDATE_CLEANUP_INVALID")
        cleanup_value = {"runId": args.cleanup_snapshot_run_id, "snapshotRequest": {"requestId": args.cleanup_request_id, "projectArchiveDigest": args.cleanup_archive_digest}}
        journal = Journal(args.state_root, args.cleanup_snapshot_run_id)
        identity = _snapshot_stage_identity(cleanup_value, journal)
        if identity is None or not _cleanup_snapshot_staging(cleanup_value, journal, identity):
            raise LifecycleError("PROJECT_CANDIDATE_CLEANUP_NOT_OWNED")
        return reply({"status": "CLEANED"})
    value = request()
    if value.get("apiVersion") == "platform.installer/execution-start/v1alpha2":
        return reply(_start_v2(value, args.state_root, args.runtime_release, args.controller, args.bundle_digest))
    if value.get("apiVersion") in ("platform.installer/runtime-secret-lease/v1alpha1", "platform.installer/runtime-secret-lease/v1alpha2"):
        return reply(put_runtime_secret_lease(value, args.state_root))
    operation = value["operation"]
    if value.get('apiVersion') == image_preparation.REQUEST_VERSION and operation in ('PrepareApplicationImages', 'BuildDeploymentPlan'):
        observed = runtime_evidence(args)
        expected_release = dict(bundleDigest=observed['bundleDigest'], coreVersion=observed['coreVersion'],
                                catalogDigest=observed['catalogDigest'], planningProtocol=observed['protocol'])
        if value.get('runtimeRelease') != expected_release:
            raise LifecycleError('EXECUTION_RUNTIME_RELEASE_INVALID')
    if operation == "GetCapabilities":
        return reply(_image_capabilities(args) if value['apiVersion'] == image_preparation.REQUEST_VERSION else _b0_capabilities(args, value['apiVersion'] == SKIP_PLAN_REQUEST_VERSION) if value['apiVersion'] in (B0_PLAN_REQUEST_VERSION, SKIP_PLAN_REQUEST_VERSION) else _application_capabilities(args) if value['apiVersion'] == APPLICATION_PLAN_REQUEST_VERSION else _capabilities_v4(args))
    if operation == 'PrepareApplicationImages':
        if value['phase'] == 'DESCRIBE':
            return reply(core_operation(value, args.state_root, args.runtime_release, operation))
        return reply(image_preparation.prepare(Journal(args.state_root, value['runId']), value, args.runtime_release, value['runtimeRelease']))
    if operation in ("ValidateProject", "BuildDeploymentPlan"): return reply(core_operation(value, args.state_root, args.runtime_release, operation))
    if operation == "BuildProjectSnapshot":
        candidate = _validated_snapshot_request(value)
        runtime_release = value.get("runtimeRelease")
        if not isinstance(runtime_release, dict) or runtime_release.get("bundleDigest") != args.bundle_digest:
            raise LifecycleError("PROJECT_SNAPSHOT_RUNTIME_MISMATCH")
        if candidate is not None:
            if candidate.get("artifactLockDigest") != args.bundle_digest or runtime_release.get("bundleDigest") != args.bundle_digest:
                raise LifecycleError("PROJECT_SNAPSHOT_RUNTIME_MISMATCH")
        return reply(snapshot(value, args.state_root, args.runtime_release, runtime_evidence(args)))
    if operation == "BuildServiceConfigurationPreview":
        runtime_release = value.get("runtimeRelease")
        if not isinstance(runtime_release, dict) or runtime_release.get("bundleDigest") != args.bundle_digest or "snapshotRequest" in value:
            raise LifecycleError("SERVICE_CONFIGURATION_PREVIEW_INPUT_INVALID")
        return reply(snapshot(value, args.state_root, args.runtime_release, runtime_evidence(args), operation))
    if operation == "BuildRuntimeSecretDescriptors":
        runtime_release = value.get("runtimeRelease")
        if not isinstance(runtime_release, dict) or runtime_release.get("bundleDigest") != args.bundle_digest or _validated_snapshot_request(value) is None:
            raise LifecycleError("RUNTIME_SECRET_DESCRIPTORS_INPUT_INVALID")
        return reply(runtime_secret_descriptors(value, args.state_root, args.runtime_release, runtime_evidence(args)))
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
    except (OSError, ValueError, LifecycleError, subprocess.CalledProcessError, tarfile.TarError) as error:
        reply({"apiVersion": "platform.installer/execution-runtime/v1alpha1", "status": "FAILED", "error": str(error).split("\n", 1)[0][:256]})
        raise SystemExit(2)
