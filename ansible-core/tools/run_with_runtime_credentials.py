#!/usr/bin/env python3
"""Run Ansible with ephemeral bootstrap credentials outside the project tree."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ALLOWED_CREDENTIAL_KEYS = {"ansible_password", "ansible_become_password"}


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", required=True, type=Path)
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not args.command or args.command[0] != "--":
        parser.error("command must follow '--'")
    args.command = args.command[1:]
    if not args.command:
        parser.error("command must not be empty")
    return args


def load_credentials(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("credential file must contain a non-empty JSON object")
    unexpected = set(payload) - ALLOWED_CREDENTIAL_KEYS
    if unexpected:
        raise ValueError("credential file contains unsupported keys")
    if any(not isinstance(value, str) or not value for value in payload.values()):
        raise ValueError("credential values must be non-empty strings")
    return payload


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    credentials = load_credentials(args.credentials_file)
    args.runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor_path = None
    try:
        fd, descriptor_path = tempfile.mkstemp(prefix="bootstrap-", suffix=".json", dir=args.runtime_dir)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as descriptor:
            json.dump(credentials, descriptor)
        command = [*args.command, "--extra-vars", "@" + descriptor_path]
        return subprocess.run(command, check=False).returncode
    finally:
        if descriptor_path:
            Path(descriptor_path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
