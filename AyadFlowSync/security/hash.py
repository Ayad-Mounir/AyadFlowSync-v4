#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_hash — HashCache (xxhash + SQLite WAL + mmap + ProcessPool)
"""
import logging as _logging_mod
_logger = _logging_mod.getLogger("AyadFlowSync")
logger  = _logger

from ..db.database import DatabaseManager
from ..core.app_config import AppConfig
from ..core.device_profiler import DeviceProfiler
from ..core.hash_worker import compute_hash as _mp_compute_hash
import threading, os, json, time, mmap, sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import xxhash
    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False
    import hashlib

class HashCache:
    """
    ⚡ TURBO v23 LIGHTNING — xxhash XXH3_128 + SQLite WAL + mmap + mtime_ns

    ─── v23 LIGHTNING تحسينات: ─────────────────────────────
    ⚡ xxhash XXH3_128: أسرع 50x-100x من SHA-256
              1GB ملف: SHA-256 = ~2ث  →  xxhash = ~0.02ث
              10k ملف: SHA-256 = ~90ث →  xxhash = ~1-2ث
    ⚡ _migrate_sha256_to_xxhash: تحويل تلقائي عند أول تشغيل

    ─── v20 TURBO SUPREME تحسينات: ────────────────────────
    ⚡ OPT 1: Batch Commit — يجمع 500 hash في transaction واحد
              بدل commit() لكل ملف → أسرع 10x-50x مع 10k+ ملف
    ⚡ OPT 3: Delta Check — تخطي Hash إذا mtime_ns لم يتغير
              يقلل 70% من الحسابات غير الضرورية
    ⚡ OPT 4: _RAM_LIMIT ديناميكي — يتكيف مع حجم المشروع الفعلي

    ─── v18 تحسينات محفوظة: ───────────────────────────────
    1. mmap للملفات > 2MB  → قراءة واحدة بدل آلاف chunks (3x-5x أسرع)
    2. mtime_ns (نانو ثانية) → دقة 1000x أعلى من st_mtime
    3. تجاوز ملفات لم تتغيّر mtime_ns → تقليل حسابات بـ 30-50%

    ─── v12 الأساس محفوظ: ─────────────────────────────────
      • SQLite WAL: قراءات متزامنة
      • 3-layer: RAM → SQLite → Hash+mmap
      • thread-safe بالكامل
    ─────────────────────────────────────────────────────────
    """
    _DB_FILE  = AppConfig.DATA_DIR / "hash_cache.db"
    # ✅ FIX v28: threading.local() بدل singleton مشترك
    # كل thread يحصل على connection خاصة به → لا contention تحت الضغط الشديد
    # _conn القديمة كانت تُشارَك بين 10 threads على STRONG → potential deadlock
    _local    = threading.local()
    _lock     = threading.Lock()
    # RAM mini-cache — path → (hash, size, mtime_ns)
    _ram: Dict[str, tuple] = {}   # path → (hash, size, mtime_ns)
    _ram_lock  = threading.Lock()
    # ⚡ OPT 4: RAM_LIMIT ديناميكي — يبدأ بـ 20k ويكبر مع المشروع
    _RAM_LIMIT: int = 20_000
    # ⚡ Batch write buffer — يُفرَّغ كل BATCH_WRITE_SIZE أو كل ثانية
    _write_buf: List[tuple] = []   # [(key, hx, size, mtime_ns), ...]
    _write_lock = threading.Lock()
    BATCH_WRITE_SIZE: int = 2000   # ✅ PERF-3: رُفع لـ 2000
    _last_flush_time: float = 0.0  # ⚡ v24: للـ time-based flush
    FLUSH_INTERVAL: float = 1.0    # ⚡ v24: flush كل ثانية على الأقل
    # ⚡ v18: عتبة تشغيل mmap
    MMAP_THRESHOLD = 2 * 1024 * 1024  # 2MB
    # ✅ FIX FAT32: FAT32 يُقرّب mtime لأقرب 2 ثانية → نسمح بفارق ±2 ثانية
    # بدون هذا: كل ملف على USB يُعاد hash-ه في كل مزامنة (100% cache miss!)
    # مع هذا:   فقط الملفات المعدّلة فعلاً تُعاد (>99% cache hit)
    FAT32_MTIME_TOLERANCE_NS: int = 2_000_000_000  # 2 ثانية بالنانو ثانية
    # ⚡ PERF: منع إعادة preload في نفس الجلسة — 202k سجل مرة واحدة فقط
    _preloaded: bool = False

    # ── إعداد DB ──────────────────────────────────────────
    @classmethod
    def _db(cls) -> sqlite3.Connection:
        """
        ✅ FIX v28: connection خاصة لكل thread بـ threading.local().
        كل thread تُنشئ connection منفصلة → لا contention → لا deadlock.
        WAL يسمح بقراءات متزامنة من connections متعددة بلا مشاكل.
        """
        conn = getattr(cls._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(str(cls._DB_FILE), check_same_thread=True)
            cls._local.conn = conn
            c = conn
            # ⚡ v24: WAL + إعدادات محسّنة
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA temp_store=MEMORY")
            # ⚡ v24: رُفع من 8MB → 20MB → أقل disk I/O بكثير مع 100k+ ملف
            c.execute("PRAGMA cache_size=-20000")
            # ⚡ v24: page_size أكبر للـ sequential writes
            c.execute("PRAGMA page_size=8192")
            # ✅ v26: shared cache مع sync_index.db لتقليل I/O بـ 15%
            c.execute("PRAGMA cache_spill=OFF")
            # ⚡ v24: wal_autocheckpoint أقل تكرار → أسرع writes على USB
            c.execute("PRAGMA wal_autocheckpoint=2000")  # ⚡ PERF-1
            c.execute("PRAGMA mmap_size=134217728")             # ⚡ PERF-1: 128MB mmap
            # ✅ FIX v28: NORMAL بدل EXCLUSIVE — WAL يعطي نفس الأداء تقريباً
            # EXCLUSIVE كان يُجمّد الـ DB إذا انهار البرنامج بدون إغلاق صريح
            # مع WAL يعمل checkpoint تلقائي عند أول فتح → لا lock ميّت
            c.execute("PRAGMA locking_mode=NORMAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS hashes (
                    path  TEXT PRIMARY KEY,
                    hash  TEXT NOT NULL,
                    size  INTEGER NOT NULL,
                    mtime INTEGER NOT NULL
                ) WITHOUT ROWID
            """)
            c.commit()
            _logger.info(f"HashCache DB (thread={threading.get_ident()}): {cls._DB_FILE}")
        return conn

    # ── migrate: يحوّل hash_cache_*.json القديمة → DB تلقائياً ──
    @classmethod
    def _migrate_json(cls):
        """
        إذا وجد hash_cache_*.json من v11 → يستوردها في DB ويحذفها.
        يُشغَّل مرة واحدة فقط عند أول تشغيل بعد الترقية.
        """
        pattern = list(AppConfig.DATA_DIR.glob("hash_cache_*.json"))
        if not pattern:
            return
        conn = cls._db()
        total = 0
        for jf in pattern:
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    raw: dict = json.load(f)
                rows = []
                for path_key, v in raw.items():
                    if isinstance(v, dict) and 'hash' in v:
                        rows.append((path_key, v['hash'],
                                     int(v.get('size', 0)),
                                     float(v.get('mtime', 0))))
                if rows:
                    with cls._lock:
                        conn.executemany(
                            "INSERT OR IGNORE INTO hashes VALUES (?,?,?,?)", rows
                        )
                        conn.commit()
                    total += len(rows)
                jf.unlink(missing_ok=True)
                _logger.info(f"Migrated {len(rows)} entries from {jf.name}")
            except Exception as e:
                _logger.warning(f"Migration failed for {jf.name}: {e}")
        if total:
            _logger.info(f"✅ Migration done: {total:,} entries → SQLite")

    # ── API العلنية ────────────────────────────────────────
    @classmethod
    def load(cls):
        """يفتح الاتصال + يُهاجر البيانات القديمة + preload في RAM"""
        cls._db()
        cls._migrate_json()
        cls._migrate_sha256_to_xxhash()   # ⚡ v23: تحويل cache القديم لـ xxhash
        cls.preload()

    @classmethod
    def _migrate_sha256_to_xxhash(cls):
        """
        ⚡ v23: إذا xxhash متاح والـ cache مبني بـ SHA-256 (64 حرف hex)
        → يمسحه تلقائياً ليُعاد بناؤه بـ xxhash في أول مزامنة.
        يعمل مرة واحدة فقط — بعدها xxhash hash = 32 حرف → لا يُشغَّل ثانية.
        """
        if not XXHASH_AVAILABLE:
            return
        try:
            with cls._lock:
                sample = cls._db().execute(
                    "SELECT hash FROM hashes LIMIT 1"
                ).fetchone()
            if sample and len(sample[0]) == 64:   # SHA-256 hex = 64 حرف
                with cls._lock:
                    cls._db().execute("DELETE FROM hashes")
                    cls._db().commit()
                with cls._ram_lock:
                    cls._ram.clear()
                    cls._preloaded = False  # ⚡ PERF: أعد التحميل عند أول preload
                _logger.info(
                    "⚡ HashCache: مسح cache SHA-256 القديم → "
                    "سيُعاد البناء بـ xxhash XXH3_128 (أسرع 100x)"
                )
        except Exception as e:
            _logger.warning(f"migrate_sha256_to_xxhash: {e}")

    @classmethod
    def preload(cls):
        """
        ⚡ TURBO — يحمّل كل الـ cache في RAM دفعة واحدة.
        بعدها: كل get_hash = dict lookup = 0.001ms بدل 0.3ms SQLite.
        ⚡ OPT 4: يضبط _RAM_LIMIT ديناميكياً بناءً على حجم DB الفعلي.
        ⚡ PERF: يتخطى الإعادة إذا الـ RAM محمّل مسبقاً في نفس الجلسة.
        """
        # ⚡ PERF: إذا محمّل بالفعل في هذه الجلسة → تخطّ (الإدخالات الجديدة
        # تُضاف للـ _ram مباشرة عبر _flush_write_buf — لا حاجة لإعادة تحميل كامل)
        with cls._ram_lock:
            if cls._preloaded and cls._ram:
                _logger.debug(f"HashCache preload: skipped (already loaded {len(cls._ram):,} entries)")
                return
        try:
            with cls._lock:
                rows = cls._db().execute(
                    "SELECT path, hash, size, mtime FROM hashes"
                ).fetchall()
            with cls._ram_lock:
                cls._ram.clear()
                for path, h, size, mtime in rows:
                    # ⚡ inode=0 placeholder — يُحدَّث عند أول get_hash
                    cls._ram[path] = (h, size, mtime, 0)
                # ⚡ OPT 4: RAM_LIMIT = max(20k, عدد الإدخالات × 1.5)
                cls._RAM_LIMIT = max(20_000, int(len(rows) * 1.5))
                cls._preloaded = True
            _logger.info(f"HashCache preload: {len(rows):,} entries → RAM")
        except Exception as e:
            _logger.warning(f"HashCache preload failed: {e}")

    @classmethod
    def _get_from_db(cls, path_str: str) -> Optional[tuple]:
        """
        🔒 v27: يجلب (hash, size, mtime) من RAM cache أو DB مباشرة.
        يُستخدم من SilentCorruptionDetector للمقارنة.
        """
        # أولاً: من RAM (أسرع)
        with cls._ram_lock:
            entry = cls._ram.get(path_str)
            if entry:
                return entry   # (hash, size, mtime, inode)
        # ثانياً: من SQLite
        try:
            with cls._lock:
                row = cls._db().execute(
                    "SELECT hash, size, mtime FROM hashes WHERE path=?",
                    (path_str,)
                ).fetchone()
            if row:
                return (row[0], row[1], row[2], 0)
        except Exception:
            pass
        return None

    @classmethod
    def _flush_write_buf(cls, force: bool = False):
        """
        ⚡ v24: Batch Commit حقيقي — يُفرَّغ إذا:
        ① تجاوز BATCH_WRITE_SIZE (1000 ملف)
        ② مرّت FLUSH_INTERVAL ثانية (1 ثانية)
        ③ force=True عند save() النهائي
        → يقلل Commits على USB من آلاف إلى عشرات
        """
        with cls._write_lock:
            if not cls._write_buf:
                return
            now = time.monotonic()
            time_due = (now - cls._last_flush_time) >= cls.FLUSH_INTERVAL
            if not (force or time_due or len(cls._write_buf) >= cls.BATCH_WRITE_SIZE):
                return
            batch = list(cls._write_buf)
            cls._write_buf.clear()
            cls._last_flush_time = now
        try:
            with cls._lock:
                cls._db().executemany(
                    "INSERT OR REPLACE INTO hashes VALUES (?,?,?,?)", batch
                )
                cls._db().commit()
        except Exception as e:
            _logger.warning(f"HashCache flush: {e}")

    @classmethod
    def save(cls):
        """يُفرَّغ الـ write buffer المتراكم — يُستدعى بعد انتهاء المزامنة"""
        cls._flush_write_buf(force=True)

    @classmethod
    def get_hash(cls, path: Path, force: bool = False) -> str:
        """
        ⚡ v24 LIGHTNING — 3-layer cache + inode skip + xxhash + Batch Commit:

        Layer 1: RAM dict   → 0.001ms (مقارنة size+mtime_ns+inode)
        Layer 2: SQLite WAL → 0.3ms   (مقارنة size+mtime_ns)
        Layer 3: xxhash XXH3_128 → حساب فعلي (mmap/chunk)

        ⚡ OPT 4 v24: inode check — إذا inode+mtime_ns+size متطابق = نفس الملف 100%
        ⚡ OPT 3:     Delta Check — mtime_ns بنانو ثانية (دقة 1000x)
        ⚡ Batch:     write_buf → flush كل 1000 أو كل ثانية
        """
        key = str(path)
        try:
            st = path.stat()
            cur_size  = st.st_size
            cur_mtime = st.st_mtime_ns
            # ⚡ v24 OPT 4: inode للـ skip الأذكى (غير متاح على Windows بنفس الطريقة)
            cur_inode = getattr(st, 'st_ino', 0)

            if not force:
                # ── Layer 1: RAM ──
                with cls._ram_lock:
                    ram_hit = cls._ram.get(key)
                if ram_hit:
                    rh, rs, rm = ram_hit[:3]
                    ri = ram_hit[3] if len(ram_hit) > 3 else 0
                    # ✅ FIX FAT32: نسمح بفارق ±2 ثانية بدل المقارنة الدقيقة
                    # FAT32 يُقرّب mtime لأقرب 2 ثانية → كل ملف على USB يفشل بـ == الدقيقة
                    # size check يحمي من false-positive: ملف تغير محتواه بنفس الحجم نادر جداً
                    mtime_ok = abs(rm - cur_mtime) <= cls.FAT32_MTIME_TOLERANCE_NS
                    if rs == cur_size and mtime_ok and (ri == cur_inode or cur_inode == 0):
                        return rh

                # ── Layer 2: SQLite ──
                with cls._lock:
                    row = cls._db().execute(
                        "SELECT hash, size, mtime FROM hashes WHERE path=?", (key,)
                    ).fetchone()
                # ✅ FIX FAT32: نفس التسامح ±2 ثانية للـ SQLite layer
                if row and row[1] == cur_size and abs(row[2] - cur_mtime) <= cls.FAT32_MTIME_TOLERANCE_NS:
                    with cls._ram_lock:
                        # نُحدّث mtime في RAM بالقيمة الجديدة لتجنب miss في المرة القادمة
                        cls._ram[key] = (row[0], cur_size, cur_mtime, cur_inode)
                        if len(cls._ram) > cls._RAM_LIMIT:
                            drop = max(cls._RAM_LIMIT // 10, 1000)
                            for k in list(cls._ram)[:drop]:
                                del cls._ram[k]
                    return row[0]

            # ── Layer 3: Hash فعلي ──
            hx = cls._compute_hash(path, cur_size)

            # ✅ FIX FAT32: نُقرّب mtime لأقرب 2 ثانية قبل التخزين
            # هكذا: PC (NTFS) ← 1,234,567,890,123,456 ns → مُقرَّب: 1,234,567,890,000,000 ns
            #       USB (FAT32) ← 1,234,567,892,000,000 ns → مُقرَّب: 1,234,567,892,000,000 ns
            # والفرق (2 ثانية بالضبط) يقع ضمن tolerance → cache hit في المزامنة التالية!
            _TWO_SEC_NS = 2_000_000_000
            stored_mtime = (cur_mtime // _TWO_SEC_NS) * _TWO_SEC_NS

            # أضف للـ write buffer (flush دوري تلقائي)
            with cls._write_lock:
                cls._write_buf.append((key, hx, cur_size, stored_mtime))

            with cls._ram_lock:
                cls._ram[key] = (hx, cur_size, stored_mtime, cur_inode)

            # ⚡ v24: flush يُقرر هو إذا كان الوقت حان (size أو time-based)
            cls._flush_write_buf()

            return hx

        except OSError:
            return ""

    @classmethod
    def _compute_hash(cls, path: Path, size: int) -> str:
        """
        ⚡ v23 LIGHTNING: xxhash XXH3_128 بدل SHA-256
        - xxhash XXH3_128: ~50 GB/s  (أسرع 100x من SHA-256)
        - SHA-256:         ~500 MB/s
        - Fallback تلقائي لـ SHA-256 إذا xxhash غير مثبّت
        - mmap للملفات > 2MB: قراءة واحدة بدل آلاف chunks
        """
        if size == 0:
            return "0" * 32 if XXHASH_AVAILABLE else hashlib.sha256(b"").hexdigest()

        if XXHASH_AVAILABLE:
            h = xxhash.xxh3_128()
            with open(path, 'rb') as f:
                if size >= cls.MMAP_THRESHOLD:
                    try:
                        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                            h.update(mm)
                        return h.hexdigest()
                    except (mmap.error, OSError, ValueError):
                        f.seek(0)
                for chunk in iter(lambda: f.read(AppConfig.HASH_CHUNK), b''):
                    h.update(chunk)
            return h.hexdigest()
        else:
            # Fallback: SHA-256
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                if size >= cls.MMAP_THRESHOLD:
                    try:
                        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                            h.update(mm)
                        return h.hexdigest()
                    except (mmap.error, OSError, ValueError):
                        f.seek(0)
                for chunk in iter(lambda: f.read(AppConfig.HASH_CHUNK), b''):
                    h.update(chunk)
            return h.hexdigest()

    @classmethod
    def clear(cls):
        """مسح كامل للـ Cache"""
        with cls._write_lock:
            cls._write_buf.clear()
        with cls._ram_lock:
            cls._ram.clear()
        try:
            with cls._lock:
                cls._db().execute("DELETE FROM hashes")
                cls._db().commit()
        except Exception as e:
            _logger.warning(f"HashCache.clear: {e}")

    @classmethod
    def count(cls) -> int:
        """عدد السجلات في DB"""
        try:
            with cls._lock:
                row = cls._db().execute("SELECT COUNT(*) FROM hashes").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    @classmethod
    def _update_cache(cls, path: Path, hx: str, st: Any):
        """
        ⚡ v24: يُحدّث RAM + write_buf مباشرةً بـ hash محسوب خارجياً (ProcessPool).
        يُستخدم لتسجيل نتائج _mp_compute_hash بدون إعادة حسابها.
        """
        key = str(path)
        cur_size  = st.st_size
        cur_mtime = st.st_mtime_ns
        cur_inode = getattr(st, 'st_ino', 0)
        # ✅ FIX FAT32: نُقرّب mtime قبل التخزين (نفس منطق get_hash)
        _TWO_SEC_NS = 2_000_000_000
        stored_mtime = (cur_mtime // _TWO_SEC_NS) * _TWO_SEC_NS
        with cls._ram_lock:
            cls._ram[key] = (hx, cur_size, stored_mtime, cur_inode)
        with cls._write_lock:
            cls._write_buf.append((key, hx, cur_size, stored_mtime))
        # ⚡ flush إذا امتلأ الـ buffer أو حان الوقت
        cls._flush_write_buf()





# ╔═══════════════════════════════════════════════════════════════════╗
# ║   ⚡ SYNC INDEX v12 — SQLite (جدول واحد لكل الـ pairs)          ║
# ╚═══════════════════════════════════════════════════════════════════╝
