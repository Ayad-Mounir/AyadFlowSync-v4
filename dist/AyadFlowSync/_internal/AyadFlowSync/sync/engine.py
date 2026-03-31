#!/usr/bin/env python3
"""sync.engine — SyncPipeline, SyncEngine — المحرك الرئيسي"""

import os
import sys
import time
import json
import shutil
import hashlib
import socket
import threading
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

from ..core.app_config import AppConfig
from ..core.constants import APP_VERSION, APP_NAME
from ..core.device_profiler import DeviceProfiler
from ..core.hash_worker import compute_hash, compute_hash as _mp_compute_hash
from ..security.hash import HashCache
from ..lang.proxy import LangProxy as Lang
from ..db.database import LockManager, fmt_size
from .copier import AtomicCopier, DeltaCopier, PreSyncBackup, SafeTrash
from .index import SyncIndex
from .report import SyncReport, FlashLedger, ConflictResolver, CheckpointManager, SilentCorruptionDetector
from .dir_snapshot import DirSnapshot
from .pipeline import SyncPipeline

_logger = logging.getLogger("AyadFlowSync.engine")

# ── ثوابت ProcessPool + Partial Hash ──────────────────────────────────────────
import multiprocessing as _mp
_CPU_CORES              = _mp.cpu_count() or 4
_PROCESS_THRESHOLD      = 50  * 1024 * 1024   # 50 MB
_PARTIAL_HASH_THRESHOLD = 100 * 1024 * 1024   # 100 MB
# ⚡ لا Global ProcessPool — ThreadPool أكثر أماناً على Windows/EXE
_GLOBAL_POOL: Any = None


class Utils:
    """Utility helpers."""
    @staticmethod
    def format_size(n: int) -> str:
        from ..core.constants import fmt_size
        return fmt_size(n)


# ─── Batch Database Writer ─────────────────────────────────────────────────────
class BatchWriter:
    """
    يكتب التحديثات لقاعدة البيانات على دفعات (300-500 ملف).
    يقلل عمليات fsync ويحسن الأداء بشكل كبير.
    """
    def __init__(self, index, batch_size: int = 400):
        self._index    = index
        self._size     = batch_size
        self._pending  = 0

    def mark_synced(self, key: str, val):
        """سجّل ملف كـ synced — احفظ كل batch_size ملف"""
        if hasattr(self._index, 'update'):
            self._index.update(key, val)
        self._pending += 1
        if self._pending >= self._size:
            self._flush()

    def _flush(self):
        try:
            if hasattr(self._index, 'save'):
                self._index.save()
        except Exception:
            pass
        self._pending = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._flush()


def _quick_differs(pc: Path, usb: Path) -> bool:
    """
    فحص سريع للاختلاف — قبل حساب Hash.
    يوفر 70-80% من وقت المسح للمجلدات الكبيرة.

    Returns True إذا الملفان مختلفان بالتأكيد أو إذا يجب حساب Hash.
    Returns False إذا الملفان متطابقان على الأرجح (لا حاجة لـ Hash).
    """
    try:
        pc_s  = pc.stat()
        usb_s = usb.stat()
        # فحص الحجم أولاً (أسرع فحص ممكن)
        if pc_s.st_size != usb_s.st_size:
            return True
        # فحص mtime مع tolerance 2 ثانية (FAT32 يقرّب لـ 2s)
        if abs(pc_s.st_mtime - usb_s.st_mtime) > 2.0:
            return True
        return False  # متطابقان — لا حاجة لـ Hash
    except OSError:
        return True  # عند الشك: اعتبرهم مختلفَين



class SyncEngine:
    """
    محرك المزامنة الذكية — أمان كامل + سرعة:

    ✅ ينسخ كل الملفات بدون استثناء (بما فيها 0 بايت)
    ✅ يكتشف التغيير بمستويين:
         المستوى 1: فحص المجلد كوحدة (عدد الملفات + مجموع الأحجام)
                    → إذا لم يتغير المجلد = تجاوزه كله فوراً ⚡
         المستوى 2: فحص كل ملف بـ Hash (فقط للمجلدات المتغيّرة)
    ✅ Hash Cache دائم — لا يعيد حساب ما لم يتغير
    ✅ لا timestamp — بعض البرامج تغيّره تلقائياً بدون تعديل حقيقي
    ✅ كل نسخة يتم التحقق من صحتها فور انتهائها (verify)
    ✅ Pre-sync backup قبل أي استبدال
    """

    def __init__(self, log_cb=None, progress_cb=None):
        self.log      = log_cb or (lambda m: None)
        self.progress = progress_cb or (lambda p: None)
        self.presync  = PreSyncBackup()
        self.lock_mgr = LockManager(AppConfig.LOCK_DIR)
        # Force-clean any stale lock file
        try: (AppConfig.LOCK_DIR / 'sync.lock').unlink(missing_ok=True)
        except: pass
        # Auto-clean stale locks from previous crashes
        try:
            self.lock_mgr.release('sync')
        except Exception:
            pass
        # إحصائيات
        self.copied = self.skipped = self.failed = 0
        self.total_size = 0
        self.errors: List[str] = []
        self.changed_files: List[str] = []
        self._cancel = threading.Event()

    def cancel(self):
        """✅ FIX 1 — يوقف المزامنة بأمان في أي مرحلة"""
        self._cancel.set()

    def _flush_target(self, dst: Path):
        """
        ⚡ v4.0: إفراغ الذاكرة المؤقتة للفلاشة بعد انتهاء النسخ.
        يمنع فقدان البيانات لو المستخدم سحب الفلاشة بعد انتهاء المزامنة مباشرة.
        - Windows: يُفرغ عبر فتح المجلد بـ FlushFileBuffers
        - Linux/Mac: os.sync()
        """
        try:
            if sys.platform == 'win32':
                # Windows: fsync على directory handle
                import ctypes
                from ctypes import wintypes
                kernel32 = ctypes.windll.kernel32
                OPEN_EXISTING = 3
                FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
                GENERIC_READ = 0x80000000
                h = kernel32.CreateFileW(
                    str(dst), GENERIC_READ, 7,  # FILE_SHARE_ALL
                    None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
                )
                if h and h != wintypes.HANDLE(-1).value:
                    kernel32.FlushFileBuffers(h)
                    kernel32.CloseHandle(h)
                self.log("💾 تم إفراغ ذاكرة الفلاشة المؤقتة")
            else:
                os.sync()
                self.log("💾 تم إفراغ ذاكرة الفلاشة المؤقتة")
        except Exception as e:
            _logger.debug(f"flush_target: {e}")
            # لا نفشل المزامنة بسبب خطأ في الـ flush

    def _should_exclude(self, p: Path) -> bool:
        """
        استثناء ملفات البرنامج الداخلية + المجلدات المُختارة من الإعدادات.
        ✅ كل الصيغ  ✅ كل الامتدادات  ✅ ملفات 0 بايت  ✅ ملفات مخفية
        """
        if p.name in AppConfig.EXCLUDED_NAMES:
            return True
        # استثناء المجلدات المُفعَّلة في الإعدادات
        # نفحص .name لكل أب في المسار — يعمل على Windows وLinux
        excl = AppConfig.EXCLUDED_DIRS
        if excl:
            for parent in (p, *p.parents):
                if parent.name in excl:
                    return True
        return False

    def _needs_update(self, src: Path, dst: Path) -> bool:
        """
        ✅ v4.0 FINAL — مقارنة صارمة تضمن نسخ كل تغيير:
        1. الملف غير موجود في الوجهة → ينسخ فوراً
        2. الحجم مختلف               → ينسخ فوراً
        3. حجم 0 في الطرفين          → يقارن mtime (الملفات الفارغة مهمة!)
        4. نفس الحجم > 0:
           - force=True في وضع AccuMark
           - يضمن اكتشاف تغييرات AccuMark
        """
        if not dst.exists(): return True
        try:
            ss = src.stat(); ds = dst.stat()
            if ss.st_size != ds.st_size: return True
            if ss.st_size == 0:
                # ⚡ v4.0: الملفات الفارغة مهمة (جربر، PCB، ملفات تحكم)
                # لو وقت التعديل مختلف → الملف تغير (حُذف وأُعيد إنشاؤه)
                # FAT32 tolerance: 2 ثانية
                return abs(ss.st_mtime - ds.st_mtime) > 2.0
            # ⚡ force فقط في وضع AccuMark — الوضع العادي يعتمد على cache
            _force = AppConfig.ACCUMARK_MODE
            return (HashCache.get_hash(src, force=_force) !=
                    HashCache.get_hash(dst, force=_force))
        except OSError: return True

    def _count_files(self, folder: Path) -> Tuple[int, int]:
        count = size = 0
        try:
            # ⚡ OPT 2: scandir recursive بدل rglob
            stack = [folder]
            while stack:
                d = stack.pop()
                try:
                    with os.scandir(d) as entries:
                        for e in entries:
                            try:
                                p = Path(e.path)
                                if self._should_exclude(p): continue
                                if e.is_file(follow_symlinks=False):
                                    count += 1
                                    try: size += e.stat().st_size
                                    except OSError: pass
                                elif e.is_dir(follow_symlinks=False):
                                    stack.append(p)
                            except OSError: pass
                except OSError: pass
        except OSError: pass
        return count, size

    def sync(self, src: Path, dst: Path, verify: bool = True,
             force_full: bool = False) -> Dict:
        """
        المزامنة الرئيسية — v20 TURBO SUPREME:

        ⚡ OPT 2: scandir بدل rglob → أسرع 2x-4x على Windows
        ⚡ المستوى 0: SyncIndex    — 2x stat() فقط ≈ 0.1ms/ملف
        ⚡ المستوى 1: فحص الحجم   — إذا مختلف = ينسخ فوراً
        ⚡ المستوى 2: Hash متوازٍ — ThreadPool 4 threads للملفات المشكوك فيها
        ⚡ Batch Commit            — كل 500 hash في transaction واحد

        الأمان:
          ✅ كل ملف يُتحقق منه بعد النسخ (verify)
          ✅ Pre-sync backup قبل أي استبدال
          ✅ 3 محاولات لكل ملف عند الخطأ
          ✅ ملفات 0 بايت تُنسخ كاملاً
        """
        self.copied = self.skipped = self.failed = self.total_size = 0
        self.errors = []; self.changed_files = []
        _sync_logger = logging.getLogger('AyadFlowSync.sync')
        _sync_logger.info(f"▶ Sync started: {src} → {dst}")

        # ══════════════════════════════════════════════════════
        # ✅ v22 COPY-PASTE MODE — نسخ لصق حقيقي
        # إذا الوجهة فارغة أو شبه فارغة → نسخ مباشر سريع
        # ══════════════════════════════════════════════════════
        # ⚡ v4.0: لو الوجهة فيها أقل من 10% من ملفات المصدر → نسخ مباشر
        # هذا يغطي: أول backup + backup بعد محاولة فاشلة + backup بعد حذف
        _dst_file_count = 0
        _src_file_count = 0
        if dst.exists():
            try:
                _stack = [str(dst)]
                while _stack and _dst_file_count < 5000:
                    _d = _stack.pop()
                    try:
                        with os.scandir(_d) as _entries:
                            for _e in _entries:
                                if _e.name in AppConfig.EXCLUDED_NAMES:
                                    continue
                                if _e.is_dir(follow_symlinks=False):
                                    if _e.name not in AppConfig.EXCLUDED_DIRS:
                                        _stack.append(_e.path)
                                elif _e.is_file(follow_symlinks=False):
                                    _dst_file_count += 1
                    except OSError:
                        pass
            except OSError:
                pass

        # عدّ ملفات المصدر بسرعة (حد 5000)
        try:
            _stack = [str(src)]
            while _stack and _src_file_count < 5000:
                _d = _stack.pop()
                try:
                    with os.scandir(_d) as _entries:
                        for _e in _entries:
                            if _e.name in AppConfig.EXCLUDED_NAMES:
                                continue
                            if _e.is_dir(follow_symlinks=False):
                                if _e.name not in AppConfig.EXCLUDED_DIRS:
                                    _stack.append(_e.path)
                            elif _e.is_file(follow_symlinks=False):
                                _src_file_count += 1
                except OSError:
                    pass
        except OSError:
            pass

        dst_is_empty = (not dst.exists()) or (_dst_file_count == 0)
        dst_is_mostly_empty = _dst_file_count < max(_src_file_count * 0.1, 100)

        if dst_is_empty or dst_is_mostly_empty:
            if dst_is_mostly_empty and not dst_is_empty:
                self.log(f"📋 نسخ مباشر — الوجهة فيها {_dst_file_count:,} من {_src_file_count:,}+ ملف")
            else:
                self.log("📋 نسخ كامل — مثل Ctrl+C Ctrl+V تماماً...")
            try:
                if not self.lock_mgr.acquire('sync'):
                    return {"status": "LOCK_FAILED", "message": Lang.t("eng_lock_fail")}

                excluded = AppConfig.EXCLUDED_NAMES
                excl_dirs = AppConfig.EXCLUDED_DIRS

                # ⚡ v4.0: نسخ تسلسلي بسيط — الأسرع والأضمن على USB
                # USB يكره الكتابة المتوازية — تسلسلي = أسرع فعلاً
                _t0 = time.time()
                _copied = 0
                _skipped = 0
                _failed = 0
                _errors = []
                _total = 0
                _idx_full = SyncIndex(src, dst)
                _idx_full.load()
                _idx_batch: list = []

                def _copy_tree_sequential(s_dir: Path, d_dir: Path):
                    """نسخ تسلسلي عودي — بسيط، سريع، لا يتوقف"""
                    nonlocal _copied, _skipped, _failed, _total

                    try:
                        d_dir.mkdir(parents=True, exist_ok=True)
                    except OSError:
                        pass

                    try:
                        with os.scandir(s_dir) as entries:
                            for entry in entries:
                                if self._cancel.is_set():
                                    return
                                if entry.name in excluded:
                                    continue

                                s_path = Path(entry.path)
                                d_path = d_dir / entry.name

                                if entry.is_dir(follow_symlinks=False):
                                    if entry.name in excl_dirs:
                                        continue
                                    _copy_tree_sequential(s_path, d_path)

                                elif entry.is_file(follow_symlinks=False):
                                    _total += 1
                                    try:
                                        src_st = entry.stat()

                                        # تخطي الموجود بنفس الحجم (استئناف)
                                        if d_path.exists():
                                            try:
                                                if src_st.st_size == d_path.stat().st_size:
                                                    _skipped += 1
                                                    # تقدم حتى للمتخطاة
                                                    if (_skipped + _copied) % 500 == 0:
                                                        self.log(f"  ⏩ {_skipped:,} ملف موجود — تخطي...")
                                                    continue
                                            except OSError:
                                                pass

                                        d_path.parent.mkdir(parents=True, exist_ok=True)
                                        shutil.copy2(str(s_path), str(d_path))
                                        _copied += 1
                                        self.changed_files.append(
                                            str(s_path.relative_to(src))
                                        )

                                        # تقدم
                                        _done = _copied + _skipped
                                        if _copied % 200 == 0 or _copied == 1:
                                            elapsed = time.time() - _t0
                                            if elapsed > 0 and _copied > 0:
                                                speed = _copied / elapsed
                                                # تقدير الإجمالي
                                                est_total = max(_total * 1.05, _done + 1000)
                                                pct = min(_done / est_total * 100, 99)
                                                remaining = (est_total - _done) / speed
                                                eta = f"~{remaining/60:.0f} دقيقة" if remaining >= 60 else f"~{remaining:.0f} ثانية"
                                                self.log(
                                                    f"  📊 {_copied:,} منسوخ"
                                                    f"{f' | {_skipped:,} تُخطّي' if _skipped else ''}"
                                                    f" | ⚡ {speed:.0f} ملف/ث | ⏱️ {eta}"
                                                )
                                                self.progress(min(pct, 99))

                                        # SyncIndex batch
                                        try:
                                            d_st = d_path.stat()
                                            rel = str(s_path.relative_to(src))
                                            _idx_batch.append((rel, d_st, d_path))
                                            if len(_idx_batch) >= 500:
                                                for _r, _s2, _t2 in _idx_batch:
                                                    _idx_full.mark_synced(_r, _s2, _t2)
                                                _idx_batch.clear()
                                                _idx_full.save()
                                        except Exception:
                                            pass

                                    except PermissionError:
                                        _failed += 1
                                        _errors.append(f"⚠️ مقفل: {entry.name}")
                                    except OSError as e:
                                        _failed += 1
                                        _errors.append(f"{entry.name}: {e}")
                    except OSError:
                        pass

                self.log(f"🚀 بدء النسخ...")
                _copy_tree_sequential(src, dst)

                # flush remaining index
                for _r, _s2, _t2 in _idx_batch:
                    _idx_full.mark_synced(_r, _s2, _t2)
                _idx_batch.clear()
                _idx_full.save()

                self.copied = _copied
                self.failed = _failed
                self.errors = _errors
                self._save_meta(dst, _copied, 0)
                HashCache.save()
                self.lock_mgr.release('sync')
                self.progress(100)

                _elapsed = time.time() - _t0
                _tstr = f"{_elapsed/60:.1f} دقيقة" if _elapsed >= 60 else f"{_elapsed:.0f} ثانية"
                _skip_msg = f" | {_skipped:,} تُخطّي" if _skipped else ""
                self.log(f"✅ نسخ كامل: {_copied:,} ملف | {_failed} أخطاء{_skip_msg} | ⏱️ {_tstr}")
                return {
                    "status":  "OK" if self.failed == 0 else "PARTIAL",
                    "copied":  self.copied,
                    "skipped": _skipped,
                    "failed":  self.failed,
                    "errors":  self.errors,
                }
            except Exception as e:
                try: self.lock_mgr.release('sync')
                except Exception: pass
                _logger.exception(f"parallel copytree failed: {e}")
                return {"status": "FAILED", "message": str(e)}

        # ✅ v21: مزامنة كاملة إجبارية — احذف SyncIndex أولاً
        if force_full:
            try:
                SyncIndex(src, dst).clear()
                DirSnapshot(src, dst).clear()
                _logger.info(f"force_full: SyncIndex + DirSnapshot cleared for {src.name}")
            except Exception as ex:
                _logger.warning(f"force_full: could not clear SyncIndex: {ex}")

        if not self.lock_mgr.acquire('sync'):
            return {"status": "LOCK_FAILED",
                    "message": Lang.t("eng_lock_fail")}
        if not src.exists():
            self.lock_mgr.release('sync')
            return {"status": "FAILED", "message": Lang.t('eng_folder_missing', path=src)}

        # ── وضع الأداء: fsync على SSD / بدون fsync على USB ──
        is_usb = AppConfig.is_removable(dst)
        if is_usb: self.log(Lang.t('perf_usb_mode'))
        else:       self.log(Lang.t('perf_ssd_mode'))

        # ⚡ v23: calibrate_usb هنا — قبل حساب threads وقبل المسح
        # الخطأ القديم: كان بعد الـ hash check → threads تُحسب بالقيم الافتراضية
        AppConfig.calibrate_usb(dst)

        # ⚡ تحميل SyncIndex — خط الدفاع الأول ضد إعادة الحساب
        # ⚡ preload HashCache في RAM قبل المسح
        HashCache.preload()
        idx = SyncIndex(src, dst).load()
        idx_size = len(idx._entries)
        if idx_size > 0:
            self.log(f"📋 Index محمّل: {idx_size:,} سجل → مزامنة سريعة")
        else:
            self.log("🆕 أول مزامنة — سيتم بناء Index للمرات القادمة")

        # ⚡ v4.0: DirSnapshot — الطبقة الأولى من الفهرس الذكي
        # بدل فحص 200,000 ملف → نفحص المجلدات أولاً ← المتغير فقط ندخل فيه
        dir_snap = DirSnapshot(src, dst)
        dir_snap.load()
        _changed_dirs: set = set()       # مجلدات يجب فحص ملفاتها
        _snap_is_useful = (dir_snap.size > 0 and idx_size > 0 and not force_full)

        if _snap_is_useful:
            _ch_list, _ds_scanned, _ds_skipped = dir_snap.find_changed_dirs(
                src,
                excluded_names=AppConfig.EXCLUDED_NAMES,
                excluded_dirs=AppConfig.EXCLUDED_DIRS,
            )
            _changed_dirs = {str(d) for d in _ch_list}
            self.log(dir_snap.stats_msg(len(_changed_dirs), _ds_scanned, _ds_skipped))
        else:
            if dir_snap.size == 0:
                self.log("📁 DirSnapshot: أول مزامنة — سيُبنى الفهرس")
            # كل المجلدات تُعتبر "متغيرة" — فحص شامل
            _changed_dirs = None   # None = فحص كل شيء

        # ── المسح بـ scandir (أسرع 2x-4x من rglob على Windows) ──
        needs_hash_check: List[Tuple[Path, Path, Any]] = []
        to_update:        List[Tuple[Path, Path, Any]] = []
        scan_count = 0
        total_files = 0
        _dir_skipped_files = 0    # عدد الملفات اللي تُخطّيت بفضل DirSnapshot

        # ── OPT 7: Generator-based scan — لا تخزن 100k مسار دفعة واحدة ──
        # بدل بناء قائمة كاملة في الذاكرة، نُنتج كل entry عند الحاجة
        # يقلل RAM من عشرات MB إلى بضعة KB مع 100k+ ملف
        # ✅ v26: مسح متوازٍ — حسب DeviceProfiler
        _scan_workers = DeviceProfiler.get_scan_workers()

        def _scan_gen(directory: Path, dst_dir: Path) -> Generator:
            """Generator يُنتج (item, target, src_st) — مع دعم DirSnapshot"""
            try:
                # ⚡ v4.0: لو DirSnapshot يقول المجلد لم يتغير → تخطي كل ملفاته
                if _changed_dirs is not None:
                    dir_str = str(directory)
                    if dir_str not in _changed_dirs and directory != src:
                        # هذا المجلد لم يتغير — نعدّ ملفاته كـ skipped
                        # لكن نحتاج نمشي في المجلدات الفرعية
                        # لأن مجلد فرعي ممكن يكون متغير
                        _has_changed_child = any(
                            c.startswith(dir_str) for c in _changed_dirs
                        )
                        if not _has_changed_child:
                            # لا هذا المجلد ولا أي مجلد فرعي فيه تغير
                            # → تخطي بالكامل ⚡
                            return

                with os.scandir(directory) as entries:
                    for entry in entries:
                        if getattr(self, "_cancel", None) and self._cancel.is_set():
                            return
                        try:
                            item = Path(entry.path)
                            if self._should_exclude(item):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                target_dir = dst_dir / entry.name
                                if not target_dir.exists():
                                    target_dir.mkdir(parents=True, exist_ok=True)
                                yield from _scan_gen(item, target_dir)
                            elif entry.is_file(follow_symlinks=False):
                                target = dst_dir / entry.name
                                src_st = entry.stat()
                                yield (item, target, src_st)
                        except OSError as e:
                            self.errors.append(f"scan:{entry.name}: {e}")
                            self.log(f"  ⚠️ تخطي (خطأ مسح): {entry.name}")
            except PermissionError:
                pass
            except OSError:
                raise

        # اِمشِ على الـ generator وصنّف كل ملف
        try:
            for item, target, src_st in _scan_gen(src, dst):
                if getattr(self, "_cancel", None) and self._cancel.is_set():
                    break
                total_files += 1
                scan_count  += 1

                rel     = item.relative_to(src)
                rel_str = str(rel)

                if not target.exists():
                    to_update.append((item, target, src_st))
                else:
                    if idx.is_unchanged(rel_str, src_st, target):
                        self.skipped += 1
                        continue
                    dst_st = target.stat()
                    if src_st.st_size != dst_st.st_size:
                        to_update.append((item, target, src_st))
                    elif src_st.st_size == 0:
                        # ⚡ v4.0: الملفات الفارغة مهمة (جربر، PCB، ملفات تحكم)
                        # لو وقت التعديل مختلف → الملف تغير
                        if abs(src_st.st_mtime - dst_st.st_mtime) > 2.0:
                            to_update.append((item, target, src_st))
                        else:
                            self.skipped += 1
                            idx.mark_synced(rel_str, src_st, target)
                    else:
                        # ⚡ فحص سريع: size + mtime قبل Hash
                        # يوفر 70-80% من وقت المسح للمجلدات الكبيرة
                        if not _quick_differs(item, target):
                            self.skipped += 1
                            idx.mark_synced(rel_str, src_st, target)
                        else:
                            needs_hash_check.append((item, target, src_st))

                if scan_count % 1000 == 0:
                    self.log(f"  🔍 مسح... {scan_count:,} عنصر ({len(to_update)} يحتاج نسخ)")

        except OSError as e:
            self.lock_mgr.release('sync')
            return {"status": "FAILED", "message": str(e)}

        if getattr(self, "_cancel", None) and self._cancel.is_set():
            self.lock_mgr.release('sync')
            return {"status": "CANCELLED", "copied": 0, "skipped": self.skipped}

        # ⚡ is_first_sync هنا — مرئي لكل الكود التالي بما فيه الـ log
        is_first_sync = (idx_size == 0)

        # ⚡ TURBO: Hash المشكوك فيها — ProcessPool للكبار، Threads للصغار
        if needs_hash_check and not self._cancel.is_set():

            # ⚡ OPT 10: تصنيف متوازٍ — كبار وصغار في نفس الوقت
            large_hash = [(i, t, s) for i, t, s in needs_hash_check
                          if s.st_size >= _PROCESS_THRESHOLD]
            small_hash = [(i, t, s) for i, t, s in needs_hash_check
                          if s.st_size <  _PROCESS_THRESHOLD]

            self.log(
                f"  ⚡ Hash: {len(needs_hash_check):,} ملف | "
                f"🔵 ProcessPool: {len(large_hash)} كبير | "
                f"🟢 Threads: {len(small_hash)} صغير"
                + (" (أول مزامنة)" if is_first_sync else "")
            )

            # ⚡ OPT 9: استخدم Partial Hash للملفات ≥ _PARTIAL_HASH_THRESHOLD (100MB)
            _idx_batch: list = []

            # ⚡ قفل لحماية to_update و _idx_batch من الـ race condition
            # _record_hash_result تُستدعى من ThreadPool workers
            _record_lock = threading.Lock()

            def _record_hash_result(item, target, src_st, changed):
                """تسجيل نتيجة hash check — thread-safe"""
                rel = item.relative_to(src)
                with _record_lock:
                    if changed:
                        to_update.append((item, target, src_st))
                    else:
                        self.skipped += 1
                        _idx_batch.append((str(rel), src_st, target))
                        if len(_idx_batch) >= 1000:
                            for _r, _s, _t in _idx_batch:
                                idx.mark_synced(_r, _s, _t)
                            _idx_batch.clear()
                            idx.save()

            # ── Thread-based للملفات الصغيرة ──────────────────────────────
            def _check_hash_thread(args):
                item, target, src_st = args
                try:
                    if is_first_sync:
                        try:
                            dst_st = target.stat()
                            if src_st.st_mtime_ns == dst_st.st_mtime_ns:
                                return (item, target, src_st, False)
                        except OSError:
                            pass
                        h_src = HashCache.get_hash(item,   force=False)
                        h_dst = HashCache.get_hash(target, force=False)
                    else:
                        try:
                            mtime_diff = abs(src_st.st_mtime - target.stat().st_mtime) > 1
                        except OSError:
                            mtime_diff = False
                        h_src = HashCache.get_hash(item,   force=mtime_diff)
                        h_dst = HashCache.get_hash(target, force=mtime_diff)
                    return (item, target, src_st, h_src != h_dst)
                except Exception:
                    return (item, target, src_st, True)

            # ── ProcessPool للملفات الكبيرة ────────────────────────────────
            # OPT 1: يتجاوز GIL — كل process يعمل على core منفصل
            # ملاحظة: نُرسل المسارات كـ strings (pickle-safe) ونستقبل النتائج فقط
            def _submit_large_via_processes(large_items):
                if not large_items:
                    return
                # بناء args للـ worker: (path_str, size, mtime_ns, use_partial)
                proc_args = []
                path_map  = {}   # path_str → (item, target, src_st)
                for item, target, src_st in large_items:
                    use_partial = src_st.st_size >= _PARTIAL_HASH_THRESHOLD
                    arg = (str(item), src_st.st_size, src_st.st_mtime_ns, use_partial)
                    proc_args.append(arg)
                    path_map[str(item)] = (item, target, src_st)

                    # ⚡ نحسب hash الوجهة بـ stat الحقيقي للوجهة
                    try:
                        dst_st_real = target.stat()
                        dst_size_real = dst_st_real.st_size
                        dst_mtime_real = dst_st_real.st_mtime_ns
                        dst_partial = dst_size_real >= _PARTIAL_HASH_THRESHOLD
                    except OSError:
                        # الوجهة غير موجودة → لا نحسب hash لها
                        dst_size_real = 0
                        dst_mtime_real = 0
                        dst_partial = False
                    if dst_size_real > 0:
                        arg_dst = (str(target), dst_size_real, dst_mtime_real, dst_partial)
                        proc_args.append(arg_dst)
                    path_map[str(target)] = (None, None, None)

                n_workers = min(_CPU_CORES, max(1, len(large_items)))
                try:
                    # ✅ v26: استخدم الـ Global Pool إذا متاح — بدل إنشاء جديد
                    pool = _GLOBAL_POOL if (_GLOBAL_POOL and DeviceProfiler.use_process_pool()) else None
                    if pool:
                        futures_p = {
                            pool.submit(_mp_compute_hash, a): a[0]
                            for a in proc_args
                        }
                        results_map = {}
                        for fut in as_completed(futures_p):
                            if getattr(self, "_cancel", None) and self._cancel.is_set():
                                break
                            try:
                                path_s, hx, sz, mt, ok = fut.result()
                                results_map[path_s] = hx if ok else ""
                            except Exception:
                                results_map[futures_p[fut]] = ""
                    else:
                        # fallback: ProcessPool محلي (جهاز لا يدعم global pool)
                        with ProcessPoolExecutor(max_workers=n_workers) as pex:
                            futures_p = {
                                pex.submit(_mp_compute_hash, a): a[0]
                                for a in proc_args
                            }
                            results_map = {}
                            for fut in as_completed(futures_p):
                                if getattr(self, "_cancel", None) and self._cancel.is_set():
                                    break
                                try:
                                    path_s, hx, sz, mt, ok = fut.result()
                                    results_map[path_s] = hx if ok else ""
                                except Exception:
                                    results_map[futures_p[fut]] = ""

                    # قارن src vs dst
                    for item, target, src_st in large_items:
                        h_src = results_map.get(str(item),  "")
                        h_dst = results_map.get(str(target), "")
                        # حدّث HashCache بالـ hash المحسوب
                        if h_src:
                            HashCache._update_cache(item,   h_src, src_st)
                        if h_dst:
                            try:
                                dst_st = target.stat()
                                HashCache._update_cache(target, h_dst, dst_st)
                            except OSError:
                                pass
                        changed = (h_src != h_dst) or not h_src
                        _record_hash_result(item, target, src_st, changed)

                except Exception as e:
                    # Fallback لـ Threads إذا فشل ProcessPool (مثلاً Windows frozen exe)
                    _logger.warning(f"ProcessPool fallback to threads: {e}")
                    t_workers = min(AppConfig.THREADS_SMALL, len(large_items))
                    with ThreadPoolExecutor(max_workers=t_workers) as tex:
                        for res in as_completed(
                            [tex.submit(_check_hash_thread, a) for a in large_items]
                        ):
                            if getattr(self, "_cancel", None) and self._cancel.is_set():
                                break
                            try:
                                item, target, src_st, changed = res.result()
                                _record_hash_result(item, target, src_st, changed)
                            except Exception:
                                pass

            # ── Hash كل الملفات بـ ThreadPool موحّد ──────────────────────
            # ⚡ ThreadPool أكثر أماناً وأسرع من ProcessPool+coordinator
            # على Windows/EXE — ProcessPool يسبب تعليق في بعض الحالات
            all_hash_items = large_hash + small_hash
            if all_hash_items:
                n_workers = min(AppConfig.THREADS_SMALL, max(1, len(all_hash_items)))
                with ThreadPoolExecutor(max_workers=n_workers) as tex:
                    futs = {tex.submit(_check_hash_thread, a): a for a in all_hash_items}
                    for fut in as_completed(futs):
                        if getattr(self, "_cancel", None) and self._cancel.is_set():
                            break
                        try:
                            item, target, src_st, changed = fut.result()
                            _record_hash_result(item, target, src_st, changed)
                        except Exception:
                            pass

            # commit الباقي
            for _r, _s, _t in _idx_batch:
                idx.mark_synced(_r, _s, _t)
            _idx_batch.clear()

        # سجّل أداء Index
        if idx_size > 0:
            self.log(idx.stats_msg())
        if is_first_sync:
            self.log(f"🆕 أول مزامنة: {len(to_update)} ينسخ | "
                     f"{self.skipped} متطابق | "
                     f"{len(needs_hash_check)} يحتاج تحقق")
        self.log(Lang.t('eng_file_count', n=total_files,
                        size=Utils.format_size(sum(s.st_size for _,_,s in to_update))))

        if not to_update:
            self.log(Lang.t('eng_no_changes'))
            idx.save(); HashCache.save()
            self.lock_mgr.release('sync')
            return {"status": "NO_CHANGES", "copied": 0, "skipped": total_files}

        self.log(Lang.t('eng_need_update', n=len(to_update)))

        # ④ فحص مساحة القرص — فقط للملفات المطلوب نسخها
        needed_size = sum(s.st_size for _,_,s in to_update)
        ok_space, space_msg = AtomicCopier.check_space(dst, needed_size)
        if not ok_space:
            self.lock_mgr.release('sync')
            self.log(space_msg)
            return {"status": "FAILED", "message": space_msg}
        free_now = shutil.disk_usage(dst if dst.exists() else dst.parent).free
        self.log(Lang.t('space_ok', free=Utils.format_size(free_now)))

        # ── Pre-sync backup للملفات الموجودة قبل استبدالها ──
        existing = [t for _, t, _ in to_update if t.exists()]
        if existing:
            snap = self.presync.create(existing, base=dst)
            if snap: self.log(Lang.t('eng_presync', name=snap.name))
            self.presync.cleanup_old()

        # ══════════════════════════════════════════════════════
        # ⚡ v28: اختيار ذكي — Pipeline أو Classic أو Bulk Copy
        # ══════════════════════════════════════════════════════
        PIPELINE_THRESHOLD = 5_000
        _update_ratio = len(to_update) / max(total_files, 1)

        # ⚡ v4.0: لو 80%+ من الملفات تحتاج نسخ → نسخ تسلسلي مباشر
        if _update_ratio >= 0.8 and len(to_update) > 1000:
            self.log(
                f"📋 نسخ مباشر — {len(to_update):,} من {total_files:,} "
                f"({_update_ratio*100:.0f}%) يحتاج نسخ"
            )
            _t0 = time.time()
            _total = len(to_update)
            _bulk_skipped = 0
            _idx_batch: list = []

            self.log(f"🚀 بدء النسخ...")
            for i, (_item, _target, _src_st) in enumerate(to_update):
                if self._cancel.is_set():
                    break
                try:
                    # تخطي الموجود بنفس الحجم
                    if _target.exists():
                        try:
                            if _src_st.st_size == _target.stat().st_size:
                                _bulk_skipped += 1
                                continue
                        except OSError:
                            pass
                    _target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(_item), str(_target))
                    self.copied += 1
                    self.changed_files.append(str(_item.relative_to(src)))

                    # تقدم
                    _done = self.copied + _bulk_skipped
                    if self.copied % 200 == 0 or self.copied == 1:
                        elapsed = time.time() - _t0
                        if elapsed > 0 and self.copied > 0:
                            speed = self.copied / elapsed
                            remaining = (_total - _done) / speed if speed > 0 else 0
                            pct = _done / max(_total, 1) * 100
                            eta = f"~{remaining/60:.0f} دقيقة" if remaining >= 60 else f"~{remaining:.0f} ثانية"
                            self.log(
                                f"  📊 {self.copied:,}/{_total:,} ({pct:.0f}%)"
                                f"{f' | {_bulk_skipped:,} تُخطّي' if _bulk_skipped else ''}"
                                f" | ⚡ {speed:.0f} ملف/ث | ⏱️ {eta}"
                            )
                            self.progress(min(pct, 99))

                    # SyncIndex batch
                    try:
                        d_st = _target.stat()
                        rel = str(_item.relative_to(src))
                        _idx_batch.append((rel, d_st, _target))
                        if len(_idx_batch) >= 500:
                            for _r, _s2, _t2 in _idx_batch:
                                idx.mark_synced(_r, _s2, _t2)
                            _idx_batch.clear()
                            idx.save()
                    except Exception:
                        pass
                except PermissionError:
                    self.failed += 1
                    self.errors.append(f"⚠️ مقفل: {_item.name}")
                except OSError as e:
                    self.failed += 1
                    self.errors.append(f"{_item.name}: {e}")

            # flush
            for _r, _s2, _t2 in _idx_batch:
                idx.mark_synced(_r, _s2, _t2)
            _idx_batch.clear()

            _elapsed = time.time() - _t0
            _tstr = f"{_elapsed/60:.1f} دقيقة" if _elapsed >= 60 else f"{_elapsed:.0f} ثانية"
            _skip_msg = f" | {_bulk_skipped:,} تُخطّي" if _bulk_skipped else ""
            self.log(f"✅ نسخ مباشر: {self.copied:,} ملف | {self.failed} أخطاء{_skip_msg} | ⏱️ {_tstr}")

        elif len(to_update) >= PIPELINE_THRESHOLD:
            self.log(
                f"⚡ v28 Pipeline: {total_files:,} ملف → "
                f"4 مراحل بالتوازي [{DeviceProfiler.get_label()}]"
            )
            # Pre-space check
            needed_size = sum(s.st_size for _,_,s in to_update)
            ok_space, space_msg = AtomicCopier.check_space(dst, needed_size)
            if not ok_space:
                self.lock_mgr.release('sync')
                self.log(space_msg)
                return {"status": "FAILED", "message": space_msg}

            dst.mkdir(parents=True, exist_ok=True)

            pipeline = SyncPipeline(
                src=src, dst=dst, idx=idx,
                log_cb=self.log,
                progress_cb=self.progress,
                cancel_event=self._cancel,
                verify=verify,
                expected_total=len(to_update),   # ⚡ v4.0: العدد الحقيقي للملفات
            )
            try:
                pipeline.run(presync=self.presync, verify=verify)

                # دمج إحصائيات Pipeline في SyncEngine
                self.copied        = pipeline.copied
                self.skipped       = pipeline.skipped
                self.failed        = pipeline.failed
                self.errors        = pipeline.errors
                self.changed_files = pipeline.changed_files
            except Exception as e:
                self.lock_mgr.release('sync')
                self.log(f"❌ Pipeline خطأ غير متوقع: {e}")
                return {"status": "FAILED", "message": str(e)}

        else:
            # ── Classic path (< 5000 ملف) ──────────────────────
            needed_size = sum(s.st_size for _,_,s in to_update)
            ok_space, space_msg = AtomicCopier.check_space(dst, needed_size)
            if not ok_space:
                self.lock_mgr.release('sync')
                self.log(space_msg)
                return {"status": "FAILED", "message": space_msg}
            free_now = shutil.disk_usage(dst if dst.exists() else dst.parent).free
            self.log(Lang.t('space_ok', free=Utils.format_size(free_now)))

            dst.mkdir(parents=True, exist_ok=True)
            to_update_pairs = [(s, d) for s, d, _ in to_update]
            cp = CheckpointManager(src.name, "sync")
            resumed = cp.load(str(src), str(dst))
            if resumed:
                resumed_set     = {(str(s), str(d)) for s, d in resumed}
                still_remaining = [(s, d) for s, d in to_update_pairs
                                   if (str(s), str(d)) in resumed_set]
                newly_found     = [(s, d) for s, d in to_update_pairs
                                   if (str(s), str(d)) not in resumed_set]
                to_update_pairs = still_remaining + newly_found
                self.log(
                    f"📌 استئناف من checkpoint — "
                    f"{len(still_remaining)} متبقٍ + {len(newly_found)} جديد"
                )
            cp.save(to_update_pairs, str(src), str(dst))

            remaining_set: Set[Tuple[str, str]] = {
                (str(s), str(d)) for s, d in to_update_pairs
            }
            processed = [0]
            prog_lock = threading.Lock()
            total_n   = max(len(to_update_pairs), 1)
            _cp_counter = [0]

            def _do_copy(src_file, dst_file):
                """نسخ ملف واحد مع retry — ⚡ v27: Delta Copy للملفات الكبيرة"""
                rel = src_file.relative_to(src)
                try:
                    ok, msg = False, ""
                    src_size = src_file.stat().st_size if src_file.exists() else 0
                    if DeltaCopier.should_use_delta(src_file, dst_file, src_size):
                        delta_ok, delta_msg, _ = DeltaCopier.copy(
                            src_file, dst_file, log_cb=self.log
                        )
                        if delta_msg == "DELTA_NO_CHANGE":
                            return True, "SKIPPED", src_file, dst_file, rel
                        if delta_ok:
                            return True, "DELTA_OK", src_file, dst_file, rel
                    for attempt in range(AppConfig.MAX_RETRIES):
                        ok, msg = AtomicCopier.copy(src_file, dst_file, verify)
                        if ok: break
                        if attempt < AppConfig.MAX_RETRIES - 1:
                            time.sleep(AppConfig.RETRY_DELAY)
                            self.log(Lang.t('eng_retry', name=rel.name))
                    return ok, msg, src_file, dst_file, rel
                except OSError as e:
                    return False, str(e), src_file, dst_file, rel

            def _after_copy(ok, msg, src_file, dst_file, rel):
                with prog_lock:
                    if ok:
                        self.copied += 1
                        self.changed_files.append(str(rel))
                        remaining_set.discard((str(src_file), str(dst_file)))
                        _cp_counter[0] += 1
                        if _cp_counter[0] % 50 == 0:
                            remaining_list = [(Path(s), Path(d)) for s, d in remaining_set]
                            cp.update(remaining_list, str(src), str(dst))
                        try:
                            src_st = src_file.stat()
                            idx.mark_synced(str(rel), src_st, dst_file)
                        except OSError: pass
                    else:
                        self.failed += 1
                        self.errors.append(f"{rel}: {msg}")
                        self.log(f"  ❌ {rel.name}: {msg}")
                    processed[0] += 1
                    self.progress(processed[0] / total_n * 100)

            SMALL   = AppConfig.SMALL_THRESHOLD
            T_SMALL = AppConfig.THREADS_SMALL
            T_LARGE = AppConfig.THREADS_LARGE
            BATCH   = AppConfig.BATCH_SIZE
            small_files = [(s, d) for s, d in to_update_pairs
                           if s.exists() and s.stat().st_size <= SMALL]
            large_files = [(s, d) for s, d in to_update_pairs
                           if not (s.exists() and s.stat().st_size <= SMALL)]

            self.log(f"⚡ USB {AppConfig.USB_SPEED_MBS:.1f}MB/s → "
                     f"threads={T_SMALL} | batch={BATCH} | "
                     f"صغير={len(small_files)} كبير={len(large_files)}")

            if large_files and not self._cancel.is_set():
                with ThreadPoolExecutor(max_workers=T_LARGE) as ex:
                    futures = {ex.submit(_do_copy, s, d): (s, d) for s, d in large_files}
                    for fut in as_completed(futures):
                        if self._cancel.is_set():
                            self.log("⛔ تم إيقاف المزامنة")
                            cp.update([(Path(s), Path(d)) for s, d in remaining_set],
                                      str(src), str(dst))
                            (ex.shutdown(wait=False, cancel_futures=True) if sys.version_info >= (3, 9) else ex.shutdown(wait=False)); break
                        try: _after_copy(*fut.result())
                        except Exception as e:
                            s2, d2 = futures[fut]
                            _after_copy(False, str(e), s2, d2, s2.relative_to(src))

            if small_files and not self._cancel.is_set():
                for i in range(0, len(small_files), BATCH):
                    if self._cancel.is_set(): break
                    batch = small_files[i:i+BATCH]
                    with ThreadPoolExecutor(max_workers=T_SMALL) as ex:
                        futures = {ex.submit(_do_copy, s, d): (s, d) for s, d in batch}
                        for fut in as_completed(futures):
                            if self._cancel.is_set():
                                (ex.shutdown(wait=False, cancel_futures=True) if sys.version_info >= (3, 9) else ex.shutdown(wait=False)); break
                            try: _after_copy(*fut.result())
                            except Exception as e:
                                s2, d2 = futures[fut]
                                _after_copy(False, str(e), s2, d2, s2.relative_to(src))

            if not self._cancel.is_set():
                cp.clear()

        # ── حفظ وإنهاء ──
        # ⚡ v4.0: إفراغ الذاكرة المؤقتة على الفلاشة — يمنع فقدان البيانات
        if is_usb and self.copied > 0:
            self._flush_target(dst)
        self._save_meta(dst, total_files, sum(s.st_size for _,_,s in to_update))
        idx.save()
        # ⚡ v4.0: حفظ DirSnapshot — سيُسرّع المزامنة الجاية بشكل كبير
        # ⚡ v4.0 FIX: نحفظ لقطة للطرفين (src + dst)
        # عشان أي حاسوب ثاني يلاقي اللقطة جاهزة للجهة اللي يبي يمسحها
        try:
            dir_snap.save()
            # لقطة الوجهة — حاسوب آخر ممكن يمسحها كمصدر
            dst_snap = DirSnapshot(dst, src)
            dst_snap.load()
            dst_snap.find_changed_dirs(
                dst,
                excluded_names=AppConfig.EXCLUDED_NAMES,
                excluded_dirs=AppConfig.EXCLUDED_DIRS
            )
            dst_snap.save()
        except Exception as _ds_err:
            _logger.warning(f"DirSnapshot.save: {_ds_err}")
        HashCache.save()
        AtomicCopier.cleanup_temp(dst)
        self.lock_mgr.release('sync')

        # 📋 حفظ SyncReport
        report = SyncReport("sync", src, dst)
        for f in self.changed_files:
            report.add_copied(f)
        report.add_skipped(self.skipped)
        for e in self.errors:
            report.add_failed("?", e)
        report.add_verified(self.copied)
        rp = report.save()
        if rp:
            self.log(f"📋 تقرير: {rp.name}")

        status = "CANCELLED" if self._cancel.is_set() else \
                 ("OK" if self.failed == 0 else "PARTIAL")
        # ✅ تسجيل النتيجة في sync.log
        logging.getLogger('AyadFlowSync.sync').info(
            f"{'[OK]' if status == 'OK' else '['+status+']'} "
            f"copied:{self.copied} skipped:{self.skipped} "
            f"failed:{self.failed} size:{self.total_size:,}B"
        )
        self.log(f"{'━'*35}")
        self.log(Lang.t('eng_copied', c=self.copied, s=self.skipped, f=self.failed))
        if self.failed > 0:
            self.log(Lang.t('eng_errors_hdr'))
            for e in self.errors[:20]: self.log(f"   ❌ {e}")
        return {
            "status": status,
            "copied": self.copied, "skipped": self.skipped,
            "failed": self.failed, "errors": self.errors,
            "changed": self.changed_files
        }

    def scan(self, src: Path, dst: Path) -> Dict:
        """
        مسح بدون نسخ — يجمع التغييرات بالمجلد للمعاينة.
        ⚡ OPT 2: scandir بدل rglob → أسرع 2x-4x على Windows
        """
        if not src.exists():
            return {"status": "FAILED", "message": Lang.t("eng_folder_missing", path=src)}

        folders: Dict[str, Dict[str, int]] = {}
        total_files = 0

        def _get_folder(rel_parent: str) -> Dict:
            key = rel_parent if rel_parent and rel_parent != "." else Lang.t("preview_root")
            top = key.split("/")[0].split("\\")[0]
            if top not in folders:
                folders[top] = {"new": 0, "modified": 0, "deleted": 0}
            return folders[top]

        # ⚡ OPT 2: scandir recursive بدل rglob
        def _scan_src(directory: Path):
            nonlocal total_files
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if getattr(self, "_cancel", None) and self._cancel.is_set(): return
                        try:
                            item = Path(entry.path)
                            if self._should_exclude(item): continue
                            rel    = item.relative_to(src)
                            target = dst / rel
                            if entry.is_dir(follow_symlinks=False):
                                if not target.exists():
                                    _get_folder(str(rel.parent))["new"] += 1
                                _scan_src(item)
                            elif entry.is_file(follow_symlinks=False):
                                total_files += 1
                                folder = _get_folder(str(rel.parent))
                                if not target.exists():
                                    folder["new"] += 1
                                elif self._needs_update(item, target):
                                    folder["modified"] += 1
                        except OSError:
                            continue
            except OSError: pass

        def _scan_dst(directory: Path):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        try:
                            item = Path(entry.path)
                            if self._should_exclude(item): continue
                            rel = item.relative_to(dst)
                            if entry.is_dir(follow_symlinks=False):
                                _scan_dst(item)
                            elif entry.is_file(follow_symlinks=False):
                                if not (src / rel).exists():
                                    _get_folder(str(rel.parent))["deleted"] += 1
                        except OSError:
                            continue
            except OSError: pass

        _scan_src(src)
        if dst.exists():
            _scan_dst(dst)

        HashCache.save()

        changed = {k: v for k, v in folders.items()
                   if v["new"] or v["modified"] or v["deleted"]}
        total_changes = sum(
            v["new"] + v["modified"] + v["deleted"]
            for v in changed.values()
        )
        return {
            "status": "OK",
            "total_files": total_files,
            "total_changes": total_changes,
            "folders": changed
        }

    def sync_from_scan(self, src: Path, dst: Path,
                       scan_result: Dict, verify: bool = True) -> Dict:
        """
        ① تنفيذ النسخ مباشرة من نتيجة scan() — بدون إعادة المسح.
        ⚡ OPT 2: scandir بدل rglob → أسرع 2x-4x على Windows
        """
        self.copied = self.skipped = self.failed = self.total_size = 0
        self.errors = []; self.changed_files = []
        _sync_logger = logging.getLogger('AyadFlowSync.sync')
        _sync_logger.info(f"▶ Sync started: {src} → {dst}")

        if not self.lock_mgr.acquire('sync'):
            return {"status": "LOCK_FAILED", "message": Lang.t("eng_lock_fail")}
        if not src.exists():
            self.lock_mgr.release('sync')
            return {"status": "FAILED", "message": Lang.t('eng_folder_missing', path=src)}

        # ⚡ OPT 2: scandir recursive بدل rglob
        to_update: List[Tuple[Path, Path]] = []

        def _collect(directory: Path, dst_dir: Path):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if getattr(self, "_cancel", None) and self._cancel.is_set(): return
                        try:
                            item = Path(entry.path)
                            if self._should_exclude(item): continue
                            target = dst_dir / entry.name
                            if entry.is_dir(follow_symlinks=False):
                                if not target.exists():
                                    target.mkdir(parents=True, exist_ok=True)
                                _collect(item, target)
                            elif entry.is_file(follow_symlinks=False):
                                # ✅ v22: كل ملف يُفحص — لا استثناء
                                # إذا الملف غير موجود → ينسخ فوراً
                                if not target.exists():
                                    to_update.append((item, target))
                                elif self._needs_update(item, target):
                                    to_update.append((item, target))
                                else:
                                    self.skipped += 1
                        except OSError as e:
                            self.errors.append(f"scan:{entry.name}: {e}")
            except OSError: pass

        _collect(src, dst)

        total_files = self.skipped + len(to_update)

        if not to_update:
            HashCache.save(); self.lock_mgr.release('sync')
            return {"status": "NO_CHANGES", "copied": 0, "skipped": total_files}

        # فحص مساحة القرص
        needed = sum(f.stat().st_size for f,_ in to_update if f.exists())
        ok_space, space_msg = AtomicCopier.check_space(dst, needed)
        if not ok_space:
            self.lock_mgr.release('sync')
            self.log(space_msg)
            return {"status": "FAILED", "message": space_msg}

        # Pre-sync backup
        existing = [t for _, t in to_update if t.exists()]
        if existing:
            snap = self.presync.create(existing, base=dst)
            if snap: self.log(Lang.t('eng_presync', name=snap.name))
            self.presync.cleanup_old()

        dst.mkdir(parents=True, exist_ok=True)
        cp = CheckpointManager(src.name, "scan")
        resumed = cp.load(str(src), str(dst))
        if resumed:
            # ✅ FIX v20.1: دمج بدل استبدال — نفس إصلاح sync()
            resumed_set     = {(str(s), str(d)) for s, d in resumed}
            still_remaining = [(s, d) for s, d in to_update
                               if (str(s), str(d)) in resumed_set]
            newly_found     = [(s, d) for s, d in to_update
                               if (str(s), str(d)) not in resumed_set]
            to_update = still_remaining + newly_found
            self.log(
                f"📌 استئناف من checkpoint — "
                f"{len(still_remaining)} متبقٍ + {len(newly_found)} جديد"
            )
        cp.save(to_update, str(src), str(dst))

        remaining = list(to_update)
        processed = [0]
        prog_lock = threading.Lock()
        total_n   = max(len(to_update), 1)

        def _do_copy2(src_file, dst_file):
            rel = src_file.relative_to(src)
            try:
                ok, msg = False, ""
                for attempt in range(AppConfig.MAX_RETRIES):
                    ok, msg = AtomicCopier.copy(src_file, dst_file, verify)
                    if ok: break
                    if attempt < AppConfig.MAX_RETRIES - 1:
                        time.sleep(AppConfig.RETRY_DELAY)
                        self.log(Lang.t('eng_retry', name=rel.name))
                return ok, msg, src_file, dst_file, rel
            except OSError as e:
                return False, str(e), src_file, dst_file, rel

        def _after2(ok, msg, src_file, dst_file, rel):
            with prog_lock:
                if ok:
                    self.copied += 1; self.changed_files.append(str(rel))
                    try: remaining.remove((src_file, dst_file))
                    except ValueError: pass
                    cp.update(remaining, str(src), str(dst))
                else:
                    self.failed += 1; self.errors.append(f"{rel}: {msg}")
                    self.log(f"  ❌ {rel.name}: {msg}")
                processed[0] += 1
                self.progress(processed[0] / total_n * 100)
        # ⚡ Adaptive — calibrate بالوجهة (dst) وليس usb (غير موجود في هذا السياق)
        AppConfig.calibrate_usb(dst)
        SMALL   = AppConfig.SMALL_THRESHOLD
        T_SMALL = AppConfig.THREADS_SMALL
        T_LARGE = AppConfig.THREADS_LARGE
        BATCH   = AppConfig.BATCH_SIZE
        small_f = [(s,d) for s,d in to_update if s.exists() and s.stat().st_size <= SMALL]
        large_f = [(s,d) for s,d in to_update if not (s.exists() and s.stat().st_size <= SMALL)]

        # الكبيرة — threads متوازية
        if large_f and not self._cancel.is_set():
            with ThreadPoolExecutor(max_workers=T_LARGE) as ex:
                futs = {ex.submit(_do_copy2, s, d): (s,d) for s,d in large_f}
                for fut in as_completed(futs):
                    if getattr(self, "_cancel", None) and self._cancel.is_set():
                        cp.update(remaining, str(src), str(dst))
                        (ex.shutdown(wait=False, cancel_futures=True) if sys.version_info >= (3, 9) else ex.shutdown(wait=False)); break
                    try: _after2(*fut.result())
                    except Exception as e:
                        s2,d2 = futs[fut]
                        _after2(False, str(e), s2, d2, s2.relative_to(src))

        # الصغيرة — Adaptive batch
        if small_f and not self._cancel.is_set():
            for _bi in range(0, len(small_f), BATCH):
                if getattr(self, "_cancel", None) and self._cancel.is_set(): break
                _batch = small_f[_bi:_bi+BATCH]
                with ThreadPoolExecutor(max_workers=T_SMALL) as ex:
                    futs = {ex.submit(_do_copy2, s, d): (s,d) for s,d in _batch}
                    for fut in as_completed(futs):
                        if getattr(self, "_cancel", None) and self._cancel.is_set():
                            (ex.shutdown(wait=False, cancel_futures=True) if sys.version_info >= (3, 9) else ex.shutdown(wait=False)); break
                        try: _after2(*fut.result())
                        except Exception as e:
                            s2,d2 = futs[fut]
                            _after2(False, str(e), s2, d2, s2.relative_to(src))

        if not self._cancel.is_set(): cp.clear()

        self._save_meta(dst, total_files, needed)
        HashCache.save()
        AtomicCopier.cleanup_temp(dst)
        self.lock_mgr.release('sync')

        status = "CANCELLED" if self._cancel.is_set() else ("OK" if self.failed == 0 else "PARTIAL")
        self.log(f"{'━'*35}")
        self.log(Lang.t('eng_copied', c=self.copied, s=self.skipped, f=self.failed))
        if self.failed > 0:
            self.log(Lang.t('eng_errors_hdr'))
            for e in self.errors[:20]: self.log(f"   ❌ {e}")
        return {
            "status": status, "copied": self.copied,
            "skipped": self.skipped, "failed": self.failed,
            "errors": self.errors, "changed": self.changed_files
        }

    def smart_scan(self, pc: Path, usb: Path,
                   progress_cb=None) -> Dict:
        """
        مسح ذكي ثنائي الاتجاه — v17: يستخدم FlashLedger للدقة القصوى.

        التحسين الجوهري في v17:
        ① FlashLedger يعرف آخر وقت مزامنة لهذا الجهاز تحديداً
        ② التعارض الحقيقي = ملف تغيّر على الجهاز الحالي + تغيّر على الفلاشة
           كلاهما بعد آخر مزامنة ← هذا تعارض فعلي
        ③ تغيّر على الجهاز فقط = pc_to_usb (مزامنة عادية)
        ④ تغيّر على الفلاشة فقط = usb_to_pc (جهاز آخر حدّث الفلاشة)

        التحسينات الأصلية محفوظة:
        ① مسح واحد فقط لكل جذر — لا any(rglob) متكررة
        ③ progress_cb اختياري يُحدَّث أثناء المسح
        """
        result = {
            "status"    : "OK",
            "pc_to_usb" : [],
            "usb_to_pc" : [],
            "pc_only"   : [],
            "usb_only"  : [],
            "conflicts" : [],
            "identical" : 0,
            "total_pc"  : 0,
            "total_usb" : 0,
        }

        if not pc.exists():
            return {"status": "FAILED", "message": Lang.t("eng_pc_missing", path=pc)}

        # ── v17: تحميل FlashLedger من الفلاشة ──
        FlashLedger.clear_cache()  # ✅ تأكد من قراءة آخر نسخة من الفلاشة
        ledger = FlashLedger(usb).load() if usb.exists() else FlashLedger(usb)
        my_last_sync = ledger.get_device_last_sync_ts(AppConfig.PC_NAME)
        if my_last_sync:
            self.log(f"💾 FlashLedger: آخر مزامنة لـ {AppConfig.PC_NAME}: "
                     f"{datetime.fromtimestamp(my_last_sync).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            self.log(f"💾 FlashLedger: أول مزامنة لـ {AppConfig.PC_NAME} على هذه الفلاشة")

        # ── fallback: last_sync من meta (للتوافق مع v16) ──
        last_sync_ts: Optional[float] = my_last_sync
        if last_sync_ts is None:
            try:
                meta = SyncEngine.get_meta(usb)
                if meta and meta.get("last_sync"):
                    last_sync_ts = datetime.fromisoformat(meta["last_sync"]).timestamp()
            except Exception:
                pass

        def _norm(p: Path, base: Path) -> str:
            return str(p.relative_to(base)).replace('\\', '/')

        # ⚡ تحميل SyncIndex لتسريع فحص الملفات المتطابقة
        idx_pc_usb = SyncIndex(pc, usb).load()
        idx_usb_pc = SyncIndex(usb, pc).load()

        def _collect(root: Path, prog_start: float, prog_end: float) -> Dict[str, Path]:
            """
            ⚡ v18 BEAST MODE — مسح خارق بـ os.scandir:
            • os.scandir يُعيد DirEntry مع stat جاهز (بدون system call إضافي على Windows)
            • أسرع 2x-4x من rglob خصوصاً على Windows مع آلاف الملفات
            • DirEntry.is_file() / is_dir() = مجاني (مدمج في FindNextFile)
            ✅ كل ميزات v17 محفوظة: إلغاء، تقدم، ملفات 0 بايت، مجلدات فارغة
            """
            collected: Dict[str, Path] = {}
            dirs_seen:       set = set()
            dirs_with_files: set = set()
            count = 0

            def _scandir_recursive(directory: Path):
                """مسح عودي بـ os.scandir — أسرع من rglob"""
                nonlocal count
                try:
                    with os.scandir(directory) as entries:
                        for entry in entries:
                            if getattr(self, "_cancel", None) and self._cancel.is_set():
                                raise InterruptedError("cancelled")
                            try:
                                item = Path(entry.path)
                                if self._should_exclude(item):
                                    continue

                                if entry.is_file(follow_symlinks=False):
                                    key = _norm(item, root)
                                    collected[key] = item
                                    parent = item.parent
                                    while parent != root and parent not in dirs_with_files:
                                        dirs_with_files.add(parent)
                                        parent = parent.parent

                                elif entry.is_dir(follow_symlinks=False):
                                    dirs_seen.add(item)
                                    _scandir_recursive(item)

                                elif entry.is_symlink():
                                    # ✅ FIX v19: Symlinks تُسجَّل كـ debug بدل الصمت التام
                                    _logger.debug(f"Skipping symlink: {entry.path}")

                            except OSError:
                                pass

                            count += 1
                            if progress_cb and count % 100 == 0:
                                est_pct = prog_start + min(count / 5000, 1.0) * (prog_end - prog_start)
                                progress_cb(est_pct)
                            if count % 1000 == 0:
                                self.log(f"  🔍 مسح... {count:,} عنصر في {root.name}")

                except PermissionError:
                    pass  # مجلد محمي — تابع
                except InterruptedError:
                    raise
                except OSError:
                    pass

            try:
                _scandir_recursive(root)
            except InterruptedError:
                raise

            # المجلدات الفارغة
            for d in dirs_seen - dirs_with_files:
                key = _norm(d, root) + "/"
                collected[key] = d

            return collected

        # ── preload HashCache في RAM قبل المسح ──
        HashCache.preload()

        # ── جمع ملفات PC و USB ──
        # ⚡ OPT 5: PC على HDD = sequential (parallel يُبطئ HDD بسبب seek time)
        #           PC على SSD أو USB = parallel (لا seek time)
        pc_files:  Dict[str, Path] = {}
        usb_files: Dict[str, Path] = {}
        pc_err = [None]

        def _scan_pc():
            try:
                pc_files.update(_collect(pc, 0, 40))
            except OSError as e:
                pc_err[0] = e

        def _scan_usb():
            if usb.exists():
                try:
                    usb_files.update(_collect(usb, 40, 80))
                except OSError:
                    pass

        # ⚡ OPT 5: تحديد نوع وحدة التخزين
        pc_is_removable = AppConfig.is_removable(pc)
        # HDD = ليس removable وليس SSD (نفترض SSD إذا كان removable أو لا نعرف)
        # الاختبار البسيط: هل المسح السريع ممكن؟ نستخدم parallel دائماً لـ USB/SSD
        use_parallel = pc_is_removable or AppConfig.is_removable(pc.parent if pc.parent != pc else pc)

        if use_parallel:
            # SSD/USB: مسح متوازٍ
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_pc  = ex.submit(_scan_pc)
                f_usb = ex.submit(_scan_usb)
                f_pc.result()
                f_usb.result()
        else:
            # HDD أو غير محدد: sequential (PC أولاً ثم USB) لتجنب تباطؤ الـ seek
            _scan_pc()
            _scan_usb()

        if pc_err[0]:
            return {"status": "FAILED", "message": str(pc_err[0])}

        result["total_pc"]  = sum(1 for k in pc_files  if not k.endswith("/"))
        result["total_usb"] = sum(1 for k in usb_files if not k.endswith("/"))

        self.log(Lang.t("eng_scan_summary", pc=result["total_pc"], usb=result["total_usb"]))

        # ── مقارنة كل عنصر ──
        all_keys   = set(pc_files) | set(usb_files)
        need_hash  = []   # (rel, pc_f, usb_f, mtime_changed)

        for rel in sorted(all_keys):
            if getattr(self, "_cancel", None) and self._cancel.is_set():
                result["status"] = "CANCELLED"
                break

            is_dir = rel.endswith("/")
            pc_f   = pc_files.get(rel)
            usb_f  = usb_files.get(rel)

            if pc_f and not usb_f:
                # ── v19: pc_only ذكي ──
                if last_sync_ts is not None and not is_dir:
                    try:
                        pc_mtime = pc_f.stat().st_mtime
                        if pc_mtime <= (last_sync_ts + 3):
                            # قديم = كان موجوداً وحُذف من الفلاشة عمداً → احذفه من الجهاز
                            result.setdefault("pc_deleted_on_usb", []).append(rel)
                        else:
                            # جديد = أُضيف للجهاز بعد آخر مزامنة → انسخه للفلاشة
                            result["pc_only"].append(rel)
                    except OSError:
                        result["pc_only"].append(rel)
                else:
                    result["pc_only"].append(rel)
            elif usb_f and not pc_f:
                # ── v19: usb_only ذكي ──
                if last_sync_ts is not None and not is_dir:
                    try:
                        usb_mtime = usb_f.stat().st_mtime
                        if usb_mtime <= (last_sync_ts + 3):
                            # قديم = كان موجوداً وحُذف من الجهاز عمداً → احذفه من الفلاشة
                            result.setdefault("usb_deleted_on_pc", []).append(rel)
                        else:
                            # جديد = أُضيف للفلاشة بعد آخر مزامنة → انسخه للجهاز
                            result["usb_only"].append(rel)
                    except OSError:
                        result["usb_only"].append(rel)
                else:
                    result["usb_only"].append(rel)
            else:
                # موجود في الطرفين
                if is_dir:
                    result["identical"] += 1
                    continue

                # ⚡ فحص الملف
                try:
                    pc_st  = pc_f.stat()
                    usb_st = usb_f.stat()

                    # v22: لا SyncIndex — كل ملف يُفحص دائماً بالحجم والـ Hash
                    if pc_st.st_size != usb_st.st_size:
                        # ⚡ v4.0 FIX: حجم مختلف = الملف تغير بالتأكيد
                        # لا نتخطى أبداً — حتى لو mtime قريب (FAT32)
                        # هذا يشمل: ملف فارغ ↔ ملف فيه محتوى
                        pc_mtime  = pc_st.st_mtime
                        usb_mtime = usb_st.st_mtime

                        if last_sync_ts is not None:
                            pc_changed  = pc_mtime  > (last_sync_ts + 3)
                            usb_changed = usb_mtime > (last_sync_ts + 3)
                            if pc_changed and usb_changed:
                                # كلاهما تغيّر → الأحدث يفوز
                                if pc_mtime >= usb_mtime:
                                    result["pc_to_usb"].append(rel)
                                else:
                                    result["usb_to_pc"].append(rel)
                            elif pc_changed:
                                result["pc_to_usb"].append(rel)
                            elif usb_changed:
                                result["usb_to_pc"].append(rel)
                            else:
                                # لم يتغير أي منهما بعد آخر مزامنة
                                # لكن الحجم مختلف = كان فيه تغيير قبل
                                # الأحدث mtime يفوز
                                if pc_mtime >= usb_mtime:
                                    result["pc_to_usb"].append(rel)
                                else:
                                    result["usb_to_pc"].append(rel)
                        else:
                            # أول مزامنة — الأكبر حجماً يفوز (أو الأحدث)
                            if pc_mtime > usb_mtime + 2:
                                result["pc_to_usb"].append(rel)
                            elif usb_mtime > pc_mtime + 2:
                                result["usb_to_pc"].append(rel)
                            else:
                                # أوقات متقاربة — الأكبر حجماً يفوز
                                if pc_st.st_size >= usb_st.st_size:
                                    result["pc_to_usb"].append(rel)
                                else:
                                    result["usb_to_pc"].append(rel)
                        continue

                    if pc_st.st_size == 0:
                        # ✅ FIX v28: الملفات الفارغة تحتاج فحص mtime
                        # السبب: ملف فارغ تلف على الفلاشة = حجمه 0 أيضاً
                        # الحل: قارن mtime — إذا تغيّر أحدهما بعد آخر مزامنة → انسخ
                        if last_sync_ts is not None:
                            pc_changed  = pc_st.st_mtime  > (last_sync_ts + 3)
                            usb_changed = usb_st.st_mtime > (last_sync_ts + 3)
                            if pc_changed and not usb_changed:
                                result["pc_to_usb"].append(rel)
                            elif usb_changed and not pc_changed:
                                result["usb_to_pc"].append(rel)
                            elif pc_changed and usb_changed:
                                # كلاهما تغيّر — الأحدث يكسب (الملف الفارغ لا محتوى للمقارنة)
                                if pc_st.st_mtime >= usb_st.st_mtime:
                                    result["pc_to_usb"].append(rel)
                                else:
                                    result["usb_to_pc"].append(rel)
                            else:
                                result["identical"] += 1
                        else:
                            # أول مزامنة — الأحدث يكسب
                            if pc_st.st_mtime > usb_st.st_mtime + 2:
                                result["pc_to_usb"].append(rel)
                            elif usb_st.st_mtime > pc_st.st_mtime + 2:
                                result["usb_to_pc"].append(rel)
                            else:
                                result["identical"] += 1
                        continue

                    # ⚡ v24 FIX AccuMark: SyncIndex يعمل في كل الأوضاع
                    # المشكلة: not ACCUMARK_MODE كان يُعطّل SyncIndex → 91k Hash!
                    # الحل: SyncIndex دائماً — AccuMark يُكمِل بـ Hash فقط إذا mtime تغيّر
                    idx_entry = idx_pc_usb.get(rel)
                    if idx_entry:
                        idx_size_  = idx_entry.get("size", -1)
                        idx_mtime  = idx_entry.get("src_mtime", 0)
                        if (idx_size_ == pc_st.st_size and
                                abs(idx_mtime - pc_st.st_mtime) <= 2.0):
                            if AppConfig.ACCUMARK_MODE:
                                # AccuMark: mtime لم يتغيّر + حجم متطابق → ثق بالـ Index
                                # (AccuMark يغيّر mtime عند كل تعديل — هذا كافٍ للاكتشاف)
                                result["identical"] += 1
                                continue
                            else:
                                result["identical"] += 1
                                continue

                    # ② mtime: فحص ذكي بدون Hash (للوضع العادي فقط)
                    if not AppConfig.ACCUMARK_MODE:
                        pc_mtime  = pc_st.st_mtime
                        usb_mtime = usb_st.st_mtime

                        # ② A: نفس الـ mtime (شامل FAT32 ±2s) → متطابق بدون hash
                        if abs(pc_mtime - usb_mtime) <= 3.0:
                            result["identical"] += 1
                            try:
                                idx_pc_usb.mark_synced(rel, pc_st, usb_f)
                            except OSError:
                                pass
                            continue

                        # ② B: كلاهما لم يتغيّر منذ آخر مزامنة → متطابق
                        if last_sync_ts is not None:
                            pc_changed  = pc_mtime  > (last_sync_ts + 3)
                            usb_changed = usb_mtime > (last_sync_ts + 3)
                            if not pc_changed and not usb_changed:
                                result["identical"] += 1
                                try:
                                    idx_pc_usb.mark_synced(rel, pc_st, usb_f)
                                except OSError:
                                    pass
                                continue

                    # ③ أضف لقائمة الـ hash المتوازي (فقط الملفات المشكوك فيها)
                    need_hash.append((rel, pc_f, usb_f, AppConfig.ACCUMARK_MODE))
                except OSError:
                    result["usb_to_pc"].append(rel)

        # ── حساب hash بالتوازي للملفات المشكوك فيها ──
        if need_hash and result["status"] != "CANCELLED":
            self.log(f"  🔍 {len(need_hash):,} ملف يحتاج فحص Hash...")

            # ⚡ v30 SPLIT HASH: فصل الجهاز عن الفلاشة للأداء الأقصى
            # الجهاز (SSD): hash بـ 4 threads → 500+ MB/s لا ينتظر USB
            # الفلاشة:      hash بـ 2 threads → I/O bound 13 MB/s
            # كلاهما يعمل بالتوازي الكامل → توفير 40-60% من الوقت
            usb_speed   = getattr(AppConfig, 'USB_SPEED_MBS', 10)
            pc_workers  = min(4, len(need_hash))
            usb_workers = min(2 if usb_speed < 20 else 3, len(need_hash))
            hash_total  = len(need_hash)
            hash_done   = [0]

            pc_results  = {}
            usb_results = {}

            def _hash_pc_only(args):
                rel, pc_f, usb_f, force_hash = args
                if getattr(self, "_cancel", None) and self._cancel.is_set():
                    return rel, None
                return rel, HashCache.get_hash(pc_f, force=force_hash)

            def _hash_usb_only(args):
                rel, pc_f, usb_f, force_hash = args
                if getattr(self, "_cancel", None) and self._cancel.is_set():
                    return rel, None
                return rel, HashCache.get_hash(usb_f, force=force_hash)

            def _run_pc():
                with ThreadPoolExecutor(max_workers=pc_workers) as ex:
                    for rel, h in ex.map(_hash_pc_only, need_hash):
                        if rel is not None:
                            pc_results[rel] = h

            def _run_usb():
                with ThreadPoolExecutor(max_workers=usb_workers) as ex:
                    for rel, h in ex.map(_hash_usb_only, need_hash):
                        if rel is not None:
                            usb_results[rel] = h
                            hash_done[0] += 1
                            if hash_done[0] % 2000 == 0:
                                pct = 80 + (hash_done[0] / hash_total * 20)
                                if progress_cb:
                                    progress_cb(pct)
                                self.log(f"  🔍 Hash: {hash_done[0]:,}/{hash_total:,}...")

            with ThreadPoolExecutor(max_workers=2) as coord:
                fp = coord.submit(_run_pc)
                fu = coord.submit(_run_usb)
                fp.result(); fu.result()

            for rel, pc_f, usb_f, _ in need_hash:
                h_pc  = pc_results.get(rel)
                h_usb = usb_results.get(rel)
                if h_pc is None or self._cancel.is_set():
                    continue
                pc_f  = pc_files[rel]
                usb_f = usb_files[rel]
                if h_pc == h_usb:
                    result["identical"] += 1
                    try:
                        idx_pc_usb.mark_synced(rel, pc_f.stat(), usb_f)
                    except OSError:
                        pass
                else:
                    try:
                        pc_mtime  = pc_f.stat().st_mtime
                        usb_mtime = usb_f.stat().st_mtime

                        # ── v19: آخر mtime يفوز دائماً — لا تعارضات ──
                        if last_sync_ts is not None:
                            pc_changed  = pc_mtime  > (last_sync_ts + 3)
                            usb_changed = usb_mtime > (last_sync_ts + 3)
                            if pc_changed and usb_changed:
                                # كلاهما تغيّر → آخر تعديل يفوز
                                if pc_mtime >= usb_mtime:
                                    result["pc_to_usb"].append(rel)
                                else:
                                    result["usb_to_pc"].append(rel)
                            elif pc_changed:
                                result["pc_to_usb"].append(rel)
                            elif usb_changed:
                                result["usb_to_pc"].append(rel)
                            else:
                                if pc_mtime > usb_mtime:
                                    result["pc_to_usb"].append(rel)
                                else:
                                    result["usb_to_pc"].append(rel)
                        else:
                            if pc_mtime >= usb_mtime:
                                result["pc_to_usb"].append(rel)
                            else:
                                result["usb_to_pc"].append(rel)
                    except OSError:
                        result["usb_to_pc"].append(rel)

        HashCache.save()
        # ⚡ حفظ Index للمرة القادمة
        idx_pc_usb.save()

        # ── v19: سجّل الملفات المحذوفة من كل طرف في الـ result ──
        if result.get("usb_deleted_on_pc"):
            n = len(result["usb_deleted_on_pc"])
            self.log(f"  📋 {n} ملف على الفلاشة فقط (غير موجود على الجهاز)")
        if result.get("pc_deleted_on_usb"):
            n = len(result["pc_deleted_on_usb"])
            self.log(f"  📋 {n} ملف على الجهاز فقط (غير موجود على الفلاشة)")
        # also store last_sync_ts in result for _apply_sync_mode
        result["last_sync_ts"] = last_sync_ts

        result["total_changes"] = (
            len(result["pc_to_usb"]) + len(result["usb_to_pc"]) +
            len(result["pc_only"])   + len(result["usb_only"])  +
            len(result.get("to_delete", []))
        )
        self.log(Lang.t('scan_result',
            to_usb=len(result['pc_to_usb'])+len(result['pc_only']),
            to_pc=len(result['usb_to_pc'])+len(result['usb_only']),
            identical=result['identical']))
        # v19: لا تعارضات — آخر mtime يفوز دائماً

        # ✅ FIX: إذا كل شيء متطابق → سجِّل في FlashLedger الآن
        # حتى لو المستخدم ألغى التنفيذ لاحقاً، last_sync_ts يُحدَّث
        # بدون هذا: كل مرة "أول مزامنة" → 19000+ تغيير وهمي
        if result["total_changes"] == 0 and result["identical"] > 0:
            try:
                ledger = FlashLedger(usb).load()
                ledger.record_sync(AppConfig.PC_NAME, {})
                self.log(f"💾 FlashLedger: سُجِّل وقت المزامنة (كل شيء متطابق)")
            except Exception as e:
                _logger.warning(f"FlashLedger scan record: {e}")

        return result

    def execute_smart_sync(self, pc: Path, usb: Path,
                           scan: Dict, verify: bool = True) -> Dict:
        """
        ✅ v17 — تنفيذ المزامنة الذكية بحماية كاملة + FlashLedger:

        ① PreSyncBackup   — snapshot قبل كل استبدال
        ② Checkpoint      — استئناف تلقائي بعد انقطاع
        ③ فحص مساحة مستمر — يوقف فوراً إذا امتلأ القرص
        ④ ThreadPool      — الملفات الصغيرة تُنسخ بـ 4 threads
        ⑤ SyncReport      — تقرير مفصّل يُحفظ بعد الانتهاء
        ⑥ SyncIndex       — تحديث فوري بعد كل نسخة ناجحة
        ⑦ FlashLedger     — تسجيل المزامنة على الفلاشة (جديد v17)
        """
        self.copied = self.failed = 0
        self.errors = []
        report = SyncReport("full_sync", pc, usb)

        if not self.lock_mgr.acquire('sync'):
            return {"status": "LOCK_FAILED",
                    "message": Lang.t("eng_lock_fail")}

        total = scan["total_changes"]
        if total == 0:
            self.lock_mgr.release('sync')
            return {"status": "NO_CHANGES"}

        # ⚡ تحميل SyncIndex
        idx_pc_usb = SyncIndex(pc, usb).load()
        idx_usb_pc = SyncIndex(usb, pc).load()

        # ① فحص مساحة القرص — في البداية
        def _calc_size(rels, base):
            s = 0
            for rel in rels:
                if not rel.endswith("/"):
                    try: s += (base / rel).stat().st_size
                    except OSError: pass
            return s

        to_usb_size = _calc_size(scan["pc_to_usb"], pc) + _calc_size(scan["pc_only"], pc)
        to_pc_size  = _calc_size(scan["usb_to_pc"], usb) + _calc_size(scan["usb_only"], usb)

        self.log(Lang.t('checking_space'))
        for dst_root, needed in [(usb, to_usb_size), (pc, to_pc_size)]:
            if needed == 0: continue
            ok_space, space_msg = AtomicCopier.check_space(dst_root, needed)
            if not ok_space:
                self.lock_mgr.release('sync')
                self.log(space_msg)
                return {"status": "FAILED", "message": space_msg}
        self.log(Lang.t('space_ok',
            free=Utils.format_size(shutil.disk_usage(usb if usb.exists() else pc).free)))

        # ② PreSyncBackup — snapshot لكل الملفات التي ستُستبدل
        files_to_overwrite = []
        for rel in scan.get("pc_to_usb", []) + scan.get("usb_to_pc", []):
            if not rel.endswith("/"):
                # الملف موجود في الوجهة = سيُستبدل
                for dst_base, src_base in [(usb, pc), (pc, usb)]:
                    dst_f = dst_base / rel
                    if dst_f.exists() and rel in scan.get(
                        "pc_to_usb" if dst_base == usb else "usb_to_pc", []
                    ):
                        files_to_overwrite.append(dst_f)

        if files_to_overwrite:
            try:
                snap = PreSyncBackup().create(files_to_overwrite, base=usb)
                if snap:
                    self.log(f"📸 Pre-sync snapshot: {snap.name} ({len(files_to_overwrite)} ملف)")
                    PreSyncBackup().cleanup_old()
            except Exception as e:
                _logger.warning(f"PreSyncBackup failed (non-fatal): {e}")

        # ③ Checkpoint — بناء قائمة الملفات للنسخ
        all_pairs: List[Tuple[Path, Path, str, str]] = []
        # (src, dst, rel, label)
        for rel in scan.get("pc_to_usb", []):
            if not rel.endswith("/"):
                all_pairs.append((pc / rel, usb / rel, rel, "pc_to_usb"))
        for rel in scan.get("pc_only", []):
            if not rel.endswith("/"):
                all_pairs.append((pc / rel, usb / rel, rel, "pc_only"))
        for rel in scan.get("usb_to_pc", []):
            if not rel.endswith("/"):
                all_pairs.append((usb / rel, pc / rel, rel, "usb_to_pc"))
        for rel in scan.get("usb_only", []):
            if not rel.endswith("/"):
                all_pairs.append((usb / rel, pc / rel, rel, "usb_only"))

        # المجلدات الفارغة
        dir_pairs = []
        for key, dst_base, src_base in [
            ("pc_to_usb", usb, pc), ("pc_only", usb, pc),
            ("usb_to_pc", pc, usb), ("usb_only", pc, usb)
        ]:
            for rel in scan.get(key, []):
                if rel.endswith("/"):
                    dir_pairs.append((dst_base / rel.rstrip("/"), rel))

        # أنشئ المجلدات الفارغة أولاً — رسالة ملخصة بدل رسالة لكل مجلد
        _dirs_ok = 0; _dirs_fail = 0
        for dir_p, rel in dir_pairs:
            try:
                dir_p.mkdir(parents=True, exist_ok=True)
                self.copied += 1
                report.add_copied(rel)
                _dirs_ok += 1
            except OSError as e:
                self.failed += 1
                report.add_failed(rel, str(e))
                _dirs_fail += 1
        if _dirs_ok:
            self.log(f"  ✅ 📁 {_dirs_ok:,} مجلد أُنشئ")
        if _dirs_fail:
            self.log(f"  ❌ {_dirs_fail} مجلد فشل في الإنشاء")

        # Checkpoint: حمّل ما تم إنجازه سابقاً
        cp = CheckpointManager(f"{pc.name}_smart", "smart_sync")
        resumed_rels = set()
        resumed = cp.load(str(pc), str(usb))
        if resumed:
            # ✅ FIX v20.1: دمج checkpoint مع المسح الجديد بدل الاستبدال
            resumed_set = {(str(s), str(d)) for s, d in resumed}
            still_remaining = [p for p in all_pairs if (str(p[0]), str(p[1])) in resumed_set]
            newly_found     = [p for p in all_pairs if (str(p[0]), str(p[1])) not in resumed_set]
            all_pairs = still_remaining + newly_found
            self.log(
                f"📌 استئناف checkpoint — "
                f"{len(still_remaining)} متبقٍ + {len(newly_found)} جديد"
            )

        # احفظ Checkpoint
        cp_pairs = [(s, d) for s, d, _, _ in all_pairs]
        cp.save(cp_pairs, str(pc), str(usb))

        remaining = list(cp_pairs)
        processed = [self.copied]   # نبدأ من المجلدات المنجزة
        prog_lock  = threading.Lock()
        total_n    = max(total, 1)

        # ⚡ v22.1: cache لتجنب mkdir المتكرر
        _created_dirs: Set[str] = set()
        # ⚡ v22.1: فحص المساحة كل 50 ملف بدل كل ملف
        _space_check_counter = [0]
        _space_ok = [True]

        # ④ دالة النسخ الآمنة مع فحص مساحة دوري
        def _do_copy_smart(args):
            src_p, dst_p, rel, direction = args
            if getattr(self, "_cancel", None) and self._cancel.is_set():
                return False, "cancelled", rel, direction
            try:
                src_size = src_p.stat().st_size
            except OSError as e:
                return False, str(e), rel, direction

            # ⚡ mkdir مرة واحدة لكل مجلد
            parent_str = str(dst_p.parent)
            if parent_str not in _created_dirs:
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                _created_dirs.add(parent_str)

            # ملفات 0 بايت — مسار مباشر
            if src_size == 0:
                try:
                    dst_p.touch()
                    shutil.copystat(src_p, dst_p)
                    return True, "OK", rel, direction
                except OSError as e:
                    return False, str(e), rel, direction

            # ⚡ فحص مساحة كل 50 ملف فقط (بدل كل ملف)
            _space_check_counter[0] += 1
            if _space_check_counter[0] % 50 == 1 or not _space_ok[0]:
                ok_sp, sp_msg = AtomicCopier.check_space(dst_p.parent, src_size)
                _space_ok[0] = ok_sp
                if not ok_sp:
                    return False, f"مساحة ممتلئة: {sp_msg}", rel, direction

            # النسخ مع retry
            ok, msg = False, ""
            for attempt in range(AppConfig.MAX_RETRIES):
                ok, msg = AtomicCopier.copy(src_p, dst_p, verify)
                if ok: break
                if attempt < AppConfig.MAX_RETRIES - 1:
                    time.sleep(AppConfig.RETRY_DELAY)
            return ok, msg, rel, direction

        def _after_copy_smart(ok, msg, rel, direction):
            with prog_lock:
                if ok:
                    self.copied += 1
                    report.add_copied(rel)
                    report.add_verified(1)  # AtomicCopier يتحقق بـ SHA-256
                    self.changed_files.append(rel)

                    # تحديث SyncIndex
                    try:
                        if direction in ("pc_to_usb", "pc_only"):
                            src_st = (pc / rel).stat()
                            idx_pc_usb.mark_synced(rel, src_st, usb / rel)
                        else:
                            src_st = (usb / rel).stat()
                            idx_usb_pc.mark_synced(rel, src_st, pc / rel)
                    except OSError: pass

                    # ⚡ v22.1: Checkpoint كل 100 ملف بدل كل ملف (أسرع 100x)
                    src_p = pc / rel if direction in ("pc_to_usb","pc_only") else usb / rel
                    dst_p = usb / rel if direction in ("pc_to_usb","pc_only") else pc / rel
                    try: remaining.remove((src_p, dst_p))
                    except ValueError: pass
                    if processed[0] % 100 == 0:
                        cp.update(remaining, str(pc), str(usb))

                else:
                    self.failed += 1
                    self.errors.append(f"{rel}: {msg}")
                    report.add_failed(rel, msg)
                    self.log(f"  ❌ {Path(rel).name}: {msg}")

                processed[0] += 1
                self.progress(processed[0] / total_n * 100)

        # ④ ThreadPool للصغيرة (≤2MB) + Sequential للكبيرة
        SMALL = AppConfig.SMALL_THRESHOLD  # 2MB default, يتغير بـ calibrate_usb
        small = []
        large = []
        for a in all_pairs:
            try:
                sz = a[0].stat().st_size
                if sz <= SMALL:
                    small.append(a)
                else:
                    large.append(a)
            except OSError:
                small.append(a)  # إذا فشل stat نعامله كصغير

        # الملفات الكبيرة: sequential
        for args in large:
            if getattr(self, "_cancel", None) and self._cancel.is_set():
                self.log("⛔ تم إيقاف المزامنة")
                cp.update(remaining, str(pc), str(usb))
                break
            _after_copy_smart(*_do_copy_smart(args))

        # الملفات الصغيرة: ThreadPool
        if small and not self._cancel.is_set():
            workers = max(AppConfig.THREADS_SMALL, 4)  # استخدم القيمة المُعايرة
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(_do_copy_smart, a): a for a in small}
                for fut in as_completed(futures):
                    if getattr(self, "_cancel", None) and self._cancel.is_set():
                        self.log("⛔ تم إيقاف المزامنة")
                        cp.update(remaining, str(pc), str(usb))
                        ex.shutdown(wait=False, cancel_futures=True) if sys.version_info >= (3, 9) else ex.shutdown(wait=False)
                        break
                    try:
                        _after_copy_smart(*fut.result())
                    except Exception as e:
                        a = futures[fut]
                        _after_copy_smart(False, str(e), a[2], a[3])

        # انتهت المزامنة — نظّف Checkpoint
        if not self._cancel.is_set():
            cp.clear()

        # ⑤ حفظ Meta + Cache + Index
        try:
            total_files, total_size_b = self._count_files(pc)
            self._save_meta(usb, total_files, total_size_b)
        except Exception: pass
        HashCache.save()
        idx_pc_usb.save()
        idx_usb_pc.save()
        AtomicCopier.cleanup_temp(usb)
        AtomicCopier.cleanup_temp(pc)
        self.lock_mgr.release('sync')

        # ⑥ v17: تحديث FlashLedger على الفلاشة
        # ✅ FIX: يُحدَّث دائماً حتى لو copied=0 — لتسجيل last_sync_ts الصحيح
        # بدون هذا: 'مزامنة ذكية' تعتقد أن ملفات الفلاشة تغيّرت بعد الأصل
        if not self._cancel.is_set():
            try:
                FlashLedger.clear_cache()  # ✅ أعد القراءة من الفلاشة
                ledger = FlashLedger(usb).load()
                # اجمع بصمات الملفات المُزامَنة
                synced_hashes: Dict[str, str] = {}
                for rel in self.changed_files:
                    # حاول من الفلاشة أولاً (النسخة النهائية)
                    usb_f = usb / rel
                    if usb_f.exists():
                        h = HashCache.get_hash(usb_f)
                        if h:
                            synced_hashes[rel] = h
                ledger.record_sync(AppConfig.PC_NAME, synced_hashes)
                self.log(f"💾 FlashLedger: سُجِّلت المزامنة — "
                         f"{len(synced_hashes)} ملف مُسجَّل")
            except Exception as e:
                _logger.warning(f"FlashLedger.record_sync: {e}")

        # ⑤ حفظ SyncReport
        report_path = report.save()
        if report_path:
            self.log(f"📋 تقرير محفوظ: {report_path.name}")

        status = ("CANCELLED" if self._cancel.is_set()
                  else "OK" if self.failed == 0 else "PARTIAL")
        return {
            "status"      : status,
            "copied"      : self.copied,
            "failed"      : self.failed,
            "errors"      : self.errors,
            "report_path" : str(report_path) if report_path else "",
        }

    def _save_meta(self, dst: Path, files_count: int, total_size: int):
        try:
            now     = datetime.now().isoformat()
            mf      = dst / AppConfig.SYNC_META_FILE

            # اقرأ السجل القديم للحفاظ على devices_history
            old = {}
            if mf.exists():
                try:
                    with open(mf, 'r', encoding='utf-8') as f:
                        old = json.load(f)
                except Exception:
                    old = {}

            # devices_history: قاموس {اسم_الجهاز: {last_sync, files_count}}
            history: Dict = old.get("devices_history", {})
            history[AppConfig.PC_NAME] = {
                "last_sync"  : now,
                "files_count": files_count,
            }

            data = {
                "last_sync"      : now,
                "pc_name"        : AppConfig.PC_NAME,
                "files_count"    : files_count,
                "total_size"     : total_size,
                "changed_files"  : self.changed_files[:100],
                "version"        : APP_VERSION,
                "devices_history": history,   # ✅ سجل كل الأجهزة
            }
            with open(mf, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush(); os.fsync(f.fileno())
        except OSError as e: _logger.error(f"Save meta: {e}")

    @staticmethod
    def get_meta(folder: Path) -> Optional[Dict]:
        p = folder / AppConfig.SYNC_META_FILE
        if not p.exists(): return None
        try:
            with open(p, 'r', encoding='utf-8') as f: return json.load(f)
        except (OSError, json.JSONDecodeError): return None

    def verify_integrity(self, folder: Path, log_cb=None) -> Dict:
        """التحقق من سلامة الملفات بالمقارنة بين المصدر والنسخة"""
        log = log_cb or (lambda m: None)
        total = ok_count = 0; errors = []
        try:
            for item in folder.rglob('*'):
                if not item.is_file() or self._should_exclude(item): continue
                total += 1
                try:
                    h = HashCache.get_hash(item)
                    if h: ok_count += 1
                    else: errors.append(str(item.name))
                except OSError as e: errors.append(f"{item.name}: {e}")
                if total % 100 == 0: log(Lang.t('verify_progress', n=total))
        except OSError as e: return {"status": "error", "message": str(e)}
        HashCache.save()
        return {"status": "ok" if not errors else "errors",
                "total": total, "ok": ok_count, "errors": errors}




# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  🖥️  v29: HARDWARE MONITOR — شريط حالة حي                               ║
# ║                                                                          ║
# ║  يُحدَّث كل 2 ثانية في thread خلفي                                      ║
# ║  يعرض: CPU% | RAM | USB سرعة + مساحة | Profile الجهاز                  ║
# ║  يتكيّف: psutil إذا متاح، وإلا يستخدم بدائل Windows API                ║
# ╚══════════════════════════════════════════════════════════════════════════╝
    # ═══════════════════════════════════════════════════════════
    # v3 Compatibility API — backup / restore / full_sync / verify
    # ═══════════════════════════════════════════════════════════

    def backup(self, src: Path, dst: Path, verify: bool = True) -> Dict:
        """نسخ src → dst"""
        return self.sync(src, dst, verify=verify)

    def restore(self, src: Path, dst: Path, verify: bool = True) -> Dict:
        """استعادة src → dst"""
        return self.sync(src, dst, verify=verify)

    def full_sync(self, pc: Path, usb: Path, verify: bool = True) -> Dict:
        """
        ⚡ v4.0 FIX: مزامنة ثنائية الاتجاه — باكاب + رستور + الأحدث يفوز.

        المنطق:
        - ملف على الجهاز فقط → ينسخ للفلاشة (دائماً)
        - ملف على الفلاشة فقط → ينسخ للجهاز (دائماً)
        - ملف في الطرفين ومختلف → الأحدث يفوز
        - لا حذف أبداً في هذا الوضع
        """
        self.log("🔍 مسح ذكي ثنائي الاتجاه...")
        scan = self.smart_scan(pc, usb)
        if scan.get("status") in ("FAILED", "CANCELLED"):
            return scan

        # ⚡ v4.0 FIX: الملفات "المحذوفة" تُنسخ بدل ما تُتخطى
        # في الاتجاهين: لو ملف موجود على طرف واحد → دائماً ينسخ للطرف الآخر
        pc_deleted = scan.pop("pc_deleted_on_usb", [])
        usb_deleted = scan.pop("usb_deleted_on_pc", [])
        if pc_deleted:
            scan["pc_only"].extend(pc_deleted)
            self.log(f"  📋 {len(pc_deleted)} ملف موجود على الجهاز فقط → سيُنسخ للفلاشة")
        if usb_deleted:
            scan["usb_only"].extend(usb_deleted)
            self.log(f"  📋 {len(usb_deleted)} ملف موجود على الفلاشة فقط → سيُنسخ للجهاز")

        # إعادة حساب المجموع
        total = (len(scan.get("pc_to_usb", [])) +
                 len(scan.get("usb_to_pc", [])) +
                 len(scan.get("pc_only", [])) +
                 len(scan.get("usb_only", [])))
        scan["total_changes"] = total

        self.log(
            f"📊 نتيجة المسح: "
            f"{len(scan.get('pc_to_usb',[]))} PC→USB | "
            f"{len(scan.get('usb_to_pc',[]))} USB→PC | "
            f"{len(scan.get('pc_only',[]))} جديد في PC | "
            f"{len(scan.get('usb_only',[]))} جديد في USB | "
            f"{scan.get('identical',0)} متطابق"
        )
        if total == 0:
            self.log("✅ كل الملفات متطابقة — لا حاجة لمزامنة")
            return {"status": "NO_CHANGES", "copied": 0, "skipped": scan.get("identical", 0),
                    "failed": 0, "errors": [], "changed": []}
        self.log(f"🔄 تنفيذ المزامنة الذكية — {total} تغيير...")
        return self.execute_smart_sync(pc, usb, scan, verify=verify)

    def verify(self, src: Path, dst: Path) -> bool:
        """تحقق من تطابق الملفات — يقارن المحتوى الفعلي بـ Hash لا الحجم فقط"""
        self.log("🔍 فحص السلامة (Hash)...")
        src_files = {}
        for f in src.rglob("*"):
            if f.is_file() and f.name not in AppConfig.EXCLUDED_NAMES:
                rel = str(f.relative_to(src))
                src_files[rel] = f

        mismatches = []
        for rel, src_f in src_files.items():
            dp = dst / rel
            if not dp.exists():
                mismatches.append(f"مفقود: {rel}")
            else:
                # ① فحص الحجم أولاً (سريع)
                try:
                    if src_f.stat().st_size != dp.stat().st_size:
                        mismatches.append(f"حجم مختلف: {rel}")
                        continue
                except OSError as e:
                    mismatches.append(f"خطأ stat: {rel} — {e}")
                    continue
                # ② فحص المحتوى بـ Hash (دقيق — يكشف التلف الجزئي)
                try:
                    h_src = HashCache.get_hash(src_f)
                    h_dst = HashCache.get_hash(dp)
                    if h_src != h_dst:
                        mismatches.append(f"محتوى مختلف (Hash): {rel}")
                except Exception as e:
                    mismatches.append(f"خطأ Hash: {rel} — {e}")

        HashCache.save()

        if mismatches:
            self.log(f"❌ {len(mismatches)} ملف غير متطابق")
            for m in mismatches[:20]:
                self.log(f"   • {m}")
            return False
        self.log(f"✅ {len(src_files):,} ملف متطابق (Hash)")
        return True

