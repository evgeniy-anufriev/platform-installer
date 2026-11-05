from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
    from .service_endpoint_resolution import DNS_DOMAIN, DNS_LABEL
except ImportError:
    from project_validation import canonical_digest
    from service_endpoint_resolution import DNS_DOMAIN, DNS_LABEL


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


def _consumer_records(topology, inventory_deployments=None):
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
        # Host-scoped services use inventory placement instead of logical
        # members.  Preserve the same generic tlsProfile contract.
        for host_id, placements in sorted((inventory_deployments or {}).items()):
            placement = placements.get(deployment_id) if isinstance(placements, dict) else None
            if not isinstance(placement, dict):
                continue
            placement_config = placement.get("configuration", {}) if isinstance(placement.get("configuration"), dict) else {}
            tls_profile = placement_config.get("tlsProfile", deployment_config.get("tlsProfile"))
            if isinstance(tls_profile, str) and tls_profile:
                records.append({
                    "deploymentId": deployment_id, "memberId": "host--%s" % host_id,
                    "hostId": host_id, "tlsProfileRef": tls_profile,
                })
    unique = {}
    for record in records:
        unique[(record["deploymentId"], record["memberId"], record.get("hostId"), record["tlsProfileRef"])] = record
    return [unique[key] for key in sorted(unique)]


def _scope_key(scope, consumer):
    if scope == "PROJECT":
        return consumer["tlsProfileRef"] + "--project"
    if scope == "MEMBER":
        return "%s--%s--%s" % (consumer["tlsProfileRef"], consumer["deploymentId"], consumer["memberId"])
    if scope == "DEPLOYMENT":
        return "%s--%s" % (consumer["tlsProfileRef"], consumer["deploymentId"])
    return "%s--%s" % (consumer["tlsProfileRef"], consumer["hostId"])


def _endpoint_values(topology, resolved_service_endpoints, deployment_ids, policy, host_id=None, application_endpoints=(), include_application_vips=False):
    projection = resolved_service_endpoints if isinstance(resolved_service_endpoints, dict) else {}
    endpoints = projection.get("endpoints", {}) if isinstance(projection.get("endpoints"), dict) else {}
    selected = [endpoints[key] for key in sorted(endpoints) if key in deployment_ids and isinstance(endpoints[key], dict)]
    host_endpoints = projection.get("hostEndpoints", {}) if isinstance(projection.get("hostEndpoints"), dict) else {}
    selected_host = [value for value in host_endpoints.values() if isinstance(value, dict)
                     and value.get("serviceDeploymentId") in deployment_ids
                     and (host_id is None or value.get("hostId") == host_id)]
    application_endpoints = list(application_endpoints)
    endpoint_groups = set(
        endpoint.get("endpointGroupId")
        for endpoint in selected + (application_endpoints if include_application_vips else [])
        if isinstance(endpoint.get("endpointGroupId"), str)
    )
    deployments = topology.get("serviceDeployments", {}) if isinstance(topology, dict) else {}
    provider_addresses = []
    if policy["includeEndpointVip"]:
        for deployment_id in sorted(deployments):
            deployment = deployments[deployment_id]
            if not isinstance(deployment, dict) or deployment.get("endpointGroupRef") not in endpoint_groups:
                continue
            virtual_addresses = deployment.get("virtualAddresses", [])
            if isinstance(virtual_addresses, list):
                provider_addresses.extend(
                    address.get("address") for address in virtual_addresses
                    if isinstance(address, dict) and _looks_like_ip(address.get("address"))
                )
    dns_endpoints = selected + selected_host + application_endpoints
    return {
        "dnsNames": _string_list(name for endpoint in dns_endpoints for name in endpoint.get("sanDnsNames", [])) if policy["includeEndpointFqdns"] else [],
        "wildcardDnsNames": _string_list(name for endpoint in dns_endpoints for name in endpoint.get("wildcardDnsNames", [])) if policy["includeEndpointWildcard"] else [],
        "ipAddresses": _string_list(provider_addresses),
    }


def application_pki_bindings(rows, desired):
    """Project only the TLS placement and endpoint identity needed for PKI."""
    bindings = {}
    for row in rows:
        endpoint = row["settings"].get("endpoint", {})
        names = None
        if endpoint.get("enabled") and endpoint.get("protocol") == "https":
            group_id = endpoint.get("endpoint_group")
            group = desired.get("endpointGroups", {}).get(group_id, {})
            domain = (group.get("address") or {}).get("domain")
            instance_id = row["instanceId"]
            if (isinstance(domain, str) and DNS_DOMAIN.fullmatch(domain) and
                    isinstance(instance_id, str) and DNS_LABEL.fullmatch(instance_id)):
                names = {"sanDnsNames": [instance_id + "." + domain],
                         "wildcardDnsNames": ["*." + domain], "endpointGroupId": group_id}
        for binding in row.get("bindings", {}).values():
            profile = binding.get("profileRef")
            if profile:
                host = row["hostId"]
                key = (host, profile, group_id, instance_id) if names else (host, profile, "", "")
                record = {"hostId": host, "tlsProfileId": profile}
                if names:
                    record["endpoint"] = names
                bindings[key] = record
    return [bindings[key] for key in sorted(bindings)]


def materialization_fingerprint(request_fingerprint, plan):
    return canonical_digest({
        "requestFingerprint": request_fingerprint,
        **{key: plan[key] for key in ("hostId", "targetDirectory", "formats", "keyAlias", "trustAlias")},
    })


def resolve_certificate_requests(project_id, topology, host_vars, defaults=None, resolved_service_endpoints=None, inventory_deployments=None, application_rows=(), application_bindings=None):
    """Purely derive certificate identity and target plans from topology bindings.

    It returns no key material or resolved secrets.  The generic `tlsProfile`
    reference is deliberately resolved from deployment/member configuration so
    services may opt in without manually creating one scope per Kafka member.
    """
    desired = topology if isinstance(topology, dict) else {}
    if application_bindings is None:
        application_bindings = application_pki_bindings(application_rows, desired)
    defaults = defaults if isinstance(defaults, dict) else {}
    missing_defaults = [key for key in REQUIRED_DEFAULT_KEYS if key not in defaults]
    if missing_defaults or not isinstance(defaults.get("sanPolicy"), dict) or not isinstance(defaults.get("subject"), dict):
        return {"status": "BLOCKED", "findings": [_finding("PKI_DEFAULTS_INVALID", "platform_pki_policy_defaults", "PKI policy defaults must be supplied by the materialization role")], "requests": [], "materializationPlans": []}
    authorities = desired.get("certificateAuthorities", {}) if isinstance(desired.get("certificateAuthorities"), dict) else {}
    profiles = desired.get("certificateProfiles", {}) if isinstance(desired.get("certificateProfiles"), dict) else {}
    tls_profiles = desired.get("tlsProfiles", {}) if isinstance(desired.get("tlsProfiles"), dict) else {}
    findings = []
    grouped = {}
    project_profiles = sorted(key for key, value in tls_profiles.items()
                              if isinstance(value, dict) and value.get("scope", defaults["scope"]) == "PROJECT")
    if len(project_profiles) > 1:
        return {"status": "BLOCKED", "findings": [_finding(
            "PROJECT_TLS_PROFILE_CONFLICT", "tlsProfiles", "Only one TLS profile may have PROJECT scope")],
            "requests": [], "materializationPlans": []}
    application_hosts = set()
    if project_profiles:
        project_profile = project_profiles[0]
        application_hosts = {
            binding["hostId"] for binding in application_bindings
            if binding["tlsProfileId"] == project_profile
        }
    consumers = _consumer_records(desired, inventory_deployments)
    if application_hosts:
        consumers.append({"tlsProfileRef": project_profile, "hostId": min(application_hosts)})
    for consumer in consumers:
        tls_profile = tls_profiles.get(consumer["tlsProfileRef"])
        service_consumer = "deploymentId" in consumer
        field = ("serviceDeployments.%s.members.%s.configuration.tlsProfile" % (consumer["deploymentId"], consumer["memberId"])
                 if service_consumer else "tlsProfiles.%s" % consumer["tlsProfileRef"])
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
        if scope not in ("HOST", "MEMBER", "DEPLOYMENT", "PROJECT"):
            findings.append(_finding("CERTIFICATE_SCOPE_INVALID", field, "TLS profile scope must be HOST, MEMBER, DEPLOYMENT or PROJECT"))
            continue
        scope_id = _scope_key(scope, consumer)
        group = grouped.setdefault(scope_id, {"scope": scope, "tlsProfile": tls_profile, "tlsProfileId": consumer["tlsProfileRef"], "profileRef": profile_ref, "authorityRef": authority_ref, "consumers": []})
        if group["tlsProfileId"] != consumer["tlsProfileRef"] and "PROJECT" in (scope, group["scope"]):
            findings.append(_finding("CERTIFICATE_SCOPE_ID_CONFLICT", field, "PROJECT certificate identity conflicts with another TLS profile"))
            continue
        if service_consumer:
            group["consumers"].append(consumer)
    if findings:
        return {"status": "BLOCKED", "findings": findings, "requests": [], "materializationPlans": []}

    requests, plans = [], []
    application_endpoints = {}
    for binding in application_bindings:
        if "endpoint" in binding:
            key = (binding["hostId"], binding["tlsProfileId"])
            application_endpoints.setdefault(key, []).append(binding["endpoint"])
    for scope_id, group in sorted(grouped.items()):
        profile = _profile_defaults(profiles[group["profileRef"]], defaults)
        authority = authorities[group["authorityRef"]]
        consumers = sorted(group["consumers"], key=lambda value: (value["hostId"], value["deploymentId"], value["memberId"]))
        hosts = _string_list(value["hostId"] for value in consumers)
        if group["scope"] == "PROJECT":
            hosts = _string_list(hosts + list(application_hosts))
        identities = [_host_identity(host_id, host_vars) for host_id in hosts]
        dns_names = _string_list(name for identity in identities for name in identity["dnsNames"]) if profile["sanPolicy"]["includeHostDns"] else []
        ip_addresses = _string_list(address for identity in identities for address in identity["ipAddresses"]) if profile["sanPolicy"]["includeHostIp"] else []
        endpoint_values = _endpoint_values(
            desired, resolved_service_endpoints, {value["deploymentId"] for value in consumers},
            profile["sanPolicy"], hosts[0] if len(hosts) == 1 else None,
            application_endpoints=(
                endpoint for host_id in hosts
                for endpoint in application_endpoints.get((host_id, group["tlsProfileId"]), ())
            ),
            include_application_vips=group["scope"] == "PROJECT",
        )
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
        if group["scope"] == "PROJECT":
            request["tlsProfileId"] = group["tlsProfileId"]
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
            plan["materializationFingerprint"] = materialization_fingerprint(
                request["certificateRequestFingerprint"], plan)
            plans.append(plan)
    if findings:
        return {"status": "BLOCKED", "findings": findings, "requests": [], "materializationPlans": []}
    return {"status": "PASS", "findings": [], "requests": requests, "materializationPlans": plans}
