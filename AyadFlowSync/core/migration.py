#!/usr/bin/env python3
"""
core.migration — Automatic migration from v2 → v3.
Runs once on first launch, then saves a version marker.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import List, Tuple

from .app_config import AppConfig

_logger = logging.getLogger("AyadFlowSync.migration")

CURRENT_VERSION = 3
VERSION_FILE = AppConfig.DATA_DIR / ".schema_version"


def get_schema_version() -> int:
    try:
        if VERSION_FILE.exists():
            return int(VERSION_FILE.read_text().strip())
    except (ValueError, OSError):
        pass
    return 1  # Default: assume v1/v2


def set_schema_version(v: int) -> None:
    try:
        VERSION_FILE.write_text(str(v), encoding='utf-8')
    except OSError:
        pass


def needs_migration() -> bool:
    return get_schema_version() < CURRENT_VERSION


def run_all_migrations() -> List[str]:
    """Run pending migrations. Returns list of messages."""
    messages = []
    current = get_schema_version()

    if current < 2:
        msgs = _migrate_v1_to_v2()
        messages.extend(msgs)

    if current < 3:
        msgs = _migrate_v2_to_v3()
        messages.extend(msgs)

    set_schema_version(CURRENT_VERSION)
    if messages:
        _logger.info(f"Migration complete: {len(messages)} actions")
        for m in messages:
            _logger.info(f"  • {m}")
    return messages


def _migrate_v1_to_v2() -> List[str]:
    """v1 → v2: Mostly structural, nothing to migrate."""
    return ["v1→v2: Schema updated"]


def _migrate_v2_to_v3() -> List[str]:
    """v2 → v3: Encrypt plaintext tokens, clean up old files."""
    messages = []

    # 1. Migrate plaintext GitHub token to encrypted
    old_token = AppConfig.DATA_DIR / ".gh_token"
    if old_token.exists():
        try:
            token = old_token.read_text(encoding='utf-8').strip()
            if token and len(token) > 10:
                from ..security.secure_store import SecureStore
                new_path = AppConfig.DATA_DIR / ".gh_token_v3"
                if SecureStore.save(new_path, token):
                    # Securely delete old plaintext
                    _overwrite_and_delete(old_token)
                    messages.append("GitHub token encrypted (was plaintext)")
                else:
                    messages.append("⚠️ Failed to encrypt GitHub token")
        except Exception as e:
            messages.append(f"⚠️ Token migration error: {e}")

    # 2. Migrate old JSON hash cache to new format
    old_caches = list(AppConfig.DATA_DIR.glob("hash_cache_*.json"))
    if old_caches:
        for cache in old_caches:
            try:
                bak = cache.with_suffix('.json.v2bak')
                shutil.copy2(cache, bak)
                messages.append(f"Hash cache backed up: {cache.name}")
            except OSError:
                pass

    # 3. Migrate old sync index JSON files
    old_index_dir = AppConfig.DATA_DIR / "sync_index"
    if old_index_dir.exists():
        idx_files = list(old_index_dir.glob("idx_*.json"))
        if idx_files:
            messages.append(f"Found {len(idx_files)} old sync index files (will be migrated on use)")

    # 4. Clean up old temp files
    cleaned = 0
    for pattern in ["*.__tmp__", "*.tmpsync", "*.__dt__", "*.delta_old"]:
        for tmp in AppConfig.DATA_DIR.rglob(pattern):
            try:
                tmp.unlink()
                cleaned += 1
            except OSError:
                pass
    if cleaned:
        messages.append(f"Cleaned {cleaned} temp files")

    # 5. Clean up old accumark files
    old_marker = AppConfig.DATA_DIR / ".first_run_done"
    if old_marker.exists():
        old_marker.unlink(missing_ok=True)

    return messages


def _overwrite_and_delete(filepath: Path) -> None:
    """Securely delete: overwrite with random bytes then delete."""
    try:
        size = filepath.stat().st_size
        if size > 0:
            import os
            with open(filepath, 'wb') as f:
                f.write(os.urandom(size))
                f.flush()
                os.fsync(f.fileno())
        filepath.unlink()
    except OSError:
        filepath.unlink(missing_ok=True)
