#!/bin/sh
# Run on Linux; dependencies are checked by the standard-library Python helper.
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec python3 "$source_root/scripts/portable_source.py" build "$source_root" "$@"
