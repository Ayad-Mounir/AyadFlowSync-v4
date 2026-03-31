#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.hardware
=============
HardwareMonitor — مراقب الأجهزة الحي في thread خلفي.
"""

import time
import shutil
import threading
import multiprocessing
import logging
from pathlib import Path
from typing import Dict, List, Callable, Optional

from .app_config import AppConfig
from .device_profiler import DeviceProfiler

_logger = logging.getLogger("AyadFlowSync")
_CPU_CORES: int = multiprocessing.cpu_count() or 4


class HardwareMonitor:
    """
    مراقب أجهزة حي — يعمل في thread خلفي داعم (daemon).
    يُحدّث كل callback مسجَّل بمعلومات CPU / RAM / USB كل UPDATE_INTERVAL ثانية.
    """

    UPDATE_INTERVAL: float = 1.0

    def __init__(self, usb_path_ref: Callable[[], Optional[Path]]):
        self._usb_ref   = usb_path_ref
        self._running   = False
        self._thread:   Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []
        self._last:     Dict = {}
        self._cpu_prev  = None

        try:
            import psutil as _ps
            self._psutil = _ps
        except ImportError:
            self._psutil = None

    # ── إدارة الـ Callbacks ──────────────────────────────────────────
    def add_callback(self, cb: Callable) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def remove_callback(self, cb: Callable) -> None:
        try:
            self._callbacks.remove(cb)
        except ValueError:
            pass

    # ── دورة الحياة ─────────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True, name="HardwareMonitor"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def get_last(self) -> Dict:
        return self._last.copy()

    def collect_now(self) -> Dict:
        """قراءة فورية متزامنة — للعرض الأول."""
        data = self._collect(blocking_cpu=False)
        self._last = data
        return data

    # ── Loop ─────────────────────────────────────────────────────────
    def _loop(self) -> None:
        while self._running:
            try:
                data = self._collect(blocking_cpu=True)
                self._last = data
                for cb in list(self._callbacks):
                    try:
                        cb(data)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(self.UPDATE_INTERVAL)

    def _collect(self, blocking_cpu: bool = True) -> Dict:
        """جمع بيانات الأجهزة — قيم افتراضية مضمونة."""
        data: Dict = {
            "cpu_pct":      0.0,
            "cpu_cores":    _CPU_CORES,
            "cpu_freq":     0.0,
            "ram_used_gb":  0.0,
            "ram_total_gb": 0.0,
            "ram_avail_gb": 0.0,
            "ram_pct":      0.0,
            "usb_free_gb":  -1.0,
            "usb_total_gb": 0.0,
            "usb_used_pct": 0.0,
            "usb_speed":    AppConfig.USB_SPEED_MBS,
            "device_label": DeviceProfiler.get_label(),
            "device_cores": _CPU_CORES,
            "device_profile": DeviceProfiler.get(),
        }

        # ── CPU ──────────────────────────────────────────────────────
        if self._psutil:
            try:
                interval = 0.2 if blocking_cpu else None
                data["cpu_pct"]   = self._psutil.cpu_percent(interval=interval)
                data["cpu_cores"] = self._psutil.cpu_count(logical=True) or _CPU_CORES
                freq = self._psutil.cpu_freq()
                data["cpu_freq"]  = freq.current if freq else 0.0
            except Exception:
                pass

        # ── RAM ──────────────────────────────────────────────────────
        if self._psutil:
            try:
                vm = self._psutil.virtual_memory()
                data["ram_used_gb"]  = vm.used      / (1024 ** 3)
                data["ram_total_gb"] = vm.total     / (1024 ** 3)
                data["ram_avail_gb"] = vm.available / (1024 ** 3)
                data["ram_pct"]      = vm.percent
            except Exception:
                pass

        # ── USB ──────────────────────────────────────────────────────
        try:
            usb_path = self._usb_ref()
            if usb_path and Path(usb_path).exists():
                usage = shutil.disk_usage(usb_path)
                data["usb_free_gb"]  = usage.free  / (1024 ** 3)
                data["usb_total_gb"] = usage.total / (1024 ** 3)
                data["usb_used_pct"] = usage.used  / max(usage.total, 1) * 100
                data["usb_path"]     = str(usb_path)
        except Exception:
            pass

        return data

    # ── مساعدات العرض ────────────────────────────────────────────────
    @staticmethod
    def format_bar(pct: float, width: int = 8) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def cpu_color(pct: float) -> str:
        if pct < 50:  return "#00ff41"
        if pct < 80:  return "#fbbf24"
        return "#ff4444"

    @staticmethod
    def ram_color(pct: float) -> str:
        if pct < 60:  return "#00d4ff"
        if pct < 85:  return "#fbbf24"
        return "#ff4444"

    @staticmethod
    def usb_color(pct: float) -> str:
        if pct < 70:  return "#a78bfa"
        if pct < 90:  return "#fbbf24"
        return "#ff4444"
