# Architecture

## Boundary

```text
Claude Code skill
      │
      ▼
small shell wrappers ──► Python core (read/validate/atomic patch)
      │                              │
      │                              ├── Clash Verge YAML (local read)
      │                              ├── provider rules (external read)
      │                              └── Mihomo Unix API (local read)
      └── macOS DNS commands (only flush-dns.sh --apply)
```

The repository is provider-neutral. Real provider rules and all account-bound files stay
outside the checkout.

## State machine

```text
IDLE → DIAG → FIX → RELOAD → VERIFY → DONE / ERROR
```

- **DIAG** is read-only except an optional diagnostic snapshot outside the repository.
- **FIX** validates all inputs, computes a minimal merge patch, and requires `--apply`.
- **RELOAD** is intentionally a user/UI action because Clash Verge owns generated config.
- **VERIFY** checks resulting configuration and node behavior independently.
- Any invalid input or failed external check transitions to **ERROR** with non-zero exit.

## Data flow

1. `profiles.yaml` is parsed only to locate an exact remote profile name.
2. Its merge UID is accepted only when it matches a conservative identifier schema.
3. The resolved merge file must be a regular file directly under `profiles/`.
4. Provider suffix rules are compared with hostname boundaries, preventing `bad-example.invalid`
   from matching `.example.invalid`.
5. The repair removes loopback proxy resolvers, adds configured external resolvers and missing
   fake-IP filters, then writes through a private backup and atomic replacement.

## Security properties

- No credentials are accepted as positional secrets or printed.
- API secrets come from an environment variable.
- Dry-run has no writes or privileged subprocesses.
- YAML parsing is strict about top-level mappings and expected list/mapping fields.
- The scripts never edit `clash-verge.yaml`, kill processes, or delete user data.

## Extension points

Environment variables configure application support, socket, state, backup and provider paths.
The provider schema can grow only with corresponding validation, fixtures and documentation;
real provider examples do not belong in the repository.
