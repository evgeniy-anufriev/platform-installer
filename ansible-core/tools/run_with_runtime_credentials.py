#!/usr/bin/env python3
"""Run Ansible with ephemeral bootstrap credentials outside the project tree."""

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


ALLOWED_CREDENTIAL_KEYS = {"ansible_password", "ansible_become_password", "privateKey"}


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
    if ("ansible_password" in payload) == ("privateKey" in payload):
        raise ValueError("exactly one SSH credential is required")
    if any(not isinstance(value, str) or not value for value in payload.values()):
        raise ValueError("credential values must be non-empty strings")
    return payload


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    credentials = load_credentials(args.credentials_file)
    args.runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    details = args.runtime_dir.lstat()
    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or details.st_mode & 0o077:
        raise ValueError("runtime credential directory is unsafe")
    descriptor_path = None
    key_path = None
    try:
        environment = dict(os.environ)
        private_key = credentials.pop("privateKey", None)
        if private_key is not None:
            try:
                key_bytes = private_key.encode("utf-8", "strict")
            except UnicodeError:
                raise ValueError("runtime SSH credential is invalid") from None
            fd, key_path = tempfile.mkstemp(prefix="target-key-", suffix=".pem", dir=args.runtime_dir)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as key_file:
                key_file.write(key_bytes)
            environment["ANSIBLE_PRIVATE_KEY_FILE"] = key_path
        if credentials:
            fd, descriptor_path = tempfile.mkstemp(prefix="bootstrap-", suffix=".json", dir=args.runtime_dir)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as descriptor:
                json.dump(credentials, descriptor)
        command = [*args.command]
        if descriptor_path is not None:
            command.extend(["--extra-vars", "@" + descriptor_path])
        return subprocess.run(command, check=False, env=environment).returncode
    finally:
        if descriptor_path:
            Path(descriptor_path).unlink(missing_ok=True)
        if key_path:
            Path(key_path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
