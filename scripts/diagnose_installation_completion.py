#!/usr/bin/env python3
"""Report post-install and run completion from the latest local execution journal."""

import argparse
import json
from pathlib import Path


POST_INSTALL = "applications:post-install"


def read_events(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                break  # The controller may still be appending the final line.
            yield json.loads(line)


def find_latest(runs):
    latest = None
    for path in runs.glob("*/events.jsonl"):
        for event in read_events(path):
            if event.get("eventType") == "RUN_STARTED":
                candidate = (event["timestamp"], path)
                if latest is None or candidate > latest:
                    latest = candidate
                break
    return latest[1] if latest else None


def event_summary(event):
    if event is None:
        return "NOT_FOUND"
    return "{eventType} {status} sequence={sequence} timestamp={timestamp}".format(**event)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_directory", nargs="?", type=Path,
                        default=Path("/var/lib/platform-installer/execution/runs"))
    args = parser.parse_args()
    try:
        if not args.runs_directory.is_dir():
            parser.exit(1, "RUN_DIRECTORY_NOT_FOUND\n")
        log = find_latest(args.runs_directory)
        if log is None:
            parser.exit(1, "STARTED_RUN_NOT_FOUND\n")

        status = json.loads(log.with_name("status.json").read_text(encoding="utf-8"))
        post_install = completion = None
        last_sequence = 0
        for event in read_events(log):
            last_sequence = event["sequence"]
            event_type = event["eventType"]
            if event_type == "ACTION_COMPLETED" and event.get("actionId") == POST_INSTALL:
                post_install = event
            if event_type == "RUN_COMPLETED" or (
                event_type == "DIAGNOSTIC"
                and event.get("status") in {"SUCCESS", "FAILED", "CANCELLED"}
                and event.get("safeMessage") in {
                    "Execution controller completed",
                    "Trusted operation failed before completion",
                    "Cancellation requested",
                }
            ):
                completion = event

        print(f"RUN: {log.parent.name}")
        print(f"STATUS: {status['state']} sequence={status['sequence']}")
        print(f"LAST_JOURNAL_SEQUENCE: {last_sequence}")
        print(f"POST_INSTALL_COMPLETION: {event_summary(post_install)}")
        print(f"RUN_COMPLETION: {event_summary(completion)}")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"EXECUTION_JOURNAL_UNREADABLE: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
