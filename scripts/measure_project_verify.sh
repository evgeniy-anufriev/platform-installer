#!/bin/sh
# Run on the Execution Node: sudo sh measure_project_verify.sh [project-directory]
set -eu
exec python3 - "$@" <<'PY'
import argparse
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time

parser = argparse.ArgumentParser(description="Замер проверки проекта Core")
parser.add_argument("project", nargs="?", help="Готовая папка проекта (необязательно)")
parser.add_argument("--archive", help="Конкретный project.tar из кэша Installer")
parser.add_argument("--repeat", type=int, default=1, help="Количество замеров, по умолчанию 1")
args = parser.parse_args()
if not 1 <= args.repeat <= 20 or (args.project and args.archive):
    parser.error("--repeat: от 1 до 20; укажите либо папку проекта, либо --archive")


def extract(archive, destination):
    # Lock the cache slot against replacement while copying its contents.
    with (archive.parent / "lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        with tarfile.open(archive, "r:*") as source:
            members = source.getmembers()
            for item in members:
                path = PurePosixPath(item.name)
                if path.is_absolute() or ".." in path.parts or not (item.isdir() or item.isfile()):
                    raise ValueError("Небезопасный путь или тип файла в архиве")
            for item in members:
                target = destination.joinpath(*PurePosixPath(item.name).parts)
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(item) as incoming, target.open("wb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)


def summarize_tasks(rows):
    groups = {}
    for seconds, name in rows:
        # Ignore Ansible's decorative padding, which depends on terminal width.
        name = name[:name.rfind("]") + 1] if "]" in name else name
        total, count = groups.get(name, (0.0, 0))
        groups[name] = (total + seconds, count + 1)
    return sorted(((total, count, total / count, name)
                   for name, (total, count) in groups.items()),
                  key=lambda row: (-row[0], row[3]))


def measure(project, runtime):
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(runtime / "ansible-core/ansible.cfg")
    paths = [runtime / "ansible-core/collections"] + sorted(runtime.glob("services/*/ansible_collections"))
    env["ANSIBLE_COLLECTIONS_PATH"] = ":".join(map(str, paths))
    env["ANSIBLE_NOCOLOR"] = "1"
    env["ANSIBLE_STDOUT_CALLBACK"] = "default"
    variables = {"platform_project_root": str(project),
                 "platform_service_catalog_path": str(runtime / "catalog/service-catalog.yml")}
    command = ["ansible-playbook", "-i", str(project / "inventory/hosts.yml"),
               str(runtime / "ansible-core/playbooks/project-snapshot-machine.yml"),
               "-e", json.dumps(variables)]
    started, current, rows = time.monotonic(), None, []
    with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors="replace", bufsize=1) as process:
        for raw in process.stdout:
            line = raw.strip()
            task = line.startswith(("TASK [", "RUNNING HANDLER ["))
            if task or line.startswith(("PLAY [", "PLAY RECAP")):
                now = time.monotonic()
                if current:
                    rows.append((now - current[0], current[1]))
                current = (now, line) if task else None
                print(line, flush=True)
            # Do not publish variable values or raw failed task output.
        rc = process.wait()
    finished = time.monotonic()
    elapsed = finished - started
    if current:
        rows.append((finished - current[0], current[1]))
    print(f"\nВремя Core: {elapsed:.2f} сек. Код завершения: {rc}. Задач: {len(rows)}")
    print("\nСводка по всем задачам, по убыванию суммарного времени:")
    print(" Сумма, сек | Вызовы | Среднее, сек | Доля Core | Задача")
    for total, count, average, name in summarize_tasks(rows):
        share = total / elapsed * 100 if elapsed else 0.0
        print(f"{total:11.2f} | {count:6d} | {average:12.3f} | {share:8.2f}% | {name}")
    task_seconds = sum(seconds for seconds, _ in rows)
    print(f"\nСумма интервалов задач: {task_seconds:.2f} сек")
    print(f"Вне интервалов задач: {max(0.0, elapsed - task_seconds):.2f} сек")
    print("Вызовы — число заголовков задач, не число хостов или элементов loop.")
    print("Интервалы включают накладные расходы Ansible между заголовками.")
    print()
    print("Самые долгие задачи (интервалы между заголовками):")
    for seconds, name in sorted(rows, reverse=True)[:30]:
        print(f"{seconds:8.2f} сек  {name}")
    if rc:
        print("Проверка завершилась ошибкой. Значения переменных и результаты задач скрыты.")
    return elapsed, rc


def main():
    runtime = Path("/var/lib/platform-installer/runtime/current").resolve()
    if not (runtime / "ansible-core/playbooks/project-snapshot-machine.yml").is_file():
        raise ValueError("В активном runtime отсутствует project-snapshot-machine.yml")
    archive = None
    if not args.project:
        if args.archive:
            archive = Path(args.archive).resolve()
        else:
            archives = sorted(Path("/var/lib/platform-installer/execution/project-archives").glob("*/project.tar"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
            if not archives:
                raise ValueError("Кэш проектов не найден. Выполните проверку в UI либо передайте папку проекта.")
            for i, path in enumerate(archives, 1):
                stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime))
                print(f"{i}. {stamp}  {path}")
            if len(archives) == 1:
                archive = archives[0]
            else:
                print("Номер архива проекта: ", end="", flush=True)
                # stdin carries this program, so read the selection from the terminal.
                with open("/dev/tty") as terminal:
                    choice = int(terminal.readline().strip())
                if not 1 <= choice <= len(archives):
                    raise ValueError("Неверный номер архива")
                archive = archives[choice - 1]
    with tempfile.TemporaryDirectory(prefix="project-verify-measure-", dir="/var/tmp") as scratch:
        os.chmod(scratch, 0o700)
        project = Path(args.project).resolve() if args.project else Path(scratch)
        if archive:
            print(f"Архив: {archive}")
            extract(archive, project)
        if not (project / "inventory/hosts.yml").is_file():
            raise ValueError("В проекте отсутствует inventory/hosts.yml")
        print(f"Проект: {project}\nRuntime: {runtime}", flush=True)
        timings = []
        for number in range(1, args.repeat + 1):
            print(f"\nЗамер {number}/{args.repeat}", flush=True)
            elapsed, rc = measure(project, runtime)
            if rc:
                return rc
            timings.append(elapsed)
        print(f"\nМедиана Core: {statistics.median(timings):.2f} сек")
    return 0


try:
    sys.exit(main())
except (OSError, ValueError, tarfile.TarError) as error:
    print(f"Ошибка: {error}", file=sys.stderr)
    sys.exit(2)
PY
