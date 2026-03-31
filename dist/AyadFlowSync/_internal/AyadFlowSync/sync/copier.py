#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_sync_copier — AtomicCopier, DeltaCopier, PreSyncBackup, SafeTrash
"""
import os
import sys
import time
import json
import shutil
import hashlib
import sqlite3
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

_logger = logging.getLogger("AyadFlowSync.copier")

from ..core.app_config import AppConfig
from ..core.device_profiler import DeviceProfiler
from ..lang.proxy import LangProxy as Lang

try:
    import xxhash
    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False

try:
    from ..security.hash import HashCache
except ImportError:
    HashCache = None

try:
    import mmap
except ImportError:
    mmap = None

# ⚡ v4: استخدام fmt_size الموحّدة من constants
from ..core.constants import fmt_size as _format_size


class Utils:
    """Compatibility shim for format_size calls."""
    format_size = staticmethod(_format_size)


class AtomicCopier:
    # اسم مؤقت أقصر — يقلل خطر تجاوز MAX_PATH على Windows
    TEMP_SUFFIX = ".__tmp__"
    # هامش أمان: 50 MB على الأقل يجب أن يبقى حراً بعد النسخ
    MIN_FREE_MB = 50

    # ── MAX_PATH fix: حد Windows الافتراضي 260 حرف ─────────────────────────
    # يُضيف بادئة \\?\ لرفع الحد إلى 32767 حرفاً إذا كان المسار طويلاً جداً
    _WIN_MAX = 240   # هامش أمان قبل إضافة \\?\

    @staticmethod
    def _win_path(p: Path) -> Path:
        """على Windows: أضف بادئة UNC إذا تجاوز المسار 240 حرفاً لرفع حد MAX_PATH."""
        if sys.platform != 'win32':
            return p
        s = str(p.resolve())
        WIN_UNC = '\\\\?\\'
        if len(s) > AtomicCopier._WIN_MAX and not s.startswith(WIN_UNC):
            s = WIN_UNC + s
        return Path(s)

    @classmethod
    def _safe_tmp(cls, dst: Path) -> Path:
        """ينشئ مسار ملف tmp مع دعم المسارات الطويلة على Windows."""
        tmp_path = Path(str(dst) + cls.TEMP_SUFFIX)
        return cls._win_path(tmp_path)

    @classmethod
    def check_space(cls, dst_root: Path, required_bytes: int) -> Tuple[bool, str]:
        """
        يتحقق من وجود مساحة كافية قبل بدء النسخ.
        required_bytes = مجموع أحجام الملفات المراد نسخها
        يُضيف هامش أمان MIN_FREE_MB فوقها.
        يرجع (True, "") إذا المساحة كافية
                (False, رسالة) إذا المساحة ناقصة
        """
        try:
            dst_root.mkdir(parents=True, exist_ok=True)
            stat = shutil.disk_usage(dst_root)
            needed  = required_bytes + cls.MIN_FREE_MB * 1024 * 1024
            free    = stat.free
            if free >= needed:
                return True, ""
            shortage = needed - free
            return False, Lang.t(
                'no_space',
                needed=Utils.format_size(needed),
                free=Utils.format_size(free),
                short=Utils.format_size(shortage)
            )
        except OSError as e:
            # إذا فشل الفحص نسمح بالمتابعة ونسجّل فقط
            _logger.warning(f"disk_usage check failed: {e}")
            return True, ""

    @classmethod
    def copy(cls, src: Path, dst: Path, verify: bool = True) -> Tuple[bool, str]:
        """
        ⚡ v24 — نسخ ذري مع:
        • OPT 5: Resume Copy — يكمل الملفات المنسوخة جزئياً بدل إعادة البداية
        • OPT 6: Adaptive COPY_CHUNK — يزيد/يقلل chunk حسب السرعة الفعلية
        • xxhash XXH3_128 للـ verify: أسرع 100x من SHA-256
        • ملفات < 64KB: shutil.copy2 مباشر (لا hash)
        • fsync يُعطَّل على USB
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        # ── تطبيق \\?\ على Windows لرفع حد MAX_PATH ─────────────────────
        src = cls._win_path(src)
        dst = cls._win_path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = cls._safe_tmp(dst)
        src_hash = ""
        use_fsync = not AppConfig.is_removable(dst.parent)

        def _new_hasher():
            if XXHASH_AVAILABLE:
                return xxhash.xxh3_128()
            return hashlib.sha256()

        try:
            src_size = src.stat().st_size

            # ── ملفات صغيرة جداً على USB: copy2 مباشر بدون tmp ──
            # على FAT32/exFAT: rename أبطأ بكثير من write مباشر للملفات الصغيرة
            if src_size < 65536:
                is_usb_dst = AppConfig.is_removable(dst.parent)
                if is_usb_dst:
                    # نسخ مباشر على USB — أسرع بكثير
                    try:
                        shutil.copy2(src, dst)
                        if verify and dst.stat().st_size != src_size:
                            dst.unlink(missing_ok=True)
                            return False, "Size mismatch"
                        return True, "OK"
                    except OSError as e:
                        return False, f"Copy error: {e}"
                # على SSD/HDD: المسار الآمن الأصلي عبر tmp
                shutil.copy2(src, tmp)
                if verify:
                    if tmp.stat().st_size != src_size:
                        tmp.unlink(missing_ok=True)
                        return False, f"Size mismatch"
                try:
                    if sys.platform == 'win32' and dst.exists():
                        old = AtomicCopier._win_path(Path(str(dst) + '.bak'))
                        try: dst.replace(old)
                        except OSError: pass
                        # ✅ FIX v29 WinError 5: retry إذا AccuMark قافل الملف
                        _last_err = None
                        for _attempt in range(4):
                            try:
                                tmp.replace(dst); old.unlink(missing_ok=True)
                                _last_err = None; break
                            except OSError as _e:
                                _last_err = _e
                                if getattr(_e, 'winerror', 0) == 5 and _attempt < 3:
                                    time.sleep(0.5 * (_attempt + 1))
                                else:
                                    break
                        if _last_err:
                            try: old.replace(dst)
                            except OSError: pass
                            return False, str(_last_err)
                    else:
                        tmp.replace(dst)
                except OSError as e:
                    return False, f"Replace error: {e}"
                return True, "OK"

            # ── OPT 5: Resume Copy ──────────────────────────────────────────
            resume_from = 0
            h_src_full  = None   # hash كامل للمصدر — يُبنى من البداية دائماً
            if tmp.exists():
                try:
                    tmp_size = tmp.stat().st_size
                    if 0 < tmp_size < src_size:
                        resume_from = tmp_size
                        _logger.debug(f"Resume copy: {src.name} from {resume_from:,} bytes")
                    else:
                        tmp.unlink(missing_ok=True)
                        resume_from = 0
                except OSError:
                    resume_from = 0

            # ── OPT 6: Adaptive COPY_CHUNK ──────────────────────────────────
            chunk_size   = AppConfig.COPY_CHUNK
            MIN_CHUNK    = 65536
            MAX_CHUNK    = 8388608
            _t_last      = time.monotonic()
            _bytes_last  = 0
            _adapt_count = 0

            # hash المصدر كاملاً من البداية دائماً (للـ verify الصحيح)
            h = _new_hasher() if verify else None

            mode = 'ab' if resume_from > 0 else 'wb'
            with open(src, 'rb') as sf, open(tmp, mode) as df:
                # إذا resume: احسب hash الـ src من البداية حتى resume_from أولاً
                if resume_from > 0 and h:
                    read_so_far = 0
                    while read_so_far < resume_from:
                        to_read = min(chunk_size, resume_from - read_so_far)
                        part = sf.read(to_read)
                        if not part:
                            break
                        h.update(part)
                        read_so_far += len(part)
                    # sf الآن عند resume_from — متابعة طبيعية

                for chunk in iter(lambda: sf.read(chunk_size), b''):
                    if h:
                        h.update(chunk)
                    df.write(chunk)

                    # ⚡ OPT 6: ضبط chunk_size كل 4 تكرارات
                    _adapt_count += 1
                    _bytes_last  += len(chunk)
                    if _adapt_count % 4 == 0:
                        now = time.monotonic()
                        dt  = now - _t_last
                        if dt > 0.05:
                            speed_mbs = (_bytes_last / dt) / (1024 * 1024)
                            if speed_mbs > 80:
                                chunk_size = min(chunk_size * 2, MAX_CHUNK)
                            elif speed_mbs < 10:
                                chunk_size = max(chunk_size // 2, MIN_CHUNK)
                            _t_last    = now
                            _bytes_last = 0

                df.flush()
                if use_fsync:
                    os.fsync(df.fileno())

            src_hash = h.hexdigest() if h else ""
            shutil.copystat(src, tmp)

        except OSError as e:
            try: tmp.unlink(missing_ok=True)
            except OSError: pass
            return False, f"Copy error: {e}"

        # ── Verify بـ xxhash ──
        if verify and src_size > 0:
            vh = _new_hasher()
            try:
                with open(tmp, 'rb') as vf:
                    if src_size >= HashCache.MMAP_THRESHOLD:
                        try:
                            with mmap.mmap(vf.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                                vh.update(mm)
                        except (mmap.error, OSError, ValueError):
                            vf.seek(0)
                            for c in iter(lambda: vf.read(AppConfig.COPY_CHUNK), b''):
                                vh.update(c)
                    else:
                        for c in iter(lambda: vf.read(AppConfig.COPY_CHUNK), b''):
                            vh.update(c)
                if vh.hexdigest() != src_hash:
                    tmp.unlink(missing_ok=True)
                    return False, "Hash mismatch after copy"
            except OSError as e:
                try: tmp.unlink(missing_ok=True)
                except OSError: pass
                return False, f"Verify error: {e}"

        # استبدال ذري
        try:
            if sys.platform == 'win32' and dst.exists():
                # ✅ FIX v19: Path(str(dst) + '.old_bak') بدل with_suffix
                old = AtomicCopier._win_path(Path(str(dst) + '.bak'))
                try: dst.replace(old)
                except OSError: pass
                # ✅ FIX v29 WinError 5: retry إذا AccuMark قافل الملف
                _last_err = None
                for _attempt in range(4):
                    try:
                        tmp.replace(dst); old.unlink(missing_ok=True)
                        _last_err = None; break
                    except OSError as _e:
                        _last_err = _e
                        if getattr(_e, 'winerror', 0) == 5 and _attempt < 3:
                            time.sleep(0.5 * (_attempt + 1))
                        else:
                            break
                if _last_err:
                    try: old.replace(dst)
                    except OSError: pass
                    return False, str(_last_err)
            else: tmp.replace(dst)
            return True, "OK"
        except OSError as e: return False, str(e)

    @classmethod
    def cleanup_temp(cls, folder: Path):
        try:
            for f in folder.rglob(f"*{cls.TEMP_SUFFIX}"):
                try: f.unlink()
                except OSError: pass
        except OSError: pass





# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  ⚡ v27: DELTA COPIER — نسخ الفرق فقط (مثل rsync)                       ║
# ║                                                                          ║
# ║  يُقسّم الملف إلى blocks بحجم 4MB                                       ║
# ║  يحسب hash لكل block — يرسل فقط الـ blocks التي تغيّرت                 ║
# ║  ملف 800MB تغيّر فيه 2MB → ينسخ 2MB فقط (أسرع 400x)                   ║
# ║                                                                          ║
# ║  يعمل تلقائياً للملفات ≥ DELTA_THRESHOLD                               ║
# ║  يحفظ block_hashes في SQLite للمقارنة السريعة                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class DeltaCopier:
    """
    ⚡ v27 — Delta Copy مثل rsync:

    بدل نسخ الملف كاملاً عند أي تغيير:
    ① يُقسّم المصدر والوجهة إلى blocks متساوية
    ② يحسب hash لكل block في الطرفين
    ③ يرسل فقط الـ blocks التي اختلفت
    ④ يُعيد بناء الملف على الوجهة

    النتيجة: ملف 800MB تغيّر فيه 10MB → يُنسخ 10MB فقط بدل 800MB.

    الحدود:
    • يعمل فقط للملفات ≥ DELTA_THRESHOLD (يختلف حسب قوة الجهاز)
    • الملفات الأصغر → AtomicCopier العادي (أسرع للصغار)
    • إذا تغيّر أكثر من 60% من الـ blocks → نسخ كامل (أكفأ)

    ✅ v27b: يتكيّف مع DeviceProfiler تلقائياً
    """

    # ── إعدادات حسب قوة الجهاز ────────────────────────────────
    # تُحسب ديناميكياً من DeviceProfiler بدل قيم ثابتة
    _DEVICE_CONFIGS = {
        "weak":   {
            "threshold_mb" : 200,    # على الضعيف: فقط للملفات > 200MB
            "block_size_mb": 8,      # blocks أكبر = أقل حسابات = أقل RAM
            "full_ratio"   : 0.40,   # إذا تغيّر 40% → نسخ كامل (أقل مخاطرة)
            "max_parallel" : 1,      # لا توازٍ على الضعيف
        },
        "mid":    {
            "threshold_mb" : 50,
            "block_size_mb": 4,
            "full_ratio"   : 0.60,
            "max_parallel" : 2,
        },
        "strong": {
            "threshold_mb" : 20,     # القوي يستفيد حتى من ملفات 20MB+
            "block_size_mb": 2,      # blocks أصغر = دقة أعلى
            "full_ratio"   : 0.70,
            "max_parallel" : 4,      # حساب blocks بالتوازي
        },
    }

    @classmethod
    def _cfg(cls) -> dict:
        """يُعيد إعدادات الجهاز الحالي"""
        p = DeviceProfiler.get() if hasattr(DeviceProfiler, '_measured') else "mid"
        return cls._DEVICE_CONFIGS.get(p, cls._DEVICE_CONFIGS["mid"])


    # SQLite لتخزين block hashes — يمنع إعادة الحساب
    _DB_FILE  = AppConfig.DATA_DIR / "delta_blocks.db"
    # ✅ FIX v28: threading.local() — connection خاصة لكل thread
    _local     = threading.local()
    _conn_lock = threading.Lock()

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
                c.execute("PRAGMA cache_size=-4000")
                c.execute("""
                    CREATE TABLE IF NOT EXISTS block_hashes (
                        path      TEXT NOT NULL,
                        mtime_ns  INTEGER NOT NULL,
                        size      INTEGER NOT NULL,
                        blocks    TEXT NOT NULL,
                        PRIMARY KEY (path)
                    )
                """)
                c.commit()
        return conn

    @classmethod
    def _hash_block(cls, data: bytes) -> str:
        """hash سريع لـ block واحد"""
        if XXHASH_AVAILABLE:
            return xxhash.xxh3_128(data).hexdigest()
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def _get_cached_blocks(cls, path: Path, st) -> Optional[List[str]]:
        """يجلب block hashes من cache إذا الملف لم يتغيّر"""
        try:
            row = cls._db().execute(
                "SELECT mtime_ns, size, blocks FROM block_hashes WHERE path=?",
                (str(path),)
            ).fetchone()
            if row and row[0] == st.st_mtime_ns and row[1] == st.st_size:
                return json.loads(row[2])
        except Exception:
            pass
        return None

    @classmethod
    def _save_blocks(cls, path: Path, st, blocks: List[str]):
        """يحفظ block hashes في cache"""
        try:
            db = cls._db()          # احصل على connection أولاً قبل القفل
            with cls._conn_lock:
                db.execute(
                    "INSERT OR REPLACE INTO block_hashes VALUES (?,?,?,?)",
                    (str(path), st.st_mtime_ns, st.st_size, json.dumps(blocks))
                )
                db.commit()
        except Exception:
            pass

    @classmethod
    def _compute_blocks(cls, path: Path, st, block_size: int = None) -> List[str]:
        """يحسب hash لكل block في الملف — مع cache"""
        if block_size is None:
            block_size = cls._cfg()["block_size_mb"] * 1024 * 1024
        cached = cls._get_cached_blocks(path, st)
        if cached is not None:
            return cached

        blocks = []
        try:
            with open(path, 'rb') as f:
                while True:
                    data = f.read(block_size)
                    if not data:
                        break
                    blocks.append(cls._hash_block(data))
        except OSError:
            return []

        cls._save_blocks(path, st, blocks)
        return blocks

    @classmethod
    def should_use_delta(cls, src: Path, dst: Path, src_size: int) -> bool:
        """يُقرر إذا كان Delta Copy مفيداً لهذا الملف — حسب قوة الجهاز"""
        threshold = cls._cfg()["threshold_mb"] * 1024 * 1024
        if src_size < threshold:
            return False
        if not dst.exists():
            return False
        try:
            dst_size  = dst.stat().st_size
            size_ratio = min(src_size, dst_size) / max(src_size, dst_size)
            return size_ratio > 0.5
        except OSError:
            return False

    @classmethod
    def copy(cls, src: Path, dst: Path, log_cb=None) -> Tuple[bool, str, int]:
        """
        ⚡ Delta Copy الرئيسية.

        Returns: (ok, message, bytes_actually_copied)
        bytes_actually_copied = الـ bytes الفعلية على USB (ليس حجم الملف)
        """
        log = log_cb or (lambda m: None)

        try:
            src_st   = src.stat()
            src_size = src_st.st_size

            # ── حساب blocks المصدر والوجهة ──────────────────────
            cfg        = cls._cfg()
            block_size = cfg["block_size_mb"] * 1024 * 1024
            full_ratio = cfg["full_ratio"]

            src_blocks = cls._compute_blocks(src, src_st, block_size)
            if not src_blocks:
                return False, "delta: فشل حساب blocks المصدر", src_size

            dst_blocks: List[str] = []
            dst_st = None
            if dst.exists():
                try:
                    dst_st     = dst.stat()
                    dst_blocks = cls._compute_blocks(dst, dst_st, block_size)
                except OSError:
                    dst_blocks = []

            # ── مقارنة blocks ──────────────────────────────────
            n_blocks      = len(src_blocks)
            n_dst_blocks  = len(dst_blocks)
            changed_idx   = []

            for i, src_h in enumerate(src_blocks):
                dst_h = dst_blocks[i] if i < n_dst_blocks else None
                if src_h != dst_h:
                    changed_idx.append(i)

            if not changed_idx:
                log(f"  ⚡ Delta: {src.name} — لا تغيير في أي block")
                return True, "DELTA_NO_CHANGE", 0

            change_ratio = len(changed_idx) / max(n_blocks, 1)

            # إذا تغيّر أكثر من full_ratio → نسخ كامل أكفأ
            if change_ratio > full_ratio:
                log(f"  ⚡ Delta: {src.name} — {change_ratio:.0%} تغيير → نسخ كامل ({DeviceProfiler.get_label()})")
                ok, msg = AtomicCopier.copy(src, dst)
                return ok, msg, src_size

            # ── تطبيق الـ blocks المتغيّرة فقط ─────────────────
            changed_bytes = len(changed_idx) * block_size
            saved_bytes   = src_size - min(changed_bytes, src_size)
            log(
                f"  ⚡ Delta [{DeviceProfiler.get_label()}]: {src.name} | "
                f"{len(changed_idx)}/{n_blocks} blocks تغيّرت | "
                f"نسخ {Utils.format_size(min(changed_bytes, src_size))} "
                f"(وفّرنا {Utils.format_size(saved_bytes)})"
            )

            # نسخ على ملف مؤقت — ذري
            tmp = AtomicCopier._win_path(Path(str(dst) + ".__dt__"))
            try:
                if dst.exists():
                    shutil.copy2(dst, tmp)
                else:
                    with open(tmp, 'wb') as f:
                        f.seek(src_size - 1)
                        f.write(b'\x00')

                # اكتب فقط الـ blocks المتغيّرة
                with open(src, 'rb') as sf, open(tmp, 'r+b') as df:
                    for idx in changed_idx:
                        offset = idx * block_size
                        sf.seek(offset)
                        data = sf.read(block_size)
                        df.seek(offset)
                        df.write(data)

                    # إذا المصدر أكبر من الوجهة — اكتب الجزء الإضافي
                    if src_size > (dst_st.st_size if dst_st else 0):
                        tail_start = n_dst_blocks * block_size
                        if tail_start < src_size:
                            sf.seek(tail_start)
                            df.seek(tail_start)
                            while True:
                                chunk = sf.read(block_size)
                                if not chunk:
                                    break
                                df.write(chunk)

                    df.truncate(src_size)
                    df.flush()

                shutil.copystat(src, tmp)

                # استبدال ذري
                if sys.platform == 'win32' and dst.exists():
                    old = Path(str(dst) + '.delta_old')
                    try: dst.replace(old)
                    except OSError: pass
                    try:
                        tmp.replace(dst)
                        old.unlink(missing_ok=True)
                    except OSError as e:
                        try: old.replace(dst)
                        except OSError: pass
                        return False, str(e), 0
                else:
                    tmp.replace(dst)

                # تحديث block cache للوجهة
                try:
                    new_dst_st = dst.stat()
                    cls._save_blocks(dst, new_dst_st, src_blocks)
                except OSError:
                    pass

                actual_copied = min(changed_bytes, src_size)
                return True, "DELTA_OK", actual_copied

            except Exception as e:
                try: tmp.unlink(missing_ok=True)
                except OSError: pass
                return False, f"delta error: {e}", src_size

        except OSError as e:
            return False, f"delta stat error: {e}", 0





# ╔═══════════════════════════════════════════╗
# ║           📸 PRE-SYNC BACKUP              ║
# ╚═══════════════════════════════════════════╝
class PreSyncBackup:
    def __init__(self):
        self.backup_dir = AppConfig.PRESYNC_DIR

    def create(self, files: List[Path], base: Path = None) -> Optional[Path]:
        """
        يحفظ الملفات بمساراتها النسبية الكاملة لتجنب تعارض الأسماء.
        مثال: موديل_001/باترن.mrk → snapshot/موديل_001/باترن.mrk
        """
        if not files: return None
        try:
            sd = self.backup_dir / datetime.now().strftime('%Y%m%d_%H%M%S')
            sd.mkdir(parents=True, exist_ok=True)
            for f in files:
                try:
                    if base and f.is_relative_to(base):
                        rel = f.relative_to(base)
                        dst = sd / rel
                    else:
                        # fallback: اسم الملف مع hash مختصر لتجنب التعارض
                        suffix = f"_{hashlib.md5(str(f).encode()).hexdigest()[:6]}"
                        dst = sd / (f.stem + suffix + f.suffix)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
                except OSError: pass
            return sd
        except OSError as e:
            _logger.warning(f"PreSyncBackup: {e}"); return None

    def list_snapshots(self) -> List[Dict]:
        snaps = []
        try:
            for d in sorted(self.backup_dir.iterdir(), reverse=True):
                if d.is_dir():
                    fc = sum(1 for _ in d.rglob('*') if _.is_file())
                    snaps.append({'path': d, 'name': d.name, 'files': fc})
        except OSError: pass
        return snaps

    def cleanup_old(self, keep: int = 5):
        for snap in self.list_snapshots()[keep:]:
            try: shutil.rmtree(snap['path'])
            except OSError: pass





# ╔══════════════════════════════════════════════════════════════╗
# ║   🗑️  SAFE TRASH — سلة المحذوفات الآمنة                    ║
# ╚══════════════════════════════════════════════════════════════╝
class SafeTrash:
    """
    🗑️ SafeTrash — بديل آمن لـ unlink() المباشر

    بدل حذف الملف نهائياً:
    ① ينقله إلى FlowSync_Data/trash/{تاريخ_الحذف}/{مصدر}/{مساره_الكامل}
    ② يحفظ معلوماته في manifest.json (المسار الأصلي، التاريخ، المصدر)
    ③ يمكن استرجاعه لمكانه الأصلي بنقرة واحدة
    ④ يُنظّف تلقائياً بعد TRASH_KEEP_DAYS يوم

    البنية:
    FlowSync_Data/trash/
      ├── manifest.json          ← فهرس كل المحذوفات
      ├── 20240201_143022/       ← جلسة الحذف (timestamp)
      │   ├── PC/                ← محذوفات من الجهاز
      │   │   └── مشروع/ملف.sch  ← نفس المسار الأصلي
      │   └── USB/               ← محذوفات من الفلاشة
      │       └── مشروع/ملف.brd
    """

    MANIFEST = AppConfig.TRASH_DIR / "manifest.json"
    _lock = threading.Lock()

    # ── تحميل وحفظ Manifest ───────────────────────────────
    @classmethod
    def _load_manifest(cls) -> List[Dict]:
        try:
            if cls.MANIFEST.exists():
                with open(cls.MANIFEST, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    @classmethod
    def _save_manifest(cls, entries: List[Dict]):
        try:
            tmp = cls.MANIFEST.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
                f.flush(); os.fsync(f.fileno())
            tmp.replace(cls.MANIFEST)
        except Exception as e:
            _logger.warning(f"SafeTrash manifest save: {e}")

    # ── Batch buffer: يجمع entries قبل الكتابة ────────────
    _batch_entries: List[Dict] = []
    _batch_session: str = ""

    @classmethod
    def begin_batch(cls, source_label: str = "PC") -> str:
        """ابدأ جلسة حذف batch — جلسة واحدة لكل العناصر"""
        with cls._lock:
            cls._batch_session = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            cls._batch_entries  = []
        return cls._batch_session

    @classmethod
    def flush_batch(cls):
        """احفظ كل الـ entries دفعة واحدة — استدعِه بعد الانتهاء"""
        with cls._lock:
            if not cls._batch_entries:
                cls._batch_session = ""
                return
            entries = cls._load_manifest()
            entries.extend(cls._batch_entries)
            cls._save_manifest(entries)
            cls._batch_entries = []
            cls._batch_session = ""

    # ── الحذف الآمن ───────────────────────────────────────
    @classmethod
    def move_to_trash(cls, file_path: Path,
                      source_label: str = "PC") -> bool:
        """
        ينقل الملف للـ Trash بدل حذفه نهائياً.

        ⚡ TURBO: إذا كان batch_session مفعّلاً → لا يكتب manifest لكل ملف
                  بل يجمع الـ entries ويكتبها دفعة واحدة في flush_batch()
                  → 2000 ملف = كتابة واحدة بدل 2000 كتابة بـ fsync

        file_path    : المسار الكامل للملف
        source_label : "PC" أو "USB" — لتنظيم المجلدات
        Returns True إذا نجح، False إذا فشل
        """
        if not file_path.exists():
            return True

        with cls._lock:
            ts = cls._batch_session or datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            use_batch = bool(cls._batch_session)

        session = AppConfig.TRASH_DIR / ts / source_label
        try:
            rel_in_trash = Path(*file_path.parts[1:]) if file_path.is_absolute() else file_path
            dst = session / rel_in_trash
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(dst))

            entry = {
                "ts"         : ts,
                "source"     : source_label,
                "original"   : str(file_path),
                "trash_path" : str(dst),
                "size"       : dst.stat().st_size if dst.exists() else 0,
                "deleted_at" : datetime.now().isoformat(),
            }

            if use_batch:
                # ⚡ TURBO: اجمع فقط — لا تكتب الآن
                with cls._lock:
                    cls._batch_entries.append(entry)
            else:
                # وضع عادي (ملف واحد): اكتب فوراً
                with cls._lock:
                    entries = cls._load_manifest()
                    entries.append(entry)
                    cls._save_manifest(entries)

            _logger.info(f"SafeTrash: moved {file_path.name} → {dst}")
            return True

        except Exception as e:
            _logger.error(f"SafeTrash.move_to_trash failed: {e}")
            return False

    # ── الاسترجاع ─────────────────────────────────────────
    @classmethod
    def restore(cls, entry: Dict) -> Tuple[bool, str]:
        """
        يسترجع ملفاً من الـ Trash لمكانه الأصلي.
        entry : سجل من manifest.json
        Returns (True, "") إذا نجح، (False, رسالة_الخطأ) إذا فشل
        """
        trash_p    = Path(entry["trash_path"])
        original_p = Path(entry["original"])

        if not trash_p.exists():
            return False, f"الملف غير موجود في الـ Trash: {trash_p.name}"

        try:
            original_p.parent.mkdir(parents=True, exist_ok=True)
            # إذا كان الملف موجوداً في المكان الأصلي — نحتفظ بالاثنين
            if original_p.exists():
                # ✅ FIX v19: str concat بدل with_suffix لدعم أي امتداد
                backup = Path(str(original_p) + f".conflict_{datetime.now().strftime('%H%M%S')}")
                original_p.rename(backup)
                _logger.info(f"Restore conflict: existing file renamed to {backup.name}")

            shutil.move(str(trash_p), str(original_p))

            # أزله من الـ manifest
            with cls._lock:
                entries = cls._load_manifest()
                entries = [e for e in entries
                           if e.get("trash_path") != entry["trash_path"]]
                cls._save_manifest(entries)

            # نظّف المجلدات الفارغة في الـ Trash
            try:
                session_dir = trash_p.parent
                if session_dir.exists() and not any(session_dir.rglob('*')):
                    shutil.rmtree(session_dir, ignore_errors=True)
            except Exception:
                pass

            return True, ""

        except Exception as e:
            return False, str(e)

    # ── قائمة المحذوفات ───────────────────────────────────
    @classmethod
    def list_items(cls) -> List[Dict]:
        """يرجع قائمة كل الملفات في الـ Trash مرتبة من الأحدث للأقدم"""
        entries = cls._load_manifest()
        # تحقق أن الملف لا يزال موجوداً فعلاً في الـ Trash
        valid = []
        for e in entries:
            if Path(e.get("trash_path", "")).exists():
                valid.append(e)
        # إذا تغيّر العدد (ملفات حُذفت يدوياً) — نحدّث الـ manifest
        if len(valid) != len(entries):
            with cls._lock:
                cls._save_manifest(valid)
        return sorted(valid, key=lambda x: x.get("deleted_at", ""), reverse=True)

    # ── حجم الـ Trash ─────────────────────────────────────
    @classmethod
    def total_size(cls) -> int:
        """مجموع حجم كل الملفات في الـ Trash بالبايت"""
        total = 0
        try:
            for item in AppConfig.TRASH_DIR.rglob('*'):
                if item.is_file() and item.name != 'manifest.json':
                    try: total += item.stat().st_size
                    except OSError: pass
        except OSError:
            pass
        return total

    # ── التنظيف التلقائي ──────────────────────────────────
    @classmethod
    def auto_cleanup(cls, keep_days: int = None):
        """
        يحذف نهائياً الملفات التي مضى عليها أكثر من keep_days يوم.
        يُستدعى عند فتح البرنامج.
        """
        keep_days = keep_days or AppConfig.TRASH_KEEP_DAYS
        cutoff    = datetime.now() - timedelta(days=keep_days)
        entries   = cls._load_manifest()
        remaining = []
        deleted_count = 0

        for e in entries:
            try:
                da_str = e.get("deleted_at", "")
                if not da_str:
                    continue
                deleted_at = datetime.fromisoformat(da_str)
                if deleted_at < cutoff:
                    # مضى عليه أكثر من المدة — احذفه نهائياً
                    tp = Path(e.get("trash_path", ""))
                    if tp.exists():
                        tp.unlink(missing_ok=True)
                    deleted_count += 1
                else:
                    remaining.append(e)
            except Exception:
                remaining.append(e)

        if deleted_count > 0:
            with cls._lock:
                cls._save_manifest(remaining)
            # نظّف المجلدات الفارغة
            try:
                for d in sorted(AppConfig.TRASH_DIR.iterdir(), reverse=True):
                    if d.is_dir() and d.name != 'manifest.json':
                        if not any(d.rglob('*')):
                            shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
            _logger.info(f"SafeTrash: auto-cleanup removed {deleted_count} old items")

    # ── حذف كامل للـ Trash ────────────────────────────────
    @classmethod
    def empty_trash(cls):
        """يفرغ الـ Trash بالكامل — لا رجعة"""
        try:
            for item in AppConfig.TRASH_DIR.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                elif item.name != 'manifest.json':
                    item.unlink(missing_ok=True)
            with cls._lock:
                cls._save_manifest([])
        except Exception as e:
            _logger.error(f"SafeTrash.empty_trash: {e}")





# ╔══════════════════════════════════════════════════════════════╗
# ║   📋  SYNC REPORT — تقرير المزامنة المفصّل                  ║
# ╚══════════════════════════════════════════════════════════════╝



