"""Read only the protected, request-scoped PKI markers used by reissue.

This module is shared by target-free Core planning and the fixed execution
controller. It does not resolve certificate semantics or write PKI state.
"""

import os
import re
import stat


_PROJECT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,127}\Z")
_REQUEST_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,127}\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_MATERIAL_FILES = ("leaf.key", "leaf.crt", "keystore.p12", "truststore.p12")


def _directory(root, parts):
    if not isinstance(root, str) or not os.path.isabs(root):
        raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
    segments = [part for part in os.path.normpath(root).split(os.sep) if part] + list(parts)
    descriptor = os.open(os.sep, _DIR_FLAGS)
    try:
        for segment in segments:
            if segment in ("", ".", "..") or os.sep in segment:
                raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
            try:
                child = os.open(segment, _DIR_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                return None
            os.close(descriptor)
            descriptor = child
        return os.dup(descriptor)
    except OSError:
        raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
    finally:
        os.close(descriptor)


def _file(directory, name, marker=False):
    if directory is None:
        return None
    try:
        descriptor = os.open(name, _FILE_FLAGS, dir_fd=directory)
    except FileNotFoundError:
        return None
    except OSError:
        raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > (80 if marker else 1 << 30):
            raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
        if marker:
            raw = os.read(descriptor, 81)
            try:
                value = raw.decode("ascii").rstrip("\n")
            except UnicodeDecodeError:
                raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
            if _FINGERPRINT.fullmatch(value) is None:
                raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
            return value
        return True
    finally:
        os.close(descriptor)


def inspect_reissue(state_root, project_identity, requests):
    """Return deterministic changed/resumable request marker observations."""
    if (_PROJECT_ID.fullmatch(project_identity or "") is None or
            not isinstance(requests, list) or len(requests) > 4096):
        raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
    base = os.path.join(state_root, "pki")
    result, seen = [], set()
    for request in sorted(requests, key=lambda item: item.get("id", "") if isinstance(item, dict) else ""):
        if not isinstance(request, dict):
            raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
        request_id, desired = request.get("id"), request.get("certificateRequestFingerprint")
        authority_id, authority_fingerprint = request.get("authorityId"), request.get("authorityFingerprint")
        if (not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None or
                request_id in seen or not isinstance(desired, str) or
                _FINGERPRINT.fullmatch(desired) is None or
                not isinstance(authority_id, str) or _REQUEST_ID.fullmatch(authority_id) is None or
                not isinstance(authority_fingerprint, str) or _FINGERPRINT.fullmatch(authority_fingerprint) is None):
            raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
        seen.add(request_id)
        request_dir = recovery_dir = authority_dir = None
        try:
            request_dir = _directory(base, (project_identity, "requests", request_id))
            recovery_dir = _directory(base, (project_identity, "reissues"))
            authority_dir = _directory(base, (project_identity, "authorities", authority_id))
            old = _file(request_dir, "request-fingerprint", marker=True)
            recovery = _file(recovery_dir, request_id + ".fingerprint", marker=True)
            if recovery is not None and recovery != desired:
                raise ValueError("PKI_REISSUE_RECOVERY_MISMATCH")
            if recovery is None:
                material = [_file(request_dir, name) is not None for name in _MATERIAL_FILES]
                if (old is None and any(material)) or (old is not None and not all(material[:2])):
                    raise ValueError("PKI_REISSUE_STATE_INCOMPLETE")
            if recovery is not None or (old is not None and old != desired):
                authority_marker = _file(authority_dir, "authority-fingerprint", marker=True)
                if (authority_marker != authority_fingerprint or
                        _file(authority_dir, "ca.key") is None or
                        _file(authority_dir, "ca.crt") is None):
                    raise ValueError("PKI_REISSUE_AUTHORITY_CHANGED")
                result.append({"requestId": request_id, "expectedOldFingerprint": old,
                               "desiredFingerprint": desired, "recoveryFingerprint": recovery,
                               "authorityId": authority_id, "authorityFingerprint": authority_marker})
        finally:
            if request_dir is not None:
                os.close(request_dir)
            if recovery_dir is not None:
                os.close(recovery_dir)
            if authority_dir is not None:
                os.close(authority_dir)
    return result


def assert_reissue_unchanged(state_root, project_identity, expected):
    if not isinstance(expected, list) or not expected or len(expected) > 256:
        raise ValueError("PKI_REISSUE_STATE_UNAVAILABLE")
    requests = [{"id": item.get("requestId"), "certificateRequestFingerprint": item.get("desiredFingerprint"),
                 "authorityId": item.get("authorityId"), "authorityFingerprint": item.get("authorityFingerprint")}
                for item in expected if isinstance(item, dict)]
    if len(requests) != len(expected) or inspect_reissue(state_root, project_identity, requests) != expected:
        raise ValueError("PKI_REISSUE_PLAN_STALE")
