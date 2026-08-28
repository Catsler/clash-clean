"""Provider DNS matching and diagnostics."""
from __future__ import annotations

import urllib.parse
from typing import Any

from config_io import (
    ConfigError,
    host_matches_suffix,
    normalize_host,
    require_list,
    require_mapping,
    require_string_list,
    safe_label,
)


def is_local_resolver(value: Any) -> bool:
    text = str(value).strip().lower()
    candidate = text if "://" in text else f"//{text}"
    try:
        host = urllib.parse.urlparse(candidate).hostname or text
    except ValueError:
        host = text
    return host == "localhost" or host == "::1" or host.startswith("127.")


def provider_dns_report(config: dict[str, Any], providers: dict[str, Any]) -> list[str]:
    dns = require_mapping(config.get("dns"), "dns")
    raw_filters = require_string_list(dns.get("fake-ip-filter"), "fake-ip-filter")
    raw_resolvers = require_string_list(
        dns.get("proxy-server-nameserver"), "proxy-server-nameserver"
    )
    filters = {normalize_host(item).lstrip("+") for item in raw_filters}
    raw_servers = require_list(config.get("proxies"), "proxies")
    if any(not isinstance(item, dict) for item in raw_servers):
        raise ConfigError("proxies 必须只包含 mapping")
    servers = [str(item.get("server", "")) for item in raw_servers]
    reports = []
    for provider_id, raw in providers.items():
        if not isinstance(raw, dict):
            reports.append(
                f"[PROVIDER] {safe_label(provider_id, 'provider')}: 配置必须是 mapping"
            )
            continue
        suffixes = require_string_list(raw.get("server_suffixes"), "server_suffixes")
        expected_filters = require_string_list(
            raw.get("fake_ip_filters"), "fake_ip_filters"
        )
        matched = any(
            host_matches_suffix(server, suffix)
            for server in servers
            for suffix in suffixes
        )
        if not matched:
            continue
        expected = [normalize_host(item).lstrip("+") for item in expected_filters]
        missing = [item for item in expected if item not in filters]
        local = [item for item in raw_resolvers if is_local_resolver(item)]
        if missing:
            reports.append(
                f"[PROVIDER] {safe_label(provider_id, 'provider')}: "
                f"缺少 fake-ip 排除 {', '.join(missing)}"
            )
        if local:
            reports.append(f"[PROVIDER] {safe_label(provider_id, 'provider')}: 节点 DNS 含本地 resolver")
    return reports
