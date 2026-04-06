#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AyadFlowSync.core
=================
Public API للوحدة الأساسية.
استورد من هنا فقط لتجنب الاستيراد الدائري.
"""

from .constants      import AppInfo, Theme, BINARY_EXTENSIONS, APP_NAME, APP_VERSION, IGNORED_DIRS
from .app_config     import AppConfig, PORTABLE
from .device_profiler import DeviceProfile, DeviceProfiler
from .hardware       import HardwareMonitor
from .logging_setup  import setup_logging
from .hash_worker    import compute_hash, _mp_compute_hash

__all__ = [
    "AppInfo", "Theme", "BINARY_EXTENSIONS", "APP_NAME", "APP_VERSION",
    "IGNORED_DIRS", "AppConfig", "PORTABLE",
    "DeviceProfile", "DeviceProfiler",
    "HardwareMonitor",
    "setup_logging",
    "compute_hash", "_mp_compute_hash",
]
