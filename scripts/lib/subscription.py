"""Read-only remote profile status checks."""
from __future__ import annotations

import http.client
import ipaddress
import socket
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

from config_io import ConfigError, load_yaml, safe_label


def resolve_public_addresses(hostname: str, port: int) -> list[str]:
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        return []
    resolved = []
    for address in addresses:
        try:
            ip_address = ipaddress.ip_address(address[4][0])
        except (IndexError, ValueError):
            return []
        if not ip_address.is_global:
            return []
        if str(ip_address) not in resolved:
            resolved.append(str(ip_address))
    return resolved


def has_public_address(hostname: str, port: int) -> bool:
    return bool(resolve_public_addresses(hostname, port))


def parse_https_url(url: str) -> urllib.parse.ParseResult | None:
    try:
        parsed = urllib.parse.urlparse(url)
        parsed.port
    except (TypeError, ValueError):
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None
    return parsed


def profile_entries(path: Path) -> list[tuple[str, str]]:
    data = load_yaml(path)
    items = data.get("items")
    if not isinstance(items, list):
        raise ConfigError("profiles.yaml 缺少 items list")
    entries = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "remote":
            continue
        url = item.get("url")
        parsed = parse_https_url(url) if isinstance(url, str) else None
        if parsed is None:
            continue
        entries.append((safe_label(item.get("name"), "unnamed-profile"), url))
    return entries


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that pins TCP dialing to a validated public address."""

    def __init__(self, hostname: str, address: str, port: int, timeout: float) -> None:
        super().__init__(hostname, port, timeout=timeout)
        self.address = address
        self._create_connection = self._connect_to_pinned_address

    def _connect_to_pinned_address(
        self, _address: tuple[str, int], timeout: float, source_address: Any = None
    ) -> socket.socket:
        return socket.create_connection((self.address, self.port), timeout, source_address)


def fetch_status(url: str, timeout: float = 12) -> int:
    parsed = parse_https_url(url)
    if parsed is None or parsed.hostname is None:
        return 0
    port = parsed.port or 443
    addresses = resolve_public_addresses(parsed.hostname, port)
    if not addresses:
        return 0
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    for address in addresses:
        connection = PinnedHTTPSConnection(parsed.hostname, address, port, timeout)
        try:
            connection.request("GET", path, headers={"User-Agent": "clean-clash/0.1"})
            response = connection.getresponse()
            response.read()
            return int(response.status)
        except (OSError, http.client.HTTPException, urllib.error.URLError):
            continue
        finally:
            connection.close()
    return 0


def check_subscription(profiles: Path) -> int:
    failed = False
    for label, url in profile_entries(profiles):
        status = fetch_status(url)
        if 200 <= status < 300:
            print(f"[SUB] ✓ {label}: {status}")
        elif status == 403:
            print(f"[SUB] ✗ {label}: 403（服务端拒绝）")
            failed = True
        elif status == 0:
            print(f"[SUB] ? {label}: 000（连接失败）")
            failed = True
        else:
            print(f"[SUB] ? {label}: {status}")
            failed = True
    return int(failed)
