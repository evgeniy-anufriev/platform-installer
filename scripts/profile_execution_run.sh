#!/bin/sh
# Read-only profile of an existing Installer run. Run on the Execution Node.
set -eu
exec python3 - "$@" <<'PY'
import argparse
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

BASE = Path('/var/lib/platform-installer/execution/runs')
RESOLVER = 'platform.core.resolve_application_libraries'
FIRST = 'Проверка комплектности пакетов библиотек перед загрузкой значений по умолчанию'
LAST = 'Сбор рассчитанных записей приложений в порядке размещений'
LIBRARY_ACTION_PREFIX = 'applications:library:'
LIBRARIES_CLEANUP = 'Удаление временных файлов учётных данных после установки библиотек'


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def library_events(events, library):
    action = LIBRARY_ACTION_PREFIX + library
    selected = []
    boundary = None
    for event in events:
        event_action = event.get('actionId', '')
        kind = event.get('eventType')
        if not selected:
            if event_action == action and kind == 'ACTION_STARTED':
                selected.append(event)
            continue
        if event_action == action and kind == 'ACTION_COMPLETED':
            selected.append(event)
            break
        if kind == 'ACTION_STARTED' and (event_action or '').startswith(LIBRARY_ACTION_PREFIX):
            boundary = event
            break
        if event_action != 'applications:apply':
            continue
        if kind == 'ACTION_COMPLETED' or (
                kind == 'TASK_STARTED' and event.get('task', {}).get('name') == LIBRARIES_CLEANUP):
            boundary = event
            break
        if kind in ('TASK_STARTED', 'TASK_COMPLETED'):
            selected.append(event)
    if not selected:
        raise ValueError(f'В журнале нет события начала установки библиотеки {library}')
    return selected, boundary


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


def report_library_gaps(tasks, start, end):
    gaps = []
    edge, previous = start, ('', 'Начало этапа')
    completed = sorted((row for row in tasks if row['end'] is not None), key=lambda row: row['start'])
    incomplete = sorted(row['start'] for row in tasks if row['end'] is None)
    for row in completed:
        begin, stop = max(start, row['start']), min(end, row['end'])
        if stop < begin:
            continue
        task = (row['role'], row['name'])
        if begin > edge:
            gaps.append((edge, begin, previous, task))
        if stop >= edge:
            edge, previous = stop, task
    if end > edge:
        gaps.append((edge, end, previous, ('', 'Граница этапа')))

    durations = [stop - begin for begin, stop, _, _ in gaps]
    outside = sum(durations)
    print(f'Интервалы задач с результатом без перекрытий: {max(0, end - start - outside):.2f} сек.')
    print(f'Вне этих интервалов: {outside:.2f} сек в {len(gaps)} разрывах. '
          f'Задач без результата: {len(incomplete)}.')
    for lower, upper, label in ((0, 1, '< 1'), (1, 5, '1–<5'), (5, 10, '5–<10'), (10, float('inf'), '≥ 10')):
        bucket = [duration for duration in durations if lower <= duration < upper]
        if bucket:
            print(f'Разрывы {label} сек: {len(bucket)} шт., всего {sum(bucket):.2f} сек.')
    if gaps:
        print('До пяти самых длинных разрывов вне интервалов задач:')
        for begin, stop, before, after in sorted(gaps, key=lambda row: row[0] - row[1])[:5]:
            opened = bisect_left(incomplete, stop) - bisect_left(incomplete, begin)
            detail = f' | Начато без результата: {opened}' if opened else ''
            stamp = datetime.fromtimestamp(begin, timezone.utc).isoformat()
            print(f'{stop - begin:8.2f} сек | {stamp} | После: {before[1]} | Перед: {after[1]}{detail}')
    transitions = defaultdict(lambda: [0.0, 0])
    short_transitions = defaultdict(lambda: [0.0, 0])
    for begin, stop, before, after in gaps:
        duration = stop - begin
        totals = transitions[(before[1], after[1])]
        totals[0] += duration
        totals[1] += 1
        if 1 <= duration < 5:
            totals = short_transitions[(before, after)]
            totals[0] += duration
            totals[1] += 1
    repeated = [(names, totals) for names, totals in transitions.items() if totals[1] > 1]
    if repeated:
        print('Повторяющиеся переходы с наибольшей суммой разрывов:')
        for (before, after), (seconds, count) in sorted(repeated, key=lambda row: -row[1][0])[:5]:
            print(f'{seconds:8.2f} сек | {count} раз | в среднем {seconds / count:.2f} сек | {before} → {after}')
    if short_transitions:
        print('Все переходы с разрывами 1–<5 сек, по убыванию суммарного времени:')
        print('Сумма, сек | Повторы | Роль / задача до → Роль / задача после')
        for (before, after), (seconds, count) in sorted(short_transitions.items(),
                                                       key=lambda row: (-row[1][0], row[0])):
            before_role, before_name = before
            after_role, after_name = after
            print(f'{seconds:10.2f} | {count:7d} | '
                  f'{before_role or "—"} / {before_name} → {after_role or "—"} / {after_name}')


def benchmark_journal(directory, size, event_count, status_size, stage_event_count):
    samples = 32
    entry_size = (size + event_count - 1) // event_count
    entry_prefix, entry_suffix = b'{"sequence":1,"pad":"', b'"}\n'
    entry = entry_prefix + b'x' * (entry_size - len(entry_prefix) - len(entry_suffix)) + entry_suffix
    status_data = b'{"pad":"' + b'x' * (status_size - 10) + b'"}'
    measurements = defaultdict(list)

    with tempfile.TemporaryDirectory(prefix='.profile-journal-', dir=directory) as scratch:
        work = Path(scratch)
        journal = work / 'events.jsonl'
        with journal.open('wb') as stream:
            for _ in range(event_count):
                stream.write(entry)

        for _ in range(samples):
            began = time.perf_counter()
            for _ in range(2):
                with journal.open('rb') as stream:
                    json.loads(stream.read().rstrip(b'\n').split(b'\n')[-1])
            read = time.perf_counter()
            with journal.open('ab') as stream:
                stream.write(entry)
                stream.flush()
                os.fsync(stream.fileno())
            appended = time.perf_counter()
            with tempfile.NamedTemporaryFile(dir=work, delete=False) as temporary:
                temporary.write(status_data)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary.name, work / 'status.json')
            saved = time.perf_counter()

            measurements['Два чтения журнала и разбор номера'].append(read - began)
            measurements['Дописать событие и fsync'].append(appended - read)
            measurements['Записать статус, fsync и заменить файл'].append(saved - appended)
            measurements['Итого на событие'].append(saved - began)

    print(f'Стендовый замер журнала на том же файловом разделе: {samples} записей, '
          f'исходный размер около {size / (1024 * 1024):.2f} МиБ.')
    for name, results in measurements.items():
        average = sum(results) / samples
        percentile = sorted(results)[(samples * 95 + 99) // 100 - 1]
        print(f'{name}: среднее {average * 1000:.2f} мс, p95 {percentile * 1000:.2f} мс.')
    estimate = sum(measurements['Итого на событие']) / samples * stage_event_count
    print(f'Ориентир на {stage_event_count} учтённых событий: {estimate:.2f} сек.')
    print('Замер на временных данных. Ожидание блокировки, нагрузка Ansible и исходного запуска не измерены.')


def report(events, status, cutoff, top=None, library=None):
    actions, resolves, tasks, groups = profile(events)
    print(f"Событий прочитано: {len(events)}. Начатых задач: {len(tasks)}. Задач с результатом: {sum(t['elapsed'] is not None for t in tasks)}")
    print(f"Состояние запуска: {status.get('state', 'неизвестно')}")
    if library:
        stage = next(row for row in actions if row['action'] == LIBRARY_ACTION_PREFIX + library)
        end = stage['end'] if stage['end'] is not None else cutoff
        stage_status = stage['status'] if stage['end'] is not None else 'нет маркера завершения'
        print(f"Длительность этапа библиотеки: {max(0, end - stage['start']):.2f} сек ({stage_status})")
    print(f'Сумма по всем задачам с результатом: {sum(group[0] for group in groups.values()):.2f} сек.')
    if library:
        report_library_gaps(tasks, stage['start'], end)
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
    ranked = sorted(groups.items(), key=lambda item: -item[1][0])
    for (action, role, name), (seconds, calls, results, failed) in ranked[:top]:
        print(f'{seconds:10.2f} | {calls:6} | {seconds/calls:12.3f} | {results:16} | {failed:6} | {action} / {role} / {name}')
    if top is not None and top < len(ranked):
        print(f'Показано {top} из {len(ranked)} строк. Итог включает все задачи с результатом.')
    if top is not None:
        return
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
    parser.add_argument('--library', help='Показать только этап установки и проверки указанной библиотеки')
    parser.add_argument('--top', metavar='N', type=int, help='Сколько строк задач показать (с --library по умолчанию 10)')
    parser.add_argument('--benchmark-journal', action='store_true',
                        help='Дополнительно замерить операции журнала на временных файлах рядом с ним')
    args = parser.parse_args()
    if args.top is not None and args.top < 1:
        parser.error('--top должен быть положительным')
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
    journal_event_count = len(events)
    if args.library:
        events, boundary = library_events(events, args.library)
    cutoff = max(timestamp(e['timestamp']) for e in events)
    if args.library and boundary is not None:
        cutoff = max(cutoff, timestamp(boundary['timestamp']))
    elif not args.library:
        try:
            cutoff = max(cutoff,timestamp(status['updatedAt']))
        except (ValueError, KeyError, TypeError):
            pass
    print(f'Журнал: {path}')
    if args.library:
        print(f'Библиотека: {args.library}')
    if broken:
        print(f'Предупреждение: пропущено неполных/некорректных строк: {broken}')
    top = 10 if args.library and args.top is None else args.top
    report(events, status, cutoff, top=top, library=args.library)
    if args.benchmark_journal:
        benchmark_journal(path.parent, len(raw), journal_event_count, len(json.dumps(status)), len(events))
    return 0


try:
    sys.exit(main())
except (OSError, ValueError) as error:
    print(f'Ошибка: {error}', file=sys.stderr)
    sys.exit(2)
PY
