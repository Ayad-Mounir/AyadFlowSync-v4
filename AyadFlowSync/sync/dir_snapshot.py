#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.dir_snapshot — DirSnapshot: فهرس المجلدات للمسح فائق السرعة
================================================================

⚡ v4.0 — الطبقة الأولى من الفهرس الذكي

المشكلة:
    مشروع فيه 200,000 ملف — تغيّر ملف واحد فقط.
    المسح القديم: يفحص 200,000 ملف واحد واحد = دقائق.
    المسح الجديد: يفحص 2,000 مجلد → يدخل فقط في المتغير = ثوانٍ.

الفكرة:
    عند كل مزامنة، يُحفظ لكل مجلد:
    - عدد الملفات المباشرة فيه
    - مجموع أحجام ملفاته المباشرة
    - أحدث وقت تعديل لملف مباشر فيه (max mtime)

    عند المزامنة الجاية:
    1. يمشي على المجلدات (لا الملفات)
    2. يقارن كل مجلد باللقطة المحفوظة
    3. لو المجلد لم يتغير → يقفز عليه بالكامل ⚡
    4. لو تغير → يدخل فيه ويفحص ملفاته فقط

    النتيجة: بدل 200,000 عملية stat → بضع مئات فقط.

التخزين:
    SQLite في DATA_DIR/dir_snapshots.db
    جدول واحد: pair_id + dir_path + file_count + total_size + max_mtime
"""

import os
import sqlite3
import hashlib
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..core.app_config import AppConfig

_logger = logging.getLogger("AyadFlowSync.dir_snapshot")


class DirSnapshot:
    """
    ⚡ فهرس المجلدات — الطبقة الأولى من المسح السريع.

    الاستخدام:
        snap = DirSnapshot(src, dst)
        snap.load()

        # عند المسح:
        changed_dirs = snap.find_changed_dirs(src)
        # → قائمة المجلدات المتغيرة فقط

        # بعد المزامنة:
        snap.update_dir(dir_path, file_count, total_size, max_mtime)
        snap.save()
    """

    _DB_FILE = AppConfig.DATA_DIR / "dir_snapshots.db"
    _local = threading.local()
    _init_lock = threading.Lock()

    def __init__(self, src: Path, dst: Path):
        self.src = src
        self.dst = dst
        self._pair_id = self._make_pair_id(src, dst)
        # RAM cache: dir_rel → (file_count, total_size, max_mtime_ns)
        self._cache: Dict[str, Tuple[int, int, int]] = {}
        self._dirty: Set[str] = set()

    @staticmethod
    def _make_pair_id(src: Path, dst: Path) -> str:
        # ⚡ v4.0 FIX: اسم المشروع + جهة — يعمل على أي حاسوب
        project_name = src.name
        # كشف: هل المجلد على الفلاشة أم الجهاز؟
        try:
            vault = AppConfig.VAULT_DIR
            src.relative_to(vault)
            side = "usb"
        except (ValueError, Exception):
            side = "pc"
        raw = f"v4||{project_name}||{side}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    # ── إعداد DB ────────────────────────────────────────────
    @classmethod
    def _db(cls) -> sqlite3.Connection:
        conn = getattr(cls._local, 'conn', None)
        if conn is None:
            with cls._init_lock:
                AppConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(
                    str(cls._DB_FILE), check_same_thread=True
                )
                cls._local.conn = conn
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dir_entries (
                        pair_id   TEXT NOT NULL,
                        dir_rel   TEXT NOT NULL,
                        fcount    INTEGER NOT NULL,
                        fsize     INTEGER NOT NULL,
                        max_mtime INTEGER NOT NULL,
                        PRIMARY KEY (pair_id, dir_rel)
                    ) WITHOUT ROWID
                """)
                conn.commit()
        return conn

    # ── تحميل ───────────────────────────────────────────────
    def load(self) -> "DirSnapshot":
        """يحمّل اللقطة من DB → RAM."""
        try:
            db = self._db()
            rows = db.execute(
                "SELECT dir_rel, fcount, fsize, max_mtime "
                "FROM dir_entries WHERE pair_id = ?",
                (self._pair_id,)
            ).fetchall()
            self._cache = {
                row[0]: (row[1], row[2], row[3])
                for row in rows
            }
            _logger.debug(f"DirSnapshot loaded: {len(self._cache)} dirs for {self._pair_id}")
        except Exception as e:
            _logger.warning(f"DirSnapshot.load: {e}")
            self._cache = {}
        return self

    # ── حفظ ──────────────────────────────────────────────────
    def save(self) -> None:
        """يحفظ التغييرات فقط (الـ dirty entries)."""
        if not self._dirty:
            return
        try:
            db = self._db()
            batch = []
            for dir_rel in self._dirty:
                if dir_rel in self._cache:
                    fc, fs, mm = self._cache[dir_rel]
                    batch.append((self._pair_id, dir_rel, fc, fs, mm))

            if batch:
                db.executemany(
                    "INSERT OR REPLACE INTO dir_entries "
                    "(pair_id, dir_rel, fcount, fsize, max_mtime) "
                    "VALUES (?, ?, ?, ?, ?)",
                    batch
                )

            # حذف المجلدات اللي انحذفت
            deleted = self._dirty - set(self._cache.keys())
            if deleted:
                for d in deleted:
                    db.execute(
                        "DELETE FROM dir_entries WHERE pair_id=? AND dir_rel=?",
                        (self._pair_id, d)
                    )

            db.commit()
            self._dirty.clear()
            _logger.debug(f"DirSnapshot saved: {len(batch)} dirs")
        except Exception as e:
            _logger.warning(f"DirSnapshot.save: {e}")

    # ── المسح السريع — اكتشاف المجلدات المتغيرة ──────────────
    def find_changed_dirs(self, root: Path,
                          excluded_names: set = None,
                          excluded_dirs: set = None) -> Tuple[List[Path], int, int]:
        """
        يمسح المجلدات ويقارنها باللقطة المحفوظة.

        Returns:
            (changed_dirs, total_dirs_scanned, total_dirs_skipped)

        changed_dirs = المجلدات اللي تغير فيها شيء → يحتاج مسح ملفاتها.
        """
        if not root.exists():
            return [], 0, 0

        excl_names = excluded_names or AppConfig.EXCLUDED_NAMES
        excl_dirs = excluded_dirs or AppConfig.EXCLUDED_DIRS

        changed: List[Path] = []
        scanned = 0
        skipped = 0
        new_snapshots: Dict[str, Tuple[int, int, int]] = {}

        def _scan_dir(directory: Path):
            nonlocal scanned, skipped

            try:
                dir_rel = str(directory.relative_to(root)).replace('\\', '/')
                if dir_rel == '.':
                    dir_rel = ''
            except ValueError:
                return

            scanned += 1
            file_count = 0
            total_size = 0
            max_mtime_ns = 0
            subdirs: List[Path] = []

            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            if entry.name in excl_names:
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name in excl_dirs:
                                    continue
                                subdirs.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                st = entry.stat()
                                file_count += 1
                                total_size += st.st_size
                                if st.st_mtime_ns > max_mtime_ns:
                                    max_mtime_ns = st.st_mtime_ns
                        except OSError:
                            continue
            except (OSError, PermissionError):
                # مجلد لا يمكن قراءته → اعتبره متغير
                changed.append(directory)
                return

            # قارن باللقطة القديمة
            current = (file_count, total_size, max_mtime_ns)
            new_snapshots[dir_rel] = current

            old = self._cache.get(dir_rel)
            if old is None:
                # مجلد جديد
                changed.append(directory)
            elif old != current:
                # تغير: عدد الملفات أو حجمها أو أحدث وقت تعديل
                changed.append(directory)
            else:
                # لم يتغير → تخطي ⚡
                skipped += 1

            # ادخل في المجلدات الفرعية
            for subdir in subdirs:
                _scan_dir(subdir)

        _scan_dir(root)

        # حدّث الكاش بالقيم الجديدة
        for dir_rel, snap in new_snapshots.items():
            if self._cache.get(dir_rel) != snap:
                self._cache[dir_rel] = snap
                self._dirty.add(dir_rel)

        # احذف المجلدات اللي اختفت
        new_dirs = set(new_snapshots.keys())
        old_dirs = set(self._cache.keys())
        for gone in old_dirs - new_dirs:
            del self._cache[gone]
            self._dirty.add(gone)

        return changed, scanned, skipped

    # ── تحديث مجلد بعد المزامنة ─────────────────────────────
    def update_dir(self, dir_rel: str,
                   file_count: int, total_size: int, max_mtime_ns: int):
        """يُحدّث لقطة مجلد بعد المزامنة الناجحة."""
        self._cache[dir_rel] = (file_count, total_size, max_mtime_ns)
        self._dirty.add(dir_rel)

    # ── إحصائيات ─────────────────────────────────────────────
    @property
    def size(self) -> int:
        return len(self._cache)

    def clear(self):
        """مسح كامل — يُستخدم عند force_full."""
        try:
            db = self._db()
            db.execute(
                "DELETE FROM dir_entries WHERE pair_id = ?",
                (self._pair_id,)
            )
            db.commit()
        except Exception:
            pass
        self._cache.clear()
        self._dirty.clear()

    def stats_msg(self, changed_count: int, scanned: int, skipped: int) -> str:
        """رسالة إحصائيات المسح للعرض في السجل."""
        if scanned == 0:
            return "📁 DirSnapshot: لا مجلدات"
        pct = (skipped / scanned * 100) if scanned > 0 else 0
        return (
            f"📁 DirSnapshot: {scanned:,} مجلد مسحي | "
            f"{skipped:,} تخطي ({pct:.0f}%) | "
            f"{changed_count:,} متغير"
        )
