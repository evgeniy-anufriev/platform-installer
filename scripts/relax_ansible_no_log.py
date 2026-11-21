#!/usr/bin/env python3
"""Relax no_log in an isolated Ansible tree using synthetic credentials.

Requires PyYAML. Defaults to a dry run. --apply edits the supplied copy.
Unknown data is intentionally treated as nonsecret, so this is a fixture tool.
"""

import argparse
import os
from pathlib import Path
import re
import sys

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


SECRET = re.compile(
    r"password|passwd|passphrase|private[\s_.-]*key|secret|credential|"
    r"(?:access[\s_.-]*|auth[\s_.-]*|vault[\s_.-]*)token|"
    r"pem[\s_.-]*identity|identity\.pem|_pem_inputs|"
    r"парол|закрыт\w*\s+ключ|уч[её]тн\w*\s+данн|секрет",
    re.IGNORECASE,
)

TASK_LISTS = frozenset(("tasks", "pre_tasks", "post_tasks", "handlers"))
BLOCK_LISTS = frozenset(("block", "rescue", "always"))
SKIP_DIRECTORIES = frozenset(("vendor", "_vendor", "portable-source", ".git", ".runtime", "node_modules"))
INSTALLED = Path("/var/lib/platform-installer")


def mentions_secret(node, seen):
    if id(node) in seen:
        return False
    seen.add(id(node))
    if isinstance(node, ScalarNode):
        return node.tag == "!vault" or bool(SECRET.search(node.value))
    if isinstance(node, MappingNode):
        return any(mentions_secret(child, seen) for pair in node.value for child in pair)
    if isinstance(node, SequenceNode):
        return any(mentions_secret(child, seen) for child in node.value)
    return False


def visit_tasks(sequence, inherited_secret, changes, protected, active):
    if not isinstance(sequence, SequenceNode) or id(sequence) in active:
        return
    active.add(id(sequence))
    try:
        for task in sequence.value:
            if not isinstance(task, MappingNode):
                continue
            fields = {key.value: value for key, value in task.value if isinstance(key, ScalarNode)}
            groups = TASK_LISTS | BLOCK_LISTS
            sensitive = inherited_secret or any(
                SECRET.search(key) or mentions_secret(value, set())
                for key, value in fields.items()
                if key not in groups and key != "no_log"
            )
            option = fields.get("no_log")
            if isinstance(option, ScalarNode):
                span = (option.start_mark.index, option.end_mark.index)
                name_option = next(key for key, value in task.value
                                   if isinstance(key, ScalarNode) and key.value == "no_log" and value is option)
                # An alias points to the anchor's source position, not its own.
                if sensitive or option.start_mark.index < name_option.end_mark.index:
                    protected.add(span)
                elif option.tag != "tag:yaml.org,2002:bool" or option.value.lower() not in ("false", "no", "off"):
                    changes.add(span)
            for key in groups & fields.keys():
                visit_tasks(fields[key], sensitive, changes, protected, active)
    finally:
        active.remove(id(sequence))


def task_edits(source):
    changes, protected = set(), set()
    for document in yaml.compose_all(source, Loader=yaml.SafeLoader):
        visit_tasks(document, False, changes, protected, set())
    spans = sorted(changes - protected, reverse=True)
    for start, end in spans:
        source = source[:start] + "false" + source[end:]
    return source, len(spans)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path, help="Directory of an isolated diagnostic copy")
    parser.add_argument("--apply", action="store_true", help="Apply edits to the diagnostic copy")
    args = parser.parse_args()
    root = args.copy.resolve()
    if not root.is_dir():
        parser.error("diagnostic copy must be a directory")
    if root == INSTALLED or INSTALLED in root.parents or root in INSTALLED.parents:
        parser.error("use a diagnostic copy outside the Installer runtime tree")

    pending = []
    for directory, subdirectories, filenames in os.walk(root):
        folder = Path(directory)
        subdirectories[:] = sorted(
            name for name in subdirectories
            if name not in SKIP_DIRECTORIES and not (folder / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = folder / filename
            if (path.suffix.lower() not in (".yml", ".yaml") or path.is_symlink()
                    or not path.is_file() or path.stat().st_nlink != 1):
                continue
            with path.open(encoding="utf-8", newline="") as stream:
                source = stream.read()
            if "no_log" not in source:
                continue
            relative = path.relative_to(root)
            try:
                updated, count = task_edits(source)
            except yaml.YAMLError:
                print(f"Skipped unparseable YAML: {relative}", file=sys.stderr)
                continue
            if count:
                print(f"{relative}: {count}")
                pending.append((path, updated, count))

    if args.apply:
        for path, updated, _ in pending:
            with path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(updated)
    print(f"{'Changed' if args.apply else 'Dry run'}: "
          f"{sum(count for _, _, count in pending)} settings in {len(pending)} files")


if __name__ == "__main__":
    main()
