# Changelog

## [Unreleased]

- Add system-resolver diagnostics (`sysdns`/`probe`/`aaaa`/`excluded`/`sniffer`) that catch GFW-poisoned system DNS under TUN fake-IP.
- Document the system-DNS repair procedure (listener-aware branch selection, backup, rollback) and 12 known DIAG pitfalls in SKILL.md.
- Resolve the Mihomo control socket dynamically and detect the TUN interface via route lookup instead of hardcoded paths.
- Continue hardening the provider-neutral diagnostic core and fixture coverage.

## [0.1.0] - 2026-08-28

- Publish a sanitized macOS Clash Verge Rev / Mihomo diagnostic skill.
- Add TUN, core, interface, route, fake-IP DNS, subscription, and node checks.
- Add explicit, backup-first provider DNS merge repair.
- Add opt-in macOS DNS cache flushing.
