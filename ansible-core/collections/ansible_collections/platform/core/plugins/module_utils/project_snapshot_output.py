"""Public snapshot artifact shared by the action and its redacting callback."""
import json
import os
import re
import tempfile

from ansible.errors import AnsibleError


class SnapshotInputError(AnsibleError):
    """Closed reason token; parser text and input values stay private."""


def snapshot_input_message(stage, error, context=None):
    reasons = {
        'INPUT_MISSING': 'Отсутствует обязательный документ.',
        'INPUT_PARSE_FAILED': 'Не удалось прочитать YAML/JSON документа.',
        'PROJECT_ROOT_MISSING': 'Папка проекта не существует.',
        'INVENTORY_OUTSIDE_PROJECT': 'Inventory находится вне папки проекта.',
        'INVENTORY_SELECTION_MISMATCH': 'Ansible загрузил другой inventory.',
        'CATALOG_REFERENCE_MISSING': 'Не найден файл, указанный в каталоге сервисов.',
        'CATALOG_MANIFEST_MISSING': 'Не найдены исходные манифесты сервисов набора.',
        'APPLICATION_ARTIFACT_LOCK_CONFLICT': 'artifactLock проекта конфликтует с platform_artifact_lock.',
        'APPLICATION_EXECUTION_MODEL_MISMATCH': 'Модель приложений не совпадает с ожидаемой.',
        'APPLICATION_BUNDLE_DIGEST_INVALID': 'Некорректный digest набора приложений.',
        'APPLICATION_BUNDLE_MANIFEST_INVALID': 'Некорректный манифест набора приложений.',
        'PROJECT_RESOLUTION_INVALID': 'Разрешённая проекция проекта не прошла проверку.',
        'Canonical project variable directories must not contain symlinks': 'Каталоги переменных проекта содержат запрещённые символические ссылки.',
        'Canonical project documents must not be symlinks': 'Документы проекта содержат запрещённые символические ссылки.',
        'Application resolve role must run before snapshot': 'Не выполнено разрешение библиотек приложений.',
        'Application projection placement identity mismatch': 'Размещение приложений изменилось во время разрешения.',
        'Application package inputs changed during resolution': 'Пакеты приложений изменились во время разрешения.',
    }
    # Exact reason tokens and bounded Ansible identifier patterns only.
    # Never emit raw parser output, paths, hostvars or exception values.
    reason = reasons.get(str(error)) if isinstance(error, (SnapshotInputError, ValueError)) else None
    if reason is None and isinstance(error, AnsibleError):
        text = str(error)[:65536]
        attribute = re.search(r"has no attribute ['\"]([A-Za-z_][A-Za-z0-9_]{0,127})['\"]", text)
        variable = re.search(r"['\"]([A-Za-z_][A-Za-z0-9_]{0,127})['\"] is undefined", text)
        if attribute:
            reason = 'В шаблоне отсутствует поле «%s».' % attribute.group(1)
        elif variable:
            reason = 'Не определена переменная «%s».' % variable.group(1)
        elif 'recursive loop' in text.lower():
            reason = 'Обнаружена циклическая ссылка в шаблоне.'
    if reason is None:
        reason = ('Недостаточно прав для чтения входных данных.' if isinstance(error, PermissionError)
                  else 'Ошибка чтения входных данных.' if isinstance(error, OSError)
                  else 'Отсутствует обязательное поле входных данных.' if isinstance(error, KeyError)
                  else 'Ошибка вычисления переменных Ansible.' if isinstance(error, AnsibleError)
                  else 'Нарушена структура входных данных.' if isinstance(error, (TypeError, ValueError))
                  else 'Внутренний сбой построения снимка.')
    message = 'Не удалось построить снимок проекта. Этап: %s. %s' % (stage, reason)
    context = context if isinstance(context, dict) else {}
    for key, label in (('libraryId', 'Библиотека'), ('slotId', 'приложение'), ('hostId', 'узел')):
        value = context.get(key)
        if isinstance(value, str) and re.fullmatch(r'[a-z][A-Za-z0-9_.-]{0,127}', value):
            message += ' %s: «%s».' % (label, value)
    return message.encode('utf-8')[:512].decode('utf-8', errors='ignore')


def write_snapshot_output(payload):
    destination = os.environ.get('PLATFORM_PROJECT_SNAPSHOT_OUTPUT')
    if not destination:
        return
    directory = os.path.dirname(os.path.realpath(destination))
    if not os.path.isdir(directory):
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.project-snapshot-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(payload, output, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def snapshot_failure_published():
    """A no_log callback must not overwrite the action's safe error artifact."""
    path = os.environ.get('PLATFORM_PROJECT_SNAPSHOT_OUTPUT')
    if not path or os.path.islink(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return False
        payload = json.loads(raw)
        finding = payload.get('adapterError') if isinstance(payload, dict) else None
        return (isinstance(finding, dict)
                and finding.get('code') == 'PROJECT_SNAPSHOT_INPUT_INVALID'
                and isinstance(finding.get('safeMessage'), str)
                and 0 < len(finding['safeMessage'].encode('utf-8')) <= 512)
    except (OSError, ValueError):
        return False
