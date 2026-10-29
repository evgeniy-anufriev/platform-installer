#!/usr/bin/env python3
"""Create a tools-only image context from local vendored Wails sources."""
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("project", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = args.project.resolve()
output = args.output.resolve()
if output.exists():
    raise SystemExit("Context destination must be new")
for name in ("go.mod", "vendor/modules.txt", "cmd/wails/internal/version.txt"):
    if not (source / "third_party/wails" / name).is_file():
        raise SystemExit("Missing Wails CLI source: " + str(source / "third_party/wails" / name))
output.mkdir(parents=True)
shutil.copytree(source / "third_party/wails", output / "wails",
                ignore=shutil.ignore_patterns(".git", ".runtime", "node_modules", "__pycache__"))
for name in ("Dockerfile", "build-target.sh"):
    shutil.copyfile(Path(__file__).parent / name, output / name)
print("Tools-only Docker context: " + str(output))
