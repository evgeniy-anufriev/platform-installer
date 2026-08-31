from __future__ import absolute_import, division, print_function

__metaclass__ = type


DEFAULT_AUTO_ORDER = ("LOCAL_INSTALLER", "EXPLICIT_TARGET")


def _finding(code, status, details):
    return {"code": code, "status": status, "details": details}


def evaluate_candidate(candidate, capabilities):
    """Separate pre-preparation eligibility from post-preparation readiness."""
    candidate = candidate or {}
    capabilities = capabilities or {}
    required = ("linux", "bootstrapReachable", "resourcesAvailable")
    missing = [name for name in required if not capabilities.get(name, False)]
    eligible = not missing
    ready_checks = ("python", "ansible", "workspace", "offlinePayload", "executionIdentity")
    missing_ready = [name for name in ready_checks if not capabilities.get(name, False)]
    return {
        "candidateId": candidate.get("id", "local-installer"),
        "kind": candidate.get("kind", "LOCAL_INSTALLER"),
        "eligibility": "CANDIDATE_ELIGIBLE" if eligible else "CANDIDATE_INELIGIBLE",
        "readiness": "EXECUTION_READY" if eligible and not missing_ready else "NOT_READY",
        "missingEligibility": missing,
        "missingReadiness": missing_ready,
        "findings": [
            _finding("EXECUTION_CANDIDATE_INELIGIBLE", "BLOCKED", ",".join(missing))
        ] if missing else [],
    }


def resolve_execution_selection(selection, local_candidate, target_candidates):
    """Resolve selection without inspecting service topology or mutating state."""
    selection = selection or {"mode": "AUTO"}
    mode = selection.get("mode", "AUTO")
    local = evaluate_candidate(local_candidate, (local_candidate or {}).get("capabilities", {}))
    targets = {
        candidate.get("id"): evaluate_candidate(candidate, candidate.get("capabilities", {}))
        for candidate in sorted(target_candidates or [], key=lambda value: value.get("id", ""))
    }
    if mode == "LOCAL_INSTALLER":
        return _selection_result(mode, local if local["eligibility"] == "CANDIDATE_ELIGIBLE" else None, [local])
    if mode == "EXPLICIT_TARGET":
        selected = targets.get(selection.get("targetHostId"))
        return _selection_result(mode, selected if selected and selected["eligibility"] == "CANDIDATE_ELIGIBLE" else None, list(targets.values()))
    if mode == "EXTERNAL_EXECUTION_HOST":
        external = selection.get("externalHost")
        candidate = {
            "id": external.get("address") if external else "external",
            "kind": "EXTERNAL_EXECUTION_HOST",
            "capabilities": (external or {}).get("capabilities", {}),
        }
        evaluated = evaluate_candidate(candidate, candidate.get("capabilities"))
        return _selection_result(mode, evaluated if evaluated["eligibility"] == "CANDIDATE_ELIGIBLE" else None, [evaluated])
    for candidate in (local,) + tuple(targets.values()):
        if candidate["eligibility"] == "CANDIDATE_ELIGIBLE":
            return _selection_result("AUTO", candidate, [local] + list(targets.values()))
    return _selection_result("AUTO", None, [local] + list(targets.values()))


def _selection_result(mode, selected, candidates):
    return {
        "status": "PASS" if selected else "BLOCKED",
        "mode": mode,
        "selected": selected,
        "candidates": candidates,
        "findings": [] if selected else [_finding("EXECUTION_NODE_NO_ELIGIBLE_CANDIDATE", "BLOCKED", "")],
    }
