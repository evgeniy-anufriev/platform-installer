"""Closed typed-payload admission only; no lease, service or process lifecycle.

Not wired into the active runtime. Integration must supply trusted manifest
input descriptors and independently check the existing lease/run bindings.
"""
import json

MAX_PAYLOAD_BYTES = 1114112


class InputWireError(ValueError):
    pass


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value


def _bytes(value, maximum):
    if not isinstance(value, str) or not 1 <= len(value.encode("utf-8", "strict")) <= maximum:
        raise ValueError()


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8", "strict")


def decode_payload(data, validator, schema_path, expected_inputs):
    """Expected descriptors come from Core's trusted private manifest, not UI.

    Missing conditional inputs are permitted here; their runtime prerequisite
    is checked by the service before mutation. Extra or wrong-scope inputs
    never pass admission. Parse errors expose neither values nor paths.
    """
    try:
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_PAYLOAD_BYTES or not isinstance(expected_inputs, list):
            raise ValueError()
        def reject(value):
            raise ValueError()
        payload = json.loads(data.decode("utf-8", "strict"), object_pairs_hook=_unique, parse_constant=reject)
        if validator.validate(payload, schema_path):
            raise ValueError()
        _bytes(payload["username"], 255)
        if payload["pkiStorePassword"] is not None:
            _bytes(payload["pkiStorePassword"], 4096)
        total = 0
        for value in payload["runtimeSecretValues"].values():
            _bytes(value, 4096)
            total += len(value.encode("utf-8"))
        if total > 65536:
            raise ValueError()
        expected = {}
        for descriptor in expected_inputs:
            if not isinstance(descriptor, dict) or set(descriptor) != {"requirementRef", "purpose", "serviceDeployment", "operations"}:
                raise ValueError()
            key = (descriptor["serviceDeployment"], descriptor["requirementRef"])
            if key in expected:
                raise ValueError()
            expected[key] = descriptor
        seen, total = set(), 0
        for item in payload["runtimeSecretInputs"]:
            key = (item["serviceDeployment"], item["requirementRef"])
            if key in seen or expected.get(key) != {name: item[name] for name in ("requirementRef", "purpose", "serviceDeployment", "operations")}:
                raise ValueError()
            seen.add(key)
            if item["purpose"] == "SERVICE_ADMIN_TOKEN":
                _bytes(item["value"], 4096)
                size = len(item["value"].encode("utf-8"))
            else:
                for share in item["value"]:
                    _bytes(share, 128)
                size = len(_encoded(item["value"]))
                if size > 32768:
                    raise ValueError()
            total += size
        if total > 65536:
            raise ValueError()
        return payload
    except (ValueError, TypeError, UnicodeError, KeyError, RecursionError):
        raise InputWireError("TARGET_CREDENTIAL_LEASE_INPUT_INVALID") from None
