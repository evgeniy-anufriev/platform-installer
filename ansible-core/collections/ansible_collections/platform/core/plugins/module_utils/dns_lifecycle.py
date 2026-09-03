from __future__ import absolute_import, division, print_function

__metaclass__ = type

"""Explicit, fail-closed recovery of BIND serial lifecycle metadata."""

import copy


def _error(code, message):
    return {"code": code, "message": message}


def recover_dns_lifecycle(generated_state, zones, recovery):
    """Adopt an audited serial floor only for an explicit DNS migration.

    This is deliberately not normal serial allocation: callers must supply an
    observed historical fingerprint that differs from the newly resolved
    canonical content and serials for exactly the current DNS participants.
    """
    generated_state = generated_state if isinstance(generated_state, dict) else {}
    zones = zones if isinstance(zones, dict) else {}
    recovery = recovery if isinstance(recovery, dict) else {}
    state = copy.deepcopy(generated_state)
    entries = state.setdefault("serviceDeployments", {})
    findings = []

    for deployment_id, evidence in sorted(recovery.items()):
        zone = zones.get(deployment_id)
        evidence = evidence if isinstance(evidence, dict) else {}
        if not isinstance(zone, dict):
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_DEPLOYMENT_UNKNOWN", "Recovery deployment is not a resolved DNS zone"))
            continue
        if evidence.get("zone") != zone.get("zone"):
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_ZONE_MISMATCH", "Recovery zone identity does not match canonical DNS zone"))
            continue
        current_fingerprint = zone.get("contentFingerprint")
        historical_fingerprint = evidence.get("historicalContentFingerprint")
        if not isinstance(historical_fingerprint, str) or not historical_fingerprint.startswith("sha256:"):
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_HISTORICAL_FINGERPRINT_REQUIRED", "Recovery requires an audited historical content fingerprint"))
            continue
        if historical_fingerprint == current_fingerprint:
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_NOT_A_NEW_REVISION", "Recovery cannot advance a serial for unchanged logical content"))
            continue
        serials = evidence.get("observedSerials")
        if not isinstance(serials, dict):
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_SERIALS_REQUIRED", "Recovery requires observed serials for current participants"))
            continue
        participants = [zone.get("primary", {}).get("hostId")] + [item.get("hostId") for item in zone.get("secondaries", [])]
        expected_hosts = set(item for item in participants if isinstance(item, str))
        if set(serials) != expected_hosts:
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_PARTICIPANTS_MISMATCH", "Observed serials must cover exactly the canonical DNS participants"))
            continue
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in serials.values()):
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_SERIAL_INVALID", "Observed DNS serials must be positive integers"))
            continue
        observed_maximum = max(serials.values())
        existing = entries.get(deployment_id, {}).get("dns", {})
        existing_serial = existing.get("currentSerial", 0)
        if not isinstance(existing_serial, int) or isinstance(existing_serial, bool) or existing_serial < 0:
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_STATE_INVALID", "Existing generated DNS serial is invalid"))
            continue
        if existing_serial > observed_maximum:
            findings.append(_error("BIND_LIFECYCLE_RECOVERY_SERIAL_REGRESSION", "Existing generated serial exceeds the audited observed serial floor"))
            continue
        entries[deployment_id] = {"dns": {"contentFingerprint": current_fingerprint, "currentSerial": observed_maximum + 1}}

    return {"status": "BLOCKED" if findings else "PASS", "generatedState": state, "findings": findings}
