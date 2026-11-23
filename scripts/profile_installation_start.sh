#!/bin/sh
# Read-only profile of plan confirmation and startup on the Execution Node.
set -eu
exec python3 - "$@" <<'PY'
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys


OPERATIONS = {
    'BuildRuntimeSecretDescriptors': 'Требования к секретам',
    'PrepareApplicationImages': 'Входы проверки registry (DESCRIBE)',
    'BuildDeploymentPlan': 'Сборка авторитетного плана',
}
EVENTS = {
    'ACCEPTED': 'Контроллер принят к запуску',
    'RUN_STARTED': 'Контроллер запущен',
    'ACTION_STARTED': 'Первое действие плана',
    'TASK_STARTED': 'Первая задача Ansible',
}


def timestamp(value):
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.utcoffset() is None:
        raise ValueError('Укажите часовой пояс, например +03:00')
    return at.astimezone(timezone.utc)


def format_time(at):
    return at.astimezone().isoformat(timespec='milliseconds')


def seconds(value):
    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
        return f'{value:.3f} с'
    return '—'


def run_events(directory):
    marks = {}
    with (directory / 'events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            if not line.endswith('\n'):
                break
            event = json.loads(line)
            kind = event.get('eventType')
            if kind == 'DIAGNOSTIC' and event.get('message') == 'Detached controller accepted':
                kind = 'ACCEPTED'
            if kind in EVENTS and kind not in marks:
                marks[kind] = timestamp(event['timestamp'])
                if kind == 'TASK_STARTED':
                    break
    return marks


def show_core(directory, scope, since, until):
    records = []
    by_project = {}
    ignored = 0
    for operation in OPERATIONS:
        for path in directory.glob(f'{scope}.{operation}.timing.json'):
            try:
                with path.open(encoding='utf-8') as stream:
                    finished = datetime.fromtimestamp(os.fstat(stream.fileno()).st_mtime, timezone.utc)
                    if not since <= finished <= until:
                        continue
                    data = json.load(stream)
                if data.get('operation') != operation:
                    raise ValueError('Unexpected operation')
                project = path.name.split('.', 1)[0]
                resolution = data.get('resolution')
                if not isinstance(resolution, dict):
                    resolution = {}
                records.append((finished, operation, project, data, resolution))
                by_project.setdefault(project, {})[operation] = (finished, resolution, data.get('elapsedSeconds'))
            except (OSError, ValueError, AttributeError):
                ignored += 1
    print('Вызовы Core, завершённые в выбранном интервале')
    for finished, operation, project, data, resolution in sorted(records, key=lambda row: row[0]):
        source = resolution.get('source')
        if source not in ('fresh', 'shared', 'request'):
            source = '—'
        reusable = resolution.get('reusable')
        reusable_label = str(reusable).lower() if type(reusable) is bool else '—'
        print(f'{format_time(finished)}  {OPERATIONS[operation]} ({operation})'
              f'  ключ проекта {project[:12]}'
              f'  всего {seconds(data.get("elapsedSeconds"))}'
              f'  ожидание блокировки {seconds(data.get("lockWaitSeconds"))}'
              f'  расчёт {source}  reusable={reusable_label}'
              f'  разрешение {seconds(resolution.get("resolveSeconds"))}'
              f'  чтение кэша {seconds(resolution.get("readSeconds"))}')
    if not records:
        print('Файлы таймингов в этом интервале не найдены.')
    if ignored:
        print(f'Пропущено нечитаемых или некорректных файлов: {ignored}')
    for project, operations in sorted(by_project.items()):
        descriptors = operations.get('BuildRuntimeSecretDescriptors')
        describe = operations.get('PrepareApplicationImages')
        if not descriptors or not describe or seconds(describe[2]) == '—':
            continue
        if (describe[0] - descriptors[0]).total_seconds() < describe[2]:
            continue
        earlier, later = descriptors[1], describe[1]
        if earlier.get('source') != 'fresh' or later.get('source') != 'fresh':
            continue
        if earlier.get('reusable') is False:
            explanation = 'расчёт требований к секретам оказался непригоден для общего кэша.'
        elif earlier.get('reusable') is True:
            explanation = 'расчёт требований пригоден для общего кэша, но DESCRIBE его не использовал. Сверьте ревизию и входы. Точная причина в таймингах отсутствует.'
        else:
            explanation = 'в тайминге требований нет поля reusable, поэтому причину определить нельзя.'
        print(f'Два fresh для ключа {project[:12]} — {explanation}')


def main():
    parser = argparse.ArgumentParser(description='Профиль от одобрения плана до первой задачи')
    parser.add_argument('--run', help='ID запуска installer-… из журнала')
    parser.add_argument('--since', help='Время нажатия кнопки с часовым поясом ISO 8601')
    parser.add_argument('--state-root', type=Path, default=Path('/var/lib/platform-installer/execution'),
                        help='Каталог состояния Execution Node или локальная копия для разбора')
    args = parser.parse_args()
    if args.run and not re.fullmatch(r'installer-[0-9a-f]{32}', args.run):
        parser.error('Некорректный ID запуска')

    now = datetime.now(timezone.utc)
    marks = {}
    scope = '[0-9a-f]' * 64 + '.json'
    if args.run:
        directory = args.state_root / 'runs' / args.run
        with (directory / 'metadata.json').open(encoding='utf-8') as stream:
            project = json.load(stream)['projectIdentity']
        # Same project key as Core's project_resolution.scope_name.
        scope = hashlib.sha256(json.dumps([project], sort_keys=True).encode()).hexdigest() + '.json'
        marks = run_events(directory)

    until = marks.get('TASK_STARTED', now)
    since = timestamp(args.since) if args.since else marks.get('ACCEPTED', until) - timedelta(minutes=10)
    if since > until:
        parser.error('Начало интервала позже первой задачи или текущего времени')
    print(f'Интервал: {format_time(since)} — {format_time(until)}')
    if not args.run:
        print('Показаны тайминги всех проектов в этом интервале. Для отбора по проекту укажите --run.')
    show_core(args.state_root / 'project-resolutions', scope, since, until)
    if args.run:
        print('\nСобытия принятого запуска')
        previous = since if args.since else None
        for kind, label in EVENTS.items():
            if kind in marks:
                at = marks[kind]
                delta = f'  +{(at - previous).total_seconds():.3f} с' if previous else ''
                print(f'{format_time(at)}  {label}{delta}')
                previous = at
        if 'TASK_STARTED' not in marks:
            print('Первое событие задачи пока отсутствует.')
        elif args.since:
            print('От нажатия до первой задачи: ' + seconds((marks['TASK_STARTED'] - since).total_seconds()))
    print('\nФайлы Core содержат последний замер каждой операции для проекта. При параллельных запусках строки могут относиться к разным попыткам.')
    print('DESCRIBE не включает сетевой проход registry. Тайминги Core не включают локальную проверку bundle и передачу проекта.')


try:
    main()
except (OSError, ValueError, TypeError, KeyError) as error:
    print(f'Ошибка: {error}', file=sys.stderr)
    sys.exit(2)
PY
