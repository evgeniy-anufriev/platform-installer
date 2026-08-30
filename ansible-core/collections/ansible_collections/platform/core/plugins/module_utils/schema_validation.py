from __future__ import absolute_import, division, print_function

__metaclass__ = type

"""Offline Draft 2020-12 validation boundary for Platform Core.

The vendored jsonschema implementation is deliberately hidden behind this
small interface.  Callers receive safe structured findings and never consume
jsonschema exception text directly (which could contain a secret value).
"""

import json
import os
import sys
from pathlib import Path


_MODULE_UTILS = os.path.dirname(__file__)
_VENDOR = os.path.join(_MODULE_UTILS, "_vendor")
if _MODULE_UTILS not in sys.path:
    sys.path.insert(0, _MODULE_UTILS)
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

# Explicit qualified imports make Ansible's module dependency packager carry
# the complete offline dependency set into the transferred module. The local
# fallback keeps the pure unit-test import path usable as well.
try:
    # Load under their canonical top-level names first.  pyrsistent's own
    # modules use absolute imports (pyrsistent._pmap, etc.).
    import attr as _vendored_attr
    import pyrsistent as _vendored_pyrsistent
except ImportError:
    from ansible_collections.platform.core.plugins.module_utils._vendor import attr as _vendored_attr
    from ansible_collections.platform.core.plugins.module_utils._vendor import pyrsistent as _vendored_pyrsistent

# Keep Ansible's static AnsiballZ dependency scanner aware of the absolute
# submodules imported by these two vendored packages.
try:
    from ansible_collections.platform.core.plugins.module_utils._vendor.pyrsistent import (
        _pmap, _pvector, _pset, _pbag, _plist, _pdeque, _checked_types,
        _field_common, _precord, _pclass, _immutable, _helpers,
        _transformations, _toolz, typing as _pyrsistent_typing,
    )
    from ansible_collections.platform.core.plugins.module_utils._vendor.attr import (
        _make as _attr_make, _compat as _attr_compat, validators as _attr_validators,
        converters as _attr_converters, filters as _attr_filters, setters as _attr_setters,
        exceptions as _attr_exceptions,
    )
    from ansible_collections.platform.core.plugins.module_utils._vendor.jsonschema import (
        _format as _jsonschema_format, _types as _jsonschema_types,
        exceptions as _jsonschema_exceptions, protocols as _jsonschema_protocols,
        validators as _jsonschema_validators, _validators as _jsonschema_validator_impl,
        _utils as _jsonschema_utils, _legacy_validators as _jsonschema_legacy,
    )
except ImportError:
    from _vendor.pyrsistent import (
        _pmap, _pvector, _pset, _pbag, _plist, _pdeque, _checked_types,
        _field_common, _precord, _pclass, _immutable, _helpers,
        _transformations, _toolz, typing as _pyrsistent_typing,
    )
    from _vendor.attr import (
        _make as _attr_make, _compat as _attr_compat, validators as _attr_validators,
        converters as _attr_converters, filters as _attr_filters, setters as _attr_setters,
        exceptions as _attr_exceptions,
    )
    from _vendor.jsonschema import (
        _format as _jsonschema_format, _types as _jsonschema_types,
        exceptions as _jsonschema_exceptions, protocols as _jsonschema_protocols,
        validators as _jsonschema_validators, _validators as _jsonschema_validator_impl,
        _utils as _jsonschema_utils, _legacy_validators as _jsonschema_legacy,
    )

sys.modules.setdefault("attr", _vendored_attr)
sys.modules.setdefault("pyrsistent", _vendored_pyrsistent)

try:
    import jsonschema as _vendored_jsonschema
except ImportError:
    from ansible_collections.platform.core.plugins.module_utils._vendor import jsonschema as _vendored_jsonschema
sys.modules.setdefault("jsonschema", _vendored_jsonschema)

try:
    from ansible_collections.platform.core.plugins.module_utils._vendor import jsonschema
    from ansible_collections.platform.core.plugins.module_utils._vendor.jsonschema import (
        FormatChecker,
        RefResolver,
    )
    from ansible_collections.platform.core.plugins.module_utils._vendor.jsonschema.exceptions import (
        RefResolutionError,
    )
except ImportError:
    from _vendor import jsonschema
    from _vendor.jsonschema import FormatChecker, RefResolver
    from _vendor.jsonschema.exceptions import RefResolutionError


class SchemaValidationError(Exception):
    """Raised for an invalid local schema or forbidden reference."""


def _no_network(uri):
    raise SchemaValidationError("SCHEMA_EXTERNAL_REF_FORBIDDEN: %s" % uri)


def _json_pointer(path):
    parts = []
    for item in path:
        value = str(item).replace("~", "~0").replace("/", "~1")
        parts.append(value)
    return "/" + "/".join(parts) if parts else ""


def _safe_schema_path(error):
    return _json_pointer(error.absolute_schema_path)


class SchemaValidator(object):
    """Validate documents with a local-only Draft 2020-12 registry."""

    def __init__(self, schema_root):
        self.schema_root = Path(schema_root).resolve()
        self.schemas = {}
        self._load_local_registry()

    def _load_local_registry(self):
        if not self.schema_root.is_dir():
            raise SchemaValidationError(
                "SCHEMA_REGISTRY_NOT_FOUND: %s" % self.schema_root
            )
        for path in sorted(self.schema_root.rglob("*.json")):
            with path.open("r", encoding="utf-8") as source:
                document = json.load(source)
            schema_id = document.get("$id")
            if not isinstance(schema_id, str) or not schema_id:
                continue
            if schema_id in self.schemas:
                raise SchemaValidationError(
                    "SCHEMA_ID_DUPLICATE: %s" % schema_id
                )
            self.schemas[schema_id] = document

    def validate(self, instance, schema_path):
        """Return safe Finding dictionaries for one local schema path."""
        path = Path(schema_path).resolve()
        try:
            path.relative_to(self.schema_root)
        except ValueError:
            raise SchemaValidationError("SCHEMA_PATH_OUTSIDE_REGISTRY")
        with path.open("r", encoding="utf-8") as source:
            schema = json.load(source)
        schema_id = schema.get("$id")
        if not schema_id or self.schemas.get(schema_id) != schema:
            raise SchemaValidationError("SCHEMA_NOT_REGISTERED: %s" % path)

        external_refs = []

        def reject_external(uri):
            external_refs.append(uri)
            raise SchemaValidationError("SCHEMA_EXTERNAL_REF_FORBIDDEN: %s" % uri)

        resolver = RefResolver(
            base_uri=schema_id,
            referrer=schema,
            store=self.schemas,
            handlers={
                "http": reject_external,
                "https": reject_external,
                "file": reject_external,
            },
        )
        validator = jsonschema.Draft202012Validator(
            schema,
            resolver=resolver,
            format_checker=FormatChecker(),
        )
        try:
            errors = sorted(
                validator.iter_errors(instance),
                key=lambda error: (_json_pointer(error.absolute_path), _safe_schema_path(error)),
            )
        except SchemaValidationError:
            raise
        except RefResolutionError as error:
            if external_refs:
                raise SchemaValidationError(
                    "SCHEMA_EXTERNAL_REF_FORBIDDEN: %s" % external_refs[0]
                )
            cause = error
            for _ in range(8):
                cause = getattr(cause, "_cause", cause)
                if isinstance(cause, SchemaValidationError):
                    raise cause
                if str(cause).startswith("SCHEMA_EXTERNAL_REF_FORBIDDEN:"):
                    raise SchemaValidationError(str(cause))
                if not isinstance(cause, RefResolutionError):
                    break
            raise SchemaValidationError(
                "SCHEMA_VALIDATION_ENGINE_ERROR: %s" % error.__class__.__name__
            )
        except Exception as error:
            if external_refs:
                raise SchemaValidationError(
                    "SCHEMA_EXTERNAL_REF_FORBIDDEN: %s" % external_refs[0]
                )
            raise SchemaValidationError(
                "SCHEMA_VALIDATION_ENGINE_ERROR: %s" % error.__class__.__name__
            )
        findings = []
        for error in errors:
            findings.append(
                {
                    "apiVersion": "platform.installer/finding/v1alpha1",
                    "kind": "Finding",
                    "code": "SCHEMA_VALIDATION_FAILED",
                    "status": "BLOCKED",
                    "category": "schema-validation",
                    "field": _json_pointer(error.absolute_path),
                    "safeMessage": "Значение не соответствует опубликованной схеме",
                    "safeDetails": {
                        "schema": schema_id,
                        "keyword": error.validator,
                        "schemaPath": _safe_schema_path(error),
                    },
                }
            )
        return findings
