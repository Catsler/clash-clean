import importlib.util
import socket as socket_module
import stat
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "lib" / "clean_clash.py"
sys.path.insert(0, str(MODULE_PATH.parent))
import mihomo_api
import subscription
from config_io import safe_label
SPEC = importlib.util.spec_from_file_location("clean_clash", MODULE_PATH)
assert SPEC and SPEC.loader
clean_clash = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = clean_clash
SPEC.loader.exec_module(clean_clash)

FIXTURES = ROOT / "tests" / "fixtures"


def provider_args(
    app_support: Path, provider_config: Path, backup_dir: Path, apply: bool
) -> Namespace:
    return Namespace(
        app_support=str(app_support),
        provider_config=str(provider_config),
        provider="example-provider",
        backup_dir=str(backup_dir),
        apply=apply,
        socket="/tmp/does-not-exist",
    )


def make_app_support(tmp_path: Path) -> Path:
    app_support = tmp_path / "app-support"
    (app_support / "profiles").mkdir(parents=True)
    (app_support / "profiles.yaml").write_text(
        (FIXTURES / "profiles-fixture.yaml").read_text(), encoding="utf-8"
    )
    (app_support / "profiles" / "example-merge.yaml").write_text(
        (FIXTURES / "profile.yaml").read_text(), encoding="utf-8"
    )
    return app_support


def test_host_suffix_requires_hostname_boundary() -> None:
    assert clean_clash.host_matches_suffix("edge.example.invalid", ".example.invalid")
    assert clean_clash.host_matches_suffix("EXAMPLE.INVALID.", "example.invalid")
    assert not clean_clash.host_matches_suffix("badexample.invalid", ".example.invalid")
    assert not clean_clash.host_matches_suffix("", ".example.invalid")


def test_diagnose_provider_report_detects_missing_filter_and_loopback() -> None:
    config = clean_clash.load_yaml(FIXTURES / "profile.yaml")
    providers = clean_clash.provider_config(FIXTURES / "providers.yaml")
    reports = clean_clash.provider_dns_report(config, providers)
    assert any("缺少 fake-ip 排除" in report for report in reports)
    assert not clean_clash.is_local_resolver("localhost.example.invalid")


def test_preview_does_not_write_target_or_backup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app_support = make_app_support(tmp_path)
    provider_config = FIXTURES / "providers.yaml"
    backup_dir = tmp_path / "backups"
    target = app_support / "profiles" / "example-merge.yaml"
    before = target.read_bytes()

    result = clean_clash.fix_provider_dns(
        provider_args(app_support, provider_config, backup_dir, apply=False)
    )

    assert result == 0
    assert target.read_bytes() == before
    assert not backup_dir.exists()
    assert "backup=" not in capsys.readouterr().out


def test_apply_is_atomic_backup_first_and_idempotent(tmp_path: Path) -> None:
    app_support = make_app_support(tmp_path)
    provider_config = FIXTURES / "providers.yaml"
    backup_dir = tmp_path / "backups"
    args = provider_args(app_support, provider_config, backup_dir, apply=True)
    target = app_support / "profiles" / "example-merge.yaml"

    assert clean_clash.fix_provider_dns(args) == 0
    first = target.read_bytes()
    assert list(backup_dir.glob("*.bak-*"))
    assert stat.S_IMODE(target.stat().st_mode) == 0o600

    assert clean_clash.fix_provider_dns(args) == 0
    assert target.read_bytes() == first
    assert len(list(backup_dir.glob("*.bak-*"))) == 2
    result = clean_clash.load_yaml(target)
    assert result["dns"]["fake-ip-filter"].count("+.example.invalid") == 1
    assert result["dns"]["proxy-server-nameserver"] == ["9.9.9.9", "1.1.1.1"]


def test_profile_entries_accept_only_https_and_safe_labels(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "items:\n"
        "  - type: remote\n"
        "    name: Safe Label\n"
        "    url: https://example.invalid/a?case=1\n"
        "  - type: remote\n"
        "    name: HTTP\n"
        "    url: http://example.invalid/a\n",
        encoding="utf-8",
    )
    entries = subscription.profile_entries(profiles)
    assert entries == [("Safe Label", "https://example.invalid/a?case=1")]
    assert safe_label("safe\nlabel", "fallback") == "safe label"


def test_check_subscription_does_not_print_urls(tmp_path: Path, monkeypatch, capsys) -> None:
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text((FIXTURES / "profiles-fixture.yaml").read_text(), encoding="utf-8")
    monkeypatch.setattr(subscription, "fetch_status", lambda url: 403)

    assert clean_clash.check_subscription(profiles) == 1
    output = capsys.readouterr().out
    assert "Example Provider" in output
    assert "subscription.example.invalid" not in output
    assert "case=fixture" not in output


def test_subscription_rejects_nonpublic_resolved_address(monkeypatch) -> None:
    monkeypatch.setattr(
        subscription.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(0, 0, 0, "", ("127.0.0.1", 443))],
    )
    assert subscription.fetch_status("https://example.invalid/feed") == 0


def test_subscription_rejects_embedded_credentials() -> None:
    assert subscription.parse_https_url("https://user:pass@example.invalid/feed") is None


def test_check_nodes_handles_selector_and_malformed_api(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    api_responses = {
        "/proxies": {
            "proxies": {
                "Auto": {"type": "Selector", "now": "Node A"},
                "Node A": {"type": "trojan"},
            }
        },
        "/proxies/Node%20A/delay?url=https%3A%2F%2Fwww.gstatic.com%2F"
        "generate_204&timeout=8000": {
            "delay": 123
        },
    }
    monkeypatch.setattr(
        mihomo_api, "api_json", lambda _path, endpoint, _secret="": api_responses[endpoint]
    )
    assert clean_clash.check_nodes(
        tmp_path / "mihomo.sock", "https://www.gstatic.com/generate_204"
    ) == 0
    assert "123 ms" in capsys.readouterr().out

    monkeypatch.setattr(mihomo_api, "api_json", lambda *_args: {"unexpected": []})
    with pytest.raises(clean_clash.ConfigError):
        clean_clash.check_nodes(tmp_path / "mihomo.sock", "https://example.invalid")


def test_socket_validation_rejects_symlink() -> None:
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:
        socket_path = Path(directory) / "mihomo.sock"
        server = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_STREAM)
        server.bind(str(socket_path))
        try:
            mihomo_api.validate_socket_path(socket_path)
            link = Path(directory) / "link.sock"
            link.symlink_to(socket_path)
            with pytest.raises(clean_clash.ConfigError, match="类型或所有权"):
                mihomo_api.validate_socket_path(link)
        finally:
            server.close()


def test_merge_uid_and_path_are_validated(tmp_path: Path) -> None:
    app_support = make_app_support(tmp_path)
    profiles = app_support / "profiles.yaml"
    profiles.write_text(
        "items:\n"
        "  - type: remote\n"
        "    name: Example Provider\n"
        "    url: https://example.invalid/profile\n"
        "    option:\n"
        "      merge: ../outside\n",
        encoding="utf-8",
    )
    args = provider_args(app_support, FIXTURES / "providers.yaml", tmp_path / "backups", False)
    with pytest.raises(clean_clash.ConfigError, match="merge UID"):
        clean_clash.fix_provider_dns(args)


def test_symlink_merge_target_is_rejected(tmp_path: Path) -> None:
    app_support = make_app_support(tmp_path)
    profiles = app_support / "profiles.yaml"
    profiles.write_text(
        "items:\n"
        "  - type: remote\n"
        "    name: Example Provider\n"
        "    url: https://example.invalid/profile\n"
        "    option:\n"
        "      merge: alias\n",
        encoding="utf-8",
    )
    (app_support / "profiles" / "alias.yaml").symlink_to("example-merge.yaml")
    args = provider_args(app_support, FIXTURES / "providers.yaml", tmp_path / "backups", False)
    with pytest.raises(clean_clash.ConfigError, match="受信任的 profiles 目录"):
        clean_clash.fix_provider_dns(args)


def test_diagnose_dry_run_does_not_create_state(tmp_path: Path, monkeypatch) -> None:
    app_support = tmp_path / "app-support"
    app_support.mkdir()
    (app_support / "clash-verge.yaml").write_text(
        "mode: rule\ntun:\n  enable: true\ndns:\n  enhanced-mode: fake-ip\n",
        encoding="utf-8",
    )
    (app_support / "verge.yaml").write_text("enable_tun_mode: true\n", encoding="utf-8")
    commands = []
    monkeypatch.setattr(
        clean_clash, "command_succeeded", lambda command: commands.append(command) or True
    )
    monkeypatch.setattr(clean_clash, "command_output", lambda _command: "interface: utun1024")
    args = Namespace(
        app_support=str(app_support),
        socket=str(tmp_path / "missing.sock"),
        state_dir=str(tmp_path / "state"),
        provider_config=None,
        dry_run=True,
    )
    assert clean_clash.diagnose(args) == 1
    assert any(
        "[[:space:]]" in argument
        for command in commands
        for argument in command
    )
    assert not (tmp_path / "state").exists()
