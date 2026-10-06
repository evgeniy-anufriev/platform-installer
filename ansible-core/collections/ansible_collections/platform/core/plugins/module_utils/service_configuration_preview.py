"""Closed, presentation-only admission for ordinary service setting values.

This is deliberately narrower than service configuration validation. It is
shared by the immutable bundle builder and the target-free Core projection so
neither producer serializes a value that the UI is not permitted to display.
"""

import math
import re


_REFERENCE = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
_DNS_PATTERN = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,63}$"
_DNS = re.compile(_DNS_PATTERN)
_EXPRESSION_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value)) and abs(value) <= 2 ** 53
    except (OverflowError, ValueError):
        return False


def _integer(value):
    return _number(value) and float(value).is_integer()


def _safe_text(value):
    if not isinstance(value, str):
        return False
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return False
    return (size <= 4096 and not any(ord(char) < 32 or ord(char) == 127 for char in value)
            and not any(marker in value for marker in _EXPRESSION_MARKERS))


def ordinary_presentation_value(setting, value):
    """Return True only for a manifest-proven closed editor shape and value."""
    if not isinstance(setting, dict) or setting.get("kind") != "MANAGED" or setting.get("schema"):
        return False
    ui = setting.get("ui", {})
    validation = setting.get("validation", {})
    if not isinstance(ui, dict) or "x-runtimeSecretRequirement" in ui or not isinstance(validation, dict):
        return False
    value_type = setting.get("type")
    reference = ui.get("x-referenceKind")
    if reference is not None:
        return (reference in ("TLS_PROFILE", "SERVICE_DEPLOYMENT") and value_type == "string"
                and set(validation) == {"minLength"} and type(validation["minLength"]) is int and validation["minLength"] == 1
                and _safe_text(value) and len(value) <= 128 and _REFERENCE.fullmatch(value) is not None)
    if set(validation) == {"enum"}:
        choices = validation["enum"]
        if not isinstance(choices, list) or not 1 <= len(choices) <= 256:
            return False
        if value_type == "string":
            return _safe_text(value) and value in choices and all(isinstance(item, str) for item in choices)
        if value_type == "boolean":
            return isinstance(value, bool) and value in choices and all(isinstance(item, bool) for item in choices)
        if value_type in ("integer", "number"):
            numeric = _integer if value_type == "integer" else _number
            return numeric(value) and all(numeric(item) for item in choices) and value in choices
        return False
    if value_type == "boolean":
        return not validation and isinstance(value, bool)
    if value_type in ("integer", "number"):
        if set(validation) != {"minimum", "maximum"}:
            return False
        minimum, maximum = validation["minimum"], validation["maximum"]
        numeric = _integer if value_type == "integer" else _number
        return numeric(value) and numeric(minimum) and numeric(maximum) and minimum <= value <= maximum
    if value_type != "string" or not _safe_text(value):
        return False
    if set(validation) == {"minLength", "maxLength", "pattern"}:
        return (type(validation["minLength"]) is int and type(validation["maxLength"]) is int
                and validation["minLength"] == 4 and validation["maxLength"] == 253
                and validation["pattern"] == _DNS_PATTERN and 4 <= len(value) <= 253
                and _DNS.fullmatch(value) is not None)
    if set(validation) == {"minLength", "maxLength"}:
        minimum, maximum = validation["minLength"], validation["maxLength"]
        return (type(minimum) is int and type(maximum) is int and 0 <= minimum <= maximum <= 4096
                and minimum <= len(value) <= maximum)
    return False
