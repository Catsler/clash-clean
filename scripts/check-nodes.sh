#!/bin/sh
# Check active Mihomo selector nodes through the Unix API.
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/lib/clean_clash.py" check-nodes "$@"
