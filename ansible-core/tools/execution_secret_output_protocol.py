#!/usr/bin/env python3
"""Fixed, separate binary-safe SecretOutputDelivery SSH entrypoint."""
import json
import os
import sys

from execution_lifecycle import EXECUTION_STATE_ROOT
import execution_secret_output
from secret_output_wire import OutputWireError, decode_request

BUNDLE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE_UTILS = os.path.join(BUNDLE_ROOT, "ansible-core", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
if MODULE_UTILS not in sys.path:
    sys.path.insert(0, MODULE_UTILS)
from schema_validation import SchemaValidator

CONTRACT_ROOT = os.path.join(BUNDLE_ROOT, "contracts", "secret-output-delivery", "v1alpha1")
REQUEST_SCHEMA = os.path.join(CONTRACT_ROOT, "request.schema.json")
METADATA_SCHEMA = os.path.join(CONTRACT_ROOT, "metadata.schema.json")
RESPONSE_SCHEMA = os.path.join(CONTRACT_ROOT, "response.schema.json")
MAX_REQUEST_BYTES = 8192
ERROR_CODES = frozenset(("OUTPUT_REQUEST_INVALID", "OUTPUT_UNAVAILABLE", "OUTPUT_NOT_FOUND",
                         "OUTPUT_ACCESS_DENIED", "OUTPUT_IDENTITY_MISMATCH", "OUTPUT_BUSY",
                         "OUTPUT_RECOVERY_REQUIRED", "OUTPUT_TRANSFER_FAILED", "OUTPUT_CLEANUP_FAILED"))


def _write_json(value):
    sys.stdout.buffer.write(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8"))
    sys.stdout.buffer.flush()


def _error(operation, code):
    _write_json({"protocol": "SecretOutputDelivery/v1alpha1", "operation": operation,
                 "errorCode": code if code in ERROR_CODES else "OUTPUT_RECOVERY_REQUIRED"})


def main():
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    validator = SchemaValidator(CONTRACT_ROOT)
    try:
        request = decode_request(raw, validator, REQUEST_SCHEMA)
        operation = request["operation"]
        project_id = request["projectId"]
        if operation == "GetCapabilities":
            response = {"protocol": "SecretOutputDelivery/v1alpha1", "operation": operation,
                        "maxPayloadBytes": 65536,
                        "operations": ["ListPending", "Fetch", "Acknowledge"]}
            if validator.validate(response, RESPONSE_SCHEMA):
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            _write_json(response)
        elif operation == "ListPending":
            response = execution_secret_output.list_pending(
                EXECUTION_STATE_ROOT, project_id, request["limit"], request.get("cursor"),
                validator, RESPONSE_SCHEMA)
            _write_json(response)
        elif operation == "Fetch":
            frame = execution_secret_output.fetch(
                EXECUTION_STATE_ROOT, request["packageId"], project_id,
                request["expectedGeneration"], validator, METADATA_SCHEMA)
            sys.stdout.buffer.write(frame)
            sys.stdout.buffer.flush()
        else:
            response = execution_secret_output.acknowledge(
                EXECUTION_STATE_ROOT, project_id, request["packageId"],
                request["expectedGeneration"], request["receiptId"],
                request["ciphertextDigests"])
            if validator.validate(response, RESPONSE_SCHEMA):
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            _write_json(response)
        return 0
    except OutputWireError as error:
        operation = locals().get("operation", "GetCapabilities")
        _error(operation, str(error))
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        operation = locals().get("operation", "GetCapabilities")
        _error(operation, "OUTPUT_RECOVERY_REQUIRED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
