"""Validate literal chrony.conf inputs using standard IP parsing."""

import csv
import ipaddress
import re


DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


def source_name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 253 or "%" in value:
        return ""
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        name = value.removesuffix(".")
        labels = name.split(".")
        if not all(DNS_LABEL.fullmatch(label) for label in labels):
            return ""
        if all(label.isascii() and label.isdecimal() for label in labels):
            return ""
        return name.lower()


def valid_network(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Fa-f:.]+/[0-9]{1,3}", value):
        return False
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        return False
    return True


def synchronized_to(output, source):
    expected = source_name(source)
    return bool(expected) and any(
        len(row) >= 3 and row[:2] == ["^", "*"] and source_name(row[2]) == expected
        for row in csv.reader(output.splitlines())
    )


class FilterModule:
    def filters(self):
        return {
            "source_name": source_name,
            "valid_network": valid_network,
            "synchronized_to": synchronized_to,
        }
