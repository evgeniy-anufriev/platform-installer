#!/bin/sh
# Run on the Execution Node. With no argument, list recent plan files.
set -eu

if [ "$#" -gt 1 ]; then
    echo "Usage: sudo sh $0 [installer-stage-id]" >&2
    exit 2
fi

runtime=$(readlink -f /var/lib/platform-installer/runtime/current)
case "$runtime" in
    /var/lib/platform-installer/runtime/releases/*) ;;
    *) echo RUNTIME_NOT_FOUND >&2; exit 1 ;;
esac
test -d "$runtime/contracts" || { echo RUNTIME_NOT_FOUND >&2; exit 1; }
runs=/var/lib/platform-installer/execution/runs
printf 'Runtime: %s\n' "${runtime##*/}"
date -Is

if [ "$#" -eq 0 ]; then
    find "$runs" -maxdepth 2 -type f \
        \( -name manifest.json -o -name deployment-plan.json -o -name core-diagnostic.json \) \
        -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' |
        sort -r | head -20
    exit
fi

python3 -B - "$runtime" "$runs" "$1" <<'PY'
import json
import re
import sys
import traceback
from pathlib import Path


def token(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_./:\[\]-]{1,512}", value) else "-"


def read_document(name):
    path = stage / name
    if not path.is_symlink() and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def print_findings(label, findings):
    for finding in findings:
        print(label, token(finding.get("code")), token(finding.get("field")))


def print_failure(label, error):
    code = str(error)
    print(label, type(error).__name__, code if re.fullmatch(r"[A-Z][A-Z0-9_]{1,127}", code) else "-")
    for frame in traceback.extract_tb(error.__traceback__):
        print("AT", Path(frame.filename).name, frame.lineno, frame.name)


def check_registration(manifest):
    import execution_secret_lease as lease
    from execution_lifecycle import LifecycleError, digest

    project = manifest.get("projectIdentity")
    fingerprint = manifest.get("planFingerprint")
    project_ok = isinstance(project, str) and bool(lease._PROJECT.fullmatch(project))
    fingerprint_ok = isinstance(fingerprint, str) and bool(lease._DIGEST.fullmatch(fingerprint))
    release_ok = isinstance(manifest.get("runtimeRelease"), dict)
    print("PROJECT_ID_FORMAT_OK", project_ok)
    print("PLAN_FINGERPRINT_FORMAT_OK", fingerprint_ok)
    print("RUNTIME_RELEASE_IS_OBJECT", release_ok)
    if not (project_ok and fingerprint_ok and release_ok):
        raise SystemExit("REGISTRATION_INPUT_INVALID")

    try:
        record = lease.resolve_plan(str(runs.parent), {
            "executionManifestDigest": digest(manifest),
            "projectIdentity": project,
            "planFingerprint": fingerprint,
        })
    except LifecycleError as error:
        print_failure("REGISTRATION_FAILED", error)
        raise SystemExit(1) from None
    matches = record.get("stagingId") == stage_id
    print("REGISTRATION_MATCHES_STAGE", matches)
    if not matches:
        raise SystemExit(1)


def diagnose():
    diagnostic = read_document("core-diagnostic.json")
    if diagnostic is not None:
        print("CORE_DIAGNOSTIC", token(diagnostic.get("errorCode")))
        print_findings("CORE_FINDING", diagnostic.get("findings", []))

    plan = read_document("deployment-plan.json")
    if plan is not None:
        print("PLAN", token(plan.get("status")), token(plan.get("apiVersion")))
        print_findings("PLAN_FINDING", plan.get("findings", []))

    manifest = read_document("manifest.json")
    if manifest is None:
        raise SystemExit("MANIFEST_NOT_FOUND")
    version = manifest["apiVersion"].rsplit("/", 1)[-1]
    if not re.fullmatch(r"v[0-9]+alpha[0-9]+", version):
        raise SystemExit("MANIFEST_VERSION_INVALID")
    print("MANIFEST", version, token(manifest.get("executionMode")))
    print("OPERATIONS", *(token(op.get("operation")) for op in manifest.get("operations", [])))

    from execution_controller import validate_application_manifest
    from schema_validation import SchemaValidator

    contracts = runtime / "contracts"
    schema = contracts / "execution-manifest" / version / "schema.json"
    if schema.is_file():
        print_findings("SCHEMA_FINDING", SchemaValidator(str(contracts)).validate(manifest, schema))
    else:
        print("SCHEMA_MISSING", version)

    try:
        validate_application_manifest(manifest)
    except Exception as error:
        print_failure("VALIDATION_FAILED", error)
        raise SystemExit(1) from None
    print("VALIDATION_OK")
    check_registration(manifest)


runtime = Path(sys.argv[1])
runs = Path(sys.argv[2]).resolve()
stage_id = sys.argv[3]
if not re.fullmatch(r"installer-[a-f0-9]+", stage_id):
    raise SystemExit("STAGE_ID_INVALID")
stage = runs / stage_id
if stage.is_symlink() or not stage.is_dir():
    raise SystemExit("STAGE_NOT_FOUND")

core = runtime / "ansible-core"
sys.path[:0] = [
    str(core / "tools"),
    str(core / "collections/ansible_collections/platform/core/plugins/module_utils"),
]
try:
    diagnose()
except Exception as error:
    print_failure("DIAGNOSTIC_FAILED", error)
    raise SystemExit(1) from None
PY
