#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
github.ops
==========
Auth          — مصادقة + حفظ Token
ProjectInspector — تحليل بنية المشروع
LFS           — Git Large File Storage
Uploader      — رفع مشروع جديد / تحديث
Cloner        — استنساخ مستودع
Batch         — رفع متعدد من مجلد رئيسي
"""

import os
import re
import sys
import json
import shutil
import subprocess
import threading
import tempfile
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ..core.app_config   import AppConfig
from ..core.constants    import BINARY_EXTENSIONS, IGNORED_DIRS, MAX_FILE_SIZE_MB
from .client             import GitRunner, GitHubAPI
from .manager            import RepoMgr

_logger = logging.getLogger("AyadFlowSync.github")

LogCB = Optional[Callable[[str], None]]


# ══════════════════════════════════════════════════════════════════
# Auth — مصادقة GitHub
# ══════════════════════════════════════════════════════════════════

class Auth:
    """حفظ وتحميل GitHub Token.
    
    بدون PIN → حفظ عادي (بجانب البرنامج في data/)
    مع PIN مفعّل → تشفير PBKDF2 + HMAC
    """

    _TOKEN_FILE = AppConfig.DATA_DIR / ".gh_token"

    @classmethod
    def save(cls, token: str) -> None:
        cls._TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        from ..security.secure_store import SecureStore
        if SecureStore._master_pin:
            # PIN مفعّل → تشفير
            SecureStore.save(cls._TOKEN_FILE, token.strip())
        else:
            # بدون PIN → حفظ عادي
            cls._TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
            try:
                import os
                os.chmod(cls._TOKEN_FILE, 0o600)
            except Exception:
                pass

    @classmethod
    def load(cls) -> str:
        if not cls._TOKEN_FILE.exists():
            return ""
        try:
            # Try plain text first
            raw = cls._TOKEN_FILE.read_text(encoding="utf-8").strip()
            if raw and not raw.startswith("{"):
                return raw
            # JSON = encrypted format
            from ..security.secure_store import SecureStore
            result = SecureStore.load(cls._TOKEN_FILE)
            return result or ""
        except Exception:
            return ""

    @classmethod
    def clear(cls) -> None:
        cls._TOKEN_FILE.unlink(missing_ok=True)

    @classmethod
    def verify(cls, token: str) -> bool:
        return GitRunner.verify_token(token)


# ══════════════════════════════════════════════════════════════════
# ProjectInspector — تحليل بنية المشروع
# ══════════════════════════════════════════════════════════════════

class ProjectInspector:
    """
    يحلل مشروعاً في مسح واحد (3× أسرع من scanner منفصل).
    يكتشف: النوع، المكتبات، اللغة، عدد الملفات.
    """

    _INDICATORS: Dict[str, Tuple[str, str]] = {
        "package.json":    ("Node.js",   "JavaScript/TypeScript"),
        "requirements.txt":("Python",    "Python"),
        "setup.py":        ("Python",    "Python"),
        "pyproject.toml":  ("Python",    "Python"),
        "Cargo.toml":      ("Rust",      "Rust"),
        "go.mod":          ("Go",        "Go"),
        "pom.xml":         ("Java/Maven","Java"),
        "build.gradle":    ("Java/Gradle","Java/Kotlin"),
        "*.csproj":        ("C#/.NET",   "C#"),
        "pubspec.yaml":    ("Flutter",   "Dart"),
        "CMakeLists.txt":  ("C/C++",     "C/C++"),
        "Makefile":        ("C/C++",     "C/C++"),
        "composer.json":   ("PHP",       "PHP"),
        "Gemfile":         ("Ruby",      "Ruby"),
    }

    @classmethod
    def inspect(cls, project: Path, deep: bool = False) -> Dict:
        """
        فحص المشروع وإعادة النتائج.
        deep=True → تحليل أعمق (أبطأ)
        """
        result = {
            "type":      "Unknown",
            "language":  "Unknown",
            "files":     0,
            "size_mb":   0.0,
            "libraries": [],
            "has_git":   (project / ".git").exists(),
            "readme":    None,
            "gitignore": (project / ".gitignore").exists(),
        }

        total_size = 0
        file_count = 0

        try:
            for entry in os.scandir(project):
                if entry.name in IGNORED_DIRS:
                    continue
                # كشف نوع المشروع
                for pattern, (ptype, lang) in cls._INDICATORS.items():
                    if pattern.startswith("*"):
                        if entry.name.endswith(pattern[1:]):
                            result["type"]     = ptype
                            result["language"] = lang
                    elif entry.name == pattern:
                        result["type"]     = ptype
                        result["language"] = lang

                # README
                if entry.name.lower().startswith("readme"):
                    result["readme"] = entry.name

                if entry.is_file(follow_symlinks=False):
                    file_count  += 1
                    total_size  += entry.stat().st_size

        except OSError as e:
            _logger.warning(f"ProjectInspector: {e}")

        result["files"]   = file_count
        result["size_mb"] = round(total_size / 1_048_576, 2)

        if deep:
            result["libraries"] = cls._detect_libraries(project, result["type"])

        return result

    @classmethod
    def _detect_libraries(cls, project: Path, ptype: str) -> List[str]:
        """كشف المكتبات الرئيسية."""
        libs = []
        try:
            if ptype == "Python":
                req = project / "requirements.txt"
                if req.exists():
                    for line in req.read_text(errors="ignore").splitlines():
                        line = line.strip().split("==")[0].split(">=")[0]
                        if line and not line.startswith("#"):
                            libs.append(line)
                            if len(libs) >= 10:
                                break
            elif ptype == "Node.js":
                pkg = project / "package.json"
                if pkg.exists():
                    data = json.loads(pkg.read_text(errors="ignore"))
                    libs = list(data.get("dependencies", {}).keys())[:10]
        except Exception:
            pass
        return libs


# ══════════════════════════════════════════════════════════════════
# LFS — Git Large File Storage
# ══════════════════════════════════════════════════════════════════

class LFS:
    """تفعيل Git LFS وإعداد .gitattributes."""

    @staticmethod
    def is_available() -> bool:
        try:
            subprocess.run(["git", "lfs", "version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    @staticmethod
    def setup(repo_path: Path, patterns: List[str], log_cb: LogCB = None) -> bool:
        log = log_cb or (lambda m: None)
        if not LFS.is_available():
            log("⚠️ git-lfs غير مثبت — تخطي LFS")
            return False
        try:
            runner = GitRunner(repo_path)
            runner.run(["lfs", "install"])

            # كتابة .gitattributes
            ga = repo_path / ".gitattributes"
            lines = []
            if ga.exists():
                lines = ga.read_text(errors="ignore").splitlines()

            for pat in patterns:
                rule = f"{pat} filter=lfs diff=lfs merge=lfs -text"
                if rule not in lines:
                    lines.append(rule)

            ga.write_text("\n".join(lines) + "\n", encoding="utf-8")
            log(f"✅ LFS: {len(patterns)} نمط في .gitattributes")
            return True
        except Exception as e:
            log(f"❌ LFS: {e}")
            return False

    @staticmethod
    def detect_large_files(path: Path, limit_mb: int = MAX_FILE_SIZE_MB) -> List[Path]:
        """كشف الملفات الأكبر من limit_mb."""
        limit = limit_mb * 1_048_576
        result = []
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    if p.stat().st_size > limit:
                        result.append(p)
                except OSError:
                    pass
        return result


# ══════════════════════════════════════════════════════════════════
# Uploader — رفع مشروع إلى GitHub
# ══════════════════════════════════════════════════════════════════

class Uploader:
    """
    يرفع مشروعاً محلياً إلى GitHub:
    ① ينشئ Repo
    ② يُهيّئ Git
    ③ يضيف remote
    ④ يرفع (push)
    يتعامل مع FAT32 بنقل .git مؤقتاً.
    """

    def __init__(self, token: str, log_cb: LogCB = None):
        self._token  = token
        self._log    = log_cb or (lambda m: None)
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def upload(
        self,
        project_path: Path,
        repo_name:    str,
        desc:         str  = "",
        private:      bool = False,
        license_id:   str  = "MIT",
        use_lfs:      bool = False,
        branch:       str  = "main",
        update_existing: bool = False,
        commit_msg:   str  = "",
    ) -> bool:
        """
        إنشاء Repo ورفع المشروع — أو تحديث repo موجود.
        update_existing=True → يتخطى إنشاء repo، يعمل add+commit+push فقط.
        """
        log   = self._log
        path  = Path(project_path)

        if not path.exists():
            log(f"❌ المشروع غير موجود: {path}")
            return False

        if not GitRunner.has_git():
            log("❌ Git غير مثبت")
            return False

        # كشف ملفات كبيرة
        large = LFS.detect_large_files(path)
        if large and not use_lfs:
            names = [f.name for f in large[:3]]
            log(f"⚠️ ملفات كبيرة (>{MAX_FILE_SIZE_MB}MB): {', '.join(names)}")

        # ── تحديث repo موجود ────────────────────────────────────
        if update_existing:
            return self._push_update(path, repo_name, branch,
                                     commit_msg or "Update via AyadFlowSync",
                                     use_lfs, large)

        # ── إنشاء repo جديد ─────────────────────────────────────
        log(f"🔨 إنشاء Repo: {repo_name}...")
        try:
            mgr  = RepoMgr(self._token)
            repo = mgr.create_repo(
                name=repo_name, description=desc,
                private=private, license_id=license_id,
                auto_init=False,
            )
            remote_url = repo["clone_url"]
            remote_url = remote_url.replace(
                "https://", f"https://{self._token}@"
            )
            log(f"✅ Repo جاهز: {repo['html_url']}")
        except Exception as e:
            err = str(e)
            # إذا الـ repo موجود بالفعل → حاول التحديث
            if "already exists" in err.lower() or "422" in err:
                log(f"📦 Repo موجود — تحديث بدل إنشاء...")
                return self._push_update(path, repo_name, branch,
                                         commit_msg or "Initial commit via AyadFlowSync",
                                         use_lfs, large)
            log(f"❌ فشل إنشاء Repo: {e}")
            return False

        if self._cancel.is_set():
            return False

        return self._git_push(path, remote_url, branch,
                              commit_msg or "Initial commit via AyadFlowSync",
                              use_lfs, large, repo, mgr)

    def _push_update(self, path: Path, repo_name: str, branch: str,
                     msg: str, use_lfs: bool, large: list) -> bool:
        """
        ✅ FIX v4.1 — تحديث repo مع إصلاح 3 مشاكل:

        BUG 1 (Critical): الكود القديم كان يحذف .git بعد كل push على FAT32
            → المرة الجاية: git init من الصفر → non-fast-forward error
            FIX: نُعيد .git لمكانه الأصلي بعد كل push

        BUG 2 (Critical): لا يوجد معالجة لـ non-fast-forward rejection
            → Push يفشل بعد re-init أو diverged history
            FIX: نحاول push عادي أولاً، ثم --force-with-lease إذا فشل

        BUG 3 (Medium): _get_username() يُستدعى داخل try بعد git init
            → إذا فشل (rate limit / network) → remote URL فارغ بصمت
            FIX: نجلب username مرة واحدة في البداية ونتحقق منه
        """
        log = self._log
        log(f"🔄 تحديث {repo_name}...")

        # ── جلب username مبكراً — نتوقف مبكراً إذا فشل ─────────────
        username = self._get_username()
        if not username:
            log("❌ فشل جلب اسم المستخدم من GitHub — تحقق من الـ Token")
            return False

        # ── FAT32 detection — نقل .git مؤقتاً إذا على فلاشة ─────────
        is_fat32 = AppConfig.is_removable(path)
        git_dir  = path / ".git"
        git_tmp  = None

        # ⚡ v4.1: FAT32 = دائماً نعمل في مجلد مؤقت (حتى لو .git غير موجود)
        if is_fat32:
            git_tmp = Path(tempfile.mkdtemp()) / ".git"
            if git_dir.exists():
                try:
                    shutil.move(str(git_dir), str(git_tmp))
                    log("📦 FAT32: .git نُقل مؤقتاً للسرعة")
                except Exception:
                    try:
                        shutil.copytree(str(git_dir), str(git_tmp))
                        log("📦 FAT32: .git نُسخ مؤقتاً")
                    except Exception:
                        pass

        work_dir   = git_tmp.parent if git_tmp else path
        fresh_init = False   # هل هذا init جديد؟

        try:
            runner = GitRunner(work_dir)

            if not (work_dir / ".git").exists():
                log("📁 تهيئة Git...")
                runner.run(["init", "-b", branch])
                runner.run(["config", "user.email", "flowsync@ayad.dev"])
                runner.run(["config", "user.name",  "AyadFlowSync"])
                fresh_init = True

            # ⚡ v4.1: إعدادات HTTP لمنع timeout مع المشاريع الكبيرة
            runner.run(["config", "http.postBuffer", "524288000"], check=False)  # 500MB
            runner.run(["config", "http.lowSpeedLimit", "1000"], check=False)
            runner.run(["config", "http.lowSpeedTime", "300"], check=False)

            # ── ضبط remote ──────────────────────────────────────────
            remote_url = f"https://{self._token}@github.com/{username}/{repo_name}.git"
            try:
                runner.run(["remote", "set-url", "origin", remote_url], check=False)
            except Exception:
                pass
            try:
                runner.run(["remote", "add", "origin", remote_url], check=False)
            except Exception:
                pass

            # ── LFS إذا مطلوب ────────────────────────────────────────
            if use_lfs and large:
                patterns = list({f"*{f.suffix}" for f in large if f.suffix})
                LFS.setup(work_dir, patterns, log)

            # ── تجاهل الملفات الكبيرة ────────────────────────────────
            if large and not use_lfs:
                self._add_large_to_gitignore(work_dir, large, log)

            # ── FAT32: نسخ الملفات للمجلد المؤقت ────────────────────
            if git_tmp:
                log("📋 نسخ الملفات للمجلد المؤقت...")
                excluded = {'.git', '.ayadsync_meta.json', '__pycache__',
                            'node_modules', 'venv', '.venv', 'env', '.env',
                            '.gradle', '.dart_tool', 'build', 'dist',
                            'target', '.idea', '.vs', 'Pods'}
                for item in path.iterdir():
                    if item.name in excluded:
                        continue
                    dst_item = work_dir / item.name
                    try:
                        if item.is_dir():
                            shutil.copytree(str(item), str(dst_item),
                                            dirs_exist_ok=True)
                        else:
                            shutil.copy2(str(item), str(dst_item))
                    except Exception as _copy_err:
                        log(f"⚠️ تخطي {item.name}: {_copy_err}")

            # ── .gitignore ذكي ────────────────────────────────────────
            self._ensure_gitignore(work_dir, path, log)

            # ── Add + Commit ─────────────────────────────────────────
            log("📁 إضافة التغييرات...")
            runner.run(["add", "-A"])

            try:
                runner.run(["commit", "-m", msg])
            except subprocess.CalledProcessError:
                log("✅ لا توجد تغييرات جديدة للـ commit")
                return True

            # ── Push مع معالجة non-fast-forward ─────────────────────
            log(f"⬆️ Push إلى {repo_name}...")
            pushed = False

            # المحاولة 1: push عادي
            try:
                runner.run(["push", "-u", "origin", branch], timeout=600)
                pushed = True
            except subprocess.CalledProcessError as e1:
                err_msg = (e1.stderr or "").lower()

                # non-fast-forward أو unrelated histories → نحتاج --force-with-lease
                if any(x in err_msg for x in (
                    "non-fast-forward", "rejected", "fetch first",
                    "unrelated", "failed to push"
                )):
                    log("⚠️ Push مرفوض — محاولة force-with-lease...")
                    try:
                        runner.run(
                            ["push", "--force-with-lease", "-u", "origin", branch],
                            timeout=600
                        )
                        pushed = True
                        log("✅ Push بـ force-with-lease نجح")
                    except subprocess.CalledProcessError as e2:
                        # آخر خيار: --force (تحذير)
                        log("⚠️ force-with-lease فشل — محاولة --force...")
                        try:
                            runner.run(
                                ["push", "--force", "-u", "origin", branch],
                                timeout=600
                            )
                            pushed = True
                            log("⚠️ Push بـ --force نجح (تم الكتابة فوق التاريخ)")
                        except subprocess.CalledProcessError as e3:
                            raise RuntimeError(
                                f"فشل Push بعد 3 محاولات: {e3.stderr[:200]}"
                            )
                else:
                    raise RuntimeError(
                        f"فشل Push: {e1.stderr[:200] if e1.stderr else str(e1)}"
                    )

            if not pushed:
                raise RuntimeError("Push لم يكتمل")

            log(f"✅ تم تحديث {repo_name}")

            # ── ملفات كبيرة → Release Assets ─────────────────────────
            if large and not use_lfs:
                try:
                    mgr       = RepoMgr(self._token)
                    repo_info = mgr.get_repo(f"{username}/{repo_name}")
                    if repo_info:
                        self._upload_large_as_releases(repo_info, large, mgr, log)
                except Exception as e:
                    log(f"⚠️ Release Assets: {e}")

            return True

        except Exception as e:
            log(f"❌ فشل التحديث: {e}")
            return False

        finally:
            # ✅ FIX: نُعيد .git — مع معالجة read-only على FAT32
            if git_tmp and git_tmp.exists():
                def _force_rm(fn, path, exc):
                    """FAT32: ملفات .git/objects تكون read-only"""
                    try:
                        os.chmod(path, 0o777)
                        fn(path)
                    except Exception:
                        pass

                try:
                    if git_dir.exists():
                        shutil.rmtree(str(git_dir), onerror=_force_rm)
                    shutil.move(str(git_tmp), str(git_dir))
                    log("📦 .git أُعيد للفلاشة")
                except Exception:
                    try:
                        if git_dir.exists():
                            shutil.rmtree(str(git_dir), onerror=_force_rm)
                        shutil.copytree(str(git_tmp), str(git_dir))
                        log("📦 .git أُعيد للفلاشة (نسخ)")
                    except Exception as _cp_err:
                        log(f"⚠️ فشل إعادة .git — لا يؤثر على Push: {_cp_err}")
                finally:
                    try:
                        shutil.rmtree(git_tmp.parent, onerror=_force_rm)
                    except Exception:
                        pass

    def _get_username(self) -> str:
        """جلب اسم المستخدم من GitHub API."""
        try:
            api = GitHubAPI(self._token)
            user = api.get("/user")
            return user.get("login", "")
        except Exception:
            return ""

    def _git_push(self, path: Path, remote_url: str, branch: str,
                  msg: str, use_lfs: bool, large: list,
                  repo: dict = None, mgr: "RepoMgr" = None) -> bool:
        """
        ✅ FIX v4.1 — منطق Git المشترك: init → add → commit → push

        BUG 1 (Critical — سبب "لا شيء على GitHub"):
            الكود القديم: إذا فشل commit بـ CalledProcessError → return True بصمت
            بدون push — الـ repo يُنشأ على GitHub لكن فارغ تماماً.
            الأسباب الشائعة: git config مفقود، .gitignore يستثني كل شيء،
            أو كل الملفات في BINARY_EXTENSIONS.
            FIX: نتحقق أولاً بـ `git status --porcelain` — إذا لا يوجد شيء
            للـ add نُبلّغ المستخدم بوضوح بدل الصمت.

        BUG 2 (Critical):
            Push بمحاولة واحدة فقط — بدون fallback لـ non-fast-forward.
            FIX: نفس منطق _push_update (3 محاولات تصاعدية).

        BUG 3 (FAT32):
            نسخ ملفات المشروع للمجلد المؤقت كان مفقوداً في _git_push
            (موجود في _push_update فقط).
            FIX: أُضيف نسخ الملفات قبل add إذا كنا على FAT32.
        """
        log = self._log

        # ── FAT32: دائماً نعمل في مجلد مؤقت ──────────────────
        is_fat32 = AppConfig.is_removable(path)
        git_dir  = path / ".git"
        git_tmp  = None

        if is_fat32:
            git_tmp = Path(tempfile.mkdtemp()) / ".git"
            if git_dir.exists():
                try:
                    shutil.move(str(git_dir), str(git_tmp))
                    log("📦 FAT32: .git نُقل مؤقتاً")
                except Exception:
                    try:
                        shutil.copytree(str(git_dir), str(git_tmp))
                        log("📦 FAT32: .git نُسخ مؤقتاً")
                    except Exception:
                        pass

        work_dir = git_tmp.parent if git_tmp else path

        try:
            runner = GitRunner(work_dir)

            # ── تهيئة Git ────────────────────────────────────────
            if not (work_dir / ".git").exists():
                log("📁 تهيئة Git...")
                runner.run(["init", "-b", branch])
                runner.run(["config", "user.email", "flowsync@ayad.dev"])
                runner.run(["config", "user.name",  "AyadFlowSync"])

            # ⚡ v4.1: إعدادات HTTP لمنع timeout
            runner.run(["config", "http.postBuffer", "524288000"], check=False)
            runner.run(["config", "http.lowSpeedLimit", "1000"], check=False)
            runner.run(["config", "http.lowSpeedTime", "300"], check=False)

            # ── LFS ──────────────────────────────────────────────
            if use_lfs and large:
                patterns = list({f"*{f.suffix}" for f in large if f.suffix})
                LFS.setup(work_dir, patterns, log)

            # ── Remote ───────────────────────────────────────────
            try:
                runner.run(["remote", "set-url", "origin", remote_url], check=False)
            except Exception:
                pass
            try:
                runner.run(["remote", "add", "origin", remote_url], check=False)
            except Exception:
                pass

            # ── .gitignore للملفات الكبيرة ───────────────────────
            if large and not use_lfs:
                self._add_large_to_gitignore(work_dir, large, log)

            # ── FAT32: نسخ ملفات المشروع للمجلد المؤقت ──────────
            if git_tmp:
                log("📋 نسخ الملفات للمجلد المؤقت...")
                excluded = {'.git', '.ayadsync_meta.json', '__pycache__',
                            'node_modules', 'venv', '.venv', 'env', '.env',
                            '.gradle', '.dart_tool', 'build', 'dist',
                            'target', '.idea', '.vs', 'Pods'}
                for item in path.iterdir():
                    if item.name in excluded:
                        continue
                    dst_item = work_dir / item.name
                    try:
                        if item.is_dir():
                            shutil.copytree(str(item), str(dst_item),
                                            dirs_exist_ok=True)
                        else:
                            shutil.copy2(str(item), str(dst_item))
                    except Exception as _ce:
                        log(f"⚠️ تخطي {item.name}: {_ce}")

            # ── .gitignore ذكي ────────────────────────────────────
            self._ensure_gitignore(work_dir, path, log)

            # ── Add ───────────────────────────────────────────────
            log("📁 إضافة الملفات...")
            runner.run(["add", "-A"])

            # ✅ FIX BUG 1: تحقق هل يوجد شيء فعلاً للـ commit
            status = runner.run(["status", "--porcelain"], check=False)
            has_changes = bool((status.stdout or "").strip())

            if not has_changes:
                # ── لا يوجد شيء للـ commit ────────────────────────
                # فحص هل يوجد HEAD (commits سابقة) → اعتبره نجاحاً
                has_head = runner.run(
                    ["rev-parse", "--verify", "HEAD"], check=False
                ).returncode == 0

                if has_head:
                    # repo موجود ومزامَن — نُبلّغ ونُكمل
                    log("✅ الملفات متطابقة — لا يوجد شيء جديد للرفع")
                    return True
                else:
                    # repo جديد فارغ تماماً — مشكلة حقيقية
                    log("❌ لا يوجد ملفات للرفع — تحقق من:")
                    log("   • أن المجلد يحتوي ملفات")
                    log("   • أن الملفات ليست كلها في .gitignore")
                    log(f"   • المجلد: {path}")
                    return False

            # ── Commit ───────────────────────────────────────────
            try:
                runner.run(["commit", "-m", msg])
            except subprocess.CalledProcessError as _ce:
                stderr = (_ce.stderr or "").lower()
                if "nothing to commit" in stderr or "nothing added" in stderr:
                    log("✅ لا توجد تغييرات للـ commit")
                    return True
                raise RuntimeError(f"فشل Commit: {_ce.stderr[:200] if _ce.stderr else _ce}")

            # ── Push مع 3 محاولات تصاعدية ────────────────────────
            log("⬆️  رفع إلى GitHub...")
            pushed = False

            try:
                runner.run(["push", "-u", "origin", branch], timeout=600)
                pushed = True
            except subprocess.CalledProcessError as _e1:
                err = (_e1.stderr or "").lower()
                if any(x in err for x in (
                    "non-fast-forward", "rejected", "fetch first",
                    "unrelated", "failed to push"
                )):
                    log("⚠️ Push مرفوض — محاولة force-with-lease...")
                    try:
                        runner.run(
                            ["push", "--force-with-lease", "-u", "origin", branch],
                            timeout=600
                        )
                        pushed = True
                        log("✅ Push بـ force-with-lease نجح")
                    except subprocess.CalledProcessError as _e2:
                        log("⚠️ force-with-lease فشل — محاولة --force...")
                        try:
                            runner.run(
                                ["push", "--force", "-u", "origin", branch],
                                timeout=600
                            )
                            pushed = True
                            log("⚠️ Push بـ --force نجح")
                        except subprocess.CalledProcessError as _e3:
                            raise RuntimeError(
                                f"فشل Push بعد 3 محاولات: {_e3.stderr[:200] if _e3.stderr else _e3}"
                            )
                else:
                    raise RuntimeError(
                        f"فشل Push: {_e1.stderr[:200] if _e1.stderr else _e1}"
                    )

            if pushed:
                url = repo.get('html_url', '') if repo else ''
                log(f"✅ اكتمل الرفع{': ' + url if url else ''}")

            # ── ملفات كبيرة → Release Assets ─────────────────────
            if large and not use_lfs and repo and mgr:
                self._upload_large_as_releases(repo, large, mgr, log)

            return True

        except Exception as e:
            log(f"❌ فشل الرفع: {e}")
            return False

        finally:
            # ✅ FIX: نُعيد .git — مع معالجة read-only على FAT32
            if git_tmp and git_tmp.exists():
                def _force_rm2(fn, path, exc):
                    try:
                        os.chmod(path, 0o777)
                        fn(path)
                    except Exception:
                        pass

                try:
                    if git_dir.exists():
                        shutil.rmtree(str(git_dir), onerror=_force_rm2)
                    shutil.move(str(git_tmp), str(git_dir))
                    log("📦 .git أُعيد لمكانه")
                except Exception:
                    try:
                        if git_dir.exists():
                            shutil.rmtree(str(git_dir), onerror=_force_rm2)
                        shutil.copytree(str(git_tmp), str(git_dir))
                        log("📦 .git أُعيد لمكانه (نسخ)")
                    except Exception as _cp:
                        log(f"⚠️ فشل إعادة .git — لا يؤثر على Push: {_cp}")
                finally:
                    try:
                        shutil.rmtree(git_tmp.parent, onerror=_force_rm2)
                    except Exception:
                        pass

    # ── .gitignore ذكي ─────────────────────────────────────────
    _GITIGNORE_TEMPLATES = {
        'python': [
            '__pycache__/', '*.py[cod]', '*$py.class', '*.so',
            'dist/', 'build/', '*.egg-info/', '.eggs/',
            'venv/', 'env/', '.env/', '.venv/',
            '*.whl', '.mypy_cache/', '.pytest_cache/',
            'htmlcov/', '.coverage', '*.log',
        ],
        'node': [
            'node_modules/', 'dist/', 'build/', '.next/',
            '.nuxt/', '.cache/', 'coverage/',
            '*.log', 'npm-debug.log*', '.env', '.env.local',
        ],
        'java': [
            'target/', '*.class', '*.jar', '*.war',
            '.gradle/', 'build/', '.idea/', '*.iml',
        ],
        'rust': [
            'target/', '*.pdb', 'Cargo.lock',
        ],
        'go': [
            'bin/', 'vendor/',
        ],
        'flutter': [
            '.dart_tool/', '.flutter-plugins', '.flutter-plugins-dependencies',
            'build/', '.packages', '*.iml',
        ],
        'csharp': [
            'bin/', 'obj/', '*.user', '*.suo', '.vs/',
        ],
        'common': [
            '.DS_Store', 'Thumbs.db', '*.swp', '*.swo', '*~',
            '.idea/', '.vscode/', '*.tmp', '*.bak',
        ],
    }

    def _ensure_gitignore(self, work_dir: Path, project_path: Path, log) -> None:
        """
        ⚡ v4.1: توليد .gitignore ذكي تلقائياً إذا غير موجود.
        يكشف نوع المشروع من الملفات الموجودة ويولّد قواعد مناسبة.
        لا يعدّل .gitignore موجود — فقط ينشئ جديد أو يضيف أنماط مفقودة.
        """
        gitignore = work_dir / ".gitignore"

        # كشف أنواع المشروع
        detected = set()
        scan_dir = project_path if project_path.exists() else work_dir
        try:
            names = set()
            for item in scan_dir.iterdir():
                names.add(item.name)
            # Python
            if any(n in names for n in ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile']):
                detected.add('python')
            elif any(n.endswith('.py') for n in names):
                detected.add('python')
            # Node
            if 'package.json' in names:
                detected.add('node')
            # Java/Kotlin
            if any(n in names for n in ['pom.xml', 'build.gradle', 'build.gradle.kts']):
                detected.add('java')
            # Rust
            if 'Cargo.toml' in names:
                detected.add('rust')
            # Go
            if 'go.mod' in names:
                detected.add('go')
            # Flutter/Dart
            if 'pubspec.yaml' in names:
                detected.add('flutter')
            # C#
            if any(n.endswith('.csproj') or n.endswith('.sln') for n in names):
                detected.add('csharp')
        except OSError:
            pass

        if not detected:
            detected.add('python')  # default

        # بناء القواعد
        rules = list(self._GITIGNORE_TEMPLATES['common'])
        for lang in detected:
            rules.extend(self._GITIGNORE_TEMPLATES.get(lang, []))

        if not gitignore.exists():
            # إنشاء .gitignore جديد
            header = "# Auto-generated by AyadFlowSync\n"
            header += f"# Detected: {', '.join(sorted(detected))}\n\n"
            content = header + "\n".join(rules) + "\n"
            try:
                gitignore.write_text(content, encoding='utf-8')
                log(f"📝 .gitignore ذكي: {', '.join(sorted(detected))} ({len(rules)} قاعدة)")
            except Exception as e:
                log(f"⚠️ .gitignore: {e}")
        else:
            # إضافة أنماط مفقودة حرجة فقط
            try:
                existing = gitignore.read_text(encoding='utf-8', errors='ignore')
                critical = ['__pycache__/', 'node_modules/', '.env', 'venv/', '.DS_Store']
                missing = [r for r in critical if r not in existing and r in rules]
                if missing:
                    section = "\n# Added by AyadFlowSync\n" + "\n".join(missing) + "\n"
                    with open(gitignore, "a", encoding="utf-8") as fp:
                        fp.write(section)
                    log(f"📝 .gitignore: أُضيف {len(missing)} نمط مفقود")
            except Exception:
                pass

    def _add_large_to_gitignore(self, path: Path, large: list, log) -> None:
        """
        يُضيف الملفات الكبيرة لـ .gitignore تلقائياً:
        - يحافظ على المحتوى الموجود
        - يُضيف فقط الأسماء الجديدة
        - يُبلّغ المستخدم بالملفات المُستثناة
        """
        gitignore = path / ".gitignore"
        try:
            existing = gitignore.read_text(encoding='utf-8', errors='ignore') \
                if gitignore.exists() else ""
            to_add = []
            for f in large:
                rel = str(f.relative_to(path)).replace("\\", "/")
                if rel not in existing:
                    to_add.append(rel)
            if to_add:
                section = "\n# Large files — uploaded as GitHub Release Assets by AyadFlowSync\n"
                section += "\n".join(to_add) + "\n"
                with open(gitignore, "a", encoding="utf-8") as fp:
                    fp.write(section)
                log(f"📝 .gitignore: أُضيف {len(to_add)} ملف كبير (سيُرفع كـ Release)")
        except Exception as e:
            log(f"⚠️ .gitignore: {e}")

    def _upload_large_as_releases(
        self,
        repo:  Dict,
        files: List[Path],
        mgr:   RepoMgr,
        log:   Callable,
    ) -> None:
        """رفع الملفات الكبيرة كـ Release Assets."""
        try:
            log(f"📦 رفع {len(files)} ملف كـ Release Assets...")
            release = mgr.create_release(
                repo["full_name"],
                tag="v1.0-assets",
                name="Large File Assets",
                body="Uploaded by AyadFlowSync",
            )
            upload_url = release.get("upload_url", "")
            for f in files:
                if self._cancel.is_set():
                    break
                mgr.upload_release_asset(upload_url, f, log)
        except Exception as e:
            log(f"⚠️ Release Assets: {e}")


# ══════════════════════════════════════════════════════════════════
# Cloner — استنساخ مستودع
# ══════════════════════════════════════════════════════════════════

class Cloner:
    """استنساخ مستودع GitHub إلى مجلد محلي."""

    def __init__(self, token: str = "", log_cb: LogCB = None):
        self._token = token
        self._log   = log_cb or (lambda m: None)

    def clone(self, url: str, dest: Path, branch: str = "") -> bool:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # تضمين Token في الـ URL إذا متاح
        clone_url = url
        if self._token and "github.com" in url:
            clone_url = url.replace("https://", f"https://{self._token}@")

        self._log(f"⬇️  Clone: {url}")
        try:
            runner = GitRunner(dest.parent)
            args   = ["clone", clone_url, dest.name]
            if branch:
                args += ["-b", branch]
            runner.run(args, timeout=600)
            self._log(f"✅ Clone اكتمل: {dest}")
            return True
        except Exception as e:
            self._log(f"❌ Clone فشل: {e}")
            return False


# ══════════════════════════════════════════════════════════════════
# Batch — رفع متعدد
# ══════════════════════════════════════════════════════════════════

class Batch:
    """
    رفع كل المشاريع من مجلد رئيسي.
    كل مجلد فرعي = Repo مستقل.
    يتخطى المجلدات التي لديها .git/config بالفعل.
    """

    def __init__(self, token: str, log_cb: LogCB = None):
        self._token   = token
        self._log     = log_cb or (lambda m: None)
        self._cancel  = threading.Event()
        self._uploader = Uploader(token, log_cb)

    def cancel(self) -> None:
        self._cancel.set()
        self._uploader.cancel()

    def upload_all(self, parent: Path) -> Dict:
        parent = Path(parent)
        if not parent.exists():
            self._log(f"❌ المجلد غير موجود: {parent}")
            return {"ok": 0, "skipped": 0, "failed": 0}

        projects = [
            d for d in sorted(parent.iterdir())
            if d.is_dir() and d.name not in IGNORED_DIRS
        ]

        self._log(f"📦 Batch: {len(projects)} مشروع في {parent.name}")
        ok = skipped = failed = 0

        for i, proj in enumerate(projects, 1):
            if self._cancel.is_set():
                break

            # تخطي ما رُفع مسبقاً
            if (proj / ".git" / "config").exists():
                config = (proj / ".git" / "config").read_text(errors="ignore")
                if "github.com" in config:
                    self._log(f"  ⏭️  [{i}/{len(projects)}] تخطي (موجود): {proj.name}")
                    skipped += 1
                    continue

            self._log(f"\n  📁 [{i}/{len(projects)}] {proj.name}")
            success = self._uploader.upload(
                project_path = proj,
                repo_name    = proj.name,
            )
            if success:
                ok += 1
            else:
                failed += 1

        self._log(f"\n{'━'*40}")
        self._log(f"✅ اكتمل Batch: {ok} ناجح | {skipped} متخطى | {failed} فشل")
        return {"ok": ok, "skipped": skipped, "failed": failed}
