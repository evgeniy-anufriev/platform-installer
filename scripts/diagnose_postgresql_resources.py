#!/usr/bin/env python3
"""Summarize existing PostgreSQL provider events without replaying a run.

Run on the Execution Node:
  sudo -n python3 scripts/diagnose_postgresql_resources.py installer-<32 hex digits>

Only the standard library is required. This script does not invoke Core,
Ansible or PostgreSQL, and does not display module output or runtime secrets.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="Existing Installer run ID")
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
        invalid = 0
        with (root / "events.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    task = event.get("task") or {}
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
        print("\nINCOMPLETE_OR_INVALID_EVENT_ROWS:", invalid)
        print("An active run can append events after this snapshot.")
        print("libraryJobs is transient Ansible state; this report cannot recover it.")
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
