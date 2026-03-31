#!/usr/bin/env python3
"""sync.index — SyncIndex: SQLite-backed sync state per pair."""

import os
import json
import sqlite3
import socket
import hashlib
import threading
import logging
from pathlib import Path
from typing import Dict, Optional, Set

from ..core.app_config import AppConfig

_logger = logging.getLogger("AyadFlowSync.sync.index")

class SyncIndex:
    """
    ⚡ SyncIndex v12 — SQLite بدل JSON-per-pair

    v11: ملف JSON منفصل لكل (src,dst) pair → عشرات الملفات
    v12: جدول واحد في DB مشترك → استعلام فوري

    نفس الـ API تماماً — استبدال شفاف لـ v11

    الجدول:
        pair_id TEXT  — hash مختصر من (src_path + dst_path)
        rel     TEXT  — المسار النسبي للملف
        sm REAL, ss INTEGER  — src mtime + size
        dm REAL, ds INTEGER  — dst mtime + size
        PRIMARY KEY (pair_id, rel)
    """

    _DB_FILE  = AppConfig.DATA_DIR / "sync_index.db"
    # ✅ FIX v28: threading.local() — connection خاصة لكل thread
    _local     = threading.local()
    _conn_lock = threading.Lock()

    # ── إعداد DB مشترك ───────────────────────────────────
    @classmethod
    def _db(cls) -> sqlite3.Connection:
        conn = getattr(cls._local, 'conn', None)
        if conn is None:
            with cls._conn_lock:
                conn = sqlite3.connect(
                    str(cls._DB_FILE), check_same_thread=True
                )
                cls._local.conn = conn
                c = conn
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("PRAGMA synchronous=NORMAL")
                c.execute("PRAGMA cache_size=-1000")
                c.execute("""
                    CREATE TABLE IF NOT EXISTS sync_entries (
                        pair_id TEXT NOT NULL,
                        rel     TEXT NOT NULL,
                        sm      REAL NOT NULL,
                        ss      INTEGER NOT NULL,
                        dm      REAL NOT NULL,
                        ds      INTEGER NOT NULL,
                        PRIMARY KEY (pair_id, rel)
                    ) WITHOUT ROWID
                """)
                c.execute(
                    "CREATE INDEX IF NOT EXISTS idx_pair "
                    "ON sync_entries(pair_id)"
                )
                c.commit()
        return conn

    # ── migrate: يحوّل idx_*.json القديمة → DB ───────────
    @classmethod
    def migrate_json_files(cls):
        """يستورد ملفات idx_*.json من v11 ثم يحذفها"""
        old_dir = AppConfig.DATA_DIR / "sync_index"
        if not old_dir.exists():
            return
        pattern = list(old_dir.glob("idx_*.json"))
        if not pattern:
            return
        db = cls._db()
        total = 0
        for jf in pattern:
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    data: dict = json.load(f)
                # pair_id من اسم الملف
                pair_id = jf.stem  # idx_src_dst
                rows = []
                for rel, e in data.items():
                    if all(k in e for k in ('sm','ss','dm','ds')):
                        rows.append((pair_id, rel,
                                     float(e['sm']), int(e['ss']),
                                     float(e['dm']), int(e['ds'])))
                if rows:
                    with cls._conn_lock:
                        db.executemany(
                            "INSERT OR IGNORE INTO sync_entries VALUES (?,?,?,?,?,?)",
                            rows
                        )
                        db.commit()
                    total += len(rows)
                jf.unlink(missing_ok=True)
            except Exception as e:
                _logger.warning(f"SyncIndex migrate {jf.name}: {e}")
        if total:
            _logger.info(f"✅ SyncIndex migration: {total:,} entries → SQLite")

    # ── instance ─────────────────────────────────────────
    def __init__(self, src: Path, dst: Path):
        # ✅ FIX v4.1: pair_id = اسم المشروع فقط (لا مسارات مطلقة)
        #
        # المشكلة القديمة (v4.0):
        #   raw = f"v4||{src.resolve()}||{dst.resolve()}"
        #   C:\Users\Ahmed\Projects ≠ C:\Users\Sami\Projects
        #   → كل جهاز يبني SyncIndex من الصفر = فحص hash لكل الملفات
        #
        # الحل: اسم المجلد ثابت على كل الحواسيب
        #   "MyProject" = "MyProject" على كل الأجهزة ✅
        #
        # الأمان: is_unchanged يتحقق من mtime + size فعلياً
        #   → لن يُتخطى ملف تغيّر حتى لو pair_id مشترك
        #
        # ملاحظة: إذا كان عندك مشروعان بنفس الاسم على أجهزة مختلفة
        #   مثلاً "backup" على C:\ و "backup" على D:\ بمحتوى مختلف
        #   → is_unchanged يكشف الاختلاف عبر mtime/size → آمن تماماً
        src_name = src.name or src.resolve().name
        dst_name = dst.name or dst.resolve().name
        raw = f"v4.1||{src_name}||{dst_name}"
        self._pair_id = hashlib.md5(raw.encode()).hexdigest()[:16]
        self._src = src
        self._dst = dst
        # RAM cache للـ pair الحالي (يُملأ عند load)
        self._entries: Dict[str, tuple] = {}   # rel → (sm,ss,dm,ds)
        self._dirty       = False
        self._hits        = 0
        self._misses      = 0
        self._write_count = 0        # عداد الكتابات للـ batch commit
        self.BATCH_SIZE   = 400      # احفظ كل 400 ملف

    def load(self) -> 'SyncIndex':
        """تحميل كل entries هذا الـ pair في RAM — استعلام واحد فقط"""
        try:
            rows = self._db().execute(
                "SELECT rel, sm, ss, dm, ds FROM sync_entries WHERE pair_id=?",
                (self._pair_id,)
            ).fetchall()
            self._entries = {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}
        except Exception:
            self._entries = {}
        return self

    def save(self):
        """يحفظ التغييرات الجديدة في DB"""
        if not self._dirty:
            return
        try:
            rows = [
                (self._pair_id, rel, e[0], e[1], e[2], e[3])
                for rel, e in self._entries.items()
            ]
            with self._conn_lock:
                db = self._db()
                db.execute(
                    "DELETE FROM sync_entries WHERE pair_id=?",
                    (self._pair_id,)
                )
                if rows:
                    db.executemany(
                        "INSERT INTO sync_entries VALUES (?,?,?,?,?,?)", rows
                    )
                db.commit()
            self._dirty = False
        except Exception as e:
            _logger.warning(f"SyncIndex.save: {e}")

    # ── نفس API v11 ──────────────────────────────────────
    # ✅ FIX v21: امتدادات لا تُتخطى أبداً عبر SyncIndex — تُفحص دائماً بالـ Hash
    # هذه الملفات صغيرة الحجم وتتغير كثيراً → تكلفة إعادة الفحص زهيدة جداً
    _ALWAYS_CHECK_EXTS: Set[str] = {
        '.ctl', '.9', '.ini', '.cfg', '.xml', '.json',
        '.dat', '.db', '.log', '.tmp', '.bak', '.conf',
    }

    # ✅ FIX FAT32: tolerance ثانيتان — FAT32 يُقرّب mtime لأقرب 2 ثانية
    # بدون هذا: SyncIndex يعتبر كل ملف USB "تغيّر" → 15,000 ملف للـ Hash!
    _FAT32_TOL: float = 2.0

    @staticmethod
    def _mtime_round(t: float) -> float:
        """يُقرّب mtime لأقرب 2 ثانية — لضمان توافق FAT32 عند التخزين"""
        return float(int(t / 2) * 2)

    def is_unchanged(self, rel: str, src_st, dst: Path) -> bool:
        """
        ✅ v24 TURBO — zero dst.stat() fast path:

        إذا src لم يتغيّر (mtime+size مطابقان للـ index):
        → dst لم يتغيّر هو الآخر (Index يحفظ dst_mtime+dst_size)
        → نتجنب dst.stat() الإضافية تماماً = 2x أسرع على 150k ملف

        FAT32 tolerance ±2 ثانية محفوظة في كل المقارنات.
        """
        e = self._entries.get(rel)
        if not e:
            self._misses += 1
            return False

        # حجم المصدر تغيّر → ينسخ (لا حاجة لأي stat إضافية)
        if e[1] != src_st.st_size:
            self._misses += 1
            return False

        # ⚡ FAST PATH: إذا src_mtime مطابق للـ index → src لم يتغيّر
        # → dst لم يتغيّر هو الآخر (Index موثوق) → تخطّ dst.stat()
        src_mtime_match = abs(e[0] - self._mtime_round(src_st.st_mtime)) <= self._FAT32_TOL
        if src_mtime_match:
            # للامتدادات الحرجة (AccuMark): نؤكد عبر dst.stat() حتى مع fast path
            rel_path = Path(rel)
            if rel_path.suffix.lower() in self._ALWAYS_CHECK_EXTS:
                try:
                    dst_st = dst.stat()
                    if dst_st.st_size != e[3] or abs(e[2] - dst_st.st_mtime) > self._FAT32_TOL:
                        self._misses += 1
                        return False
                except OSError:
                    self._misses += 1
                    return False
            self._hits += 1
            return True

        # src_mtime تغيّر → تحقق من dst
        try:
            dst_st = dst.stat()
        except OSError:
            self._misses += 1
            return False

        if dst_st.st_size != src_st.st_size:
            self._misses += 1
            return False

        if abs(e[2] - dst_st.st_mtime) > self._FAT32_TOL or e[3] != dst_st.st_size:
            self._misses += 1
            return False

        self._hits += 1
        return True

    def mark_synced(self, rel: str, src_st, dst: Path):
        try:
            dst_st = dst.stat()
            # ✅ FIX FAT32: نُخزّن mtime مُقرَّباً لأقرب 2 ثانية
            # هكذا: is_unchanged ستنجح دائماً حتى لو FAT32 غيّر الأرقام قليلاً
            self._entries[rel] = (
                self._mtime_round(src_st.st_mtime), src_st.st_size,
                self._mtime_round(dst_st.st_mtime), dst_st.st_size,
            )
            self._dirty = True
            # ⚡ Batch commit: احفظ كل BATCH_SIZE ملف — يقلل fsync
            self._write_count += 1
            if self._write_count >= self.BATCH_SIZE:
                self.save()
                self._write_count = 0
        except OSError:
            pass

    def get(self, rel: str) -> Optional[Dict]:
        """يرجع معلومات الملف من Index أو None إذا غير موجود"""
        e = self._entries.get(rel)
        if not e:
            return None
        return {"src_mtime": e[0], "size": e[1], "dst_mtime": e[2], "dst_size": e[3]}

    def mark_deleted(self, rel: str):
        if rel in self._entries:
            del self._entries[rel]
            self._dirty = True

    def stats_msg(self) -> str:
        total = self._hits + self._misses
        pct   = int(self._hits / max(total, 1) * 100)
        return (f"⚡ Index: {self._hits:,} ملف تخطّيناه ({pct}%) | "
                f"{self._misses:,} ملف فحصناه")

    def clear(self):
        try:
            with self._conn_lock:
                self._db().execute(
                    "DELETE FROM sync_entries WHERE pair_id=?",
                    (self._pair_id,)
                )
                self._db().commit()
        except Exception:
            pass
        self._entries = {}

    # ── حذف كل الـ index (زر إعادة ضبط) ─────────────────
    @classmethod
    def clear_all(cls):
        try:
            with cls._conn_lock:
                cls._db().execute("DELETE FROM sync_entries")
                cls._db().commit()
        except Exception:
            pass

    # ── backward compat: _INDEX_DIR يبقى للكود القديم ──
    _INDEX_DIR = AppConfig.DATA_DIR / "sync_index"





# ╔═══════════════════════════════════════════╗
# ║           📁 ATOMIC COPIER               ║
# ╚═══════════════════════════════════════════╝



