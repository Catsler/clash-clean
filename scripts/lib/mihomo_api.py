"""Read-only checks through the Mihomo Unix HTTP API."""
from __future__ import annotations

import http.client
import json
import os
import socket
import stat
import struct
import urllib.parse
from pathlib import Path
from typing import Any

from config_io import ConfigError, safe_label

NODE_TIMEOUT_MS = 8000
LOCAL_SOCKET_LEVEL = 0
LOCAL_PEERCRED_SIZE = 12
PROXY_TYPES = {
    "trojan",
    "vmess",
    "vless",
    "shadowsocks",
    "hysteria2",
    "tuic",
    "wireguard",
    "http",
    "socks5",
}


def validate_socket_path(socket_path: Path) -> None:
    """Reject replaceable or non-socket paths before sending API credentials."""
    try:
        parent_info = socket_path.parent.lstat()
        socket_info = socket_path.lstat()
    except OSError as exc:
        raise ConfigError(f"Mihomo socket 不可用：{socket_path}") from exc
    if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid not in {0, os.geteuid()}:
        raise ConfigError("Mihomo socket 父目录所有权不可信")
    if parent_info.st_mode & stat.S_IWOTH:
        raise ConfigError("Mihomo socket 父目录不能被全局写入")
    if parent_info.st_mode & stat.S_IWGRP:
        trusted_shared_dir = parent_info.st_uid == 0 and parent_info.st_mode & stat.S_ISGID
        if not trusted_shared_dir:
            raise ConfigError("Mihomo socket 父目录的组权限不可信")
    if not stat.S_ISSOCK(socket_info.st_mode) or socket_info.st_uid not in {0, os.geteuid()}:
        raise ConfigError("Mihomo socket 类型或所有权不可信")


def peer_uid(connection: socket.socket) -> int:
    """Return the macOS Unix peer UID, failing closed when unavailable."""
    peercred_option = getattr(socket, "LOCAL_PEERCRED", None)
    if peercred_option is None:
        raise ConfigError("当前平台不支持 Mihomo socket peer credential")
    try:
        credentials = connection.getsockopt(
            LOCAL_SOCKET_LEVEL, peercred_option, LOCAL_PEERCRED_SIZE
        )
        _version, uid = struct.unpack_from("=II", credentials)
    except (OSError, struct.error) as exc:
        raise ConfigError("无法验证 Mihomo socket peer credential") from exc
    return uid


class UnixHTTPConnection(http.client.HTTPConnection):
    """Minimal HTTP connection over a Unix domain socket."""

    def __init__(self, socket_path: Path, timeout: float = 12) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(str(self.socket_path))
            if peer_uid(self.sock) not in {0, os.geteuid()}:
                raise ConfigError("Mihomo socket peer credential 不可信")
        except Exception:
            self.sock.close()
            raise


def api_json(socket_path: Path, endpoint: str, secret: str = "") -> Any:
    validate_socket_path(socket_path)
    connection = UnixHTTPConnection(socket_path)
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    try:
        connection.request("GET", endpoint, headers=headers)
        response = connection.getresponse()
        body = response.read()
    except (OSError, http.client.HTTPException) as exc:
        raise ConfigError(f"Mihomo API 不可用：{socket_path}") from exc
    finally:
        connection.close()
    if response.status >= 400:
        raise ConfigError(f"Mihomo API 返回 HTTP {response.status}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ConfigError("Mihomo API 返回了无效 JSON") from exc


def check_nodes(socket_path: Path, test_url: str) -> int:
    try:
        parsed_url = urllib.parse.urlparse(test_url)
    except ValueError as exc:
        raise ConfigError("节点测试 URL 无效") from exc
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ConfigError("节点测试 URL 必须是带主机名的 HTTP(S) URL")
    data = api_json(
        socket_path, "/proxies", os.environ.get("CLEAN_CLASH_API_SECRET", "")
    )
    proxies = data.get("proxies") if isinstance(data, dict) else None
    if not isinstance(proxies, dict):
        raise ConfigError("Mihomo /proxies 返回格式无效")
    selected = []
    for value in proxies.values():
        proxy_type = str(value.get("type", "")).lower() if isinstance(value, dict) else ""
        if proxy_type in {"selector", "urltest", "fallback", "loadbalance"}:
            current = value.get("now")
            if isinstance(current, str) and current in proxies and current not in selected:
                selected.append(current)
    if not selected:
        selected = [
            name for name, value in proxies.items()
            if isinstance(value, dict)
            and str(value.get("type", "")).lower() in PROXY_TYPES
        ][:3]
    failed = False
    for name in selected:
        endpoint = "/proxies/" + urllib.parse.quote(name, safe="") + "/delay?"
        endpoint += urllib.parse.urlencode({"url": test_url, "timeout": NODE_TIMEOUT_MS})
        try:
            result = api_json(
                socket_path, endpoint, os.environ.get("CLEAN_CLASH_API_SECRET", "")
            )
        except ConfigError as exc:
            print(f"[NODE] ✗ {safe_label(name, 'node')}: {exc}")
            failed = True
            continue
        delay = result.get("delay") if isinstance(result, dict) else None
        if type(delay) is int:
            print(f"[NODE] ✓ {safe_label(name, 'node')}: {delay} ms")
        else:
            print(f"[NODE] ✗ {safe_label(name, 'node')}: 测试失败")
            failed = True
    if not selected:
        print("[NODE] ✗ 没有可测试的活动节点")
        return 1
    return int(failed)
