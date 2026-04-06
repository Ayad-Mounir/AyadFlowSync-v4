#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.device_profiler
====================
⚡ v4.0 — DeviceProfiler: قياس دقيق بـ 4 مستويات + نقاط أداء

المستويات:
  🔴 ضعيف   (0-29)  : ≤2 cores أو RAM<2GB أو hash<200 MB/s
  🟡 متوسط  (30-59) : 4 cores, RAM 2-8GB
  🟢 قوي    (60-84) : 8+ cores, RAM 8-16GB, hash سريع
  ⚡ خارق   (85-100): 12+ cores, RAM 16+GB, hash فائق السرعة

النقاط:
  CPU:  0-35 نقطة (عدد الأنوية + هل فيه hyper-threading)
  RAM:  0-35 نقطة (الإجمالي + المتاح)
  HASH: 0-30 نقطة (سرعة xxhash الفعلية)

الإعدادات التلقائية:
  كل مستوى يضبط: threads, batch_size, ram_cache, process_pool
  يمنع الجهاز الضعيف من التجمد
  يستغل الجهاز الخارق بالكامل
"""

import multiprocessing
import logging

from .app_config import AppConfig

_logger = logging.getLogger("AyadFlowSync")


class DeviceProfile:
    """تصنيف الجهاز — 4 مستويات"""
    WEAK   = "weak"     # 🔴 score 0-29
    MID    = "mid"      # 🟡 score 30-59
    STRONG = "strong"   # 🟢 score 60-84
    ULTRA  = "ultra"    # ⚡ score 85-100


class DeviceProfiler:
    """
    ⚡ v4.0 — قياس دقيق بالنقاط + 4 مستويات.
    استدعاء measure() مرة واحدة فقط — النتيجة محفوظة.
    """
    _profile:  str   = DeviceProfile.MID
    _measured: bool  = False
    _score:    int   = 50   # النقاط الإجمالية (0-100)

    _cores:         int   = 0
    _ram_available: float = 0.0
    _ram_total:     float = 0.0
    _hash_speed:    float = 0.0
    _cpu_score:     int   = 0
    _ram_score:     int   = 0
    _hash_score:    int   = 0
    _disk_speed:    float = 0.0   # اختياري

    _PROFILES = {
        DeviceProfile.WEAK: {
            "threads_small":     2,
            "threads_large":     1,
            "use_process_pool":  False,
            "batch_size":        50,
            "ram_cache_limit":   5_000,
            "partial_threshold_mb": 50,
            "scan_workers":      1,
            "copytree_workers":  2,
            "pipeline_queue":    50,
            "label":     "🔴 ضعيف",
            "label_en":  "🔴 Weak",
            "color":     "#f87171",
        },
        DeviceProfile.MID: {
            "threads_small":     4,
            "threads_large":     2,
            "use_process_pool":  True,
            "batch_size":        200,
            "ram_cache_limit":   20_000,
            "partial_threshold_mb": 100,
            "scan_workers":      2,
            "copytree_workers":  4,
            "pipeline_queue":    200,
            "label":     "🟡 متوسط",
            "label_en":  "🟡 Mid",
            "color":     "#fbbf24",
        },
        DeviceProfile.STRONG: {
            "threads_small":     8,
            "threads_large":     4,
            "use_process_pool":  True,
            "batch_size":        800,
            "ram_cache_limit":   80_000,
            "partial_threshold_mb": 200,
            "scan_workers":      4,
            "copytree_workers":  8,
            "pipeline_queue":    800,
            "label":     "🟢 قوي",
            "label_en":  "🟢 Strong",
            "color":     "#34d399",
        },
        DeviceProfile.ULTRA: {
            "threads_small":     16,
            "threads_large":     8,
            "use_process_pool":  True,
            "batch_size":        2000,
            "ram_cache_limit":   200_000,
            "partial_threshold_mb": 500,
            "scan_workers":      8,
            "copytree_workers":  16,
            "pipeline_queue":    2000,
            "label":     "⚡ خارق",
            "label_en":  "⚡ Ultra",
            "color":     "#818cf8",
        },
    }

    # ── القياس ──────────────────────────────────────────────
    @classmethod
    def measure(cls) -> str:
        """قياس الجهاز وإرجاع التصنيف. استدعاء واحد فقط."""
        if cls._measured:
            return cls._profile

        cores = multiprocessing.cpu_count() or 2

        # ── قياس RAM ────────────────────────────────────────
        ram_total_gb = 4.0
        ram_avail_gb = 2.0
        try:
            import psutil
            mem = psutil.virtual_memory()
            ram_total_gb = mem.total / (1024 ** 3)
            ram_avail_gb = mem.available / (1024 ** 3)
        except ImportError:
            ram_total_gb = 4.0 if cores >= 4 else 1.5
            ram_avail_gb = ram_total_gb * 0.5

        # ── قياس سرعة Hash ──────────────────────────────────
        hash_speed = 0.0
        try:
            import os, time as _t
            # اختبار بـ 32MB بيانات
            test = os.urandom(32 * 1024 * 1024)
            try:
                import xxhash
                h = xxhash.xxh3_128()
            except ImportError:
                import hashlib
                h = hashlib.sha256()
            t0 = _t.perf_counter()
            h.update(test)
            elapsed = max(_t.perf_counter() - t0, 0.001)
            hash_speed = 32.0 / elapsed  # MB/s
        except Exception:
            hash_speed = 200.0

        # ── حساب النقاط ─────────────────────────────────────
        # CPU Score (0-35)
        if cores <= 1:
            cpu_score = 5
        elif cores == 2:
            cpu_score = 15
        elif cores <= 4:
            cpu_score = 22
        elif cores <= 6:
            cpu_score = 27
        elif cores <= 8:
            cpu_score = 30
        elif cores <= 12:
            cpu_score = 33
        else:
            cpu_score = 35

        # RAM Score (0-35)
        if ram_total_gb < 2:
            ram_score = 5
        elif ram_total_gb < 4:
            ram_score = 12
        elif ram_total_gb < 8:
            ram_score = 20
        elif ram_total_gb < 16:
            ram_score = 27
        elif ram_total_gb < 32:
            ram_score = 32
        else:
            ram_score = 35

        # إذا الذاكرة المتاحة أقل من 25% من الإجمالي → خفض النقاط
        if ram_total_gb > 0 and (ram_avail_gb / ram_total_gb) < 0.25:
            ram_score = max(5, ram_score - 8)

        # Hash Score (0-30)
        if hash_speed < 100:
            hash_score = 5
        elif hash_speed < 300:
            hash_score = 12
        elif hash_speed < 600:
            hash_score = 18
        elif hash_speed < 1200:
            hash_score = 23
        elif hash_speed < 3000:
            hash_score = 27
        else:
            hash_score = 30

        total_score = cpu_score + ram_score + hash_score

        # ── التصنيف بالنقاط ─────────────────────────────────
        if total_score < 30:
            profile = DeviceProfile.WEAK
        elif total_score < 60:
            profile = DeviceProfile.MID
        elif total_score < 85:
            profile = DeviceProfile.STRONG
        else:
            profile = DeviceProfile.ULTRA

        # ── حفظ النتائج ─────────────────────────────────────
        cls._cores         = cores
        cls._hash_speed    = hash_speed
        cls._ram_available = ram_avail_gb
        cls._ram_total     = ram_total_gb
        cls._score         = total_score
        cls._cpu_score     = cpu_score
        cls._ram_score     = ram_score
        cls._hash_score    = hash_score
        cls._profile       = profile
        cls._measured      = True

        cls._apply()

        _logger.info(
            f"🖥️  DeviceProfiler: {cls._PROFILES[profile]['label']} "
            f"({total_score}/100) | cores={cores} | "
            f"RAM={ram_avail_gb:.1f}/{ram_total_gb:.0f}GB | "
            f"hash={hash_speed:.0f}MB/s"
        )
        return cls._profile

    # ── تطبيق الإعدادات ──────────────────────────────────────
    @classmethod
    def _apply(cls) -> None:
        """تطبيق إعدادات الأداء على AppConfig حسب المستوى."""
        cfg = cls._PROFILES[cls._profile]
        if AppConfig.USB_SPEED_MBS == 0.0:
            AppConfig.THREADS_SMALL = cfg["threads_small"]
            AppConfig.THREADS_LARGE = cfg["threads_large"]
            AppConfig.BATCH_SIZE    = cfg["batch_size"]

    # ── الاستعلام ──────────────────────────────────────────
    @classmethod
    def get(cls) -> str:
        return cls._profile

    @classmethod
    def get_score(cls) -> int:
        return cls._score

    @classmethod
    def get_label(cls) -> str:
        return cls._PROFILES.get(cls._profile, {}).get("label", "?")

    @classmethod
    def get_color(cls) -> str:
        return cls._PROFILES.get(cls._profile, {}).get("color", "#718096")

    @classmethod
    def use_process_pool(cls) -> bool:
        return cls._PROFILES.get(cls._profile, {}).get("use_process_pool", True)

    @classmethod
    def get_copytree_workers(cls) -> int:
        return cls._PROFILES.get(cls._profile, {}).get("copytree_workers", 4)

    @classmethod
    def get_scan_workers(cls) -> int:
        return cls._PROFILES.get(cls._profile, {}).get("scan_workers", 2)

    @classmethod
    def get_pipeline_queue_size(cls) -> int:
        return cls._PROFILES.get(cls._profile, {}).get("pipeline_queue", 200)

    # ── نصوص العرض ────────────────────────────────────────────
    @classmethod
    def get_specs_text(cls) -> str:
        """نص مواصفات الجهاز للعرض في الواجهة."""
        if not cls._measured:
            return "🖥️  جاري القياس..."

        label     = cls.get_label()
        cores_txt = f"{cls._cores} نواة"
        ram_txt   = (
            f"RAM {cls._ram_available:.1f} / {cls._ram_total:.0f} GB"
            if cls._ram_total > 0
            else f"RAM {cls._ram_available:.1f} GB"
        )
        hash_txt  = f"⚡ {cls._hash_speed:.0f} MB/s" if cls._hash_speed > 0 else ""

        parts = [f"🖥️  {cores_txt}", ram_txt]
        if hash_txt:
            parts.append(hash_txt)
        parts.append(f"{label} ({cls._score}/100)")
        return "   |   ".join(parts)

    @classmethod
    def get_usb_specs_text(cls) -> str:
        spd = AppConfig.USB_SPEED_MBS
        if spd <= 0:
            return "💾  الفلاشة: لم تُقَس"
        icon = "🟢" if spd >= 100 else ("🟡" if spd >= 30 else "🔴")
        return f"💾  الفلاشة: {icon} {spd:.0f} MB/s"

    # ── بيانات مفصلة للـ Dashboard ──────────────────────────
    @classmethod
    def get_detailed_info(cls) -> dict:
        """بيانات مفصلة لعرضها في لوحة التحكم."""
        return {
            "profile":    cls._profile,
            "score":      cls._score,
            "label":      cls.get_label(),
            "color":      cls.get_color(),
            "cores":      cls._cores,
            "ram_total":  cls._ram_total,
            "ram_avail":  cls._ram_available,
            "hash_speed": cls._hash_speed,
            "cpu_score":  cls._cpu_score,
            "ram_score":  cls._ram_score,
            "hash_score": cls._hash_score,
            "threads_small": cls._PROFILES[cls._profile]["threads_small"],
            "threads_large": cls._PROFILES[cls._profile]["threads_large"],
            "batch_size":    cls._PROFILES[cls._profile]["batch_size"],
        }
