#VERIFY PROJECT
sudo python3 - <<'PY'
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

expected = "sha256:c5e6f733ec8d"
runtime = Path("/var/lib/platform-installer/runtime/current").resolve()
collections = runtime / "ansible-core/collections"
utils = collections / "ansible_collections/platform/core/plugins/module_utils"
sys.path.insert(0, str(utils))
from project_snapshot import project_documents

base = Path("/var/lib/platform-installer/execution/project-archives")
archives = sorted(base.glob("*/project.tar"),
                  key=lambda p: p.stat().st_mtime, reverse=True)

for archive in archives:
    with tempfile.TemporaryDirectory(prefix="installer-core-check-") as temporary:
        project = Path(temporary)

        with tarfile.open(archive) as package:
            members = package.getmembers()
            if any(
                Path(m.name).is_absolute()
                or ".." in Path(m.name).parts
                or not (m.isfile() or m.isdir())
                for m in members
            ):
                continue
            package.extractall(project, members=members)

        _, revision = project_documents(str(project))
        if not revision.startswith(expected):
            continue

        print("Ревизия:", revision, flush=True)
        print("Архив:", archive, flush=True)

        env = dict(os.environ)
        env["ANSIBLE_CONFIG"] = str(runtime / "ansible-core/ansible.cfg")
        env["ANSIBLE_STDOUT_CALLBACK"] = "default"
        env["ANSIBLE_COLLECTIONS_PATH"] = os.pathsep.join(
            [str(collections)] +
            [str(p) for p in sorted(
                runtime.glob("services/*/ansible_collections"))]
        )

        variables = {
            "platform_project_root": str(project),
            "platform_project_manifest_path": str(project / "project.yml"),
            "platform_service_catalog_path":
                str(runtime / "catalog/service-catalog.yml"),
        }
        result = subprocess.run([
            "ansible-playbook",
            "-i", str(project / "inventory/hosts.yml"),
            str(runtime / "ansible-core/playbooks/project-snapshot-machine.yml"),
            "-e", json.dumps(variables),
            "-vvv",
        ], env=env)
        raise SystemExit(result.returncode)

raise SystemExit(
    "Архив нужной ревизии не найден. Повторите проверку проекта "
    "и убедитесь, что команда выполняется на выбранном узле выполнения."
)
PY
#===============================================================================================================
#CHECK_TASK
ansible node1 \
  -i 'node1,' \
  -e 'ansible_host=IP_NODE1' \
  -u scada-docker \
  --ask-pass \
  --become --ask-become-pass \
  -m ansible.builtin.slurp \
  -a 'src=/etc/platform-installer/pki/project-bc8d04c2dcc8c9e4/installer-tls--node1/ca-chain.pem'


sudo find /var/lib/platform-installer/execution/runs \
  -type f -path '*/raw-ansible-diagnostics/ansible-output-*.log' \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n'

  
