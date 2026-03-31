#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github.manager
==============
RepoMgr — إدارة كاملة للمستودعات (قراءة / إنشاء / حذف / metadata).
"""

import logging
from typing import Dict, List, Optional

from .client import GitHubAPI

_logger = logging.getLogger("AyadFlowSync.github")


class RepoMgr:
    """
    إدارة مستودعات GitHub.

    mgr = RepoMgr(token)
    repos = mgr.list_repos()
    mgr.delete_repo("user/repo")
    info  = mgr.get_repo("user/repo")
    """

    def __init__(self, token: str):
        self._api = GitHubAPI(token)

    def list_repos(
        self,
        visibility: str = "all",   # all | public | private
        sort:       str = "updated",
    ) -> List[Dict]:
        """
        جلب كل مستودعات المستخدم مع metadata كاملة.
        """
        try:
            repos = self._api.get_all_pages(
                "/user/repos",
                per_page=100,
            )
            # ترتيب
            key_map = {"updated": "updated_at", "name": "name", "stars": "stargazers_count"}
            key     = key_map.get(sort, "updated_at")
            reverse = (sort in ("updated", "stars"))
            repos.sort(key=lambda r: r.get(key, ""), reverse=reverse)

            # فلترة
            if visibility != "all":
                is_priv = (visibility == "private")
                repos   = [r for r in repos if r.get("private") == is_priv]

            _logger.info(f"RepoMgr: {len(repos)} repos")
            return repos
        except Exception as e:
            _logger.error(f"list_repos: {e}")
            return []

    def get_repo(self, full_name: str) -> Optional[Dict]:
        """جلب معلومات مستودع واحد."""
        try:
            return self._api.get(f"/repos/{full_name}")
        except Exception as e:
            _logger.error(f"get_repo {full_name}: {e}")
            return None

    def create_repo(
        self,
        name:        str,
        description: str  = "",
        private:     bool = False,
        license_id:  str  = "MIT",
        auto_init:   bool = True,
    ) -> Dict:
        """
        إنشاء مستودع جديد.
        يعيد dict معلومات الـ repo (يحتوي على clone_url, html_url, ...).
        """
        body: Dict = {
            "name":        name,
            "description": description,
            "private":     private,
            "auto_init":   auto_init,
        }
        if license_id and license_id.lower() not in ("none", ""):
            body["license_template"] = license_id.lower()

        result = self._api.post("/user/repos", body)
        _logger.info(f"RepoMgr: created {result.get('full_name')}")
        return result

    def delete_repo(self, full_name: str) -> None:
        """
        حذف مستودع نهائياً — لا تراجع.
        """
        self._api.delete(f"/repos/{full_name}")
        _logger.info(f"RepoMgr: deleted {full_name}")

    def update_repo(
        self,
        full_name:   str,
        description: Optional[str] = None,
        private:     Optional[bool] = None,
        homepage:    Optional[str]  = None,
    ) -> Dict:
        """تعديل معلومات مستودع."""
        body = {}
        if description is not None: body["description"] = description
        if private     is not None: body["private"]     = private
        if homepage    is not None: body["homepage"]    = homepage
        return self._api.patch(f"/repos/{full_name}", body)

    def list_releases(self, full_name: str) -> List[Dict]:
        """جلب كل الإصدارات."""
        try:
            return self._api.get_all_pages(f"/repos/{full_name}/releases")
        except Exception:
            return []

    def create_release(
        self,
        full_name: str,
        tag:       str,
        name:      str  = "",
        body:      str  = "",
        draft:     bool = False,
    ) -> Dict:
        """إنشاء إصدار جديد."""
        return self._api.post(f"/repos/{full_name}/releases", {
            "tag_name": tag,
            "name":     name or tag,
            "body":     body,
            "draft":    draft,
        })

    def upload_release_asset(
        self,
        upload_url: str,
        file_path:  "Path",
        log_cb      = None,
    ) -> bool:
        """
        رفع ملف كـ Release Asset.
        upload_url من create_release()["upload_url"]
        """
        import re
        from pathlib import Path

        log = log_cb or (lambda m: None)
        fp  = Path(file_path)
        if not fp.exists():
            log(f"❌ الملف غير موجود: {fp}")
            return False

        # تنظيف الـ URL
        url = re.sub(r"\{.*?\}", "", upload_url) + f"?name={fp.name}"

        try:
            import requests as req
            size = fp.stat().st_size
            log(f"⬆️  رفع {fp.name} ({size // 1_048_576}MB)...")

            with open(fp, "rb") as f:
                r = req.post(
                    url,
                    data=f,
                    headers={
                        "Authorization": f"token {self._api._token}",
                        "Content-Type":  "application/octet-stream",
                    },
                    timeout=600,
                )
            if r.status_code in (200, 201):
                log(f"✅ رُفع: {fp.name}")
                return True
            log(f"❌ فشل رفع {fp.name}: {r.status_code}")
            return False
        except Exception as e:
            log(f"❌ {e}")
            return False

    @property
    def username(self) -> str:
        return self._api.username
