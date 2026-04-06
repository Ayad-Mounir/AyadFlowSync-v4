#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db.database — DatabaseManager, LockManager
"""
import os, json, threading, logging, time
from pathlib import Path
from typing import Any, Dict

_logger = logging.getLogger("AyadFlowSync")

# ⚡ v4: استخدام fmt_size الموحّدة من constants
from ..core.constants import fmt_size

class DatabaseManager:
    def __init__(self, config_file: Path):
        self.config_file = Path(config_file)
        self.data: Dict  = {}
        self._lock       = threading.Lock()
        self._load()

    def _load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (OSError, json.JSONDecodeError):
                self.data = {}

    def save(self) -> bool:
        with self._lock:
            try:
                tmp = self.config_file.with_suffix('.dat.tmp')
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                    f.flush(); os.fsync(f.fileno())
                tmp.replace(self.config_file); return True
            except Exception as e:
                _logger.error(f"DB save: {e}"); return False

    def get(self, k: str, default: Any = None) -> Any: return self.data.get(k, default)
    def set(self, k: str, v: Any) -> None: self.data[k] = v
    def delete(self, k: str) -> None: self.data.pop(k, None)
    def all(self) -> Dict: return dict(self.data)

class LockManager:
    """
    ✅ FIX v4.1 — Lock مع Renewal تلقائي
    
    المشكلة القديمة:
        stale timeout = 60 ثانية فقط.
        مزامنة مجلد كبير (>60s) تفقد الـ lock → مزامنتان متزامنتان ممكنة.

    الحل:
        1. stale timeout رُفع إلى 3600 ثانية (ساعة كاملة).
        2. renewal thread يُحدّث mtime كل 30 ثانية تلقائياً.
           → الـ lock لن يُعتبر "قديم" ما دام البرنامج يعمل.
        3. عند crash حقيقي: البرنامج لا يُجدد → الـ lock يُعتبر stale بعد ساعة.
    """

    # ── ثوابت ─────────────────────────────────────────────
    STALE_TIMEOUT  = 3600    # ساعة كاملة — أمان ضد crashes
    RENEWAL_INTERVAL = 30    # تجديد كل 30 ثانية

    def __init__(self, lock_dir: Path):
        self._dir   = Path(lock_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, Path] = {}
        # renewal threads — واحد لكل lock نشط
        self._renewers: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}

    def acquire(self, name: str) -> bool:
        f = self._dir / f"{name}.lock"
        if f.exists():
            try:
                age = time.time() - f.stat().st_mtime
                if age > self.STALE_TIMEOUT:
                    _logger.warning(
                        f"LockManager: حذف lock قديم '{name}' (عمره {age:.0f}s)"
                    )
                    f.unlink(missing_ok=True)
                else:
                    return False
            except OSError:
                try: f.unlink(missing_ok=True)
                except: pass

        try:
            f.touch()
            self._locks[name] = f
            self._start_renewal(name, f)
            return True
        except OSError:
            return False

    def _start_renewal(self, name: str, f: Path):
        """يبدأ thread يُجدد mtime الـ lock كل RENEWAL_INTERVAL ثانية."""
        stop = threading.Event()
        self._stop_events[name] = stop

        def _renew():
            while not stop.wait(timeout=self.RENEWAL_INTERVAL):
                try:
                    if f.exists():
                        f.touch()
                except OSError:
                    break   # الـ lock حُذف خارجياً — توقف

        t = threading.Thread(target=_renew, daemon=True,
                             name=f"LockRenewer-{name}")
        t.start()
        self._renewers[name] = t

    def release(self, name: str):
        # أوقف الـ renewal أولاً
        stop = self._stop_events.pop(name, None)
        if stop:
            stop.set()
        self._renewers.pop(name, None)

        f = self._locks.pop(name, None)
        if f and f.exists():
            try: f.unlink()
            except OSError: pass

    def is_locked(self, name: str) -> bool:
        f = self._dir / f"{name}.lock"
        if not f.exists():
            return False
        try:
            age = time.time() - f.stat().st_mtime
            return age <= self.STALE_TIMEOUT
        except OSError:
            return False

    def release_all(self):
        for name in list(self._locks):
            self.release(name)
