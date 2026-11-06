#!/bin/sh
# Run on the Execution Node with an archive from a trusted project.
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    echo "Usage: sudo sh $0 <full-sha256-revision> [library@version] [application@version]" >&2
    exit 2
fi

python3 -B - "$1" "${2:-sdku@1.0.0}" "${3:-data-manager@1.0.0}" <<'PY'
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

import yaml

expected, library_ref, app_ref = sys.argv[1:]
if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
    raise SystemExit("Укажите полный sha256 из сообщения Verify.")
if any(not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*@[0-9]+\.[0-9]+\.[0-9]+", ref)
       for ref in (library_ref, app_ref)):
    raise SystemExit("Укажите ссылки на пакеты в формате имя@версия.")

runtime = Path("/var/lib/platform-installer/runtime/current").resolve()
collections = runtime / "ansible-core/collections"
utils = collections / "ansible_collections/platform/core/plugins/module_utils"
if not (utils / "project_snapshot.py").is_file() or not (runtime / "contracts").is_dir():
    raise SystemExit("Активный runtime Installer не найден.")
sys.path.insert(0, str(utils))
from application_libraries import load_package
from project_snapshot import project_documents
from schema_validation import SchemaValidator

SAFE_PACKAGE_ERRORS = {
    "APPLICATION_PACKAGE_VERSION_UNSUPPORTED",
    "Defaults absent from allowlist",
    "Defaults identity mismatch",
    "Duplicate package script identity",
    "Invalid exact package reference",
    "Invalid package component",
    "Invalid package directory",
    "Invalid package path",
    "Library dotenv contract invalid",
    "Package allowlist mismatch",
    "Package defaults namespace invalid",
    "Package defaults shape invalid",
    "Package directory symlink",
    "Package file limit exceeded",
    "Package file missing",
    "Package identity mismatch",
    "Package manifest shape invalid",
    "Package path escapes project",
    "Package root must not be a symlink",
    "Package script is not allowlisted",
    "Package script reference invalid",
    "Package symlinks are forbidden",
}


class PackageYamlError(Exception):
    pass


def read_yaml(path, project):
    try:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = f", строка {mark.line + 1}, столбец {mark.column + 1}" if mark else ""
        raise PackageYamlError(f"{Path(path).relative_to(project)}{location}") from None


def verify(project):
    validator = SchemaValidator(str(runtime / "contracts"))
    packages_ok = True
    for kind, ref in (("library", library_ref), ("application", app_ref)):
        try:
            load_package(str(project), ref, kind, lambda path: read_yaml(path, project), validator)
        except PackageYamlError as error:
            print(f"{kind} {ref}: ошибка YAML в {error}")
            packages_ok = False
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            reason = str(error)
            print(f"{kind} {ref}: {reason if reason in SAFE_PACKAGE_ERRORS else type(error).__name__}")
            packages_ok = False
        else:
            print(f"{kind} {ref}: OK")

    snapshot = project.parent / "verify-snapshot.json"
    env = dict(os.environ,
               ANSIBLE_CONFIG=str(runtime / "ansible-core/ansible.cfg"),
               ANSIBLE_STDOUT_CALLBACK="default",
               ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json",
               PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(snapshot),
               ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(
                   [str(collections)] + [str(p) for p in sorted(runtime.glob("services/*/ansible_collections"))]))
    variables = {
        "platform_project_root": str(project),
        "platform_project_manifest_path": str(project / "project.yml"),
        "platform_service_catalog_path": str(runtime / "catalog/service-catalog.yml"),
    }
    result = subprocess.run([
        "ansible-playbook", "-i", str(project / "inventory/hosts.yml"),
        str(runtime / "ansible-core/playbooks/project-snapshot-machine.yml"), "-e", json.dumps(variables),
    ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if not snapshot.is_file():
        print(f"Снимок Verify не создан. Код выхода Ansible: {result.returncode}")
        return 1
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    print("Статус Verify:", document.get("status"))
    for finding in document.get("findings", []):
        print(json.dumps({key: finding[key] for key in ("code", "field", "safeMessage")
                          if key in finding}, ensure_ascii=False))
    return 0 if packages_ok and result.returncode == 0 and document.get("status") == "PASS" else 1


base = Path("/var/lib/platform-installer/execution/project-archives")
archives = sorted((p for p in base.glob("*/project.tar") if p.is_file() and not p.is_symlink()),
                  key=lambda p: p.stat().st_mtime, reverse=True)
for archive in archives:
    with tempfile.TemporaryDirectory(prefix="installer-core-check-") as temporary:
        project = Path(temporary) / "project"
        project.mkdir(mode=0o700)
        try:
            with tarfile.open(archive) as package:
                members = package.getmembers()
                if any(Path(m.name).is_absolute() or ".." in Path(m.name).parts
                       or not (m.isfile() or m.isdir()) for m in members):
                    continue
                for member in members:
                    member.mode = 0o700 if member.isdir() else 0o600
                    member.uid, member.gid = os.geteuid(), os.getegid()
                    member.uname = member.gname = ""
                package.extractall(project, members=members, numeric_owner=False)
            _, revision = project_documents(str(project))
        except (OSError, tarfile.TarError, ValueError):
            continue
        if revision == expected:
            print("Ревизия:", revision)
            print("Архив:", archive)
            raise SystemExit(verify(project))

raise SystemExit("Архив указанной ревизии не найден на этом Execution Node.")
PY
