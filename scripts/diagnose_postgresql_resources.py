#!/usr/bin/env python3
"""Summarize existing PostgreSQL provider events without replaying a run.

Run on the Execution Node:
  sudo -n python3 scripts/diagnose_postgresql_resources.py installer-<32 hex digits>

The default report requires only the standard library and does not invoke Core,
Ansible or PostgreSQL. Module output and runtime secrets are not displayed.

Optional --resolve-provider-inputs runs target-free Core/Ansible calculation on
the Execution Node using the saved run project and application projection.
It creates only private temporary diagnostic files, removed on completion.
Completed runs use their recorded release digest and nonsecret manifest
parameters when the transient application projection has been cleaned up.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


BOUNDARY_NAMES = {
    "Проверка всех выбранных ресурсов PostgreSQL до внесения изменений",
    "Создание всех ресурсов библиотеки перед экземплярами",
    "Согласование учетных записей PostgreSQL по развёртываниям",
    "Подготовка обработчиков инфраструктурных учётных записей и ресурсов по общему снимку",
    "Фиксация завершения подготовки",
}
RESOURCE_NAMES = (
    "создание только отсутствующей базы данных",
    "проверка или создание ролей и баз данных",
    "восстановление дампа формата custom",
    "маркировка владельца только после успешного восстановления",
)
PREPARATION_TIMELINE_NAMES = (
    "Проверка всех выбранных ресурсов PostgreSQL",
    "Создание топиков библиотеки Kafka",
    "Подготовка защищённых PEM-файлов только для Apply",
    "Создание всех ресурсов библиотеки",
    "Фиксация завершения подготовки",
)


def report_runtime(run_id, proc_root=Path("/proc"),
                   current_link=Path("/var/lib/platform-installer/runtime/current")):
    """Read only the matching controller's release argument, never dump argv."""
    print("\nRUNTIME SOURCE CHECK:")
    try:
        current = current_link.resolve(strict=True)
        print("CURRENT:", current)
    except (OSError, RuntimeError):
        current = None
        print("CURRENT: unavailable")
    try:
        processes = list(proc_root.iterdir())
    except OSError:
        print("RUN RELEASE: process information unavailable")
        return []
    found = False
    releases = []
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            argv = (process / "cmdline").read_bytes().decode("utf-8").split("\0")
            if not any(Path(arg).name == "execution_controller.py" for arg in argv):
                continue
            if argv[argv.index("--run-id") + 1] != run_id:
                continue
            release = Path(argv[argv.index("--runtime-release") + 1]).resolve(strict=True)
        except (OSError, ValueError, IndexError, UnicodeError, RuntimeError):
            continue
        found = True
        releases.append(release)
        print("CONTROLLER PID:", process.name)
        print("RUN RELEASE:", release)
        print("MATCH_CURRENT:", release == current if current is not None else "unknown")
        source = release / "ansible-core/playbooks/applications/stages/provider-stage.yml"
        try:
            text = source.read_text(encoding="utf-8")
            print("RESOURCE_CALL_PRESENT:",
                  "Создание всех ресурсов библиотеки перед экземплярами" in text)
        except (OSError, UnicodeError):
            print("RESOURCE_CALL_PRESENT: unknown (source unavailable)")
    if not found:
        print("RUN RELEASE: no matching live controller found or accessible")
        print("The historical run release cannot be inferred from runtime/current.")
    return list(dict.fromkeys(releases))


def recorded_runtime(root, manifest,
                     releases_root=Path("/var/lib/platform-installer/runtime/releases")):
    """Use immutable run identity, never substitute the current release."""
    expected = manifest.get("runtimeRelease", {})
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    digest = expected.get("bundleDigest", "")
    # Start stores the bundle digest in metadata and the release object in
    # the manifest. Also accept the object form used by earlier diagnostics.
    recorded = metadata.get("runtimeRelease")
    if isinstance(recorded, dict):
        recorded = recorded.get("bundleDigest")
    if recorded != digest:
        print("RECORDED RELEASE: metadata/manifest identity mismatch")
        return []
    if not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
        print("RECORDED RELEASE: bundle digest unavailable")
        return []
    release = releases_root / digest[7:]
    if not release.is_dir() or release.is_symlink():
        print("RECORDED RELEASE: required directory unavailable:", release)
        return []
    print("RECORDED RUN RELEASE:", release)
    return [release]


def recompute_provider_inputs(root, release):
    """Opt-in target-free Core calculation; never include provider apply roles."""
    projection = root / (".runtime-projection-" + hashlib.sha256(b"applications:apply").hexdigest() + ".json")
    print("\nRECOMPUTED PROVIDER INPUTS (not a recording of the original Ansible facts):", flush=True)
    with tempfile.TemporaryDirectory(prefix="pg-provider-diagnostic-") as directory:
        temporary = Path(directory)
        if not projection.is_file():
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            operations = [item for item in manifest.get("operations", [])
                          if item.get("operation") == "APPLICATION_LIBRARIES_APPLY"]
            if len(operations) != 1:
                print("RECOMPUTE: one recorded application Apply operation is required")
                return 1
            catalog = release / "catalog/service-catalog.yml"
            if not catalog.is_file():
                print("RECOMPUTE: required runtime catalog unavailable:", catalog)
                return 1
            safe_projection = {
                "platform_project_root": str(root / "project"),
                "platform_project_id": manifest.get("projectIdentity"),
                "platform_service_catalog_path": str(catalog),
                "platform_contracts_root": str(release / "contracts"),
                "platform_execution_bundle_root": str(release),
                "platform_application_library_order": operations[0]["applicationLibraries"],
                "platform_application_pki_bindings": manifest.get("applicationPkiBindings", []),
            }
            if manifest.get("applicationExecutionScope"):
                safe_projection["platform_application_execution_scope"] = manifest["applicationExecutionScope"]
            projection = temporary / "diagnostic-projection.json"
            projection.write_text(json.dumps(safe_projection), encoding="utf-8")
            print("PROJECTION SOURCE: recorded manifest; runtime credentials are not reconstructed")
        else:
            print("PROJECTION SOURCE: existing application projection")
        output = temporary / "summary.json"
        tasks = [
            {"ansible.builtin.include_role": {"name": "platform.core.project_settings"}},
            {"ansible.builtin.include_role": {"name": "platform.core.resolve_application_libraries"}},
            {"platform.core.project_snapshot": {
                "project_root": "{{ platform_project_root }}",
                "service_catalog_path": "{{ platform_service_catalog_path }}"},
             "register": "application_snapshot"},
            {"platform.core.prepare_application_selection": {}, "register": "application_selection"},
            {"ansible.builtin.assert": {"that": "application_selection.status == 'PASS'"}},
            {"ansible.builtin.set_fact": {"application_snapshot": "{{ application_selection.prepared }}"}},
            {"platform.core.prepare_application_providers": {
                "project_root": "{{ platform_project_root }}",
                "service_catalog_path": "{{ platform_service_catalog_path }}"},
             "register": "application_provider_inputs"},
            {"ansible.builtin.copy": {"dest": str(output), "mode": "0600", "content": """
{% set result = {'status': application_provider_inputs.status,
                 'snapshotRevision': application_snapshot.snapshot.projectRevision,
                 'findings': application_provider_inputs.findings | default([]) | map(attribute='code') | list} %}
{% for phase in ['jobs', 'libraryJobs', 'instanceJobs'] %}
{% set counts = [] %}
{% for job in application_provider_inputs[phase] | default([]) if job.serviceType == 'postgresql' %}
{% set _ = counts.append({'providerId': job.providerId, 'libraryId': job.libraryId | default('all'),
                         'databaseCount': job.databases | length,
                         'restoreCount': job.databases | selectattr('restoreOnCreate', 'defined') | list | length,
                         'accountCount': job.accounts | length}) %}
{% endfor %}
{% set _ = result.update({phase: counts}) %}
{% endfor %}
{{ result | to_json }}"""}},
        ]
        playbook = temporary / "diagnostic.json"
        playbook.write_text(json.dumps([{
            "hosts": "localhost", "connection": "local", "gather_facts": False,
            "become": False, "no_log": True, "tasks": tasks,
        }]), encoding="utf-8")
        overrides = temporary / "overrides.json"
        overrides.write_text(json.dumps({
            "platform_project_root": str(root / "project"),
            "ansible_connection": "local", "ansible_become": False,
        }), encoding="utf-8")
        collections = [release / "ansible-core/collections"]
        collections.extend(sorted((release / "services").glob("*/ansible_collections")))
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("ANSIBLE_", "PLATFORM_EXECUTION_"))}
        environment.update(
            ANSIBLE_CONFIG=str(release / "ansible-core/ansible.cfg"),
            ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(map(str, collections)),
            ANSIBLE_LOCAL_TEMP=str(temporary / "ansible-tmp"),
            ANSIBLE_SSH_EXECUTABLE="/usr/bin/false", ANSIBLE_LOG_PATH=os.devnull,
            ANSIBLE_STDOUT_CALLBACK="default", ANSIBLE_NOCOLOR="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        try:
            result = subprocess.run([
                "ansible-playbook", "-i", str(root / "project/inventory/hosts.yml"),
                str(playbook), "-e", "@" + str(projection), "-e", "@" + str(overrides),
                "--limit", "localhost",
            ], env=environment, cwd=root / "project", capture_output=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            print("RECOMPUTE: prerequisite failure or timeout; raw output suppressed")
            return 1
        if result.returncode or not output.is_file():
            print("RECOMPUTE: calculation failed; raw Ansible output suppressed")
            return 1
        summary = json.loads(output.read_text(encoding="utf-8"))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("Current saved inputs were recalculated; original libraryJobs is still not persisted.")
        return 0 if summary.get("status") == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="Existing Installer run ID")
    parser.add_argument("--resolve-provider-inputs", action="store_true",
                        help="Recalculate provider inputs locally through Core; no database operations")
    parser.add_argument(
        "--runs-root", type=Path,
        default=Path("/var/lib/platform-installer/execution/runs"),
        help="Directory containing existing run directories",
    )
    args = parser.parse_args()
    if re.fullmatch(r"installer-[0-9a-f]{32}", args.run_id) is None:
        parser.error("expected installer- followed by 32 lowercase hex digits")
    root = args.runs_root / args.run_id
    try:
        status = json.loads((root / "status.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        scope = manifest.get("applicationExecutionScope") or {}
        print("RUN:", args.run_id)
        print("STATE:", status.get("state"))
        print("INSTALL:", scope.get("installLibraries", "not recorded"))
        print("SKIP:", scope.get("skippedLibraries", []))
        if not scope:
            for operation in manifest.get("operations", []):
                if operation.get("operation") == "APPLICATION_LIBRARIES_APPLY":
                    print("APPLY LIBRARIES:", operation.get("applicationLibraries", []))

        tasks = Counter()
        boundaries = Counter()
        timeline = []
        resource_tasks = Counter()
        invalid = 0
        failures = []
        with (root / "events.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    task = event.get("task") or {}
                    name = task.get("name", "?")
                    result = event.get("status", "?")
                    event_type = event.get("eventType")
                    if (event_type in ("TASK_STARTED", "TASK_COMPLETED")
                            and isinstance(name, str)
                            and any(label in name for label in PREPARATION_TIMELINE_NAMES)):
                        timeline.append([
                            event.get("sequence"), event_type, result,
                            task.get("role") or "-", name,
                        ])
                    if result == "FAILED":
                        code = (event.get("error") or {}).get("code", "")
                        failures.append({
                            "eventType": event.get("eventType"),
                            "actionId": event.get("actionId"),
                            "task": name,
                            "code": code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code) else "",
                        })
                    if name in BOUNDARY_NAMES:
                        boundaries[(event.get("eventType", "?"), result, name)] += 1
                    if (event.get("eventType") == "TASK_COMPLETED"
                            and isinstance(name, str)
                            and any(label in name.lower() for label in RESOURCE_NAMES)):
                        resource_tasks[(task.get("role", "<no role>"), result, name)] += 1
                    if (event.get("eventType") == "TASK_COMPLETED"
                            and task.get("role") == "platform.postgresql.application_provider"):
                        tasks[(task.get("name", "?"), event.get("status", "?"))] += 1
                except (ValueError, AttributeError, TypeError):
                    invalid += 1

        print("\nPOSTGRESQL PROVIDER COMPLETED TASKS:")
        for (name, result), count in tasks.items():
            print("%s x%d %s" % (json.dumps(result, ensure_ascii=False), count,
                                  json.dumps(name, ensure_ascii=False)))
        if not tasks:
            print("No matching completed tasks in the available journal.")
        print("\nPROVIDER CALL BOUNDARIES (including tasks outside roles):")
        for (event_type, result, name), count in boundaries.items():
            print(json.dumps([event_type, result, count, name], ensure_ascii=False))
        if not boundaries:
            print("No matching boundary events recorded; this alone does not prove a skipped call.")
        print("\nKAFKA / POSTGRESQL PREPARATION TIMELINE (journal order):")
        for row in timeline:
            print(json.dumps(row, ensure_ascii=False))
        if not timeline:
            print("No matching preparation events recorded.")
        print("\nDATABASE RESOURCE TASKS (any role):")
        for (role, result, name), count in resource_tasks.items():
            print(json.dumps([role, result, count, name], ensure_ascii=False))
        if not resource_tasks:
            print("No matching completed resource tasks recorded.")
        print("\nINCOMPLETE_OR_INVALID_EVENT_ROWS:", invalid)
        print("\nLAST FAILURE IDENTITIES (no module output):")
        for failure in failures[-5:]:
            print(json.dumps(failure, ensure_ascii=False))
        print("An active run can append events after this snapshot.")
        print("libraryJobs is transient Ansible state; this report cannot recover it.")
        releases = report_runtime(args.run_id)
        if args.resolve_provider_inputs:
            if not releases:
                releases = recorded_runtime(root, manifest)
            if len(releases) != 1:
                print("RECOMPUTE: exactly one accessible recorded or live run release is required")
                return 1
            return recompute_provider_inputs(root, releases[0])
        return 0
    except FileNotFoundError as error:
        print("Required file not found: %s" % error.filename, file=sys.stderr)
    except PermissionError:
        print("Access denied: run with the established Execution Node sudo identity.", file=sys.stderr)
    except (ValueError, AttributeError, TypeError):
        print("Invalid run metadata; raw content was not displayed.", file=sys.stderr)
    except OSError:
        print("Unable to read run files; raw content was not displayed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
