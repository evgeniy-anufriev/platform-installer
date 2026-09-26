"""Bounded SecretOutputDelivery codec; no storage, subprocess or target access.

SchemaValidator is supplied by the trusted runtime caller. This module does
not resolve user paths or acquire schemas from a network.
"""
import json
import struct

PROTOCOL = "SecretOutputDelivery/v1alpha1"
MAX_REQUEST_BYTES = 8192
MAX_FRAME_BYTES = 65536


class OutputWireError(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OutputWireError("OUTPUT_REQUEST_INVALID")
        result[key] = value
    return result


def _constant(value):
    raise OutputWireError("OUTPUT_REQUEST_INVALID")


def decode_request(data, validator, schema_path):
    """Validate exact UTF-8 bytes without returning raw parser diagnostics."""
    try:
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_REQUEST_BYTES:
            raise ValueError()
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=_constant)
        if validator.validate(value, schema_path):
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise OutputWireError("OUTPUT_REQUEST_INVALID") from None


def encode_fetch(metadata, token, shares, validator, schema_path):
    """Build one fixed frame only from validated trusted package bytes.

    Transport must not emit the frame until successful protected reads and
    authorization. Callers own clearing their secret buffers after transport.
    """
    try:
        if validator.validate(metadata, schema_path) or metadata["state"] != "READY":
            raise ValueError()
        if not isinstance(token, bytes) or not isinstance(shares, bytes):
            raise ValueError()
        if not 1 <= len(token) <= 4096 or not 1 <= len(shares) <= 32768:
            raise ValueError()
        token.decode("utf-8")
        json.loads(shares.decode("utf-8"), object_pairs_hook=_object,
                   parse_constant=_constant)
        header = json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                            separators=(",", ":")).encode("utf-8")
        if not 1 <= len(header) <= 8192 or 16 + len(header) + len(token) + len(shares) > MAX_FRAME_BYTES:
            raise ValueError()
        return struct.pack(">4sIII", b"SOD1", len(header), len(token), len(shares)) + header + token + shares
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise OutputWireError("OUTPUT_TRANSFER_FAILED") from None
