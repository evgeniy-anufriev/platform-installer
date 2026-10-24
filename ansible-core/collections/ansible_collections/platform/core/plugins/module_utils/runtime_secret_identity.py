"""Opaque deployment-bound identities shared by existing runtime-secret projections."""
import hashlib
import json


def generated_password_ref(project, library, instance, account):
    encoded = json.dumps([project, library, instance, account], ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return "pla-generated-" + hashlib.sha256(encoded).hexdigest()[:40]


def secret_input_requirement_ref(service_deployment, manifest_requirement_ref, purpose):
    encoded = json.dumps([service_deployment, manifest_requirement_ref, purpose], ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "si-" + hashlib.sha256(encoded).hexdigest()[:40]
