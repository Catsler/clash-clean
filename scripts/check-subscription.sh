#!/bin/sh
# Check remote profile status without printing URLs or query strings.
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/lib/clean_clash.py" check-subscription "$@"
