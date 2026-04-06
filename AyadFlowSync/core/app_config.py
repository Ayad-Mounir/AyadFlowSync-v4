#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.app_config
===============
AppConfig — إعدادات التطبيق ومساراته.
لا يستورد من UI أو GitHub أو أي وحدة عليا.
"""

import os
import sys
import json
import threading
from pathlib import Path
from typing import Set

from .constants import SCRIPT_DIR, PORTABLE_MARKER, _FIRST_RUN_MARKER


# ── كشف الوضع المحمول ──────────────────────────────────────────
def _detect_portable() -> bool:
    """هل البرنامج يشتغل من وسيط محمول؟"""
    if PORTABLE_MARKER.exists():
        return True
    if (SCRIPT_DIR / 'data').exists():
        return True
    if sys.platform != 'win32':
        for prefix in ('/media/', '/mnt/usb', '/run/media/', '/Volumes/'):
            if str(SCRIPT_DIR).startswith(prefix):
                return True
    return False


PORTABLE = _detect_portable()


class AppConfig:
    """
    إعدادات التطبيق المركزية.
    كل إعداد له قيمة افتراضية معقولة وطريقة تحميل/حفظ.
    """
    # ── مسارات ─────────────────────────────────────────────────
    BASE_DIR        = SCRIPT_DIR.resolve()
    # ⚡ دائماً portable — البيانات بجانب البرنامج أينما كان
    DATA_DIR        = SCRIPT_DIR / 'data' 
    VAULT_DIR       = BASE_DIR / "FlowSync_Backup"
    LOG_DIR         = DATA_DIR / "logs"
    LOCK_DIR        = DATA_DIR / "locks"
    PRESYNC_DIR     = DATA_DIR / "presync_snapshots"
    TRASH_DIR       = DATA_DIR / "trash"
    REPORTS_DIR     = DATA_DIR / "sync_reports"
    CONFIG_FILE     = DATA_DIR / "config.dat"
    KEY_FILE        = DATA_DIR / ".keyfile"
    PC_NAME_FILE    = DATA_DIR / "pc_name.txt"
    PC_NAMES_FILE   = DATA_DIR / "pc_names.json"
    HASH_CACHE_FILE = DATA_DIR / "hash_cache_default.json"
    TRASH_KEEP_DAYS = 30

    # ── اسم الجهاز ─────────────────────────────────────────────
    PC_NAME: str = ""

    # ── ملفات وفولدرات مستثناة من المزامنة ─────────────────────
    EXCLUDED_NAMES: Set[str] = {
        '.ayadsync_meta.json',
        '.ayadsync_speed_cache',
        '.ayadsync_speed_test',
        '.ayadsync_readme_snap',
        '.ayadsync_push_log.json',
    }
    SYNC_META_FILE = ".ayadsync_meta.json"

    EXCLUDED_DIRS: Set[str] = set()

    EXCLUDED_DIRS_DEFAULTS: dict = {
        # ⚡ الافتراضي: لا شيء مستثنى — نسخ مطابق 100%
        # المستخدم يختار ما يريد استثناءه من الإعدادات
        '__pycache__': False,
        '.git':        False,
        'venv':        False,
        '.venv':       False,
        'env':         False,
        'node_modules': False,
        'dist':        False,
        'build':       False,
        '.idea':       False,
        '.vscode':     False,
        'FlowSync_Data':    False,
        'FlowSync_Backup':  False,
        'AyadSync_Data':    False,
        'AyadNomadKit_Data': False,
    }

    EXCLUDED_NAMES_DEFAULTS: set = {
        '.flash_secret',
        'hash_cache.db',

    }

    # ── إعدادات الأداء (تُضبط تلقائياً) ───────────────────────
    COPY_CHUNK       = 524_288    # 512 KB
    HASH_CHUNK       = 524_288
    THREADS_SMALL    = 4
    THREADS_LARGE    = 2
    SMALL_THRESHOLD  = 2_097_152  # 2 MB
    BATCH_SIZE       = 200
    USB_SPEED_MBS    = 0.0
    MAX_RETRIES      = 3
    RETRY_DELAY      = 0.5

    # ── وضع AccuMark ─────────────────────────────────────────────
    ACCUMARK_MODE: bool = False

    # ──────────────────────────────────────────────────────────────
    @classmethod
    def init_dirs(cls) -> None:
        """إنشاء كل المجلدات الضرورية."""
        for d in [
            cls.DATA_DIR, cls.VAULT_DIR, cls.LOG_DIR,
            cls.LOCK_DIR, cls.PRESYNC_DIR, cls.TRASH_DIR,
            cls.REPORTS_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def update_cache_path(cls) -> None:
        """ضبط مسار Hash Cache الخاص بهذا الجهاز."""
        safe = (
            cls.PC_NAME
            .replace("/", "_").replace("\\", "_")
            .replace(":", "_").replace(" ", "_")
        )
        cls.HASH_CACHE_FILE = cls.DATA_DIR / f"hash_cache_{safe}.json"

    @classmethod
    def load_excluded_dirs(cls) -> None:
        """تحميل المجلدات المستثناة — الافتراضي: لا شيء مستثنى."""
        f = cls.DATA_DIR / "excluded_dirs.json"
        try:
            if f.exists():
                data = json.loads(f.read_text(encoding='utf-8'))
                cls.EXCLUDED_DIRS = {k for k, v in data.items() if v}
            else:
                # لا يوجد ملف → لا استثناءات
                cls.EXCLUDED_DIRS = set()
        except Exception:
            cls.EXCLUDED_DIRS = set()

    @classmethod
    def save_excluded_dirs(cls, state: dict) -> None:
        f = cls.DATA_DIR / "excluded_dirs.json"
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            cls.EXCLUDED_DIRS = {k for k, v in state.items() if v}
        except Exception:
            pass

    @classmethod
    def load_accumark(cls) -> None:
        f = cls.DATA_DIR / "accumark_mode.txt"
        try:
            cls.ACCUMARK_MODE = f.read_text(encoding='utf-8').strip() == "1"
        except Exception:
            cls.ACCUMARK_MODE = False

    @classmethod
    def save_accumark(cls, enabled: bool) -> None:
        f = cls.DATA_DIR / "accumark_mode.txt"
        try:
            f.write_text("1" if enabled else "0", encoding='utf-8')
            cls.ACCUMARK_MODE = enabled
        except Exception:
            pass

    @classmethod
    def calibrate_usb(cls, usb_path: Path) -> None:
        """
        قياس سرعة USB الفعلية (كتابة + قراءة) مع cache لـ 24 ساعة.
        يُستدعى في thread خلفي — لا يوقف الواجهة.
        """
        if cls.USB_SPEED_MBS > 0:
            return

        import time

        cache_file = usb_path / ".ayadsync_speed_cache"
        try:
            if cache_file.exists():
                cached = json.loads(cache_file.read_text(encoding='utf-8'))
                age_h = (time.time() - cached.get("ts", 0)) / 3600
                if age_h < 24 and cached.get("speed", 0) > 0:
                    cls.USB_SPEED_MBS = cached["speed"]
                    cls._apply_speed_profile(cached["speed"])
                    return
        except Exception:
            pass

        test_size = 16 * 1024 * 1024
        test_file = usb_path / ".ayadsync_speed_test"
        try:
            data = os.urandom(test_size)

            # Warm-up 2MB
            warmup = usb_path / ".ayadsync_warmup_tmp"
            try:
                with open(warmup, 'wb') as wf:
                    wf.write(os.urandom(2 * 1024 * 1024))
                    wf.flush(); os.fsync(wf.fileno())
                warmup.unlink(missing_ok=True)
            except Exception:
                try: warmup.unlink(missing_ok=True)
                except Exception: pass

            t0 = time.perf_counter()
            with open(test_file, 'wb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            write_speed = test_size / max(time.perf_counter() - t0, 0.001) / 1_048_576

            t0 = time.perf_counter()
            _ = test_file.read_bytes()
            read_speed = test_size / max(time.perf_counter() - t0, 0.001) / 1_048_576

            test_file.unlink(missing_ok=True)

            speed = min(write_speed, read_speed)
            cls.USB_SPEED_MBS = speed
            cls._apply_speed_profile(speed)

            _cache = {"speed": round(speed, 1), "write": round(write_speed, 1),
                      "read": round(read_speed, 1), "ts": time.time()}

            def _write():
                try:
                    cache_file.write_text(json.dumps(_cache, ensure_ascii=False), encoding='utf-8')
                except OSError:
                    pass

            import threading as _t
            _t.Thread(target=_write, daemon=True).start()

        except Exception as e:
            import logging
            logging.getLogger("AyadFlowSync").warning(f"calibrate_usb: {e}")
            try: test_file.unlink(missing_ok=True)
            except Exception: pass

    @classmethod
    def _apply_speed_profile(cls, speed: float) -> None:
        """ضبط معاملات الأداء حسب سرعة USB."""
        if speed < 15:
            t_s, t_l = 2, 1
            cls.SMALL_THRESHOLD = 512 * 1024
            cls.BATCH_SIZE      = 50
            cls.COPY_CHUNK      = 262_144
        elif speed < 40:
            t_s, t_l = 4, 2
            cls.SMALL_THRESHOLD = 1 * 1024 * 1024
            cls.BATCH_SIZE      = 150
            cls.COPY_CHUNK      = 524_288
        elif speed < 80:
            t_s, t_l = 6, 3
            cls.SMALL_THRESHOLD = 4 * 1024 * 1024
            cls.BATCH_SIZE      = 300
            cls.COPY_CHUNK      = 1_048_576
        else:
            t_s, t_l = 8, 4
            cls.SMALL_THRESHOLD = 8 * 1024 * 1024
            cls.BATCH_SIZE      = 500
            cls.COPY_CHUNK      = 2_097_152

        cls.THREADS_SMALL = t_s
        cls.THREADS_LARGE = t_l

    @classmethod
    def is_removable(cls, path: Path) -> bool:
        """هل المسار على وسيط قابل للإزالة؟"""
        if sys.platform == 'win32':
            try:
                import ctypes
                drive = str(path.resolve())[:3]
                return ctypes.windll.kernel32.GetDriveTypeW(drive) == 2
            except Exception:
                return False
        elif sys.platform == 'darwin':
            return str(path.resolve()).startswith('/Volumes/')
        else:  # Linux
            resolved = str(path.resolve())
            for prefix in ('/media/', '/mnt/usb', '/run/media/'):
                if resolved.startswith(prefix):
                    return True
            return False


# تهيئة فورية
AppConfig.init_dirs()
AppConfig.load_accumark()
AppConfig.load_excluded_dirs()
