#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

# Wrappers must reject malformed input without touching local files.
if "$ROOT/scripts/fix-provider-dns.sh" --provider example-provider >/dev/null 2>&1; then
  printf '%s\n' 'fix-provider-dns unexpectedly accepted missing provider config' >&2
  exit 1
fi

if "$ROOT/scripts/flush-dns.sh" >/dev/null 2>&1; then
  :
else
  printf '%s\n' 'flush-dns preview should be successful on macOS' >&2
  exit 1
fi

printf '%s\n' 'shell wrapper checks passed'
