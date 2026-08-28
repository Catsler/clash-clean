#!/usr/bin/env python3
"""Safe, provider-neutral helpers for the clean-clash skill."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from config_io import (
    ConfigError,
    atomic_write_json,
    atomic_write_yaml,
    host_matches_suffix,
    load_yaml,
    require_mapping,
    require_string_list,
    secure_backup,
)
from mihomo_api import check_nodes
from provider_dns import is_local_resolver, provider_dns_report
from subscription import check_subscription


DEFAULT_APP_SUPPORT = (
    Path.home()
    / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
)
DEFAULT_SOCKET = Path("/tmp/verge/verge-mihomo.sock")
DEFAULT_STATE = Path.home() / "Library/Application Support/clean-clash/state"


def provider_config(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    providers = data.get("providers")
    if not isinstance(providers, dict):
        raise ConfigError("provider 配置缺少 providers mapping")
    return providers


def command_succeeded(command: list[str]) -> bool:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, check=False
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def command_output(command: list[str]) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def diagnose(args: argparse.Namespace) -> int:
    app_support = Path(args.app_support)
    config = load_yaml(app_support / "clash-verge.yaml")
    verge = load_yaml(app_support / "verge.yaml")
    tun = require_mapping(config.get("tun"), "tun")
    dns = require_mapping(config.get("dns"), "dns")
    mode = str(config.get("mode", "unknown")).lower()
    values = {
        "tun": tun.get("enable") is True,
        "ui_tun": verge.get("enable_tun_mode") is True,
        "mode": mode in {"rule", "global"},
        "core": command_succeeded(
            ["pgrep", "-f", r"(^|/)verge-mihomo(-alpha)?([[:space:]]|$)"]
        ),
        "utun": command_succeeded(["ifconfig", "utun1024"]),
        "route": "utun1024" in command_output(["route", "-n", "get", "198.18.0.1"]),
        "socket": Path(args.socket).is_socket(),
    }
    print(
        "[DIAG] TUN={} UI={} mode={} core={} utun1024={} route={} socket={} dns={}"
        .format(
            values["tun"], values["ui_tun"], mode, values["core"], values["utun"],
            values["route"], values["socket"], dns.get("enhanced-mode", "unknown")
        )
    )
    issues = [
        name for name in ("tun", "ui_tun", "mode", "core", "utun", "route", "socket")
        if not values[name]
    ]
    if args.provider_config:
        provider_path = Path(args.provider_config)
        if not provider_path.is_file():
            raise ConfigError(f"provider 配置不存在：{provider_path}")
        for report in provider_dns_report(config, provider_config(provider_path)):
            print(report)
            issues.append("provider-dns")
    if not args.dry_run:
        state_dir = Path(args.state_dir)
        state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_write_json(state_dir / "last-check.json", values)
    return int(bool(issues))


def fix_provider_dns(args: argparse.Namespace) -> int:
    if not args.apply:
        print("[PROVIDER] 这是只读预览；写入必须显式使用 --apply")
    providers = provider_config(Path(args.provider_config))
    raw = providers.get(args.provider)
    if not isinstance(raw, dict):
        raise ConfigError(f"找不到 provider：{args.provider}")
    profile_name = raw.get("profile_name")
    if not isinstance(profile_name, str) or not profile_name:
        raise ConfigError("provider 缺少 profile_name")
    profiles_path = Path(args.app_support) / "profiles.yaml"
    profile_data = load_yaml(profiles_path)
    profiles = profile_data.get("items")
    if not isinstance(profiles, list):
        raise ConfigError("profiles.yaml 缺少 items list")
    matches = [
        item for item in profiles
        if isinstance(item, dict)
        and item.get("type") == "remote"
        and item.get("name") == profile_name
    ]
    if len(matches) != 1:
        raise ConfigError(f"profile_name 匹配数量不是 1：{profile_name}")
    option = require_mapping(matches[0].get("option"), "profile option")
    merge_id = option.get("merge")
    if not isinstance(merge_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", merge_id):
        raise ConfigError("merge UID 格式无效")
    profiles_dir = (Path(args.app_support) / "profiles").resolve()
    candidate = profiles_dir / f"{merge_id}.yaml"
    if candidate.parent != profiles_dir or candidate.is_symlink() or not candidate.is_file():
        raise ConfigError("merge 目标不在受信任的 profiles 目录")
    target = candidate
    data = load_yaml(target)
    dns = require_mapping(data.get("dns"), "merge dns")
    data["dns"] = dns
    filters = require_string_list(dns.get("fake-ip-filter"), "fake-ip-filter")
    resolvers = require_string_list(
        dns.get("proxy-server-nameserver"), "proxy-server-nameserver"
    )
    dns["fake-ip-filter"] = filters
    dns["proxy-server-nameserver"] = resolvers
    expected_filters = require_string_list(
        raw.get("fake_ip_filters"), "fake_ip_filters"
    )
    expected_resolvers = require_string_list(
        raw.get("proxy_server_nameservers"), "proxy_server_nameservers"
    )
    for item in expected_filters:
        if item not in filters:
            filters.append(item)
    dns["proxy-server-nameserver"] = [
        item for item in resolvers if not is_local_resolver(item)
    ]
    for item in expected_resolvers:
        if item not in dns["proxy-server-nameserver"]:
            dns["proxy-server-nameserver"].append(item)
    print(
        f"[PROVIDER] target={target.name} filters={len(filters)} "
        f"resolvers={len(dns['proxy-server-nameserver'])}"
    )
    if args.apply:
        backup = secure_backup(target, Path(args.backup_dir))
        atomic_write_yaml(target, data)
        print(f"[PROVIDER] backup={backup}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Safe Clash Verge diagnostics")
    sub = root.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--app-support",
        default=os.environ.get("CLEAN_CLASH_APP_SUPPORT", str(DEFAULT_APP_SUPPORT)),
    )
    common.add_argument(
        "--socket", default=os.environ.get("CLEAN_CLASH_SOCKET", str(DEFAULT_SOCKET))
    )
    diagnose_parser = sub.add_parser("diagnose", parents=[common])
    diagnose_parser.add_argument(
        "--state-dir",
        default=os.environ.get("CLEAN_CLASH_STATE_DIR", str(DEFAULT_STATE)),
    )
    diagnose_parser.add_argument(
        "--provider-config", default=os.environ.get("CLEAN_CLASH_PROVIDER_CONFIG")
    )
    diagnose_parser.add_argument("--dry-run", action="store_true")
    nodes = sub.add_parser("check-nodes", parents=[common])
    nodes.add_argument(
        "--test-url",
        default=os.environ.get("CLEAN_CLASH_TEST_URL", "https://www.gstatic.com/generate_204"),
    )
    subs = sub.add_parser("check-subscription", parents=[common])
    provider = sub.add_parser("fix-provider-dns", parents=[common])
    provider.add_argument(
        "--provider-config", default=os.environ.get("CLEAN_CLASH_PROVIDER_CONFIG")
    )
    provider.add_argument("--provider", required=True)
    provider.add_argument(
        "--backup-dir",
        default=os.environ.get("CLEAN_CLASH_BACKUP_DIR", str(DEFAULT_APP_SUPPORT / "backups")),
    )
    provider.add_argument("--apply", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "diagnose":
            return diagnose(args)
        if args.command == "check-nodes":
            return check_nodes(Path(args.socket), args.test_url)
        if args.command == "check-subscription":
            return check_subscription(Path(args.app_support) / "profiles.yaml")
        if args.command == "fix-provider-dns":
            if not args.provider_config:
                raise ConfigError("需要 --provider-config 或 CLEAN_CLASH_PROVIDER_CONFIG")
            return fix_provider_dns(args)
    except (ConfigError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
