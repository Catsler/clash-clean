#!/bin/sh
# Flush the macOS DNS cache only after explicit confirmation.
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
  printf '%s\n' '[DNS] 仅支持 macOS' >&2
  exit 2
fi

if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
  printf '%s\n' '[DNS] 只读预览；刷新请使用: flush-dns.sh --apply'
  exit 0
fi

sudo -v
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
printf '%s\n' '[DNS] macOS DNS 缓存已刷新'
