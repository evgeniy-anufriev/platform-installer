#!/usr/bin/env python3
"""Regenerate only portable-source artifacts; validate before replacing files."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import portable_source


def generated(name):
    return name in {"manifest.json", "portable_source.py"} or bool(
        re.fullmatch(r"source-[0-9]+\.txt", name)
    )


def update(root):
    output = root / "portable-source"
    if output.is_symlink():
        raise ValueError("portable-source must not be a symlink")
    revision = portable_source.git(root, "rev-parse", "HEAD").decode().strip()
    manifest_path = output / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous = manifest.get("sourceRevision")
        already_current = previous == revision
        if not already_current:
            parent = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD^"],
                capture_output=True, text=True,
            )
            if parent.returncode == 0 and previous == parent.stdout.strip():
                changed = portable_source.git(root, "diff", "--name-only", "-z", "HEAD^", "HEAD")
                already_current = all(
                    path.decode().startswith("portable-source/")
                    and generated(path.decode().removeprefix("portable-source/"))
                    for path in changed.split(b"\0") if path
                )
        if already_current:
            try:
                portable_source.verify(output, root)
            except (ValueError, OSError):
                already_current = False
        if already_current:
            expected = {name for name, _, _ in portable_source.source_files(root)}
            _, records = portable_source.read_package(output)
            expected_outputs = {"manifest.json", "portable_source.py"} | {
                part["name"] for part in manifest["parts"]
            }
            actual_outputs = {path.name for path in output.iterdir() if generated(path.name)}
            if (expected == {record["path"] for record, _ in records}
                    and actual_outputs == expected_outputs
                    and (output / "portable_source.py").read_bytes()
                    == Path(portable_source.__file__).read_bytes()):
                print("Portable snapshot already represents this source revision")
                return

    with tempfile.TemporaryDirectory(prefix="portable-source-update-") as workspace:
        candidate = Path(workspace) / "snapshot"
        portable_source.pack(root, candidate)
        portable_source.verify(candidate, root)
        restored = Path(workspace) / "restored"
        portable_source.unpack(candidate, restored)
        portable_source.verify(candidate, restored)
        output.mkdir(exist_ok=True)
        new_names = {path.name for path in candidate.iterdir()}
        for path in candidate.iterdir():
            target = output / path.name
            if not generated(path.name) or target.is_symlink():
                raise ValueError("Unsafe generated output: " + str(target))
            shutil.copyfile(path, target)
        for path in output.iterdir():
            if generated(path.name) and path.name not in new_names:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Unsafe stale output: " + str(path))
                path.unlink()
        portable_source.verify(output, root)


if __name__ == "__main__":
    update(Path(__file__).resolve().parent.parent)
