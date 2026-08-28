#!/bin/sh
# Preview/apply a generic provider DNS merge patch.
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/lib/clean_clash.py" fix-provider-dns "$@"
