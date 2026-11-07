#!/bin/sh
# Read-only profile of an existing Installer run. Run on the Execution Node.
set -eu
exec python3 - "$@" <<'PY'
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

BASE = Path('/var/lib/platform-installer/execution/runs')
RESOLVER = 'platform.core.resolve_application_libraries'
FIRST = 'Проверка комплектности пакетов библиотек перед загрузкой значений по умолчанию'
LAST = 'Сбор рассчитанных записей приложений в порядке размещений'


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def profile(events):
    tasks, active, actions, opened, resolves, resolving = [], {}, [], {}, [], {}
    for event in events:
        kind = event.get('eventType', '')
        context = (event.get('phaseId', ''), event.get('actionId', ''))
        at = timestamp(event['timestamp'])
        if kind == 'ACTION_STARTED':
            row = dict(phase=context[0], action=context[1], start=at, end=None, status='RUNNING')
            actions.append(row)
            opened[context] = row
        elif kind == 'ACTION_COMPLETED' and context in opened:
            opened.pop(context).update(end=at, status=event.get('status', ''))
        elif kind in ('TASK_STARTED', 'TASK_COMPLETED'):
            task = event.get('task', {})
            key = context + (task.get('uuid', ''),)
            if kind == 'TASK_STARTED':
                # Older runtimes have a different final task name. Close at
                # the next role boundary instead of pretending resolve is active.
                if context in resolving and (task.get('role') != RESOLVER or task.get('name') == FIRST):
                    call = resolving.pop(context)
                    call['end'] = call.pop('observedEnd')
                row = dict(phase=context[0], action=context[1], role=task.get('role', ''),
                           name=task.get('name', ''), start=at, end=None, elapsed=None,
                           results=0, failed=0, skipped=0)
                tasks.append(row)
                active[key] = row
                if row['role'] == RESOLVER and row['name'] == FIRST:
                    call = dict(phase=context[0], action=context[1], start=at, end=None, observedEnd=at)
                    resolves.append(call)
                    resolving[context] = call
            elif key in active:
                row = active[key]
                milliseconds = event.get('elapsedMilliseconds')
                duration = milliseconds / 1000 if isinstance(milliseconds, (int, float)) and milliseconds >= 0 else max(0, at-row['start'])
                row['elapsed'] = max(row['elapsed'] or 0, duration)
                row['end'] = max(row['end'] or at, at)
                row['results'] += 1
                row['failed'] += event.get('status') == 'FAILED'
                row['skipped'] += event.get('status') == 'SKIPPED'
                if row['role'] == RESOLVER and row['name'] == LAST and context in resolving:
                    resolving.pop(context)['end'] = at
            if task.get('role') == RESOLVER and context in resolving:
                resolving[context]['observedEnd'] = at
    # Never add still-open/include-only task intervals to the completed totals.
    groups = defaultdict(lambda: [0.0, 0, 0, 0])
    for row in tasks:
        if row['elapsed'] is not None:
            g = groups[(row['action'], row['role'], row['name'])]
            g[0] += row['elapsed']; g[1] += 1; g[2] += row['results']; g[3] += row['failed']
    return actions, resolves, tasks, groups


def report(events, status, cutoff):
    actions, resolves, tasks, groups = profile(events)
    print(f"Событий прочитано: {len(events)}. Начатых задач: {len(tasks)}. Задач с результатом: {sum(t['elapsed'] is not None for t in tasks)}")
    print(f"Состояние запуска: {status.get('state', 'неизвестно')}")
    unmatched = sum(e.get('eventType') == 'TASK_COMPLETED' for e in events) - sum(t['results'] for t in tasks)
    if unmatched:
        print(f'Предупреждение: результатов задач без события начала: {unmatched}')
    print('\nЭтапы/операции (вложенные интервалы не складывать):')
    for row in actions:
        end = row['end'] if row['end'] is not None else cutoff
        label = row['status'] if row['end'] is not None else 'НЕ ЗАВЕРШЁН'
        print(f"{max(0,end-row['start']):10.2f} сек | {label:14} | {row['phase']} | {row['action']}")
    print('\nВызовы resolve_application_libraries:')
    if not resolves:
        print('Маркеры вызовов не найдены в доступном журнале.')
    for number, row in enumerate(resolves, 1):
        end = row['end'] if row['end'] is not None else cutoff
        label = 'завершён' if row['end'] is not None else 'НЕ ЗАВЕРШЁН'
        print(f"{number:3}. {max(0,end-row['start']):9.2f} сек | {label} | {row['action']}")
    print('\nЗадачи по суммарному времени (в каждой операции отдельно):')
    print('Сумма, сек | Вызовы | Среднее, сек | Результаты хостов | Ошибки хостов | Операция / роль / задача')
    for (action, role, name), (seconds, calls, results, failed) in sorted(groups.items(), key=lambda item: -item[1][0]):
        print(f'{seconds:10.2f} | {calls:6} | {seconds/calls:12.3f} | {results:16} | {failed:6} | {action} / {role} / {name}')
    print('\nПоследние начатые задачи без результата (включают include-задачи, это не обязательно зависание):')
    for row in [t for t in tasks if t['elapsed'] is None][-10:]:
        print(f"{datetime.fromtimestamp(row['start'],timezone.utc).isoformat()} | {row['action']} | {row['role']} | {row['name']}")
    print('\nВызовы считаются по TASK_STARTED, а не по числу событий или хостов.')
    print('Для параллельных хостов берётся максимальная длительность задачи, не сумма результатов хостов.')
    print('Сумма задач не равна времени этапа: возможны вложенные задачи, параллельность и промежутки между задачами.')
    print('Незавершённые интервалы ограничены последним событием/статусом, а не текущими часами.')
    print('При обрезанном журнале или пропусках событий профиль неполон. Вывод модулей и значения переменных не печатаются.')


def main():
    parser = argparse.ArgumentParser(description='Профиль этапов уже запущенной установки без повторного выполнения Core')
    parser.add_argument('run', nargs='?', help='ID запуска installer-…; без аргумента — выбор из списка')
    parser.add_argument('--events', help='Путь к events.jsonl, в том числе сохранённой копии журнала')
    args = parser.parse_args()
    if args.run and args.events:
        parser.error('Укажите либо ID запуска, либо --events')
    if args.events:
        path = Path(args.events)
    else:
        if args.run:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', args.run):
                parser.error('Некорректный ID запуска')
            path = BASE / args.run / 'events.jsonl'
        else:
            candidates = sorted(BASE.glob('*/events.jsonl'), key=lambda p:p.stat().st_mtime, reverse=True)
            if not candidates:
                raise ValueError('Журналы запусков не найдены')
            for number, candidate in enumerate(candidates, 1):
                print(f'{number}. {candidate.parent.name}')
            choice = 1
            if len(candidates) > 1:
                print('Номер запуска: ', end='', flush=True)
                with open('/dev/tty') as terminal:
                    choice = int(terminal.readline().strip())
                if not 1 <= choice <= len(candidates):
                    raise ValueError('Неверный номер запуска')
            path = candidates[choice-1]
    events, broken = [], 0
    with path.open('rb') as source:
        # Read only the current prefix, without locking or modifying a live run.
        raw = source.read(os.fstat(source.fileno()).st_size)
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b'\n'):
            broken += 1
            continue
        try:
            event = json.loads(line)
            timestamp(event['timestamp'])
            events.append(event)
        except (ValueError, KeyError, TypeError):
            broken += 1
    if not events:
        raise ValueError('Нет полных событий с корректным временем')
    status = {}
    try:
        status = json.loads((path.parent / 'status.json').read_text())
    except (OSError, ValueError):
        pass
    cutoff = max(timestamp(e['timestamp']) for e in events)
    try:
        cutoff = max(cutoff,timestamp(status['updatedAt']))
    except (ValueError, KeyError, TypeError):
        pass
    print(f'Журнал: {path}')
    if broken:
        print(f'Предупреждение: пропущено неполных/некорректных строк: {broken}')
    report(events, status, cutoff)
    return 0


try:
    sys.exit(main())
except (OSError, ValueError) as error:
    print(f'Ошибка: {error}', file=sys.stderr)
    sys.exit(2)
PY
