# Security Policy

## Scope

This project is a local macOS diagnostic skill for Clash Verge Rev and Mihomo. It
is not a subscription service and does not handle account recovery.

## Do not disclose

When reporting an issue, remove subscription URLs, query parameters, tokens,
UUIDs, passwords, API secrets, complete profiles, node lists, and logs that
identify an account or provider. The repository intentionally contains no real
provider configuration.

## Supported reports

Report reproducible security issues through a private GitHub Security Advisory
when available. If that channel is unavailable, open a minimal issue without
sensitive data and ask for a private contact route. Do not publish credentials
in an issue or pull request.

## Local safety model

- Diagnostic commands are read-only except for an optional state snapshot.
- `--dry-run` performs no writes, backups, process changes, or privileged actions.
- Provider changes require explicit `--apply`, use a private backup, and write
  atomically.
- DNS flushing requires explicit `--apply` and an interactive `sudo -v`.
- The scripts never accept passwords as arguments and never use `sudo -S`.
- The scripts do not edit generated Clash configuration or restart Clash.
- Subscription checks allow HTTPS only, reject non-global DNS results, pin the
  validated address for TLS, and do not follow redirects.
- Mihomo API connections validate the socket parent directory, socket type and
  ownership before sending the optional API secret.

Users are responsible for protecting files kept outside this repository.
