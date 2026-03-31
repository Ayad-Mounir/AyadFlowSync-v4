#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github.upload_log
=================
UploadLog — سجل محلي لكل مشروع رُفع على GitHub.

يحفظ في data/upload_log.json:
{
  "projects": [
    {
      "local_path":   "C:/projects/myapp",
      "source":       "PC" | "USB",
      "repo_name":    "myapp",
      "repo_url":     "https://github.com/user/myapp",
      "last_push":    "2024-03-16T10:00:00",
      "last_push_ts": 1710583200.0,
      "push_count":   3,
      "status":       "synced" | "changed" | "unknown"
    }
  ]
}
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from ..core.app_config import AppConfig

_logger = logging.getLogger("AyadFlowSync.github")

UPLOAD_LOG_FILE = AppConfig.DATA_DIR / "upload_log.json"


class UploadLog:
    """سجل محلي لمشاريع GitHub — يعمل بدون إنترنت."""

    @classmethod
    def _load(cls) -> List[Dict]:
        """
        ✅ FIX v4.1: يدعم الصيغتين:
          - صيغة قديمة: {"projects": [...]}
          - صيغة جديدة: [...]  (list مباشر)
        """
        try:
            if UPLOAD_LOG_FILE.exists():
                data = json.loads(UPLOAD_LOG_FILE.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("projects", [])
        except Exception:
            pass
        return []

    @classmethod
    def _save(cls, projects: List[Dict]):
        try:
            UPLOAD_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(str(UPLOAD_LOG_FILE) + '.tmp')
            tmp.write_text(
                json.dumps(projects, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            tmp.replace(UPLOAD_LOG_FILE)
        except Exception as e:
            _logger.warning(f"UploadLog save: {e}")

    @classmethod
    def record(cls, local_path: str, source: str,
               repo_name: str, repo_url: str, pc_name: str = ""):
        """
        ⚡ v4.0: يُسجَّل بعد كل رفع — يكتشف الفلاشة ويحفظ مسار نسبي.
        """
        from ..core.app_config import AppConfig
        if not pc_name:
            pc_name = AppConfig.PC_NAME or "Unknown"

        # ⚡ v4.0: كشف تلقائي — هل المشروع على الفلاشة؟
        p = Path(local_path)
        vault = AppConfig.VAULT_DIR
        is_vault = False
        vault_rel = ""
        try:
            rel = p.relative_to(vault)
            is_vault = True
            vault_rel = str(rel).replace('\\', '/')
            if not source or source == "PC":
                source = "USB"
        except ValueError:
            pass

        projects = cls._load()
        now_ts   = time.time()
        now_iso  = datetime.now().isoformat()

        for proj in projects:
            match = (proj.get("repo_name") == repo_name
                     or (vault_rel and proj.get("vault_rel") == vault_rel)
                     or proj.get("local_path") == str(local_path))
            if match:
                proj["local_path"]   = str(local_path)
                proj["source"]       = source
                proj["repo_url"]     = repo_url
                proj["last_push"]    = now_iso
                proj["last_push_ts"] = now_ts
                proj["push_count"]   = proj.get("push_count", 0) + 1
                proj["status"]       = "synced"
                proj["pc_name"]      = pc_name
                proj["vault_rel"]    = vault_rel
                proj["is_vault"]     = is_vault
                cls._save(projects)
                return

        projects.append({
            "local_path": str(local_path), "source": source,
            "repo_name": repo_name, "repo_url": repo_url,
            "last_push": now_iso, "last_push_ts": now_ts,
            "push_count": 1, "status": "synced",
            "pc_name": pc_name, "vault_rel": vault_rel, "is_vault": is_vault,
        })
        cls._save(projects)

    @classmethod
    def _resolve_path(cls, p: Dict) -> Path:
        """
        ⚡ v4.0: يحل المسار الصحيح حتى لو الفلاشة تغير حرف القرص.
        """
        from ..core.app_config import AppConfig
        vault_rel = p.get("vault_rel", "")
        if vault_rel and p.get("is_vault"):
            resolved = AppConfig.VAULT_DIR / vault_rel
            if resolved.exists():
                return resolved
        saved = Path(p.get("local_path", ""))
        if saved.exists():
            return saved
        name = p.get("repo_name", "")
        if name:
            fallback = AppConfig.VAULT_DIR / name
            if fallback.exists():
                return fallback
        return saved

    @classmethod
    def get_all(cls) -> List[Dict]:
        """⚡ v4.0: جلب مع حل المسارات الذكي."""
        projects = cls._load()
        for p in projects:
            p["_resolved_path"] = str(cls._resolve_path(p))
            p["status"] = cls._check_status(p)
        return projects

    @classmethod
    def _check_status(cls, p: Dict) -> str:
        """⚡ v4.0: فحص حالة — يستخدم المسار المحلول + scandir."""
        import os
        path = cls._resolve_path(p)
        if not path.exists():
            return "missing"
        last_push_ts = p.get("last_push_ts", 0)
        if not last_push_ts:
            return "unknown"
        try:
            checked = 0
            stack = [str(path)]
            while stack and checked < 300:
                d = stack.pop()
                try:
                    with os.scandir(d) as entries:
                        for entry in entries:
                            if entry.name.startswith(".ayadsync") or entry.name == ".git":
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                checked += 1
                                try:
                                    if entry.stat().st_mtime > last_push_ts + 2:
                                        return "changed"
                                except OSError:
                                    pass
                except OSError:
                    pass
        except Exception:
            return "unknown"
        return "synced"

    @classmethod
    def remove(cls, repo_name: str):
        """حذف مشروع من السجل."""
        projects = cls._load()
        projects = [p for p in projects if p.get("repo_name") != repo_name]
        cls._save(projects)

    @classmethod
    def clear_all(cls):
        cls._save([])
