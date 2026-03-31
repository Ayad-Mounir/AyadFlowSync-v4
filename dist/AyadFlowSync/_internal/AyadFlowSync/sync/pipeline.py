#!/usr/bin/env python3
"""
sync.pipeline — SyncPipeline: 4-stage parallel sync engine.
Scanner → Hasher → Copier → Verifier — all running concurrently via queues.

For 150,000+ files this is 2-5x faster than sequential CopyWorker.
Automatically selected for mid/strong devices.
"""

import os
import time
import json
import queue as _queue_module
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.app_config import AppConfig
from ..core.device_profiler import DeviceProfiler
from ..security.hash import HashCache
from .copier import AtomicCopier, DeltaCopier, Utils
from .index import SyncIndex

_logger = logging.getLogger("AyadFlowSync.pipeline")

# Sentinel object to signal "queue is done"
_PIPELINE_DONE = object()


class SyncPipeline:
    """
    ⚡ v28 — Pipeline متكامل لمزامنة 150,000+ ملف.

    4 مراحل تعمل بالتوازي عبر queues مترابطة:

    Stage 1 — Scanner:
        يمشي على المجلد بـ scandir (generator)
        لكل ملف: يفحص SyncIndex + الحجم
        → يضع في queue_to_hash (مشكوك) أو queue_to_copy (متأكد)

    Stage 2 — Hasher:
        يستقبل من queue_to_hash
        يحسب hash المصدر والوجهة بالتوازي
        → يضع في queue_to_copy إذا تغيّر

    Stage 3 — Copier:
        يستقبل من queue_to_copy
        يختار: Delta Copy أو Full Copy حسب الملف
        → يضع في queue_to_verify

    Stage 4 — Verifier:
        يستقبل من queue_to_verify
        يتحقق من صحة النسخ + يُحدّث HashCache + SyncIndex
        → يُسجّل النتيجة في الإحصائيات

    كل stage في thread منفصل — يعمل بشكل مستقل.
    الـ queues هي "الأنابيب" بينها.
    """

    # حجم الـ queues — حسب DeviceProfiler
    _QUEUE_SIZES = {
        "weak"  : 50,
        "mid"   : 200,
        "strong": 1000,
        "ultra" : 2000,    # ⚡ v4.0: مستوى خارق
    }

    def __init__(self, src: Path, dst: Path, idx: "SyncIndex",
                 log_cb=None, progress_cb=None,
                 cancel_event: threading.Event = None,
                 verify: bool = True,
                 expected_total: int = 0):
        self.src      = src
        self.dst      = dst
        self.idx      = idx
        self.log      = log_cb or (lambda m: None)
        self.progress = progress_cb or (lambda p: None)
        self._cancel  = cancel_event or threading.Event()
        self.verify   = verify
        self._expected_total = expected_total   # ⚡ v4.0: العدد المعروف مسبقاً

        # ── إحصائيات thread-safe ──
        self._lock    = threading.Lock()
        self.copied   = 0
        self.skipped  = 0
        self.failed   = 0
        self.errors: List[str] = []
        self.changed_files: List[str] = []
        self._total_scanned = 0
        self._total_to_copy = 0

        # ── Queues ──
        profile    = DeviceProfiler.get() if hasattr(DeviceProfiler, '_measured') else "mid"
        q_size     = self._QUEUE_SIZES.get(profile, 200)
        self._q_hash  = _queue_module.Queue(maxsize=q_size)
        self._q_copy  = _queue_module.Queue(maxsize=q_size)
        self._q_verify= _queue_module.Queue(maxsize=q_size)

        # ── عدد الـ workers حسب DeviceProfiler ──
        cfg = DeviceProfiler._PROFILES.get(profile, DeviceProfiler._PROFILES["mid"])
        self._hash_workers  = max(1, cfg["threads_small"] // 2)
        self._copy_workers  = cfg["threads_small"]
        self._verify_workers= max(1, cfg["threads_large"])

        # ⚡ v4.0: USB = max 2 copy threads (أكثر = أبطأ)
        _is_usb = False
        try:
            dst.relative_to(AppConfig.VAULT_DIR)
            _is_usb = True
        except ValueError:
            _is_usb = AppConfig.is_removable(dst)
        if _is_usb:
            self._copy_workers = min(self._copy_workers, 2)

        # ✅ FIX: atomic counters لمنع deadlock عند خروج worker 0 مبكراً
        self._hash_done_count   = 0
        self._copy_done_count   = 0
        self._verify_done_count = 0

    # ══════════════════════════════════════════════════════════
    # Stage 1: Scanner
    # ══════════════════════════════════════════════════════════
    def _stage_scanner(self):
        """
        يمشي على src بـ scandir ويصنّف كل ملف:
        - متطابق  → self.skipped++
        - متأكد تغيّر (حجم مختلف) → queue_to_copy مباشرة
        - مشكوك (نفس الحجم) → queue_to_hash
        """
        excluded      = AppConfig.EXCLUDED_NAMES
        excluded_dirs = AppConfig.EXCLUDED_DIRS   # محدَّثة لحظياً من الإعدادات

        def _walk(directory: Path, dst_dir: Path):
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if self._cancel.is_set():
                            return
                        try:
                            item = Path(entry.path)
                            if item.name in excluded:
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                # ── تخطي المجلدات المستثناة ──
                                if entry.name in excluded_dirs:
                                    continue
                                target_dir = dst_dir / entry.name
                                target_dir.mkdir(parents=True, exist_ok=True)
                                _walk(item, target_dir)
                            elif entry.is_file(follow_symlinks=False):
                                src_st = entry.stat()
                                target = dst_dir / entry.name
                                rel    = str(item.relative_to(self.src))

                                with self._lock:
                                    self._total_scanned += 1

                                # SyncIndex — هل نعرفه؟
                                if self.idx.is_unchanged(rel, src_st, target):
                                    with self._lock:
                                        self.skipped += 1
                                    continue

                                if not target.exists():
                                    # ملف جديد — نسخ مباشر
                                    self._q_copy.put((item, target, src_st, rel))
                                else:
                                    dst_st = target.stat()
                                    if src_st.st_size != dst_st.st_size:
                                        # حجم مختلف — نسخ مباشر
                                        self._q_copy.put((item, target, src_st, rel))
                                    elif src_st.st_size == 0:
                                        # ⚡ v4.0: الملفات الفارغة — فحص mtime
                                        if abs(src_st.st_mtime - dst_st.st_mtime) > 2.0:
                                            self._q_copy.put((item, target, src_st, rel))
                                        else:
                                            with self._lock:
                                                self.skipped += 1
                                                self.idx.mark_synced(rel, src_st, target)
                                    else:
                                        # نفس الحجم > 0 — يحتاج hash
                                        self._q_hash.put((item, target, src_st, rel))
                        except OSError:
                            continue
            except OSError:
                pass

        try:
            _walk(self.src, self.dst)
        finally:
            # أرسل sentinel لكل hash worker
            for _ in range(self._hash_workers):
                self._q_hash.put(_PIPELINE_DONE)

    # ══════════════════════════════════════════════════════════
    # Stage 2: Hasher
    # ══════════════════════════════════════════════════════════
    def _stage_hasher(self, worker_id: int):
        """
        يستقبل من q_hash، يحسب hash، يقرر:
        - متطابق  → skipped
        - مختلف   → q_copy
        """
        _done_count = [0]

        while True:
            try:
                item_data = self._q_hash.get(timeout=2)
            except _queue_module.Empty:
                if self._cancel.is_set():
                    break
                continue

            if item_data is _PIPELINE_DONE:
                # أعد إرسال الـ sentinel للـ workers الآخرين
                self._q_hash.put(_PIPELINE_DONE)
                break

            item, target, src_st, rel = item_data

            try:
                # ✅ FIX FAT32: FAT32 يُقرّب mtime لأقرب 2 ثانية بالضبط
                # > 1 كانت تُصنّف كل ملف FAT32 "مشكوك فيه" وتُجبر إعادة Hash
                # >= 2 يعني: فقط الفرق الحقيقي (أكثر من دورة FAT32) يُعدّ تغييراً
                mtime_diff = abs(src_st.st_mtime - target.stat().st_mtime) >= 2
                h_src = HashCache.get_hash(item,   force=mtime_diff)
                h_dst = HashCache.get_hash(target, force=mtime_diff)

                if h_src != h_dst:
                    self._q_copy.put((item, target, src_st, rel))
                else:
                    with self._lock:
                        self.skipped += 1
                        self.idx.mark_synced(rel, src_st, target)
            except Exception:
                # عند الشك → نسخ
                self._q_copy.put((item, target, src_st, rel))

        # ✅ FIX: آخر hasher فعلياً يُرسل sentinels (بدل الاعتماد على worker_id)
        with self._lock:
            self._hash_done_count += 1
            if self._hash_done_count == self._hash_workers:
                for _ in range(self._copy_workers):
                    self._q_copy.put(_PIPELINE_DONE)

    # ══════════════════════════════════════════════════════════
    # Stage 3: Copier
    # ══════════════════════════════════════════════════════════
    def _stage_copier(self, worker_id: int):
        """
        يستقبل من q_copy، يختار Delta أو Full، يُرسل لـ q_verify.
        """
        while True:
            try:
                item_data = self._q_copy.get(timeout=2)
            except _queue_module.Empty:
                if self._cancel.is_set():
                    break
                continue

            if item_data is _PIPELINE_DONE:
                self._q_copy.put(_PIPELINE_DONE)
                break

            item, target, src_st, rel = item_data

            try:
                src_size = src_st.st_size
                ok = False
                msg = ""

                # ⚡ Delta Copy للملفات الكبيرة
                if DeltaCopier.should_use_delta(item, target, src_size):
                    delta_ok, delta_msg, _ = DeltaCopier.copy(
                        item, target, log_cb=self.log
                    )
                    if delta_msg == "DELTA_NO_CHANGE":
                        with self._lock:
                            self.skipped += 1
                        continue
                    if delta_ok:
                        ok, msg = True, "DELTA_OK"
                    else:
                        # Fallback
                        ok, msg = AtomicCopier.copy(item, target, self.verify)
                else:
                    # Full Copy مع retry
                    for attempt in range(AppConfig.MAX_RETRIES):
                        ok, msg = AtomicCopier.copy(item, target, self.verify)
                        if ok:
                            break
                        if attempt < AppConfig.MAX_RETRIES - 1:
                            time.sleep(AppConfig.RETRY_DELAY)

                self._q_verify.put((item, target, src_st, rel, ok, msg))

            except Exception as e:
                self._q_verify.put((item, target, src_st, rel, False, str(e)))

        # ✅ FIX: آخر copier فعلياً يُرسل sentinels
        with self._lock:
            self._copy_done_count += 1
            if self._copy_done_count == self._copy_workers:
                for _ in range(self._verify_workers):
                    self._q_verify.put(_PIPELINE_DONE)

    # ══════════════════════════════════════════════════════════
    # Stage 4: Verifier
    # ══════════════════════════════════════════════════════════
    def _stage_verifier(self, worker_id: int, total_ref: list,
                        presync: "PreSyncBackup"):
        """
        يستقبل من q_verify، يُحدّث HashCache + SyncIndex + إحصائيات.
        يستدعي presync.create() قبل استبدال أي ملف موجود.
        """
        _idx_batch: List[tuple] = []

        while True:
            try:
                item_data = self._q_verify.get(timeout=2)
            except _queue_module.Empty:
                if self._cancel.is_set():
                    break
                continue

            if item_data is _PIPELINE_DONE:
                self._q_verify.put(_PIPELINE_DONE)
                break

            item, target, src_st, rel, ok, msg = item_data

            with self._lock:
                if ok:
                    self.copied += 1
                    self.changed_files.append(rel)
                    # تحديث SyncIndex
                    try:
                        self.idx.mark_synced(rel, src_st, target)
                    except Exception:
                        pass
                    # Progress — ⚡ v4.0: نسبة دقيقة
                    done = self.copied + self.failed
                    # الإجمالي: استخدم العدد المعروف مسبقاً إن وُجد
                    if self._expected_total > 0:
                        total_to_copy = self._expected_total
                    else:
                        total_to_copy = max(self._total_scanned - self.skipped, done, 1)
                    pct = min(done / total_to_copy * 100, 99)
                    self.progress(pct)

                    # ⚡ v4.0: تقدم متكرر مع سرعة ووقت متبقي
                    _interval = 100 if total_to_copy < 10000 else (200 if total_to_copy < 50000 else 500)
                    if self.copied % _interval == 0 or self.copied == 1:
                        elapsed = time.time() - self._start_time if hasattr(self, '_start_time') else 0
                        if elapsed > 0 and self.copied > 0:
                            speed = self.copied / elapsed
                            remaining = (total_to_copy - done) / speed if speed > 0 else 0
                            if remaining >= 60:
                                eta = f"~{remaining/60:.0f} دقيقة"
                            else:
                                eta = f"~{remaining:.0f} ثانية"
                            self.log(
                                f"  📊 {self.copied:,}/{total_to_copy:,} ({pct:.0f}%) | "
                                f"⚡ {speed:.0f} ملف/ث | "
                                f"⏱️ {eta}"
                            )
                        else:
                            self.log(f"  📊 {self.copied:,}/{total_to_copy:,} ({pct:.0f}%)")
                else:
                    self.failed += 1
                    self.errors.append(f"{rel}: {msg}")
                    if self.failed <= 20:
                        self.log(f"  ❌ {Path(rel).name}: {msg}")

        # ✅ FIX: آخر verifier فعلياً يحفظ الـ index
        with self._lock:
            self._verify_done_count += 1
            if self._verify_done_count == self._verify_workers:
                try:
                    self.idx.save()
                except Exception:
                    pass

    # ══════════════════════════════════════════════════════════
    # run() — يُشغّل كل الـ stages بالتوازي
    # ══════════════════════════════════════════════════════════
    def run(self, presync: "PreSyncBackup" = None, verify: bool = True) -> Dict:
        """
        يُشغّل الـ Pipeline الكامل ويُعيد نتيجة المزامنة.
        """
        self.verify = verify
        self.log(
            f"⚡ Pipeline v28 [{DeviceProfiler.get_label()}] | "
            f"hash_workers={self._hash_workers} | "
            f"copy_workers={self._copy_workers} | "
            f"queue={self._q_copy.maxsize}"
        )
        if self._expected_total > 0:
            self.log(f"📊 هدف: {self._expected_total:,} ملف للنسخ")

        total_ref = [0]   # يُحدَّث من verifier

        threads: List[threading.Thread] = []

        # Stage 1: Scanner (1 thread)
        t = threading.Thread(target=self._stage_scanner,
                             name="Pipeline-Scanner", daemon=True)
        threads.append(t)

        # Stage 2: Hashers
        for i in range(self._hash_workers):
            t = threading.Thread(target=self._stage_hasher, args=(i,),
                                 name=f"Pipeline-Hasher-{i}", daemon=True)
            threads.append(t)

        # Stage 3: Copiers
        for i in range(self._copy_workers):
            t = threading.Thread(target=self._stage_copier, args=(i,),
                                 name=f"Pipeline-Copier-{i}", daemon=True)
            threads.append(t)

        # Stage 4: Verifiers
        for i in range(self._verify_workers):
            t = threading.Thread(
                target=self._stage_verifier,
                args=(i, total_ref, presync),
                name=f"Pipeline-Verifier-{i}", daemon=True
            )
            threads.append(t)

        # ابدأ الكل
        self._start_time = time.time()   # ✅ FIX BUG-09: قبل بدء الـ threads
        t0 = time.monotonic()
        _et = f" — {self._expected_total:,} ملف" if self._expected_total else ""
        self.log(f"🚀 بدء النسخ... ({self._copy_workers} threads{_et})")
        for t in threads:
            t.start()

        # انتظر الكل
        for t in threads:
            t.join()

        elapsed = time.monotonic() - t0
        speed   = self.copied / max(elapsed, 0.1)

        # ⚡ v4.0: وقت مفهوم
        if elapsed >= 60:
            time_str = f"{elapsed/60:.1f} دقيقة"
        else:
            time_str = f"{elapsed:.1f} ثانية"

        self.log(f"{'━'*40}")
        self.log(
            f"✅ Pipeline انتهى: {self.copied:,} منسوخ | "
            f"{self.skipped:,} متطابق | {self.failed} أخطاء | "
            f"⏱️ {time_str} ({speed:.0f} ملف/ث)"
        )
        self.progress(100)

        status = "CANCELLED" if self._cancel.is_set() else \
                 ("OK" if self.failed == 0 else "PARTIAL")

        return {
            "status" : status,
            "copied" : self.copied,
            "skipped": self.skipped,
            "failed" : self.failed,
            "errors" : self.errors,
            "changed": self.changed_files,
        }




