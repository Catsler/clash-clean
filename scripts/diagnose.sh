#!/bin/sh
# Diagnose Clash Verge without modifying configuration.
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/lib/clean_clash.py" diagnose "$@"
