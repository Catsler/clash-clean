"""Validated YAML and private atomic file operations for clean-clash."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when a local Clash or provider file is invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"无法读取 YAML：{path}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"YAML 顶层必须是 mapping：{path}")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"{label} 必须是 list")
    return value


def require_string_list(value: Any, label: str) -> list[str]:
    values = require_list(value, label)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ConfigError(f"{label} 必须只包含非空字符串")
    return values


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{label} 必须是 mapping")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_yaml(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, yaml.safe_dump(value, allow_unicode=True, sort_keys=False))


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False) + "\n")


def secure_backup(path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"{path.name}.bak-{stamp}-{uuid.uuid4().hex[:8]}"
    shutil.copy2(path, destination)
    destination.chmod(0o600)
    return destination


def normalize_host(value: str) -> str:
    return value.strip().rstrip(".").lower()


def host_matches_suffix(host: str, suffix: str) -> bool:
    host = normalize_host(host)
    suffix = normalize_host(suffix).lstrip(".")
    return bool(host and suffix and (host == suffix or host.endswith(f".{suffix}")))


def safe_label(value: Any, fallback: str) -> str:
    text = str(value or fallback).replace("\n", " ").replace("\r", " ")
    return "".join(char for char in text if char.isprintable())[:80] or fallback
