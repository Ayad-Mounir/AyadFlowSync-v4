#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github.client
=============
GitRunner     — تنفيذ أوامر Git مع دعم الإلغاء.
GitHubAPI     — HTTP client للـ GitHub REST API.
"""

import os
import sys
import signal
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import requests as _req
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

_logger = logging.getLogger("AyadFlowSync.github")


# ══════════════════════════════════════════════════════════════════
# GitRunner — تنفيذ Git commands
# ══════════════════════════════════════════════════════════════════

class GitRunner:
    """
    تنفيذ أوامر Git مع:
    - دعم الإلغاء (kill)
    - timeout قابل للتعديل
    - logging تلقائي
    """

    DEFAULT_TIMEOUT = 300   # 5 دقائق

    def __init__(self, cwd: Path, extra_env: Optional[Dict] = None):
        self.cwd       = Path(cwd)
        self._process: Optional[subprocess.Popen] = None
        self._lock     = threading.Lock()
        self._env      = extra_env or {}

    def run(
        self,
        args:    List[str],
        check:   bool = True,
        timeout: int  = None,
    ) -> subprocess.CompletedProcess:
        """
        تنفيذ أمر git.
        يرفع RuntimeError عند الفشل إذا check=True.
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        cmd     = ["git"] + args

        _logger.debug(f"git {args[0]} (cwd={self.cwd.name})")

        env = None
        if self._env:
            env = os.environ.copy()
            env.update(self._env)

        with self._lock:
            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(self.cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    start_new_session=(sys.platform != "win32"),
                    env=env,
                )
            except FileNotFoundError:
                raise RuntimeError("Git غير مثبت أو غير موجود في PATH")

        try:
            stdout, stderr = self._process.communicate(timeout=timeout)
            rc = self._process.returncode
        except subprocess.TimeoutExpired:
            self.kill()
            raise RuntimeError(f"Git timeout بعد {timeout}s: git {args[0]}")
        finally:
            with self._lock:
                self._process = None

        if check and rc != 0:
            _logger.warning(f"git {args[0]} failed rc={rc}: {stderr[:200]}")
            raise subprocess.CalledProcessError(rc, cmd, stdout, stderr)

        _logger.debug(f"git {args[0]} OK rc={rc}")
        return subprocess.CompletedProcess(cmd, rc, stdout, stderr)

    def kill(self) -> None:
        """إيقاف العملية الجارية فوراً."""
        with self._lock:
            p = self._process
        if p and p.poll() is None:
            try:
                if sys.platform == "win32":
                    p.terminate()
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            try:
                p.kill()
            except Exception:
                pass

    @staticmethod
    def verify_token(token: str) -> bool:
        """تحقق من صحة الـ Token عبر GitHub API."""
        if not _REQUESTS:
            return bool(token)
        try:
            r = _req.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}"},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def is_git_repo(path: Path) -> bool:
        return (Path(path) / ".git").exists()

    @staticmethod
    def has_git() -> bool:
        try:
            subprocess.run(["git", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════
# GitHubAPI — HTTP wrapper للـ REST API
# ══════════════════════════════════════════════════════════════════

class GitHubAPI:
    """
    HTTP client بسيط للـ GitHub REST API v3.
    يعيد dict/list للنجاح، يرفع RuntimeError عند الفشل.
    """

    BASE = "https://api.github.com"

    def __init__(self, token: str):
        if not token:
            raise ValueError("Token مطلوب")
        self._token = token
        self._session = None
        if _REQUESTS:
            self._session = _req.Session()
            self._session.headers.update({
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            })

    def get(self, path: str, **params) -> Any:
        return self._request("GET", path, params=params or None)

    def post(self, path: str, body: Dict) -> Any:
        return self._request("POST", path, json=body)

    def patch(self, path: str, body: Dict) -> Any:
        return self._request("PATCH", path, json=body)

    def delete(self, path: str) -> None:
        self._request("DELETE", path, expect_json=False)

    def get_all_pages(self, path: str, per_page: int = 100) -> List:
        """جلب كل الصفحات تلقائياً."""
        results = []
        page    = 1
        while True:
            data = self.get(path, per_page=per_page, page=page)
            if not data:
                break
            results.extend(data if isinstance(data, list) else [data])
            if len(data) < per_page:
                break
            page += 1
        return results

    def _request(self, method: str, path: str, expect_json: bool = True, **kwargs) -> Any:
        if not _REQUESTS:
            raise RuntimeError("مكتبة requests غير مثبتة")
        url = f"{self.BASE}{path}"
        try:
            r = self._session.request(method, url, timeout=30, **kwargs)
        except Exception as e:
            raise RuntimeError(f"خطأ في الشبكة: {e}")

        if r.status_code == 403 and "rate limit" in r.text.lower():
            raise RuntimeError("GitHub rate limit — انتظر ساعة")
        if r.status_code == 404:
            raise RuntimeError(f"غير موجود: {path}")
        if r.status_code not in (200, 201, 204):
            msg = r.json().get("message", r.text[:200]) if r.content else r.status_code
            raise RuntimeError(f"GitHub API error {r.status_code}: {msg}")

        if expect_json and r.content:
            return r.json()
        return None

    @property
    def username(self) -> str:
        """اسم المستخدم من الـ Token."""
        try:
            return self.get("/user").get("login", "")
        except Exception:
            return ""
