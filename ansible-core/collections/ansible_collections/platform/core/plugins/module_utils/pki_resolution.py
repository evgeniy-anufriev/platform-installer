from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


REQUIRED_DEFAULT_KEYS = (
    "authorityValidityDays", "leafValidityDays", "keyAlgorithm", "keySize",
    "usages", "scope", "targetRoot", "sanPolicy", "subject",
)


def _finding(code, field, message, status="BLOCKED"):
    return {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": status,
        "category": "pki-resolution",
        "field": field,
        "safeMessage": message,
    }


def _string_list(values):
    return sorted(set(value for value in values if isinstance(value, str) and value))


def _safe_identity_value(value):
    return isinstance(value, str) and value and "\n" not in value and "\r" not in value and "\x00" not in value


def _host_identity(host_id, host_vars):
    values = host_vars.get(host_id, {}) if isinstance(host_vars, dict) else {}
    values = values if isinstance(values, dict) else {}
    address = values.get("ansible_host") or host_id
    dns_names = _string_list([host_id] + ([address] if isinstance(address, str) and not _looks_like_ip(address) else []))
    ip_addresses = _string_list([address] if _looks_like_ip(address) else [])
    return {"hostId": host_id, "dnsNames": dns_names, "ipAddresses": ip_addresses}


def _looks_like_ip(value):
    if not isinstance(value, str):
        return False
    if ":" in value:
        return True
    parts = value.split(".")
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def _profile_defaults(profile, defaults):
    profile = profile if isinstance(profile, dict) else {}
    policy = profile.get("sanPolicy", {}) if isinstance(profile.get("sanPolicy"), dict) else {}
    subject = profile.get("subject", {}) if isinstance(profile.get("subject"), dict) else {}
    return {
        "authorityRef": profile.get("authorityRef"),
        "keyAlgorithm": profile.get("keyAlgorithm", defaults["keyAlgorithm"]),
        "keySize": profile.get("keySize", defaults["keySize"]),
        "validityDays": profile.get("validityDays", defaults["leafValidityDays"]),
        "usages": _string_list(profile.get("usages", defaults["usages"])),
        "sanPolicy": {
            "includeHostDns": policy.get("includeHostDns", defaults["sanPolicy"]["includeHostDns"]),
            "includeHostIp": policy.get("includeHostIp", defaults["sanPolicy"]["includeHostIp"]),
            "includeEndpointFqdns": policy.get("includeEndpointFqdns", defaults["sanPolicy"]["includeEndpointFqdns"]),
            "includeEndpointWildcard": policy.get("includeEndpointWildcard", defaults["sanPolicy"]["includeEndpointWildcard"]),
            "includeEndpointVip": policy.get("includeEndpointVip", defaults["sanPolicy"]["includeEndpointVip"]),
        },
        "subject": dict(defaults["subject"], **subject),
    }


def _consumer_records(topology):
    records = []
    deployments = topology.get("serviceDeployments", {}) if isinstance(topology, dict) else {}
    for deployment_id, deployment in sorted(deployments.items()):
        if not isinstance(deployment, dict):
            continue
        deployment_config = deployment.get("configuration", {}) if isinstance(deployment.get("configuration"), dict) else {}
        members = deployment.get("members", {}) if isinstance(deployment.get("members"), dict) else {}
        for member_id, member in sorted(members.items()):
            if not isinstance(member, dict):
                continue
            member_config = member.get("configuration", {}) if isinstance(member.get("configuration"), dict) else {}
            tls_profile = member_config.get("tlsProfile", deployment_config.get("tlsProfile"))
            if isinstance(tls_profile, str) and tls_profile:
                records.append({
                    "deploymentId": deployment_id,
                    "memberId": member_id,
                    "hostId": member.get("host"),
                    "tlsProfileRef": tls_profile,
                })
    unique = {}
    for record in records:
        unique[(record["deploymentId"], record["memberId"], record.get("hostId"), record["tlsProfileRef"])] = record
    return [unique[key] for key in sorted(unique)]


def _scope_key(scope, consumer):
    if scope == "MEMBER":
        return "%s--%s--%s" % (consumer["tlsProfileRef"], consumer["deploymentId"], consumer["memberId"])
    if scope == "DEPLOYMENT":
        return "%s--%s" % (consumer["tlsProfileRef"], consumer["deploymentId"])
    return "%s--%s" % (consumer["tlsProfileRef"], consumer["hostId"])


def _endpoint_values(resolved_service_endpoints, deployment_ids, policy):
    projection = resolved_service_endpoints if isinstance(resolved_service_endpoints, dict) else {}
    endpoints = projection.get("endpoints", {}) if isinstance(projection.get("endpoints"), dict) else {}
    selected = [endpoints[key] for key in sorted(endpoints) if key in deployment_ids and isinstance(endpoints[key], dict)]
    return {
        "dnsNames": _string_list(name for endpoint in selected for name in endpoint.get("sanDnsNames", [])) if policy["includeEndpointFqdns"] else [],
        "wildcardDnsNames": _string_list(name for endpoint in selected for name in endpoint.get("wildcardDnsNames", [])) if policy["includeEndpointWildcard"] else [],
        "ipAddresses": _string_list(address for endpoint in selected for address in endpoint.get("sanIpAddresses", [])) if policy["includeEndpointVip"] else [],
    }


def resolve_certificate_requests(project_id, topology, host_vars, defaults=None, resolved_service_endpoints=None):
    """Purely derive certificate identity and target plans from topology bindings.

    It returns no key material or resolved secrets.  The generic `tlsProfile`
    reference is deliberately resolved from deployment/member configuration so
    services may opt in without manually creating one scope per Kafka member.
    """
    desired = topology if isinstance(topology, dict) else {}
    defaults = defaults if isinstance(defaults, dict) else {}
    missing_defaults = [key for key in REQUIRED_DEFAULT_KEYS if key not in defaults]
    if missing_defaults or not isinstance(defaults.get("sanPolicy"), dict) or not isinstance(defaults.get("subject"), dict):
        return {"status": "BLOCKED", "findings": [_finding("PKI_DEFAULTS_INVALID", "platform_pki_policy_defaults", "PKI policy defaults must be supplied by the materialization role")], "requests": [], "materializationPlans": []}
    authorities = desired.get("certificateAuthorities", {}) if isinstance(desired.get("certificateAuthorities"), dict) else {}
    profiles = desired.get("certificateProfiles", {}) if isinstance(desired.get("certificateProfiles"), dict) else {}
    tls_profiles = desired.get("tlsProfiles", {}) if isinstance(desired.get("tlsProfiles"), dict) else {}
    findings = []
    grouped = {}
    for consumer in _consumer_records(desired):
        tls_profile = tls_profiles.get(consumer["tlsProfileRef"])
        field = "serviceDeployments.%s.members.%s.configuration.tlsProfile" % (consumer["deploymentId"], consumer["memberId"])
        if not isinstance(tls_profile, dict):
            findings.append(_finding("TLS_PROFILE_NOT_FOUND", field, "TLS profile reference is not defined"))
            continue
        profile_ref = tls_profile.get("certificateProfileRef")
        profile = profiles.get(profile_ref)
        if not isinstance(profile, dict):
            findings.append(_finding("CERTIFICATE_PROFILE_NOT_FOUND", field, "TLS profile references an unknown certificate profile"))
            continue
        authority_ref = profile.get("authorityRef")
        authority = authorities.get(authority_ref)
        if not isinstance(authority, dict) or authority.get("mode") != "MANAGED":
            findings.append(_finding("CERTIFICATE_AUTHORITY_UNSUPPORTED", field, "TLS profile requires a defined MANAGED certificate authority"))
            continue
        if not consumer.get("hostId"):
            findings.append(_finding("CERTIFICATE_CONSUMER_HOST_REQUIRED", field, "TLS certificate consumer has no physical host placement"))
            continue
        scope = tls_profile.get("scope", defaults["scope"])
        if scope not in ("HOST", "MEMBER", "DEPLOYMENT"):
            findings.append(_finding("CERTIFICATE_SCOPE_INVALID", field, "TLS profile scope must be HOST, MEMBER or DEPLOYMENT"))
            continue
        grouped.setdefault(_scope_key(scope, consumer), {"scope": scope, "tlsProfile": tls_profile, "tlsProfileId": consumer["tlsProfileRef"], "profileRef": profile_ref, "authorityRef": authority_ref, "consumers": []})["consumers"].append(consumer)
    if findings:
        return {"status": "BLOCKED", "findings": findings, "requests": [], "materializationPlans": []}

    requests, plans = [], []
    for scope_id, group in sorted(grouped.items()):
        profile = _profile_defaults(profiles[group["profileRef"]], defaults)
        authority = authorities[group["authorityRef"]]
        consumers = sorted(group["consumers"], key=lambda value: (value["hostId"], value["deploymentId"], value["memberId"]))
        hosts = _string_list(value["hostId"] for value in consumers)
        identities = [_host_identity(host_id, host_vars) for host_id in hosts]
        dns_names = _string_list(name for identity in identities for name in identity["dnsNames"]) if profile["sanPolicy"]["includeHostDns"] else []
        ip_addresses = _string_list(address for identity in identities for address in identity["ipAddresses"]) if profile["sanPolicy"]["includeHostIp"] else []
        endpoint_values = _endpoint_values(resolved_service_endpoints, set(value["deploymentId"] for value in consumers), profile["sanPolicy"])
        dns_names = _string_list(dns_names + endpoint_values["dnsNames"] + endpoint_values["wildcardDnsNames"])
        ip_addresses = _string_list(ip_addresses + endpoint_values["ipAddresses"])
        request = {
            "id": scope_id,
            "projectId": project_id,
            "scope": group["scope"],
            "profileId": group["profileRef"],
            "authorityId": group["authorityRef"],
            "authorityCommonName": authority.get("commonName", group["authorityRef"]),
            "authorityValidityDays": authority.get("validityDays", defaults["authorityValidityDays"]),
            "commonName": (dns_names or ip_addresses or [scope_id])[0],
            "dnsNames": dns_names,
            "ipAddresses": ip_addresses,
            "keyAlgorithm": profile["keyAlgorithm"],
            "keySize": profile["keySize"],
            "validityDays": profile["validityDays"],
            "usages": profile["usages"],
            "subject": profile["subject"],
            "consumers": consumers,
        }
        unsafe_values = [request["commonName"]] + request["dnsNames"] + request["ipAddresses"] + [request["authorityCommonName"]] + [value for value in request["subject"].values() if value]
        if not all(_safe_identity_value(value) for value in unsafe_values):
            findings.append(_finding("CERTIFICATE_IDENTITY_VALUE_INVALID", "certificateProfiles.%s" % group["profileRef"], "Certificate identity values must not contain control characters"))
            continue
        request["authorityFingerprint"] = canonical_digest({
            "authorityId": request["authorityId"],
            "commonName": request["authorityCommonName"],
            "validityDays": request["authorityValidityDays"],
            "mode": authority.get("mode"),
        })
        request["certificateRequestFingerprint"] = canonical_digest(request)
        requests.append(request)
        for host_id in hosts:
            target_root = "%s/%s/%s" % (defaults["targetRoot"].rstrip("/"), project_id, scope_id)
            plan = {
                "id": "%s--%s" % (scope_id, host_id),
                "requestId": scope_id,
                "tlsProfileId": group["tlsProfileId"],
                "authorityId": group["authorityRef"],
                "hostId": host_id,
                "targetDirectory": target_root,
                "formats": ["PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE"],
                "keyAlias": "platform-%s" % scope_id.replace("_", "-"),
                "trustAlias": "platform-ca-%s" % group["authorityRef"].replace("_", "-"),
                "storePasswordSecretRef": group["tlsProfile"].get("storePasswordSecretRef"),
            }
            plan["materializationFingerprint"] = canonical_digest({
                "requestFingerprint": request["certificateRequestFingerprint"],
                "hostId": host_id,
                "targetDirectory": target_root,
                "formats": plan["formats"],
                "keyAlias": plan["keyAlias"],
                "trustAlias": plan["trustAlias"],
            })
            plans.append(plan)
    if findings:
        return {"status": "BLOCKED", "findings": findings, "requests": [], "materializationPlans": []}
    return {"status": "PASS", "findings": [], "requests": requests, "materializationPlans": plans}
